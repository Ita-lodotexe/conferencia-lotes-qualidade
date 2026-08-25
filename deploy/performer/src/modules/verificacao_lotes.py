"""RN03 (Existência e Status do Lote na Base de Referência)."""

import pandas as pd
import logging

def carregar_base_referencia(caminho: str) -> pd.DataFrame:
    try:
        base = pd.read_csv(caminho)
    except Exception as e:
        logging.error(f"Erro ao carregar base de referência '{caminho}': {e}")
        raise
    return base


def verificar_existencia_lote(base: pd.DataFrame, lote: str) -> bool:
    if lote in base["lote_id"].values:
        return True
    return False


def verificar_status_lote(base: pd.DataFrame, lote: str):
    if verificar_existencia_lote(base, lote):
        resultado = base.loc[base["lote_id"] == lote, "status_cadastro"]
        if resultado.empty:
            return False
        status = resultado.iloc[0]
        return str(status).strip().lower() == "ativo"
    return None
