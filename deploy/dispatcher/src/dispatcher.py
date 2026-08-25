"""Lógica de execução do Bot A (Dispatcher)."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
import pandas as pd

from src import config
from src.bot_log import setup_logger
from src.modules.validacao import valida_estrutura, COLUNAS_ESPERADAS

try:
    from botcity.maestro import BotMaestroSDK
    from botcity.maestro.datapool import DataPoolEntry
except ImportError:
    BotMaestroSDK = None
    DataPoolEntry = None


class DispatcherError(Exception):
    pass


def carregar_dados_entrada() -> pd.DataFrame:
    candidatos = [
        Path(config.PASTA_ENTRADA) / config.ARQUIVO_CSV_ENTRADA,
        Path("data/processed") / "dados_relatorio.csv",
        Path("data/processed") / config.ARQUIVO_CSV_ENTRADA,
        Path("dados_entrada") / "lotes_auditoria.csv",
        Path("dados_relatorio.csv"),
    ]
    for c in candidatos:
        if c.is_file():
            return pd.read_csv(c, dtype=str, keep_default_na=False)

    raise DispatcherError(f"Arquivo de entrada não encontrado em nenhum dos caminhos esperados: {candidatos}")


def enviar_itens_fila(df: pd.DataFrame, sdk: BotMaestroSDK | None = None) -> tuple[int, int, int]:
    total_lidos = len(df)
    total_enviados = 0
    total_falhas = 0

    if not config.MAESTRO_ENABLED or sdk is None:
        logging.info("Modo local (MAESTRO_ENABLED=false): simulando enfileiramento.")
        for i, row in df.reset_index(drop=True).iterrows():
            logging.info(f"[DRY-RUN] Item {i + 1}/{total_lidos}: lote_id='{row.get('lote_id')}'")
        return total_lidos, total_lidos, 0

    datapool = sdk.get_datapool(label=config.DATAPOOL_LABEL)

    for i, row in df.reset_index(drop=True).iterrows():
        values = {col: str(row.get(col, "")) for col in COLUNAS_ESPERADAS}
        entry = DataPoolEntry(priority=0, values=values)
        try:
            datapool.create_entry(entry)
            total_enviados += 1
            logging.info(f"Item {i + 1}/{total_lidos} enfileirado: lote_id='{row.get('lote_id')}'")
        except Exception as e:
            total_falhas += 1
            logging.error(f"Erro ao enfileirar lote_id='{row.get('lote_id')}': {e}")

    return total_lidos, total_enviados, total_falhas


def disparar_bot_b(sdk: BotMaestroSDK | None, total_itens: int) -> str | None:
    if not config.MAESTRO_ENABLED or sdk is None:
        logging.info(f"[DRY-RUN] Bot A disparando Bot B ('{config.BOTCITY_PERFORMER_LABEL}').")
        return "task-mock-performer-001"

    task_b = sdk.create_task(
        activity_label=config.BOTCITY_PERFORMER_LABEL,
        parameters={
            "origem": "bot_a_dispatcher",
            "datapool": config.DATAPOOL_LABEL,
            "total_itens": total_itens,
        },
    )
    task_b_id = str(task_b.id)
    logging.info(f"Bot A disparou Bot B com sucesso (Task ID: {task_b_id}).")
    return task_b_id


def executar_dispatcher() -> int:
    logger = setup_logger("dispatcher")
    logger.info("Iniciando Bot A — Dispatcher de Lotes")

    try:
        df = carregar_dados_entrada()
    except Exception as e:
        logger.error(f"Erro ao carregar dados: {e}")
        return 1

    colunas_faltantes = valida_estrutura(df)
    if colunas_faltantes:
        logger.error(f"RN01 Violação: colunas ausentes: {colunas_faltantes}")
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
        except Exception as e:
            logger.error(f"Erro no login do Maestro: {e}")
            return 1

    total_lidos, total_enviados, total_falhas = enviar_itens_fila(df, sdk)
    logger.info(f"Enfileiramento concluído: {total_lidos} lidos, {total_enviados} enviados, {total_falhas} falhas.")

    if total_enviados > 0:
        disparar_bot_b(sdk, total_enviados)

    return 0 if total_falhas == 0 else 1
