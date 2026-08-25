"""Entry-point padrão do Bot C (Reporter) para o BotCity Maestro Runner."""

import sys
from src.reporter import executar_reporter


def main():
    sys.exit(executar_reporter())


if __name__ == "__main__":
    main()
