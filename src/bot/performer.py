"""Bot B — Performer (Auditoria e Validação de Lotes via Regras de Negócio).

Responsabilidades:
1. Obtém credenciais seguras do ERP via Credentials Vault (src/bot/vault_client.py).
2. Carrega a base de referência de lotes cadastrados (RN03).
3. Consome itens da fila (DataPool) do Maestro.
4. Aplica as regras de negócio RN01 a RN07 (src/bot/avaliador.py).
5. Registra o status de cada item (report_done / report_error com ErrorType.BUSINESS/SYSTEM).
6. Dispara o Bot C (Reporter) via sdk.create_task() para consolidação e alertas.
7. Finaliza a task do Performer no Maestro.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
import pandas as pd

from src.bot import config
from src.bot.bot import setup_logger
from src.bot.vault_client import obter_credencial_erp, VaultError
from src.bot.avaliador import avaliar_lote
from src.classificador_divergencia import classificar_divergencia
from src.modules.validacao import COLUNAS_ESPERADAS
from src.modules.verificacao_lotes import carregar_base_referencia

try:
    from botcity.maestro import (
        AutomationTaskFinishStatus,
        BotMaestroSDK,
        ErrorType,
    )
except ImportError:
    BotMaestroSDK = None
    AutomationTaskFinishStatus = None
    ErrorType = None


class PerformerError(Exception):
    """Exceção levantada para erros no fluxo do Bot B Performer."""


def carregar_base_dados_referencia() -> pd.DataFrame:
    """Carrega a base de referência de lotes."""
    caminho = Path(config.CAMINHO_BASE_REFERENCIA)
    if not caminho.is_file():
        # Tenta caminhos alternativos conhecidos no projeto
        alternativas = [
            Path("data/processed/base_lotes_referencia.csv"),
            Path("data/dev/base_lotes_referencia_dev.csv"),
        ]
        for alt in alternativas:
            if alt.is_file():
                caminho = alt
                break

    return carregar_base_referencia(str(caminho))


def disparar_bot_c(sdk: BotMaestroSDK | None, dados_resumo: dict) -> str | None:
    """Dispara a execução do Bot C (Reporter) via Maestro create_task()."""
    if not config.MAESTRO_ENABLED or sdk is None:
        logging.info(f"[DRY-RUN ORQUESTRAÇÃO] Bot B disparando Bot C ('{config.BOTCITY_REPORTER_LABEL}').")
        return "task-mock-reporter-001"

    try:
        task_c = sdk.create_task(
            activity_label=config.BOTCITY_REPORTER_LABEL,
            parameters={
                "origem": "bot_b_performer",
                "total_processados": dados_resumo.get("total_processados", 0),
                "total_divergencias": dados_resumo.get("total_com_divergencia", 0),
            },
        )
        task_c_id = str(task_c.id)
        logging.info(f"Bot B disparou com sucesso o Bot C (Task ID: {task_c_id}, Activity: {config.BOTCITY_REPORTER_LABEL}).")
        return task_c_id
    except Exception as e:
        logging.error(f"Falha ao criar task do Bot C no Maestro: {e}")
        # Alerta sem quebrar o Performer
        return None


def executar_auditoria_local(base_ref: pd.DataFrame) -> dict:
    """Executa o processamento em modo local / dry-run."""
    caminho_csv = Path(config.PASTA_ENTRADA) / config.ARQUIVO_CSV_ENTRADA
    if not caminho_csv.is_file():
        caminho_csv = Path("data/processed/dados_relatorio.csv")

    df = pd.read_csv(caminho_csv, dtype=str, keep_default_na=False)
    resumo = {
        "total_processados": 0,
        "total_conformes": 0,
        "total_com_divergencia": 0,
        "divergencias_detalhadas": [],
    }

    for i, linha in df.reset_index(drop=True).iterrows():
        lote = {col: linha.get(col, "") for col in COLUNAS_ESPERADAS}
        resumo["total_processados"] += 1

        divergencias = avaliar_lote(lote, base_ref)
        if not divergencias:
            resumo["total_conformes"] += 1
            logging.info(f"[DRY-RUN] Lote '{lote['lote_id']}': CONFORME")
        else:
            resumo["total_com_divergencia"] += 1
            regras = ", ".join(d["regra"] for d in divergencias)
            logging.warning(f"[DRY-RUN] Lote '{lote['lote_id']}': DIVERGÊNCIA ({regras})")
            classif_ml = classificar_divergencia(lote.get("observacao", ""))
            for div in divergencias:
                resumo["divergencias_detalhadas"].append({
                    "linha": i + 2,
                    "lote_id": lote["lote_id"],
                    "origem_decisao": classif_ml["origem_decisao"],
                    "confianca_ml": classif_ml["confianca_ml"],
                    "causa_provavel": classif_ml["causa_provavel"],
                    **div,
                })

    return resumo


def executar_auditoria_maestro(sdk: BotMaestroSDK, base_ref: pd.DataFrame) -> dict:
    """Executa o processamento consumindo a fila do BotCity Maestro."""
    # Cria a task de execução do Performer
    task = sdk.create_task(
        activity_label=config.BOTCITY_PERFORMER_LABEL,
        parameters={"origem": "orquestracao_performer", "datapool": config.DATAPOOL_LABEL},
    )
    task_id = str(task.id)
    logging.info(f"Task iniciada no Maestro: ID {task_id}")

    datapool = sdk.get_datapool(label=config.DATAPOOL_LABEL)
    resumo = {
        "task_id": task_id,
        "total_processados": 0,
        "total_conformes": 0,
        "total_com_divergencia": 0,
        "divergencias_detalhadas": [],
    }

    while datapool.has_next():
        item = datapool.next(task_id=task_id)
        if item is None:
            break

        resumo["total_processados"] += 1
        lote = {col: str(item.get_value(col, "")) for col in COLUNAS_ESPERADAS}

        try:
            divergencias = avaliar_lote(lote, base_ref)
            if not divergencias:
                item.report_done(finish_message=f"Lote {lote.get('lote_id')} em conformidade.")
                resumo["total_conformes"] += 1
            else:
                regras = ", ".join(d["regra"] for d in divergencias)
                item.report_error(
                    error_type=ErrorType.BUSINESS,
                    finish_message=f"Divergências detectadas: {regras}",
                )
                resumo["total_com_divergencia"] += 1

                classif_ml = classificar_divergencia(lote.get("observacao", ""))
                for div in divergencias:
                    resumo["divergencias_detalhadas"].append({
                        "lote_id": lote.get("lote_id"),
                        "origem_decisao": classif_ml["origem_decisao"],
                        "confianca_ml": classif_ml["confianca_ml"],
                        "causa_provavel": classif_ml["causa_provavel"],
                        **div,
                    })
        except Exception as e:
            logging.error(f"Erro de sistema no lote {lote.get('lote_id')}: {e}")
            item.report_error(
                error_type=ErrorType.SYSTEM,
                finish_message=f"Erro de sistema: {type(e).__name__}",
            )

    # Finaliza a task do Performer com status de SUCESSO
    sdk.finish_task(
        task_id=task_id,
        status=AutomationTaskFinishStatus.SUCCESS,
        message=f"Processamento de lotes concluído: {resumo['total_conformes']}/{resumo['total_processados']} conformes, {resumo['total_com_divergencia']} divergências.",
    )

    return resumo


def executar_performer() -> int:
    logger = setup_logger("performer")
    logger.info("=== Iniciando Bot B — Performer Validador de Lotes ===")

    try:
        usuario, _ = obter_credencial_erp()
        logger.info(f"Sessão ERP autorizada para: {usuario}")
    except VaultError as e:
        logger.error(f"Falha de autenticação no Vault: {e}")
        return 1

    try:
        base_ref = carregar_base_dados_referencia()
    except Exception as e:
        logger.error(f"Erro ao carregar base de referência (RN03): {e}")
        return 1

    sdk = None
    if config.MAESTRO_ENABLED:
        if BotMaestroSDK is None:
            logger.error("SDK botcity-maestro-sdk não instalado.")
            return 1
        try:
            sdk = BotMaestroSDK(
                server=config.BOTCITY_SERVER,
                login=config.BOTCITY_LOGIN,
                key=config.BOTCITY_KEY,
            )
            sdk.login()
            resumo = executar_auditoria_maestro(sdk, base_ref)
        except Exception as e:
            logger.error(f"Erro na execução com Maestro: {e}")
            return 1
    else:
        resumo = executar_auditoria_local(base_ref)

    logger.info(
        f"Auditoria concluída: {resumo['total_processados']} processados, "
        f"{resumo['total_conformes']} conformes, {resumo['total_com_divergencia']} divergências."
    )

    # Salva resumo intermediário para o Bot C
    caminho_inter = Path(tempfile.gettempdir()) / "resumo_auditoria_lotes.json"
    caminho_inter.write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")

    # Bot B dispara Bot C (Reporter)
    disparar_bot_c(sdk, resumo)

    return 0


if __name__ == "__main__":
    sys.exit(executar_performer())
