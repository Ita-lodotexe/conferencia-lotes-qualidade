"""Entry-point padrão do Bot B (Performer) para o BotCity Maestro Runner."""

import sys
from src.performer import executar_performer


def main():
    sys.exit(executar_performer())


if __name__ == "__main__":
    main()
