from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def pagina_html(repo_root: Path) -> Path:
    return repo_root / "webapp" / "static"
