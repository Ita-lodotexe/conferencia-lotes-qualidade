"""
Dispatcher: lê o CSV de lotes e envia cada linha como item para o DataPool
FilaAuditoriaLotes-Eqp04 no Maestro.

Uso:
    python -m scripts.dispatcher

Depende de variáveis do .env: MAESTRO_ENABLED, BOTCITY_SERVER, BOTCITY_LOGIN,
BOTCITY_KEY, PASTA_ENTRADA.
"""

import logging
import os
import sys

import pandas as pd

from src.bot import config
from src.bot.bot import setup_logger
from src.modules.validacao import COLUNAS_ESPERADAS

try:
    from botcity.maestro import BotMaestroSDK
    from botcity.maestro.datapool import DataPoolEntry
except ImportError:
    BotMaestroSDK = None
    DataPoolEntry = None

DATAPOOL_LABEL = "FilaAuditoriaLotes-Eqp04"
ARQUIVO_CSV = "lotes_auditoria.csv"  # dentro de PASTA_ENTRADA


class DispatcherError(Exception):
    """Erros do Dispatcher com mensagem sanitizada (sem dados do SDK)."""


def enviar_para_fila(df: pd.DataFrame) -> tuple[int, int, int]:
    """Envia cada linha do DataFrame como item ao DataPool.

    Retorna (total_lidos, total_enviados, total_falhos).
    """
    total_lidos = len(df)

    if not config.MAESTRO_ENABLED:
        logging.info(
            "Modo dry-run (MAESTRO_ENABLED=false): itens não serão enviados ao Maestro."
        )
        for i, row in df.reset_index(drop=True).iterrows():
            logging.info(f"[DRY-RUN] Item {i + 1}/{total_lidos}: lote_id='{row['lote_id']}'")
        return total_lidos, total_lidos, 0

    if BotMaestroSDK is None:
        raise DispatcherError("SDK botcity-maestro-sdk não está instalado.")

    try:
        sdk = BotMaestroSDK(
            server=config.BOTCITY_SERVER,
            login=config.BOTCITY_LOGIN,
            key=config.BOTCITY_KEY,
        )
        sdk.login()
    except Exception as e:
        logging.error(f"Falha ao autenticar no Maestro (tipo: {type(e).__name__}).")
        raise DispatcherError(
            "Falha ao autenticar no Maestro: verifique BOTCITY_SERVER, BOTCITY_LOGIN e BOTCITY_KEY."
        ) from None

    try:
        datapool = sdk.get_datapool(label=DATAPOOL_LABEL)
    except Exception as e:
        logging.error(f"Falha ao obter o DataPool '{DATAPOOL_LABEL}' (tipo: {type(e).__name__}).")
        raise DispatcherError(
            f"Falha ao obter o DataPool '{DATAPOOL_LABEL}'."
        ) from None

    total_enviados = 0
    total_falhos = 0

    for i, row in df.reset_index(drop=True).iterrows():
        values = {col: row[col] for col in COLUNAS_ESPERADAS}
        entry = DataPoolEntry(priority=0, values=values)

        try:
            datapool.create_entry(entry)
        except Exception as e:
            total_falhos += 1
            logging.error(
                f"Falha ao enviar lote_id='{row['lote_id']}' (tipo: {type(e).__name__})"
            )
            continue

        total_enviados += 1
        logging.info(f"Item {i + 1}/{total_lidos} enviado: lote_id='{row['lote_id']}'")

    return total_lidos, total_enviados, total_falhos


def main() -> int:
    logger = setup_logger()

    logger.info("Iniciando Dispatcher — FilaAuditoriaLotes-Eqp04")
    logger.warning(
        "ATENÇÃO: se você rodou antes, a fila terá acumulado itens "
        "(a operação não é idempotente)."
    )

    if not os.path.isdir(config.PASTA_ENTRADA):
        logger.error(f"Pasta de entrada não encontrada: {config.PASTA_ENTRADA}")
        return 1

    csv_path = os.path.join(config.PASTA_ENTRADA, ARQUIVO_CSV)
    if not os.path.isfile(csv_path):
        logger.error(f"CSV de entrada não encontrado: {csv_path}")
        return 1

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)

    colunas_faltantes = set(COLUNAS_ESPERADAS) - set(df.columns)
    if colunas_faltantes:
        logger.error(f"Colunas obrigatórias ausentes no CSV: {sorted(colunas_faltantes)}")
        return 1

    total_lidos, total_enviados, total_falhos = enviar_para_fila(df)

    print(
        f"Dispatcher concluído: {total_lidos} lidos, "
        f"{total_enviados} enviados, {total_falhos} falhas."
    )

    return 0 if total_falhos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
