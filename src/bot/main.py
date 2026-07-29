"""Entry-point do bot."""

import os
import sys

from src.bot import config
from src.bot.bot import setup_logger


def main():
    logger = setup_logger()

    logger.info("Iniciando Auditor de Lotes v1.0")
    logger.info(
        f"Configuração: MAESTRO_ENABLED={config.MAESTRO_ENABLED}, VAULT_ENABLED={config.VAULT_ENABLED}"
    )

    if not os.path.isdir(config.PASTA_ENTRADA):
        logger.error(f"Pasta de entrada não encontrada: {config.PASTA_ENTRADA}")
        sys.exit(1)

    logger.info(f"Pasta de entrada validada: {config.PASTA_ENTRADA}")


if __name__ == "__main__":
    main()
