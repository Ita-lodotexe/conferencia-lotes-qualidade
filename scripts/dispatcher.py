"""Ponto de entrada script para o Bot A (Dispatcher)."""

import sys
from src.bot.dispatcher import executar_dispatcher

if __name__ == "__main__":
    sys.exit(executar_dispatcher())
