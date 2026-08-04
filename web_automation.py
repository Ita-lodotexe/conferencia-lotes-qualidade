from __future__ import annotations

import json
import logging
import os
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
from playwright.sync_api import Page, sync_playwright
from pythonjsonlogger import jsonlogger

from src.pages.upload_page import UploadPage

EM_CONTAINER = os.environ.get("ENVIRONMENT", "local") != "local"
URL = os.environ.get("WEB_AUTOMATION_URL", "http://webapp:8000" if EM_CONTAINER else "http://127.0.0.1:8000")
ENGINE = "playwright"
HEADLESS = os.environ.get("HEADLESS", "false").lower() in ("1", "true", "yes") or EM_CONTAINER
CONTAINER_ARGS = ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
DEFAULT_TIMEOUT_MS = 10_000

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BASE_DIR / "automation_fixtures"
EVIDENCIAS_DIR = BASE_DIR / "evidencias"
LOGS_DIR = BASE_DIR / "logs"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
REPORTS_DIR = BASE_DIR / "reports"
DATA_OUTPUT_DIR = BASE_DIR / "data" / "output"
DATA_RAW_DIR = BASE_DIR / "data" / "raw"
FALLBACK_ORIGINAL = DATA_RAW_DIR / "inspecao_lotes_dia.xlsx"
ARQUIVO_ORIGINAL = Path(os.environ.get("WEB_AUTOMATION_ORIGINAL_PATH", "")) if os.environ.get("WEB_AUTOMATION_ORIGINAL_PATH") else FALLBACK_ORIGINAL
ARQUIVO_INSPECAO_REAL = FIXTURES_DIR / "inspecao_real.xlsx"
ARQUIVO_BASE_REFERENCIA = BASE_DIR / "data" / "processed" / "base_lotes_referencia.csv"


def configurar_logger(nome_engine: str | None = None) -> logging.Logger:
    nome_engine = nome_engine or ENGINE
    LOGS_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(f"automacao_web.{nome_engine}")
    logger.setLevel(logging.INFO)
    execution_id = os.environ.get("EXECUTION_ID") or os.environ.get("EXECUTIONID")
    bot_id = os.environ.get("BOT_ID") or os.environ.get("BOTID")

    class ContextFilter(logging.Filter):
        def __init__(self, execution_id: str | None, bot_id: str | None):
            super().__init__()
            self.execution_id = execution_id
            self.bot_id = bot_id

        def filter(self, record: logging.LogRecord) -> bool:
            record.execution_id = self.execution_id
            record.bot_id = self.bot_id
            return True

    log_to_file = os.environ.get("WEB_AUTOMATION_LOG_FILE", "false").lower() in ("1", "true", "yes")

    if not logger.handlers:
        fmt = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s %(execution_id)s %(bot_id)s",
            timestamp=True,
        )

        console = logging.StreamHandler()
        console.setFormatter(fmt)
        console.addFilter(ContextFilter(execution_id, bot_id))
        logger.addHandler(console)

        if log_to_file:
            LOGS_DIR.mkdir(exist_ok=True)
            arquivo = logging.FileHandler(LOGS_DIR / "automacao_web.jsonl", encoding="utf-8")
            arquivo.setFormatter(fmt)
            arquivo.addFilter(ContextFilter(execution_id, bot_id))
            logger.addHandler(arquivo)

    return logger


logger = configurar_logger()


def _ensure_directories() -> None:
    for path in (
        FIXTURES_DIR,
        EVIDENCIAS_DIR,
        LOGS_DIR,
        SCREENSHOTS_DIR,
        REPORTS_DIR,
        DATA_OUTPUT_DIR,
        ARQUIVO_BASE_REFERENCIA.parent,
        DATA_RAW_DIR,
    ):
        path.mkdir(exist_ok=True, parents=True)


def _original_path() -> Path:
    if ARQUIVO_ORIGINAL.exists():
        return ARQUIVO_ORIGINAL

    fallback = Path.home() / "Downloads" / "inspecao_lotes_dia.xlsx"
    if fallback.exists():
        logger.info(
            "Usando arquivo original em Downloads porque WEB_AUTOMATION_ORIGINAL_PATH e data/raw não foram encontrados."
        )
        return fallback

    raise FileNotFoundError(
        "Não encontrei o arquivo original de inspeção. Coloque 'inspecao_lotes_dia.xlsx' em data/raw/ ou em Downloads."
    )


def _wait_for_service(url: str, timeout_seconds: int = 30) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=2):
                return
        except OSError:
            time.sleep(1)

    raise RuntimeError(f"Serviço '{url}' não ficou disponível em {timeout_seconds}s.")


def iniciar_browser(playwright):
    args = CONTAINER_ARGS if EM_CONTAINER else []
    if EM_CONTAINER:
        logger.info("Iniciando Chromium em modo container com flags de container.")
    return playwright.chromium.launch(headless=HEADLESS, args=args)


@dataclass
class ItemDataPool:
    nome: str
    arquivo: Path
    resultado_esperado: str
    descricao: str
    screenshot: Path | None = field(default=None)


def preparar_planilha_real() -> None:
    if ARQUIVO_INSPECAO_REAL.exists() and ARQUIVO_BASE_REFERENCIA.exists():
        logger.info("Planilha real e base de referência já preparadas, reaproveitando.")
        return

    arquivo_original = _original_path()
    logger.info(f"Preparando dados a partir de {arquivo_original}")
    xls = pd.ExcelFile(arquivo_original)

    inspecao = pd.read_excel(xls, sheet_name="Inspecao_14_06_2026", header=2)
    inspecao.columns = [str(c).strip() for c in inspecao.columns]
    inspecao = inspecao.iloc[:25]

    FIXTURES_DIR.mkdir(exist_ok=True)
    inspecao.to_excel(ARQUIVO_INSPECAO_REAL, index=False)
    logger.info(f"Planilha de inspeção limpa salva em {ARQUIVO_INSPECAO_REAL} ({len(inspecao)} linhas)")

    base = pd.read_excel(xls, sheet_name="Base_Referencia", header=1)
    base.columns = [str(c).strip() for c in base.columns]

    ARQUIVO_BASE_REFERENCIA.parent.mkdir(exist_ok=True, parents=True)
    base.to_csv(ARQUIVO_BASE_REFERENCIA, index=False)
    logger.info(f"Base de referência salva em {ARQUIVO_BASE_REFERENCIA} ({len(base)} linhas)")


DATAPOOL: list[ItemDataPool] = [
    ItemDataPool(
        nome="inspecao_real_14_06",
        arquivo=ARQUIVO_INSPECAO_REAL,
        resultado_esperado="com_divergencias",
        descricao="Planilha real do dia 14/06/2026, 25 registros, 9 esperados com divergência.",
    ),
]


def _registrar_tempo(item_nome: str, segundos: float) -> None:
    EVIDENCIAS_DIR.mkdir(exist_ok=True)
    historico = []
    if TEMPOS_PATH.exists():
        historico = json.loads(TEMPOS_PATH.read_text(encoding="utf-8"))
    historico.append({"engine": ENGINE, "item": item_nome, "segundos": round(segundos, 2)})
    TEMPOS_PATH.write_text(json.dumps(historico, indent=2, ensure_ascii=False), encoding="utf-8")


def processar_item(page: Page, item: ItemDataPool) -> dict:
    inicio = time.perf_counter()
    logger.info(f"Item '{item.nome}': iniciando ({item.descricao})")

    upload_page = UploadPage(page)
    upload_page.goto(URL)
    upload_page.upload_file(str(item.arquivo))
    logger.info(f"Item '{item.nome}': arquivo '{item.arquivo.name}' selecionado")
    upload_page.submit()
    upload_page.wait_for_result(timeout=DEFAULT_TIMEOUT_MS)

    if upload_page.has_error():
        resultado_real = "erro_estrutura"
        texto_resultado = page.locator("#mensagem-erro").inner_text()
    else:
        resultado_real = "sem_divergencias" if upload_page.has_no_divergencias() else "com_divergencias"
        texto_resultado = upload_page.get_metricas()

    logger.info(f"Item '{item.nome}': resultado obtido = '{resultado_real}' | {texto_resultado!r}")

    conforme_esperado = resultado_real == item.resultado_esperado
    if not conforme_esperado:
        logger.warning(
            f"Item '{item.nome}': DIVERGÊNCIA DE NEGÓCIO — esperado "
            f"'{item.resultado_esperado}', obtido '{resultado_real}'"
        )
    else:
        logger.info(f"Item '{item.nome}': resultado confere com o esperado")

    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    caminho_screenshot = SCREENSHOTS_DIR / f"{item.nome}_{ENGINE}.png"
    page.screenshot(path=str(caminho_screenshot), full_page=True)
    item.screenshot = caminho_screenshot
    logger.info(f"Item '{item.nome}': screenshot salvo em '{caminho_screenshot}'")

    duracao = time.perf_counter() - inicio
    _registrar_tempo(item.nome, duracao)
    logger.info(f"Item '{item.nome}': concluído em {duracao:.2f}s")

    return {
        "item": item.nome,
        "resultado_esperado": item.resultado_esperado,
        "resultado_real": resultado_real,
        "conforme_esperado": conforme_esperado,
        "screenshot": str(caminho_screenshot),
        "duracao_s": round(duracao, 2),
        "texto_resultado": texto_resultado,
    }


def salvar_relatorio(resultados: list[dict]) -> None:
    DATA_OUTPUT_DIR.mkdir(exist_ok=True, parents=True)
    REPORTS_DIR.mkdir(exist_ok=True, parents=True)

    df = pd.DataFrame(resultados)
    csv_path = DATA_OUTPUT_DIR / "inspecao_lotes_resultado.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8")

    json_path = REPORTS_DIR / "inspecao_lotes_resultado.json"
    json_path.write_text(json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info(f"Relatório salvo em '{csv_path}' e resumo de execução em '{json_path}'.")


def main() -> int:
    logger.info("=== Iniciando automação Playwright (planilha real) ===")

    logger.info(f"Modo container: {EM_CONTAINER} | URL de automação: {URL}")

    _ensure_directories()

    try:
        preparar_planilha_real()
    except FileNotFoundError as erro:
        logger.error(str(erro))
        return 1

    resultados: list[dict] = []

    try:
        if EM_CONTAINER:
            _wait_for_service(URL, timeout_seconds=30)

        with sync_playwright() as playwright:
            browser = iniciar_browser(playwright)
            page = browser.new_page()

            for item in DATAPOOL:
                resultado = processar_item(page, item)
                resultados.append(resultado)

            browser.close()

    except Exception as erro:
        logger.error(f"Execução Playwright interrompida por falha: {erro!r}")
        logger.info("=== Automação Playwright finalizada com falha ===")
        return 1

    salvar_relatorio(resultados)
    logger.info("=== Automação Playwright finalizada ===")
    print(json.dumps(resultados, indent=2, ensure_ascii=False))

    houve_divergencia_inesperada = any(not r["conforme_esperado"] for r in resultados)
    return 1 if houve_divergencia_inesperada else 0


if __name__ == "__main__":
    sys.exit(main())