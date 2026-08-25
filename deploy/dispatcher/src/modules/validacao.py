"""Validação de estrutura e campos obrigatórios (RN01 e RN02)."""

from __future__ import annotations
import pandas as pd

COLUNAS_ESPERADAS = [
    "lote_id",
    "produto",
    "linha",
    "turno",
    "status",
    "responsavel",
    "data",
    "observacao",
]

CAMPOS_OBRIGATORIOS = [
    "lote_id",
    "produto",
    "linha",
    "turno",
    "status",
    "responsavel",
    "data",
]


def valida_estrutura(df: pd.DataFrame) -> list[str]:
    """Valida a estrutura da planilha de lotes (RN01)."""
    colunas_presentes = set(df.columns)
    faltando = [coluna for coluna in COLUNAS_ESPERADAS if coluna not in colunas_presentes]
    return faltando


def valida_campos_obrigatorios(df: pd.DataFrame) -> list[dict]:
    """Valida os campos obrigatórios de cada linha (RN02)."""
    ocorrencias: list[dict] = []
    for indice, linha in df.iterrows():
        for campo in CAMPOS_OBRIGATORIOS:
            if campo not in df.columns:
                continue
            if _esta_vazio(linha[campo]):
                ocorrencias.append({"linha": indice, "campo": campo})
    return ocorrencias


def _esta_vazio(valor) -> bool:
    if valor is None:
        return True
    if pd.isna(valor):
        return True
    if isinstance(valor, str) and valor.strip() == "":
        return True
    return False
