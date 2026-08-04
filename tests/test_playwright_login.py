from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from src.pages.login_page import LoginPage


def test_login_page_renders_and_logs_in(page: Page, repo_root: Path) -> None:
    login_url = (repo_root / "webapp" / "static" / "login.html").resolve().as_uri()
    target_url = (repo_root / "webapp" / "static" / "lote-teste.html").resolve().as_uri()

    login_page = LoginPage(page)
    login_page.goto(login_url)

    login_page.fazer_login("bot_local", "senha_dev")
    page.wait_for_url(target_url)

    assert page.url == target_url

    assert page.locator("#lote").is_visible()
    assert page.locator("#produto").is_visible()


def test_login_page_shows_error_for_invalid_credentials(page: Page, repo_root: Path) -> None:
    login_url = (repo_root / "webapp" / "static" / "login.html").resolve().as_uri()

    login_page = LoginPage(page)
    login_page.goto(login_url)

    login_page.fazer_login("wrong_user", "wrong_pass")
    assert page.locator("#loginError").inner_text() == "Usuário ou senha incorretos."
    assert page.locator("#loginError").is_visible()
