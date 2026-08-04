"""
Performer: consome FilaAuditoriaLotes-Eqp04, aplica RN01-RN07 em cada
item, e posta resumo como artefato no Maestro.

Uso:
    python -m src.bot.performer

Depende de: MAESTRO_ENABLED, VAULT_ENABLED, BOTCITY_ACTIVITY_LABEL,
credenciais Maestro no .env.
"""

import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

from src.bot import config
from src.bot.bot import setup_logger
from src.bot.vault_client import VaultError, obter_credencial_erp
from src.modules.validacao import COLUNAS_ESPERADAS
from src.modules.verificacao_lotes import carregar_base_referencia
from src.relatorio import avaliar_lote

try:
    from botcity.maestro import (
        AlertType,
        AutomationTaskFinishStatus,
        BotMaestroSDK,
        ErrorType,
    )
except ImportError:
    AlertType = None
    AutomationTaskFinishStatus = None
    BotMaestroSDK = None
    ErrorType = None

DATAPOOL_LABEL = "FilaAuditoriaLotes-Eqp04"
ARQUIVO_CSV = "lotes_auditoria.csv"  # dentro de PASTA_ENTRADA, usado no dry-run

# Caminho único da base de referência, gerado pelo preprocessor
# (scripts/planilha_para_csv.py) a partir da planilha oficial.
BASE_REFERENCIA = "data/processed/base_lotes_referencia.csv"

REGRAS_CONTABILIZADAS = ["RN02", "RN03", "RN06", "RN07"]


class PerformerError(Exception):
    """Erros do Performer com mensagem sanitizada (sem dados do SDK)."""


def _novo_resumo() -> dict:
    return {
        "total_processados": 0,
        "total_conformes": 0,
        "total_com_divergencia": 0,
        "total_erros_sistema": 0,
        "divergencias_por_regra": {regra: 0 for regra in REGRAS_CONTABILIZADAS},
    }


def _contabilizar_divergencias(resumo: dict, divergencias: list[dict]) -> None:
    for divergencia in divergencias:
        regra = divergencia["regra"]
        resumo["divergencias_por_regra"][regra] = (
            resumo["divergencias_por_regra"].get(regra, 0) + 1
        )


def _logar_resumo(resumo: dict) -> None:
    logging.info(
        f"Performer concluído: {resumo['total_processados']} processados, "
        f"{resumo['total_conformes']} conformes, "
        f"{resumo['total_com_divergencia']} com divergência, "
        f"{resumo['total_erros_sistema']} erros de sistema."
    )
    logging.info(f"Divergências por regra: {resumo['divergencias_por_regra']}")


def _emitir_alerta_maestro(titulo: str, mensagem: str) -> None:
    """Registra um alerta no Maestro, sem nunca propagar exceção.

    O endpoint de alerta exige uma AutomationTask real (verificado
    empiricamente: task inexistente devolve 404), por isso o alerta cria
    uma task própria e a encerra como FAILED — assim a ocorrência fica
    visível no painel mesmo quando o Performer aborta antes do loop.
    """
    if not config.MAESTRO_ENABLED or BotMaestroSDK is None:
        return

    try:
        sdk = BotMaestroSDK(
            server=config.BOTCITY_SERVER,
            login=config.BOTCITY_LOGIN,
            key=config.BOTCITY_KEY,
        )
        sdk.login()
        task = sdk.create_task(
            activity_label=config.BOTCITY_ACTIVITY_LABEL,
            parameters={"origem": "performer_local", "alerta": titulo},
        )
        sdk.alert(
            task_id=str(task.id),
            title=titulo,
            message=mensagem,
            alert_type=AlertType.ERROR,
        )
        sdk.finish_task(
            task_id=str(task.id),
            status=AutomationTaskFinishStatus.FAILED,
            message=mensagem,
        )
        logging.info(f"Alerta registrado no Maestro (task {task.id}).")
    except Exception as e:
        logging.warning(f"Não foi possível registrar alerta no Maestro (tipo: {type(e).__name__}).")


def _finalizar_task_com_falha(sdk, task_id, mensagem: str) -> None:
    """Encerra a task como FAILED para não deixá-la órfã. Nunca levanta."""
    try:
        sdk.finish_task(
            task_id=str(task_id),
            status=AutomationTaskFinishStatus.FAILED,
            message=mensagem,
        )
    except Exception as e:
        logging.warning(f"Falha ao finalizar task {task_id} (tipo: {type(e).__name__}).")


def _executar_dry_run(base_ref: pd.DataFrame) -> int:
    """Consome o CSV local diretamente, sem tocar em fila nem task."""
    logging.info("Modo dry-run (MAESTRO_ENABLED=false): consumindo CSV local, sem Maestro.")

    csv_path = os.path.join(config.PASTA_ENTRADA, ARQUIVO_CSV)
    if not os.path.isfile(csv_path):
        logging.error(f"CSV de entrada não encontrado: {csv_path}")
        return 1

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    resumo = _novo_resumo()

    for i, linha in df.reset_index(drop=True).iterrows():
        lote = {coluna: linha.get(coluna, "") for coluna in COLUNAS_ESPERADAS}
        resumo["total_processados"] += 1

        try:
            divergencias = avaliar_lote(lote, base_ref)
        except Exception as e:
            logging.error(
                f"[DRY-RUN] Erro avaliando lote_id='{lote['lote_id']}' (tipo: {type(e).__name__})."
            )
            resumo["total_erros_sistema"] += 1
            continue

        if not divergencias:
            resumo["total_conformes"] += 1
            logging.info(f"[DRY-RUN] Item {i + 1}/{len(df)}: lote_id='{lote['lote_id']}' conforme.")
        else:
            resumo["total_com_divergencia"] += 1
            _contabilizar_divergencias(resumo, divergencias)
            regras = ",".join(d["regra"] for d in divergencias)
            logging.warning(
                f"[DRY-RUN] Item {i + 1}/{len(df)}: lote_id='{lote['lote_id']}' "
                f"com divergências: {regras}"
            )

    _logar_resumo(resumo)
    return 0


def _executar_com_maestro(base_ref: pd.DataFrame) -> int:
    """Fluxo real: login, task, consumo da fila, artefato e finalização."""
    if BotMaestroSDK is None:
        raise PerformerError("SDK botcity-maestro-sdk não está instalado.")

    try:
        sdk = BotMaestroSDK(
            server=config.BOTCITY_SERVER,
            login=config.BOTCITY_LOGIN,
            key=config.BOTCITY_KEY,
        )
        sdk.login()
    except Exception as e:
        logging.error(f"Falha no login do Maestro (tipo: {type(e).__name__}).")
        raise PerformerError("Falha ao autenticar no Maestro.") from None

    # A task real é obrigatória: artefato e alerta são anexados a ela e o
    # servidor rejeita identificadores inexistentes.
    try:
        task = sdk.create_task(
            activity_label=config.BOTCITY_ACTIVITY_LABEL,
            parameters={"origem": "performer_local", "datapool": DATAPOOL_LABEL},
        )
        task_id = task.id
        logging.info(f"Task criada no Maestro: id={task_id}")
    except Exception as e:
        logging.error(f"Falha ao criar task (tipo: {type(e).__name__}).")
        raise PerformerError("Falha ao criar task no Maestro.") from None

    try:
        datapool = sdk.get_datapool(label=DATAPOOL_LABEL)
    except Exception as e:
        logging.error(f"Falha ao obter DataPool (tipo: {type(e).__name__}).")
        _finalizar_task_com_falha(sdk, task_id, "Falha ao obter DataPool")
        raise PerformerError(f"Falha ao obter DataPool {DATAPOOL_LABEL}.") from None

    resumo = _novo_resumo()
    resumo["task_id"] = task_id
    resumo["activity_label"] = config.BOTCITY_ACTIVITY_LABEL

    while datapool.has_next():
        item = datapool.next(task_id=str(task_id))
        if item is None:
            break  # outro processo pode ter consumido o item nesse meio-tempo

        resumo["total_processados"] += 1

        try:
            lote = {coluna: item.get_value(coluna, "") for coluna in COLUNAS_ESPERADAS}
            divergencias = avaliar_lote(lote, base_ref)

            if not divergencias:
                item.report_done(finish_message=f"Lote {lote['lote_id']} conforme.")
                resumo["total_conformes"] += 1
                logging.info(f"Item conforme: lote_id='{lote['lote_id']}'.")
            else:
                regras = ",".join(d["regra"] for d in divergencias)
                item.report_error(
                    error_type=ErrorType.BUSINESS,
                    finish_message=f"Divergências: {regras}",
                )
                resumo["total_com_divergencia"] += 1
                _contabilizar_divergencias(resumo, divergencias)
                logging.warning(f"Item com divergências ({regras}): lote_id='{lote['lote_id']}'.")
        except Exception as e:
            # Erro de sistema (não de negócio): marca o item e segue para o
            # próximo — uma falha isolada não pode abortar a fila.
            logging.error(f"Erro processando item (tipo: {type(e).__name__}).")
            try:
                item.report_error(
                    error_type=ErrorType.SYSTEM,
                    finish_message=f"Erro de sistema: {type(e).__name__}",
                )
            except Exception as erro_report:
                logging.error(
                    f"Falha ao reportar erro do item (tipo: {type(erro_report).__name__})."
                )
            resumo["total_erros_sistema"] += 1

    caminho_resumo = Path("/tmp") / f"resumo_performer_{task_id}.json"
    caminho_resumo.parent.mkdir(exist_ok=True, parents=True)
    with open(caminho_resumo, "w", encoding="utf-8") as arquivo:
        json.dump(resumo, arquivo, indent=2, ensure_ascii=False)

    try:
        sdk.post_artifact(
            task_id=task_id,
            artifact_name=f"resumo_{task_id}.json",
            filepath=caminho_resumo,
        )
        logging.info(f"Artefato postado no Maestro: task {task_id}.")
    except Exception as e:
        # Não é fatal: a task ainda precisa ser finalizada com o resultado.
        logging.error(f"Falha ao postar artefato (tipo: {type(e).__name__}).")

    if resumo["total_erros_sistema"] > 0 or resumo["total_com_divergencia"] > 0:
        status = AutomationTaskFinishStatus.PARTIALLY_COMPLETED
    else:
        status = AutomationTaskFinishStatus.SUCCESS

    try:
        sdk.finish_task(
            task_id=str(task_id),
            status=status,
            message=f"{resumo['total_conformes']}/{resumo['total_processados']} conformes",
            total_items=resumo["total_processados"],
            processed_items=resumo["total_conformes"],
            failed_items=resumo["total_com_divergencia"] + resumo["total_erros_sistema"],
        )
    except Exception as e:
        logging.error(f"Falha ao finalizar task (tipo: {type(e).__name__}).")

    _logar_resumo(resumo)
    return 0


def main() -> int:
    logger = setup_logger()

    logger.info("Iniciando Performer — Auditor de Lotes v1.0")

    if not os.path.isdir(config.PASTA_ENTRADA):
        logger.error(f"Pasta de entrada não encontrada: {config.PASTA_ENTRADA}")
        _emitir_alerta_maestro(
            titulo="Pasta de entrada ausente",
            mensagem=f"O Performer não encontrou a pasta de entrada '{config.PASTA_ENTRADA}'.",
        )
        return 1

    try:
        usuario, _senha = obter_credencial_erp()
    except VaultError as e:
        logger.error(f"Não foi possível obter a credencial do ERP: {e}")
        return 1

    logger.info(f"Acessando sistema com o usuário: {usuario}")

    if not os.path.isfile(BASE_REFERENCIA):
        logger.error(
            f"Base de referência não encontrada em {BASE_REFERENCIA}. "
            f"Execute 'python -m scripts.planilha_para_csv' antes."
        )
        return 1

    try:
        base_ref = carregar_base_referencia(BASE_REFERENCIA)
    except Exception as e:
        logger.error(f"Falha ao carregar a base de referência (tipo: {type(e).__name__}).")
        return 1

    try:
        if not config.MAESTRO_ENABLED:
            return _executar_dry_run(base_ref)
        return _executar_com_maestro(base_ref)
    except PerformerError as e:
        logger.error(f"Performer abortado: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
