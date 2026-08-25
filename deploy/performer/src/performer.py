"""Lógica de execução do Bot B (Performer)."""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
import pandas as pd

from src import config
from src.bot_log import setup_logger
from src.vault_client import obter_credencial_erp, VaultError
from src.avaliador import avaliar_lote
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
    pass


def carregar_base_dados_referencia() -> pd.DataFrame:
    caminho = Path(config.CAMINHO_BASE_REFERENCIA)
    if not caminho.is_file():
        alternativas = [
            Path("base_lotes_referencia.csv"),
            Path("data/processed/base_lotes_referencia.csv"),
            Path("data/dev/base_lotes_referencia_dev.csv"),
        ]
        for alt in alternativas:
            if alt.is_file():
                caminho = alt
                break
    return carregar_base_referencia(str(caminho))


def disparar_bot_c(sdk: BotMaestroSDK | None, dados_resumo: dict) -> str | None:
    if not config.MAESTRO_ENABLED or sdk is None:
        logging.info(f"[DRY-RUN] Bot B disparando Bot C ('{config.BOTCITY_REPORTER_LABEL}').")
        return "task-mock-reporter-001"

    task_c = sdk.create_task(
        activity_label=config.BOTCITY_REPORTER_LABEL,
        parameters={
            "origem": "bot_b_performer",
            "total_processados": dados_resumo.get("total_processados", 0),
            "total_divergencias": dados_resumo.get("total_com_divergencia", 0),
        },
    )
    task_c_id = str(task_c.id)
    logging.info(f"Bot B disparou Bot C com sucesso (Task ID: {task_c_id}).")
    return task_c_id


def executar_auditoria_local(base_ref: pd.DataFrame) -> dict:
    candidatos = [
        Path(config.PASTA_ENTRADA) / config.ARQUIVO_CSV_ENTRADA,
        Path("data/processed") / "dados_relatorio.csv",
        Path("data/processed") / config.ARQUIVO_CSV_ENTRADA,
        Path("dados_entrada") / "lotes_auditoria.csv",
        Path("dados_relatorio.csv"),
    ]
    df = None
    for c in candidatos:
        if c.is_file():
            df = pd.read_csv(c, dtype=str, keep_default_na=False)
            break

    if df is None:
        raise PerformerError(f"Arquivo de entrada não encontrado em: {candidatos}")
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

            # Classificação ML da observação (se houver)
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
                item.report_done(finish_message=f"Lote {lote.get('lote_id')} conforme.")
                resumo["total_conformes"] += 1
            else:
                regras = ", ".join(d["regra"] for d in divergencias)
                item.report_error(
                    error_type=ErrorType.BUSINESS,
                    finish_message=f"Divergências: {regras}",
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
            logging.error(f"Erro ao processar item {lote.get('lote_id')}: {e}")
            item.report_error(error_type=ErrorType.SYSTEM, finish_message=str(e))

    # Finaliza a task do Performer com status de SUCESSO
    sdk.finish_task(
        task_id=task_id,
        status=AutomationTaskFinishStatus.SUCCESS,
        message=f"Processamento de lotes concluído: {resumo['total_conformes']}/{resumo['total_processados']} conformes, {resumo['total_com_divergencia']} divergências.",
    )
    return resumo


def executar_performer() -> int:
    logger = setup_logger("performer")
    logger.info("Iniciando Bot B — Performer Validador de Lotes")

    try:
        usuario, _ = obter_credencial_erp()
        logger.info(f"Sessão ERP autorizada: {usuario}")
    except VaultError as e:
        logger.error(f"Erro no Vault: {e}")
        return 1

    try:
        base_ref = carregar_base_dados_referencia()
    except Exception as e:
        logger.error(f"Erro ao carregar base de referência: {e}")
        return 1

    sdk = None
    if config.MAESTRO_ENABLED and BotMaestroSDK is not None:
        try:
            sdk = BotMaestroSDK(
                server=config.BOTCITY_SERVER,
                login=config.BOTCITY_LOGIN,
                key=config.BOTCITY_KEY,
            )
            sdk.login()
            resumo = executar_auditoria_maestro(sdk, base_ref)
        except Exception as e:
            logger.error(f"Erro na execução Maestro: {e}")
            return 1
    else:
        resumo = executar_auditoria_local(base_ref)

    caminho_inter = Path(tempfile.gettempdir()) / "resumo_auditoria_lotes.json"
    caminho_inter.write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")

    disparar_bot_c(sdk, resumo)
    return 0
