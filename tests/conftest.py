from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, Playwright, sync_playwright
import pandas as pd

@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def playwright_instance() -> Playwright:
    with sync_playwright() as playwright:
        yield playwright


@pytest.fixture(scope="session")
def browser(playwright_instance: Playwright) -> Browser:
    browser = playwright_instance.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.fixture
def page(browser: Browser) -> Page:
    page = browser.new_page()
    yield page
    page.close()
"""Fixtures e configurações compartilhadas pela suíte de testes (Aula 23)."""


@pytest.fixture
def base_referencia():
    """Base_Referencia mockada — simula um sistema externo.

    Contém 3 lotes: L001 (Ativo), L002 (Inativo), L004 (Ativo).
    L003 não existe de propósito (testa RN05 — lote não cadastrado).
    """
    return pd.DataFrame(
        {
            "lote_id": ["L001", "L002", "L004"],
            "codigo_produto": ["TV", "TV", "TV"],
            "descricao_produto": ["Televisão", "Televisão", "Televisão"],
            "status_cadastro": ["Ativo", "Inativo", "Ativo"],
        }
    )
