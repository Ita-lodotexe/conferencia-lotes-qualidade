from __future__ import annotations

import os
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from src.pages.form_page import FormPageSelenium
from src.pages.login_page import LoginPageSelenium
from web_automation import EVIDENCIAS_DIR, configurar_logger

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_LOGIN_PAGE = (ROOT_DIR / "webapp" / "static" / "login.html").resolve()
DEFAULT_PAGE = (ROOT_DIR / "webapp" / "static" / "lote-teste.html").resolve()
LOGIN_URL = os.environ.get("APP_LOGIN_URL", DEFAULT_LOGIN_PAGE.as_uri())
URL = os.environ.get("APP_URL", DEFAULT_PAGE.as_uri())
LOGIN_USER = os.environ.get("APP_USER", "bot_local")
LOGIN_PASSWORD = os.environ.get("APP_PASSWORD", "senha_dev")
HEADLESS = os.environ.get("HEADLESS", "false").lower() in ("1", "true", "yes")


def run() -> int:
    logger = configurar_logger()
    logger.info("=== Iniciando automação Selenium ===")

    EVIDENCIAS_DIR.mkdir(exist_ok=True)

    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,1024")

    try:
        with webdriver.Chrome(options=options) as driver:
            login_page = LoginPageSelenium(driver)
            login_page.goto(LOGIN_URL)
            login_page.fazer_login(LOGIN_USER, LOGIN_PASSWORD)
            WebDriverWait(driver, 10).until(EC.url_to_be(URL))

            form_page = FormPageSelenium(driver)

            dados_lote = {
                "lote": "LOTE-2026-0001",
                "produto": "TV55-4K-B",
                "status": "APROVADO",
                "observacao": "",
            }

            form_page.preencher_formulario(dados_lote)
            form_page.submit()
            time.sleep(1)

            caminho_screenshot = EVIDENCIAS_DIR / "selenium_form_page.png"
            form_page.screenshot(caminho_screenshot)
            logger.info(f"Screenshot salvo em {caminho_screenshot}")

            if form_page.is_sucesso():
                logger.info("Formulário processado com sucesso pelo Selenium.")
            elif form_page.is_erro():
                logger.warning(f"Erro detectado: {form_page.get_error_message()}")
            else:
                logger.warning("Nenhuma mensagem de sucesso ou erro foi exibida.")

        return 0
    except Exception as erro:
        logger.exception("Falha na automação Selenium: %s", erro)
        return 1


if __name__ == "__main__":
    raise SystemExit(run())
