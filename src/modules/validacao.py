# Implementa as regras de negócio de estrutura e preenchimento: 
#   RN01: a planilha de lotes deve conter as 8 colunas esperadas.
#   RN02: os 7 campos obrigatórios não podem estar vazios em nenhuma linha.

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
    """Valida a estrutura da planilha de lotes (RN01).

    Retorna a lista de colunas ausentes. Uma lista vazia significa que a
    estrutura está correta.
    """
    colunas_presentes = set(df.columns)
    faltando = [coluna for coluna in COLUNAS_ESPERADAS if coluna not in colunas_presentes]
    return faltando


def valida_campos_obrigatorios(df: pd.DataFrame) -> list[dict]:
    """Valida os campos obrigatórios de cada linha (RN02).

    Percorre cada linha e verifica se algum campo obrigatório está vazio
    (None, NaN ou texto em branco). O número da linha usa a numeração da
    planilha (começa em 2, já que a linha 1 é o cabeçalho).
    """
    ocorrencias: list[dict] = []
    for indice, linha in df.iterrows():
        for campo in CAMPOS_OBRIGATORIOS:
            if campo not in df.columns:
                continue
            if _esta_vazio(linha[campo]):
                ocorrencias.append({"linha": indice + 2, "campo": campo})
    return ocorrencias


def _esta_vazio(valor) -> bool:
    """Retorna True se o valor for considerado vazio (None, NaN ou em branco)."""
    if valor is None:
        return True
    if pd.isna(valor):
        return True
    if isinstance(valor, str) and valor.strip() == "":
        return True
    return False