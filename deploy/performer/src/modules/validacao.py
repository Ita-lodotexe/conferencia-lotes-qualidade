"""RN01 e RN02 (Estrutura e Campos Obrigatórios)."""

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
    colunas_presentes = set(df.columns)
    return [coluna for coluna in COLUNAS_ESPERADAS if coluna not in colunas_presentes]


def valida_campos_obrigatorios(df: pd.DataFrame) -> list[dict]:
    ocorrencias: list[dict] = []
    for indice, linha in df.iterrows():
        for campo in CAMPOS_OBRIGATORIOS:
            if campo not in df.columns:
                continue
            if _esta_vazio(linha[campo]):
                ocorrencias.append({"linha": indice, "campo": campo})
    return ocorrencias


def _esta_vazio(valor) -> bool:
    if valor is None or pd.isna(valor):
        return True
    if isinstance(valor, str) and valor.strip() == "":
        return True
    return False
