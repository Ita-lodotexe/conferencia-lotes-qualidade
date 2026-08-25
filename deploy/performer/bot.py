"""Entry-point padrão do Bot B (Performer) para o BotCity Maestro Runner."""

import sys
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path
_raiz = Path(__file__).resolve().parent.parent.parent
if str(_raiz) not in sys.path:
    sys.path.insert(0, str(_raiz))

try:
    from src.bot.performer import executar_performer
except ImportError:
    from src.performer import executar_performer


def main():
    sys.exit(executar_performer())


if __name__ == "__main__":
    main()
