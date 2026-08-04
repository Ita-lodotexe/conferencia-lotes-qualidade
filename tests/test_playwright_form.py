from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from src.pages.form_page import FormPage


def test_form_page_accepts_valid_data(page: Page, repo_root: Path) -> None:
    login_url = (repo_root / "webapp" / "static" / "login.html").resolve().as_uri()
    login_page = page

    page.goto(login_url)
    page.wait_for_load_state("domcontentloaded")

    page.fill("#usuario", "bot_local")
    page.fill("#senha", "senha_dev")
    page.click("#btn-login")
    page.wait_for_url((repo_root / "webapp" / "static" / "lote-teste.html").resolve().as_uri())

    form_page = FormPage(page)
    form_page.preencher_formulario(
        {
            "lote": "LOTE-2026-0001",
            "produto": "TV55-4K-B",
            "status": "APROVADO",
            "observacao": "",
        }
    )
    form_page.submit()
    form_page.wait_for_result(timeout=5_000)

    assert form_page.is_sucesso() is True
    assert form_page.get_success_details()["lote"] == "LOTE-2026-0001"
    assert form_page.get_success_details()["produto"] == "TV55-4K-B"


def test_form_page_rejects_reprovado_without_observacao(page: Page, repo_root: Path) -> None:
    page.goto((repo_root / "webapp" / "static" / "login.html").resolve().as_uri())
    page.wait_for_load_state("domcontentloaded")

    page.fill("#usuario", "bot_local")
    page.fill("#senha", "senha_dev")
    page.click("#btn-login")
    page.wait_for_url((repo_root / "webapp" / "static" / "lote-teste.html").resolve().as_uri())

    form_page = FormPage(page)
    form_page.preencher_formulario(
        {
            "lote": "LOTE-2026-0002",
            "produto": "TV55-4K-B",
            "status": "REPROVADO",
            "observacao": "",
        }
    )
    form_page.submit()
    form_page.wait_for_result(timeout=5_000)

    assert form_page.is_erro() is True
    assert form_page.get_error_message() == "Erro: RN07 — lote reprovado deve ter observação preenchida."
