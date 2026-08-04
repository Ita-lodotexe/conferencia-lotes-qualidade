from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page

from src.pages.upload_page import UploadPage


def test_upload_page_processes_file(page: Page, repo_root: Path) -> None:
    upload_url = (repo_root / "webapp" / "static" / "lote-teste.html").resolve().as_uri()

    page.goto(upload_url)
    page.wait_for_load_state("domcontentloaded")

    upload_page = UploadPage(page)
    assert upload_page.page is not None

    assert page.locator("#lote").is_visible()
    assert page.locator("#produto").is_visible()
    assert page.locator("button[type='submit']").is_visible()
