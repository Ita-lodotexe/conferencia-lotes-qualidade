"""Entry-point padrão do Bot A (Dispatcher) para o BotCity Maestro Runner."""

import sys
from src.dispatcher import executar_dispatcher


def main():
    sys.exit(executar_dispatcher())


if __name__ == "__main__":
    main()
