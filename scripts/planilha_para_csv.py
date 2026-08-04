"""
Preprocessor: lê a planilha oficial do exercício LG Electronics
(inspecao_lotes_dia.xlsx) e gera os CSVs consumidos pelo Dispatcher
e pelo Performer.

Uso:
    python -m scripts.planilha_para_csv

Entrada:
    dados_referencia/inspecao_lotes_dia.xlsx

Saídas:
    dados_entrada/lotes_auditoria.csv        (25 lotes da aba Inspecao)
    data/processed/base_lotes_referencia.csv (23 lotes da aba Base_Referencia)

Normalizações aplicadas:
    - Corte de linhas de lixo (rodapé, notas, legenda) via limite explícito
    - NaN (célula vazia do Excel) → "" (string vazia) para evitar
      problemas de serialização JSON no Dispatcher
"""

import logging
import os
import sys

import pandas as pd

from src.modules.validacao import COLUNAS_ESPERADAS

PLANILHA_ENTRADA = "dados_referencia/inspecao_lotes_dia.xlsx"
CSV_FILA_SAIDA = "dados_entrada/lotes_auditoria.csv"
CSV_BASE_SAIDA = "data/processed/base_lotes_referencia.csv"

ABA_INSPECAO = "Inspecao_14_06_2026"
ABA_BASE = "Base_Referencia"

# Limites derivados do rodapé da própria planilha ("Total de registros: 25"
# na aba de inspeção, "Registros: 23" no título da base). O corte por
# posição é intencional: filtrar por lote_id não-vazio descartaria a linha
# de lote_id vazio, que é um dos erros propositais do exercício.
LIMITE_LINHAS_INSPECAO = 25  # rodapé + legenda começam depois disso
LIMITE_LINHAS_BASE = 23      # linha vazia + nota do professor começam depois disso

SKIPROWS_INSPECAO = 2  # título + metadados de coleta
SKIPROWS_BASE = 1      # título

COLUNAS_ESPERADAS_BASE = ["lote_id", "codigo_produto", "descricao_produto", "status_cadastro"]


class PreprocessorError(Exception):
    """Erros do preprocessor com mensagem descritiva."""


def _normalizar_dataframe(df: pd.DataFrame, colunas: list[str]) -> pd.DataFrame:
    """Converte NaN em string vazia e fixa a ordem canônica das colunas.

    O `astype(str)` roda depois do `fillna("")` de propósito: se a ordem
    fosse invertida, os NaN virariam a string literal "nan" — que passa
    por qualquer validação de "campo preenchido" e mascararia os erros
    propositais da planilha.
    """
    return df.fillna("").astype(str)[colunas]


def carregar_aba_inspecao(planilha_path: str) -> pd.DataFrame:
    """Lê a aba de inspeção, aplica skiprows e corte, normaliza NaN.

    Valida que as 8 colunas esperadas (COLUNAS_ESPERADAS de validacao.py)
    estão presentes. Retorna DataFrame com 25 linhas úteis. Levanta
    PreprocessorError se a estrutura estiver inválida.
    """
    df = pd.read_excel(planilha_path, sheet_name=ABA_INSPECAO, skiprows=SKIPROWS_INSPECAO)
    df = df.iloc[:LIMITE_LINHAS_INSPECAO]

    faltantes = set(COLUNAS_ESPERADAS) - set(df.columns)
    if faltantes:
        raise PreprocessorError(
            f"Aba '{ABA_INSPECAO}' não tem colunas esperadas: {sorted(faltantes)}"
        )

    return _normalizar_dataframe(df, COLUNAS_ESPERADAS)


def carregar_aba_base(planilha_path: str) -> pd.DataFrame:
    """Lê a aba de base de referência.

    Valida presença de lote_id e status_cadastro. Retorna 23 linhas úteis
    após corte da linha vazia e da nota do professor no fim da aba.
    """
    df = pd.read_excel(planilha_path, sheet_name=ABA_BASE, skiprows=SKIPROWS_BASE)
    df = df.iloc[:LIMITE_LINHAS_BASE]

    faltantes = set(COLUNAS_ESPERADAS_BASE) - set(df.columns)
    if faltantes:
        raise PreprocessorError(
            f"Aba '{ABA_BASE}' não tem colunas esperadas: {sorted(faltantes)}"
        )

    return _normalizar_dataframe(df, COLUNAS_ESPERADAS_BASE)


def main() -> int:
    from src.bot.bot import setup_logger

    setup_logger()

    logging.info(f"Preprocessor iniciado: {PLANILHA_ENTRADA}")

    if not os.path.exists(PLANILHA_ENTRADA):
        logging.error(f"Planilha não encontrada: {PLANILHA_ENTRADA}")
        return 1

    try:
        df_inspecao = carregar_aba_inspecao(PLANILHA_ENTRADA)
        df_base = carregar_aba_base(PLANILHA_ENTRADA)
    except PreprocessorError as e:
        logging.error(f"Erro no parsing: {e}")
        return 1

    os.makedirs(os.path.dirname(CSV_FILA_SAIDA), exist_ok=True)
    os.makedirs(os.path.dirname(CSV_BASE_SAIDA), exist_ok=True)

    df_inspecao.to_csv(CSV_FILA_SAIDA, index=False, encoding="utf-8")
    df_base.to_csv(CSV_BASE_SAIDA, index=False, encoding="utf-8")

    logging.info(
        f"CSVs gerados: {len(df_inspecao)} lotes → {CSV_FILA_SAIDA}, "
        f"{len(df_base)} registros → {CSV_BASE_SAIDA}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
