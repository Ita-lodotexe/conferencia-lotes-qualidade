from __future__ import annotations

import os
import sys

from playwright_fill import run as run_playwright_fill
from web_automation import main as run_web_automation


def main() -> int:
    mode = os.environ.get("BOT_MODE", "playwright").lower()

    if mode == "web_automation":
        return run_web_automation()

    if mode == "playwright":
        return run_playwright_fill()

    print(f"Modo desconhecido: {mode}. Use BOT_MODE=playwright ou BOT_MODE=web_automation.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
