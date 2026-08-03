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
from src.modules.verificacao_lotes import verificar_status_lote
from src.modules.validacao import CAMPOS_OBRIGATORIOS

ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_PAGE = (ROOT_DIR / "webapp" / "static" / "lote-teste.html").resolve()
URL = os.environ.get("APP_URL", DEFAULT_PAGE.as_uri())
HEADLESS = os.environ.get("HEADLESS", "false").lower() in ("1", "true", "yes")
DEFAULT_TIMEOUT_MS = 5_000
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
                    logger.warning("Linha %s inválida ou comentário, pulando: lote=%r", idx, lote)
                    continue

                campos_vazios = _campos_obrigatorios_vazios(row)
                if campos_vazios:
                    logger.warning(
                        "Lote %s: RN02 — campos obrigatórios vazios %s. Não será enviado ao site.",
                        lote,
                        campos_vazios,
                    )
                    resultados.append({
                        "lote": lote,
                        "resultado": "rn02_campos_vazios",
                        "campos_vazios": campos_vazios,
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
                    resultados.append({
                        "lote": lote,
                        "resultado": "rn06_ambiguo",
                        "status_original": status_resultado["status_original"],
                        "conforme": False,
                    })
                    continue

                status_normalizado = status_resultado["status_normalizado"]
                lote_status = verificar_status_lote(lote)
                if lote_status is None:
                    logger.warning("Lote %s: RN03 — não encontrado na base de referência.", lote)
                    resultados.append({
                        "lote": lote,
                        "resultado": "rn03_inexistente",
                        "conforme": False,
                    })
                    continue
                if lote_status is False:
                    logger.warning("Lote %s: RN03 — lote inativo na base de referência.", lote)
                    resultados.append({
                        "lote": lote,
                        "resultado": "rn03_inativo",
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

                page.goto(URL)
                page.wait_for_load_state("domcontentloaded")

                page.get_by_label("Número do Lote").fill(lote)
                page.get_by_label("Produto").fill(produto)
                page.get_by_label(status_normalizado).check()
                if observacao_texto:
                    page.get_by_label("Observação").fill(observacao_texto)

                page.get_by_role("button", name="Processar Lote").click()

                screenshot_path = EVIDENCIAS_DIR / f"comprovante_{screenshot_name}.png"
                resultado_real = "timeout"
                conforme = False

                try:
                    page.wait_for_selector("#mensagemSucesso.show, #mensagemErro.show", timeout=DEFAULT_TIMEOUT_MS)
                    if page.locator("#mensagemSucesso").is_visible():
                        page.locator("#mensagemSucesso").screenshot(path=str(screenshot_path))
                        resultado_real = "sucesso"
                        conforme = True
                        logger.info("Lote %s processado com sucesso. Screenshot: %s", lote, screenshot_path)
                    else:
                        mensagem_erro = page.locator("#mensagemErro").inner_text()
                        screenshot_path = EVIDENCIAS_DIR / f"erro_{screenshot_name}.png"
                        page.screenshot(path=str(screenshot_path), full_page=True)
                        resultado_real = "erro"
                        logger.warning("Lote %s gerou erro de validação no site: %s", lote, mensagem_erro)
                except PlaywrightTimeoutError:
                    logger.exception("Timeout aguardando confirmação para lote %s", lote)
                    screenshot_path = EVIDENCIAS_DIR / f"timeout_{lote}.png"
                    page.screenshot(path=str(screenshot_path), full_page=True)

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
