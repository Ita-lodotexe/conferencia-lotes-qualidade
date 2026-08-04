from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from src.pages.form_page import FormPage
from src.pages.login_page import LoginPage


def fazer_login(page: Page, pagina_html: Path) -> None:
    login_url = (pagina_html / "login.html").resolve().as_uri()
    target_url = (pagina_html / "lote-teste.html").resolve().as_uri()

    login_page = LoginPage(page)
    login_page.goto(login_url)
    login_page.fazer_login("bot_local", "senha_dev")
    page.wait_for_url(target_url)


def test_formulario_lotes_pode_cadastrar_lote_com_sucesso(page: Page, pagina_html: Path, tmp_path: Path) -> None:
    fazer_login(page, pagina_html)

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
    success_details = form_page.get_success_details()
    assert success_details["lote"] == "LOTE-2026-0001"
    assert success_details["produto"] == "TV55-4K-B"

    evidencia = form_page.screenshot(tmp_path / "formulario_lotes_sucesso.png")
    assert evidencia.exists()


def test_formulario_lotes_reprovado_sem_observacao_dispara_rn07(page: Page, pagina_html: Path) -> None:
    fazer_login(page, pagina_html)

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


def test_formulario_lotes_pagina_carrega_com_titulo_correto(page: Page, pagina_html: Path) -> None:
    fazer_login(page, pagina_html)

    form_page = FormPage(page)
    assert "Cadastro de Lotes" in form_page.get_title()


def test_formulario_lotes_produto_aceita_entrada(page: Page, pagina_html: Path) -> None:
    fazer_login(page, pagina_html)

    form_page = FormPage(page)
    form_page.preencher_produto("TV55-4K-B")
    assert form_page.get_produto_value() == "TV55-4K-B"


def test_formulario_lotes_radio_status_pendente_por_padrao(page: Page, pagina_html: Path) -> None:
    fazer_login(page, pagina_html)

    form_page = FormPage(page)
    assert form_page.get_selected_status() == "PENDENTE"


def test_formulario_lotes_sem_produto_nao_exibe_sucesso(page: Page, pagina_html: Path) -> None:
    fazer_login(page, pagina_html)

    form_page = FormPage(page)
    form_page.preencher_formulario(
        {
            "lote": "LOTE-2026-0004",
            "produto": "",
            "status": "APROVADO",
            "observacao": "",
        }
    )
    form_page.submit()
    form_page.wait_for_result(timeout=5_000)

    assert form_page.is_erro() is True
    assert form_page.get_error_message() == "Erro: RN02 — o campo 'produto' não pode ficar vazio."


def test_formulario_lotes_screenshot_como_evidencia(page: Page, pagina_html: Path, tmp_path: Path) -> None:
    fazer_login(page, pagina_html)

    form_page = FormPage(page)
    form_page.preencher_formulario(
        {
            "lote": "LOTE-2026-0005",
            "produto": "TV55-4K-B",
            "status": "APROVADO",
            "observacao": "",
        }
    )
    form_page.submit()
    form_page.wait_for_result(timeout=5_000)

    evidencia = form_page.screenshot(tmp_path / "formulario_lotes_evidence.png")

    assert evidencia.exists()
    assert evidencia.stat().st_size > 0


def test_formulario_lotes_status_ambiguidade_dispara_rn06(page: Page, pagina_html: Path) -> None:
    fazer_login(page, pagina_html)

    form_page = FormPage(page)
    form_page.preencher_lote("LOTE-2026-0003")
    form_page.preencher_produto("TV55-4K-B")
    form_page.select_status("OK")
    form_page.submit()
    form_page.wait_for_result(timeout=5_000)

    assert form_page.is_erro() is True
    assert form_page.get_error_message() == "Erro: RN06 — status 'OK' é ambíguo e requer revisão humana."


def test_formulario_lotes_lote_vazio_dispara_rn02(page: Page, pagina_html: Path) -> None:
    fazer_login(page, pagina_html)

    form_page = FormPage(page)
    form_page.preencher_formulario(
        {
            "lote": "",
            "produto": "TV55-4K-B",
            "status": "APROVADO",
            "observacao": "",
        }
    )
    form_page.submit()
    form_page.wait_for_result(timeout=5_000)

    assert form_page.is_erro() is True
    assert form_page.get_error_message() == "Erro: RN02 — o campo 'lote_id' não pode ficar vazio."
