from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from playwright.sync_api import Page, sync_playwright

URL = "http://127.0.0.1:8000"
ENGINE = "playwright"

BASE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = BASE_DIR / "automation_fixtures"
EVIDENCIAS_DIR = BASE_DIR / "evidencias"
LOGS_DIR = BASE_DIR / "logs"
TEMPOS_PATH = EVIDENCIAS_DIR / "tempos_execucao.json"

ARQUIVO_ORIGINAL = Path.home() / "Downloads" / "inspecao_lotes_dia.xlsx"
ARQUIVO_INSPECAO_REAL = FIXTURES_DIR / "inspecao_real.xlsx"
ARQUIVO_BASE_REFERENCIA = BASE_DIR / "data" / "processed" / "base_lotes_referencia.csv"


def configurar_logger() -> logging.Logger:
    LOGS_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(f"automacao_web.{ENGINE}")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter(
            f"%(asctime)s | {ENGINE.upper():10s} | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        arquivo = logging.FileHandler(LOGS_DIR / "automacao_web.log", encoding="utf-8")
        arquivo.setFormatter(formatter)
        logger.addHandler(arquivo)

        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    return logger


logger = configurar_logger()


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

    if not ARQUIVO_ORIGINAL.exists():
        raise FileNotFoundError(
            f"Não encontrei {ARQUIVO_ORIGINAL}. Coloque o inspecao_lotes_dia.xlsx original "
            "em data/raw/ antes de rodar este script."
        )

    logger.info(f"Preparando dados a partir de {ARQUIVO_ORIGINAL}")
    xls = pd.ExcelFile(ARQUIVO_ORIGINAL)

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

    page.goto(URL)

    page.set_input_files("#arquivo", str(item.arquivo))
    logger.info(f"Item '{item.nome}': arquivo '{item.arquivo.name}' selecionado")

    page.click("#btn-enviar")

    page.wait_for_selector("#resultado-section:not([hidden])", timeout=10_000)

    mensagem_erro = page.locator("#mensagem-erro")
    if mensagem_erro.is_visible():
        resultado_real = "erro_estrutura"
        texto_resultado = mensagem_erro.inner_text()
    else:
        sem_divergencias = page.locator("#sem-divergencias")
        resultado_real = "sem_divergencias" if sem_divergencias.is_visible() else "com_divergencias"
        texto_resultado = page.locator("#metricas").inner_text()

    logger.info(f"Item '{item.nome}': resultado obtido = '{resultado_real}' | {texto_resultado!r}")

    conforme_esperado = resultado_real == item.resultado_esperado
    if not conforme_esperado:
        logger.warning(
            f"Item '{item.nome}': DIVERGÊNCIA DE NEGÓCIO — esperado "
            f"'{item.resultado_esperado}', obtido '{resultado_real}'"
        )
    else:
        logger.info(f"Item '{item.nome}': resultado confere com o esperado")

    EVIDENCIAS_DIR.mkdir(exist_ok=True)
    caminho_screenshot = EVIDENCIAS_DIR / f"{item.nome}_{ENGINE}.png"
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


def main() -> int:
    logger.info("=== Iniciando automação Playwright (planilha real) ===")

    try:
        preparar_planilha_real()
    except FileNotFoundError as erro:
        logger.error(str(erro))
        return 1

    resultados: list[dict] = []

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=False)
            page = browser.new_page()

            for item in DATAPOOL:
                resultado = processar_item(page, item)
                resultados.append(resultado)

            browser.close()

    except Exception as erro:
        logger.error(f"Execução Playwright interrompida por falha: {erro!r}")
        logger.info("=== Automação Playwright finalizada com falha ===")
        return 1

    logger.info("=== Automação Playwright finalizada ===")
    print(json.dumps(resultados, indent=2, ensure_ascii=False))

    houve_divergencia_inesperada = any(not r["conforme_esperado"] for r in resultados)
    return 1 if houve_divergencia_inesperada else 0


if __name__ == "__main__":
    sys.exit(main())
