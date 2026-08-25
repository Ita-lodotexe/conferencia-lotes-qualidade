"""Bot A — Dispatcher (Ingestão de Lotes e Enfileiramento Maestro).

Responsabilidades:
1. Lê o arquivo de lotes a serem auditados (CSV/Excel).
2. Valida a estrutura inicial do arquivo (RN01).
3. Popula a fila (DataPool) do BotCity Maestro com os itens de lote.
4. Dispara a execução do Bot B (Performer) via sdk.create_task().
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
import pandas as pd

from src.bot import config
from src.bot.bot import setup_logger
from src.modules.validacao import valida_estrutura, COLUNAS_ESPERADAS

try:
    from botcity.maestro import BotMaestroSDK
    from botcity.maestro.datapool import DataPoolEntry
except ImportError:
    BotMaestroSDK = None
    DataPoolEntry = None


class DispatcherError(Exception):
    """Exceção levantada para erros no fluxo do Bot A Dispatcher."""


def carregar_dados_entrada() -> pd.DataFrame:
    """Localiza e carrega a planilha ou CSV de entrada."""
    caminho_csv = Path(config.PASTA_ENTRADA) / config.ARQUIVO_CSV_ENTRADA
    if caminho_csv.is_file():
        return pd.read_csv(caminho_csv, dtype=str, keep_default_na=False)

    # Fallback para data/processed/dados_relatorio.csv se a pasta configurada não existir
    caminho_fallback = Path("data/processed/dados_relatorio.csv")
    if caminho_fallback.is_file():
        return pd.read_csv(caminho_fallback, dtype=str, keep_default_na=False)

    raise DispatcherError(f"Arquivo de entrada não encontrado em: {caminho_csv} ou {caminho_fallback}")


def enviar_itens_fila(df: pd.DataFrame, sdk: BotMaestroSDK | None = None) -> tuple[int, int, int]:
    """Envia os registros do DataFrame para o DataPool do Maestro.

    Retorna (total_lidos, total_enviados, total_falhas).
    """
    total_lidos = len(df)
    total_enviados = 0
    total_falhas = 0

    if not config.MAESTRO_ENABLED or sdk is None:
        logging.info("Modo local (MAESTRO_ENABLED=false): simulando enfileiramento de itens (dry-run).")
        for i, row in df.reset_index(drop=True).iterrows():
            logging.info(f"[DRY-RUN ENFILEIRAMENTO] Item {i + 1}/{total_lidos} | Lote: '{row.get('lote_id')}'")
        return total_lidos, total_lidos, 0

    try:
        datapool = sdk.get_datapool(label=config.DATAPOOL_LABEL)
    except Exception as e:
        logging.error(f"Falha ao obter o DataPool '{config.DATAPOOL_LABEL}': {e}")
        raise DispatcherError(f"Falha ao acessar DataPool '{config.DATAPOOL_LABEL}'.") from e

    for i, row in df.reset_index(drop=True).iterrows():
        values = {col: str(row.get(col, "")) for col in COLUNAS_ESPERADAS}
        entry = DataPoolEntry(priority=0, values=values)
        try:
            datapool.create_entry(entry)
            total_enviados += 1
            logging.info(f"Item {i + 1}/{total_lidos} enfileirado com sucesso: lote_id='{row.get('lote_id')}'")
        except Exception as e:
            total_falhas += 1
            logging.error(f"Erro ao enfileirar lote_id='{row.get('lote_id')}': {e}")

    return total_lidos, total_enviados, total_falhas


def disparar_bot_b(sdk: BotMaestroSDK | None, total_itens: int) -> str | None:
    """Dispara a execução do Bot B (Performer) via Maestro create_task()."""
    if not config.MAESTRO_ENABLED or sdk is None:
        logging.info(f"[DRY-RUN ORQUESTRAÇÃO] Bot A disparando Bot B ('{config.BOTCITY_PERFORMER_LABEL}').")
        return "task-mock-performer-001"

    try:
        task_b = sdk.create_task(
            activity_label=config.BOTCITY_PERFORMER_LABEL,
            parameters={
                "origem": "bot_a_dispatcher",
                "datapool": config.DATAPOOL_LABEL,
                "total_itens": total_itens,
            },
        )
        task_b_id = str(task_b.id)
        logging.info(f"Bot A disparou com sucesso o Bot B (Task ID: {task_b_id}, Activity: {config.BOTCITY_PERFORMER_LABEL}).")
        return task_b_id
    except Exception as e:
        logging.error(f"Falha ao criar task do Bot B no Maestro: {e}")
        raise DispatcherError("Falha na orquestração: Bot A não conseguiu iniciar o Bot B.") from e


def executar_dispatcher() -> int:
    logger = setup_logger("dispatcher")
    logger.info("=== Iniciando Bot A — Dispatcher de Lotes ===")

    try:
        df = carregar_dados_entrada()
    except Exception as e:
        logger.error(f"Erro ao carregar dados de entrada: {e}")
        return 1

    # RN01: Validação de estrutura
    colunas_faltantes = valida_estrutura(df)
    if colunas_faltantes:
        logger.error(f"RN01 Violação: Colunas ausentes no arquivo de entrada: {colunas_faltantes}")
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
        except Exception as e:
            logger.error(f"Falha na autenticação do Maestro: {e}")
            return 1

    total_lidos, total_enviados, total_falhas = enviar_itens_fila(df, sdk)
    logger.info(f"Enfileiramento concluído: {total_lidos} lidos, {total_enviados} enviados, {total_falhas} falhas.")

    if total_enviados > 0:
        task_b_id = disparar_bot_b(sdk, total_enviados)
        logger.info(f"Orquestração concluída: Bot B acionado (ID: {task_b_id}).")

    return 0 if total_falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(executar_dispatcher())
