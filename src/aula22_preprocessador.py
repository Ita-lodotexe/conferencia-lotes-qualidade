"""Leitura de inspecao_lotes_10dias.xlsx (10 abas diárias + Base_Referencia).

Generaliza o problema que scan_estado.md apontou em
scripts/planilha_para_csv.py (ABA_INSPECAO hardcoded para 1 aba única):
aqui iteramos sobre todas as abas que começam com "Insp_", em vez de um
nome fixo, e anexamos a dimensão "dia" a cada registro (necessária para
RN11 e para o gráfico de evolução).
"""
from __future__ import annotations

import re

import pandas as pd

COLUNAS_LOTE = [
    "lote_id", "produto", "linha", "turno",
    "status", "responsavel", "data", "observacao",
]

COLUNAS_BASE = ["lote_id", "codigo_produto", "descricao_produto", "status_cadastro"]

PREFIXO_ABA_DIARIA = "Insp_"
ABA_BASE_REFERENCIA = "Base_Referencia"


def _extrair_data_referencia(nome_aba: str) -> str:
    """'Insp_15_06_2026' -> '15/06/2026'."""
    match = re.search(r"(\d{2})_(\d{2})_(\d{4})", nome_aba)
    if not match:
        return nome_aba
    dia, mes, ano = match.groups()
    return f"{dia}/{mes}/{ano}"


def carregar_planilha_10dias(caminho: str) -> tuple[dict[str, list[dict]], pd.DataFrame]:
    """Lê todas as abas diárias + Base_Referencia de uma vez.

    Returns:
        (registros_por_dia, base_referencia) — registros_por_dia é um
        dict {nome_da_aba: [registro, ...]}, na ordem das abas e das
        linhas originais. Cada registro tem as 8 colunas de negócio +
        "_dia", "_data_referencia" e "_linha_planilha" (nº da linha na
        aba de origem, 1-based, contando a partir do cabeçalho — útil
        para Fernanda rastrear o registro na planilha original).
    """
    excel = pd.ExcelFile(caminho)
    abas_diarias = [nome for nome in excel.sheet_names if nome.startswith(PREFIXO_ABA_DIARIA)]

    if not abas_diarias:
        raise ValueError(
            f"Nenhuma aba com prefixo '{PREFIXO_ABA_DIARIA}' encontrada em {caminho}."
        )
    if ABA_BASE_REFERENCIA not in excel.sheet_names:
        raise ValueError(f"Aba '{ABA_BASE_REFERENCIA}' não encontrada em {caminho}.")

    registros_por_dia: dict[str, list[dict]] = {}
    for nome_aba in abas_diarias:
        df = pd.read_excel(excel, sheet_name=nome_aba, skiprows=2, header=0)
        df = df[COLUNAS_LOTE] if set(COLUNAS_LOTE).issubset(df.columns) else df

        # Remove rodapé: linhas totalmente vazias ou onde lote_id começa
        # com "Total de registros" (mesmo padrão do footer observado em
        # todas as abas).
        df = df[~df["lote_id"].astype(str).str.startswith("Total de registros", na=False)]
        df = df.dropna(how="all")

        data_referencia = _extrair_data_referencia(nome_aba)
        registros = []
        for posicao, (_, linha) in enumerate(df.iterrows(), start=1):
            registro = linha.to_dict()
            registro["_dia"] = nome_aba
            registro["_data_referencia"] = data_referencia
            # +2 (título+metadados) +1 (cabeçalho) = linha real na planilha
            registro["_linha_planilha"] = posicao + 3
            registros.append(registro)

        registros_por_dia[nome_aba] = registros

    base_bruta = pd.read_excel(excel, sheet_name=ABA_BASE_REFERENCIA, skiprows=1, header=0)
    base_bruta = base_bruta.dropna(subset=["lote_id"])
    base_referencia = base_bruta[COLUNAS_BASE].reset_index(drop=True)

    return registros_por_dia, base_referencia
