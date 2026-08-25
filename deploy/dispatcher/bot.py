"""Entry-point padrão do Bot A (Dispatcher) para o BotCity Maestro Runner."""

import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
_raiz = Path(__file__).resolve().parent.parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

try:
    from src.bot.dispatcher import executar_dispatcher
except ImportError:
    from src.dispatcher import executar_dispatcher


def main():
    sys.exit(executar_dispatcher())


if __name__ == "__main__":
    main()
