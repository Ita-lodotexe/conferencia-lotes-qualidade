# Implementa a regra de negócio de identificação de lote:
#   RN03 — Existência: o lote_id deve existir na aba Base_Referencia da planilha.


import pandas as pd
import logging


def carregar_base_referencia(caminho: str) -> pd.DataFrame:
    try:
        base = pd.read_csv(caminho)
    except FileNotFoundError:
        logging.error("Não foi possivel encontrar o arquivo.")
        raise
    except Exception as e:
        logging.error(f"Algo ocorreu de errado ao encontrar o arquivo:\n{e}")
        raise

    if not base.empty:
        logging.info("Base de lotes para referência encontrada!")

    return base


# Função que checa se o lote do relatório existe na base de lotes:
def verificar_existencia_lote(base: pd.DataFrame, lote: str) -> bool:
    if lote in base['lote_id'].values:
        logging.info(f"Lote '{lote}' encontrado na base de dados.")
        return True
    else:
        logging.warning(f"Lote '{lote}' não encontrado.")
        return False


# Função que verifica se o lote existente está ativo:
def verificar_status_lote(base: pd.DataFrame, lote: str):
    if verificar_existencia_lote(base, lote):
        # Buscamos pelo status
        resultado = base.loc[base['lote_id'] == lote, 'status_cadastro']
        status = resultado.item()
        logging.info(f"O status do lote '{lote}' é: {status}")

        if status == 'Ativo':
            return True
        else:
            return False
    return None
