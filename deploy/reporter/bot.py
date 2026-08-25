"""Entry-point padrão do Bot C (Reporter) para o BotCity Maestro Runner."""

import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
_raiz = Path(__file__).resolve().parent.parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

try:
    from src.bot.reporter import executar_reporter
except ImportError:
    from src.reporter import executar_reporter


def main():
    sys.exit(executar_reporter())


if __name__ == "__main__":
    main()
