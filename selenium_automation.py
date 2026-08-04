from __future__ import annotations

import json
import os
import platform
import sys
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

from src.modules.normalizacao_status import validar_status
from src.modules.verificacao_lotes import carregar_base_referencia, verificar_status_lote
from src.modules.validacao import CAMPOS_OBRIGATORIOS
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
DEFAULT_TIMEOUT_MS = 5_000
POST_SUBMIT_PAUSE_SECONDS = 0.3
INSPECAO_FILE = ROOT_DIR / "automation_fixtures" / "inspecao_real.xlsx"
CAMINHO_CHROMIUM_LINUX = "/usr/bin/chromium-browser"

# logger em nível de módulo, acessível por todas as funções abaixo
logger = configurar_logger("selenium")


def _criar_driver(options: Options) -> webdriver.Chrome:
    if platform.system() == "Linux" and Path(CAMINHO_CHROMIUM_LINUX).exists():
        options.binary_location = CAMINHO_CHROMIUM_LINUX
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument(f"--user-data-dir={Path.home() / 'chromium-selenium-profile'}")
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    else:
        service = Service(ChromeDriverManager().install())

    return webdriver.Chrome(service=service, options=options)


def _sanitize_filename(value: str, fallback: str) -> str:
    sanitized = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_"))
    sanitized = sanitized.strip("-_ ")
    return sanitized or fallback


def _valid_lote_id(value: str) -> bool:
    if not value or str(value).lower() == "nan":
        return False
    return bool(pd.notna(value))


def _esta_vazio(valor) -> bool:
    if valor is None:
        return True
    if pd.isna(valor):
        return True
    if isinstance(valor, str) and valor.strip() == "":
        return True
    return False


def _campos_obrigatorios_vazios(linha: pd.Series) -> list[str]:
    return [campo for campo in CAMPOS_OBRIGATORIOS if _esta_vazio(linha.get(campo))]


def _evidencia_screenshot_path(resultado: str, screenshot_name: str) -> Path:
    return EVIDENCIAS_DIR / f"evidencia_{resultado}_{screenshot_name}.png"


def _screenshot_page(driver: webdriver.Chrome, resultado: str, screenshot_name: str) -> Path:
    screenshot_path = _evidencia_screenshot_path(resultado, screenshot_name)
    driver.save_screenshot(str(screenshot_path))
    return screenshot_path


def _wait_for_result(driver: webdriver.Chrome, timeout: int = DEFAULT_TIMEOUT_MS) -> None:
    wait = WebDriverWait(driver, timeout / 1000)
    wait.until(
        lambda d: d.execute_script(
            "return !!document.querySelector('#mensagemSucesso.show, #mensagemErro.show');"
        )
    )


def _show_error_banner(driver: webdriver.Chrome, message: str) -> None:
    driver.execute_script(
        "var banner = document.createElement('div');"
        "banner.id = 'bot-error-banner';"
        "banner.textContent = arguments[0];"
        "banner.style.position = 'fixed';"
        "banner.style.top = '0';"
        "banner.style.left = '0';"
        "banner.style.right = '0';"
        "banner.style.padding = '16px';"
        "banner.style.background = 'rgba(255, 80, 80, 0.95)';"
        "banner.style.color = '#fff';"
        "banner.style.fontSize = '16px';"
        "banner.style.fontWeight = '700';"
        "banner.style.zIndex = '9999';"
        "banner.style.textAlign = 'center';"
        "document.body.appendChild(banner);",
        message,
    )


def _login_to_form(driver: webdriver.Chrome) -> None:
    login_page = LoginPageSelenium(driver)
    login_page.goto(LOGIN_URL)
    login_page.fazer_login(LOGIN_USER, LOGIN_PASSWORD)
    WebDriverWait(driver, DEFAULT_TIMEOUT_MS / 1000).until(EC.url_to_be(URL))
    WebDriverWait(driver, DEFAULT_TIMEOUT_MS / 1000).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def _capture_error_evidence(
    driver: webdriver.Chrome,
    screenshot_name: str,
    lote: str,
    produto: str,
    status: str,
    observacao: str,
    error_message: str,
    submit: bool = False,
) -> Path:
    _login_to_form(driver)

    form_page = FormPageSelenium(driver)
    form_page.preencher_formulario(
        {
            "lote": lote,
            "produto": produto,
            "status": status,
            "observacao": observacao,
        }
    )

    if submit:
        form_page.submit()
        try:
            _wait_for_result(driver, DEFAULT_TIMEOUT_MS)
        except TimeoutException:
            pass

    _show_error_banner(driver, error_message)
    screenshot_path = _screenshot_page(driver, "erro", screenshot_name)
    time.sleep(POST_SUBMIT_PAUSE_SECONDS)
    return screenshot_path


def _capture_success_evidence(
    driver: webdriver.Chrome,
    screenshot_name: str,
    lote: str,
    produto: str,
    status: str,
    observacao: str,
) -> tuple[str, Path, bool]:
    _login_to_form(driver)

    form_page = FormPageSelenium(driver)
    form_page.preencher_formulario(
        {
            "lote": lote,
            "produto": produto,
            "status": status,
            "observacao": observacao,
        }
    )
    form_page.submit()

    resultado_real = "timeout"
    screenshot_path = _evidencia_screenshot_path("sucesso", screenshot_name)
    conforme = False

    try:
        _wait_for_result(driver, DEFAULT_TIMEOUT_MS)
        if form_page.is_sucesso():
            driver.save_screenshot(str(screenshot_path))
            resultado_real = "sucesso"
            conforme = True
            logger.info("Lote %s processado com sucesso. Screenshot: %s", lote, screenshot_path)
        else:
            mensagem_erro = form_page.get_error_message()
            screenshot_path = _evidencia_screenshot_path("erro", screenshot_name)
            driver.save_screenshot(str(screenshot_path))
            resultado_real = "erro"
            logger.warning("Lote %s gerou erro de validação no site: %s", lote, mensagem_erro)
    except TimeoutException:
        logger.exception("Timeout aguardando confirmação para lote %s", lote)
        screenshot_path = _evidencia_screenshot_path("timeout", screenshot_name)
        driver.save_screenshot(str(screenshot_path))

    time.sleep(POST_SUBMIT_PAUSE_SECONDS)
    return resultado_real, screenshot_path, conforme


def run() -> int:
    logger.info("=== Iniciando automação Selenium ===")

    if not INSPECAO_FILE.exists():
        logger.error("Arquivo de inspeção real não encontrado: %s", INSPECAO_FILE)
        return 1

    df = pd.read_excel(INSPECAO_FILE, engine="openpyxl")
    resultados: list[dict] = []

    options = Options()
    if HEADLESS:
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,1024")

    driver = _criar_driver(options)
    EVIDENCIAS_DIR.mkdir(exist_ok=True)

    try:
        base_referencia = carregar_base_referencia(ROOT_DIR / "data" / "processed" / "base_lotes_referencia.csv")

        for idx, row in df.iterrows():
            lote_raw = row.get("lote_id", "")
            lote = str(lote_raw).strip()
            produto = str(row.get("produto", "")).strip()
            status_bruto = row.get("status")
            observacao = row.get("observacao")

            if not _valid_lote_id(lote):
                logger.warning(
                    "Linha %s inválida ou comentário, tratando como erro RN02/RN03: lote=%r",
                    idx,
                    lote,
                )
                screenshot_name = _sanitize_filename(lote, fallback=f"lote_{idx}")
                inicio = time.perf_counter()
                screenshot_path = _capture_error_evidence(
                    driver,
                    screenshot_name,
                    lote,
                    produto,
                    status_bruto if status_bruto is not None else "",
                    "" if pd.isna(observacao) else str(observacao).strip(),
                    "Lote sem identificador válido; será tratado como erro.",
                    submit=True,
                )
                duracao = time.perf_counter() - inicio
                resultados.append({
                    "linha": idx + 2,
                    "lote": lote,
                    "resultado": "rn02_rn03_lote_id_invalido",
                    "descricao": "Lote sem identificador válido; será tratado como erro.",
                    "screenshot": str(screenshot_path),
                    "duracao_s": round(duracao, 2),
                    "conforme": False,
                })
                continue

            campos_vazios = _campos_obrigatorios_vazios(row)
            if campos_vazios:
                logger.warning(
                    "Lote %s: RN02 — campos obrigatórios vazios %s. Não será enviado ao site.",
                    lote,
                    campos_vazios,
                )
                screenshot_name = _sanitize_filename(lote, fallback=f"lote_{idx}")
                inicio = time.perf_counter()
                screenshot_path = _capture_error_evidence(
                    driver,
                    screenshot_name,
                    lote,
                    produto,
                    status_bruto if status_bruto is not None else "",
                    "" if pd.isna(observacao) else str(observacao).strip(),
                    f"Campos obrigatórios vazios: {', '.join(campos_vazios)}.",
                    submit=True,
                )
                duracao = time.perf_counter() - inicio
                resultados.append({
                    "lote": lote,
                    "resultado": "rn02_campos_vazios",
                    "campos_vazios": campos_vazios,
                    "screenshot": str(screenshot_path),
                    "duracao_s": round(duracao, 2),
                    "conforme": False,
                })
                continue

            status_resultado = validar_status(status_bruto)
            if status_resultado["ambiguo"]:
                logger.warning(
                    "Lote %s: RN06 — status ambíguo '%s'. Análise prévia indica revisão humana.",
                    lote,
                    status_resultado["status_original"],
                )
                screenshot_name = _sanitize_filename(lote, fallback=f"lote_{idx}")
                inicio = time.perf_counter()
                screenshot_path = _capture_error_evidence(
                    driver,
                    screenshot_name,
                    lote,
                    produto,
                    str(status_bruto),
                    "" if pd.isna(observacao) else str(observacao).strip(),
                    f"Status ambíguo '{status_resultado['status_original']}' — será analisado manualmente.",
                    submit=True,
                )
                duracao = time.perf_counter() - inicio
                resultados.append({
                    "lote": lote,
                    "resultado": "rn06_ambiguo",
                    "status_original": status_resultado["status_original"],
                    "screenshot": str(screenshot_path),
                    "duracao_s": round(duracao, 2),
                    "conforme": False,
                })
                continue

            status_normalizado = status_resultado["status_normalizado"]
            lote_status = verificar_status_lote(base_referencia, lote)
            if lote_status is None:
                logger.warning("Lote %s: RN03 — não encontrado na base de referência.", lote)
                screenshot_name = _sanitize_filename(lote, fallback=f"lote_{idx}")
                inicio = time.perf_counter()
                screenshot_path = _capture_error_evidence(
                    driver,
                    screenshot_name,
                    lote,
                    produto,
                    status_normalizado,
                    "" if pd.isna(observacao) else str(observacao).strip(),
                    "Lote não encontrado na base de referência.",
                    submit=True,
                )
                duracao = time.perf_counter() - inicio
                resultados.append({
                    "lote": lote,
                    "resultado": "rn03_inexistente",
                    "screenshot": str(screenshot_path),
                    "duracao_s": round(duracao, 2),
                    "conforme": False,
                })
                continue

            if lote_status is False:
                logger.warning("Lote %s: RN03 — lote inativo na base de referência.", lote)
                screenshot_name = _sanitize_filename(lote, fallback=f"lote_{idx}")
                inicio = time.perf_counter()
                screenshot_path = _capture_error_evidence(
                    driver,
                    screenshot_name,
                    lote,
                    produto,
                    status_normalizado,
                    "" if pd.isna(observacao) else str(observacao).strip(),
                    "Lote existe, mas está inativo na base de referência.",
                    submit=True,
                )
                duracao = time.perf_counter() - inicio
                resultados.append({
                    "lote": lote,
                    "resultado": "rn03_inativo",
                    "screenshot": str(screenshot_path),
                    "duracao_s": round(duracao, 2),
                    "conforme": False,
                })
                continue

            observacao_texto = "" if pd.isna(observacao) else str(observacao).strip()
            if status_normalizado == "REPROVADO" and observacao_texto == "":
                logger.warning(
                    "Lote %s: RN07 — lote reprovado sem observação. Enviando para o site para evidência de erro.",
                    lote,
                )

            screenshot_name = _sanitize_filename(lote, fallback=f"lote_{idx}")
            inicio = time.perf_counter()
            logger.info(
                "Processando lote %s (produto=%s, status_raw=%s, status_norm=%s)",
                lote,
                produto,
                status_bruto,
                status_normalizado,
            )

            resultado_real, screenshot_path, conforme = _capture_success_evidence(
                driver,
                screenshot_name,
                lote,
                produto,
                status_normalizado,
                observacao_texto,
            )

            duracao = time.perf_counter() - inicio
            resultados.append({
                "lote": lote,
                "resultado": resultado_real,
                "status_normalizado": status_normalizado,
                "screenshot": str(screenshot_path),
                "duracao_s": round(duracao, 2),
                "conforme": conforme,
            })

        driver.quit()
    except Exception as erro:
        logger.exception("Execução Selenium interrompida: %s", erro)
        driver.quit()
        return 1

    out = Path("evidencias") / "resultados_selenium.json"
    out.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Execução finalizada. Resultados salvos em %s", out)
    print(json.dumps(resultados, indent=2, ensure_ascii=False))
    houve_divergencia_inesperada = any(not r["conforme"] for r in resultados)
    return 1 if houve_divergencia_inesperada else 0


if __name__ == "__main__":
    sys.exit(run())