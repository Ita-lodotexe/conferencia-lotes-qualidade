from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

CAMINHO_CHROMIUM = "/usr/bin/chromium-browser"

URL = "http://127.0.0.1:8000"
ENGINE = "selenium"
TEMPO_ESPERA_MAX_S = 10

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


def processar_item(driver, wait: WebDriverWait, item: ItemDataPool) -> dict:
    inicio = time.perf_counter()
    logger.info(f"Item '{item.nome}': iniciando ({item.descricao})")

    driver.get(URL)

    input_arquivo = wait.until(EC.presence_of_element_located((By.ID, "arquivo")))

    driver.execute_script("arguments[0].removeAttribute('hidden')", input_arquivo)
    input_arquivo.send_keys(str(item.arquivo.resolve()))
    logger.info(f"Item '{item.nome}': arquivo '{item.arquivo.name}' selecionado")

    btn_enviar = wait.until(EC.element_to_be_clickable((By.ID, "btn-enviar")))
    btn_enviar.click()

    wait.until(EC.visibility_of_element_located((By.ID, "resultado-section")))

    elementos_erro = driver.find_elements(By.ID, "mensagem-erro")
    erro_visivel = bool(elementos_erro) and elementos_erro[0].is_displayed()

    if erro_visivel:
        resultado_real = "erro_estrutura"
        texto_resultado = elementos_erro[0].text
    else:
        sem_divergencias = driver.find_elements(By.ID, "sem-divergencias")
        resultado_real = (
            "sem_divergencias"
            if sem_divergencias and sem_divergencias[0].is_displayed()
            else "com_divergencias"
        )
        texto_resultado = driver.find_element(By.ID, "metricas").text

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
    driver.save_screenshot(str(caminho_screenshot))
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
    logger.info("=== Iniciando automação Selenium (planilha real) ===")

    try:
        preparar_planilha_real()
    except FileNotFoundError as erro:
        logger.error(str(erro))
        return 1

    resultados: list[dict] = []
    driver = None

    try:
        options = Options()
        options.binary_location = CAMINHO_CHROMIUM
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--headless=new")
        options.add_argument(f"--user-data-dir={Path.home() / 'chromium-selenium-profile'}")

        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
        driver = webdriver.Chrome(service=service, options=options)
        wait = WebDriverWait(driver, TEMPO_ESPERA_MAX_S)

        for item in DATAPOOL:
            resultado = processar_item(driver, wait, item)
            resultados.append(resultado)

    except WebDriverException as erro:
        logger.error(f"Falha do WebDriver (Chrome/driver não disponível?): {erro!r}")
        logger.info("=== Automação Selenium finalizada com falha ===")
        return 1

    except Exception as erro:
        logger.error(f"Execução Selenium interrompida por falha inesperada: {erro!r}")
        logger.info("=== Automação Selenium finalizada com falha ===")
        return 1

    finally:
        if driver is not None:
            driver.quit()

    logger.info("=== Automação Selenium finalizada ===")
    print(json.dumps(resultados, indent=2, ensure_ascii=False))

    houve_divergencia_inesperada = any(not r["conforme_esperado"] for r in resultados)
    return 1 if houve_divergencia_inesperada else 0


if __name__ == "__main__":
    sys.exit(main())
