from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from web_automation import EVIDENCIAS_DIR, LOGS_DIR, ARQUIVO_BASE_REFERENCIA, configurar_logger
from src.modules.normalizacao_status import validar_status
from src.modules.verificacao_lotes import carregar_base_referencia, verificar_status_lote
from src.modules.validacao import CAMPOS_OBRIGATORIOS
from src.pages.form_page import FormPage
from src.pages.login_page import LoginPage

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

LOGS_DIR.mkdir(exist_ok=True)
EVIDENCIAS_DIR.mkdir(exist_ok=True)

logger = configurar_logger()


def map_produto_to_option(codigo: str) -> str:
    codigo = (codigo or "").upper()
    if "TV" in codigo:
        return "1"
    if "MON" in codigo:
        return "2"
    return "1"


def map_status_to_radio(status: str) -> str:
    if not status or status.lower() == "nan":
        return "pendente"
    s = status.lower()
    if "ativo" in s:
        return "concluido"
    if "process" in s or "processamento" in s:
        return "processamento"
    return "pendente"


def _sanitize_filename(value: str, fallback: str) -> str:
    sanitized = "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_"))
    sanitized = sanitized.strip("-_ ")
    return sanitized or fallback


def _valid_lote_id(value: str) -> bool:
    if not value or value.lower() == "nan":
        return False
    if value.startswith("⚠"):
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


def _screenshot_page(page, resultado: str, screenshot_name: str) -> Path:
    screenshot_path = _evidencia_screenshot_path(resultado, screenshot_name)
    page.screenshot(path=str(screenshot_path), full_page=True)
    return screenshot_path


def _select_status(page, status: str) -> None:
    if not status:
        return

    normalized_status = str(status).strip().upper()
    if normalized_status in {"APROVADO", "REPROVADO", "PENDENTE"}:
        try:
            page.locator(f"input[name='status'][value=\"{normalized_status}\"]").check(timeout=0)
            return
        except PlaywrightTimeoutError:
            pass
        except Exception:
            pass

    page.evaluate(
        "(status) => {\n"
        "  const form = document.getElementById('formCadastro');\n"
        "  if (!form) return;\n"
        "  const hidden = document.createElement('input');\n"
        "  hidden.type = 'radio';\n"
        "  hidden.name = 'status';\n"
        "  hidden.value = status;\n"
        "  hidden.checked = true;\n"
        "  hidden.style.display = 'none';\n"
        "  form.appendChild(hidden);\n"
        "}",
        status,
    )


def _fill_form(page, lote: str, produto: str, status: str, observacao: str) -> None:
    form_page = FormPage(page)
    form_page.preencher_formulario(
        {
            "lote": lote,
            "produto": produto,
            "status": status,
            "observacao": observacao,
        }
    )


def _show_error_banner(page, message: str) -> None:
    page.evaluate(
        "(message) => {\n"
        "  const banner = document.createElement('div');\n"
        "  banner.id = 'bot-error-banner';\n"
        "  banner.textContent = message;\n"
        "  banner.style.position = 'fixed';\n"
        "  banner.style.top = '0';\n"
        "  banner.style.left = '0';\n"
        "  banner.style.right = '0';\n"
        "  banner.style.padding = '16px';\n"
        "  banner.style.background = 'rgba(255, 80, 80, 0.95)';\n"
        "  banner.style.color = '#fff';\n"
        "  banner.style.fontSize = '16px';\n"
        "  banner.style.fontWeight = '700';\n"
        "  banner.style.zIndex = '9999';\n"
        "  banner.style.textAlign = 'center';\n"
        "  document.body.appendChild(banner);\n"
        "}",
        message,
    )


def _login_to_form(page) -> None:
    login_page = LoginPage(page)
    login_page.goto(LOGIN_URL)
    login_page.fazer_login(LOGIN_USER, LOGIN_PASSWORD)
    page.wait_for_url(URL, timeout=DEFAULT_TIMEOUT_MS)
    page.wait_for_load_state("domcontentloaded")


def _capture_error_evidence(
    page,
    screenshot_name: str,
    lote: str,
    produto: str,
    status: str,
    observacao: str,
    error_message: str,
    submit: bool = False,
) -> Path:
    _login_to_form(page)

    form_page = FormPage(page)
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
            form_page.wait_for_result(timeout=DEFAULT_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass

    _show_error_banner(page, error_message)
    screenshot_path = _screenshot_page(page, "erro", screenshot_name)
    time.sleep(POST_SUBMIT_PAUSE_SECONDS)
    return screenshot_path


def _capture_success_evidence(
    page,
    screenshot_name: str,
    lote: str,
    produto: str,
    status: str,
    observacao: str,
) -> tuple[str, Path, bool]:
    _login_to_form(page)

    form_page = FormPage(page)
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
        form_page.wait_for_result(timeout=DEFAULT_TIMEOUT_MS)
        if form_page.is_sucesso():
            page.screenshot(path=str(screenshot_path), full_page=True)
            resultado_real = "sucesso"
            conforme = True
            logger.info("Lote %s processado com sucesso. Screenshot: %s", lote, screenshot_path)
        else:
            mensagem_erro = form_page.get_error_message()
            screenshot_path = _evidencia_screenshot_path("erro", screenshot_name)
            page.screenshot(path=str(screenshot_path), full_page=True)
            resultado_real = "erro"
            logger.warning("Lote %s gerou erro de validação no site: %s", lote, mensagem_erro)
    except PlaywrightTimeoutError:
        logger.exception("Timeout aguardando confirmação para lote %s", lote)
        screenshot_path = _evidencia_screenshot_path("timeout", screenshot_name)
        page.screenshot(path=str(screenshot_path), full_page=True)

    time.sleep(POST_SUBMIT_PAUSE_SECONDS)
    return resultado_real, screenshot_path, conforme


def run() -> int:
    if not INSPECAO_FILE.exists():
        logger.error("Arquivo de inspeção real não encontrado: %s", INSPECAO_FILE)
        return 1

    df = pd.read_excel(INSPECAO_FILE, engine="openpyxl")
    resultados = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=HEADLESS)
            page = browser.new_page()

            for idx, row in df.iterrows():
                lote_raw = row.get("lote_id", "")
                lote = str(lote_raw).strip()
                produto = str(row.get("produto", "")).strip()
                status_bruto = row.get("status")
                observacao = row.get("observacao")

                if not _valid_lote_id(lote):
                    logger.warning("Linha %s inválida ou comentário, tratando como erro RN02/RN03: lote=%r", idx, lote)
                    screenshot_name = _sanitize_filename(lote, fallback=f"lote_{idx}")
                    inicio = time.perf_counter()
                    screenshot_path = _capture_error_evidence(
                        page,
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
                        page,
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
                        page,
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
                base_referencia = carregar_base_referencia(ARQUIVO_BASE_REFERENCIA)
                lote_status = verificar_status_lote(base_referencia, lote)
                if lote_status is None:
                    logger.warning("Lote %s: RN03 — não encontrado na base de referência.", lote)
                    screenshot_name = _sanitize_filename(lote, fallback=f"lote_{idx}")
                    inicio = time.perf_counter()
                    screenshot_path = _capture_error_evidence(
                        page,
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
                        page,
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
                    page,
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

            browser.close()

    except Exception as e:
        logger.exception("Execução Playwright interrompida: %s", e)
        return 1

    out = Path("evidencias") / "resultados_playwright.json"
    out.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Execução finalizada. Resultados salvos em %s", out)
    print(json.dumps(resultados, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run())
