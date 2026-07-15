# Implementa a regra de negócio de identificação de lote: 
#   RN03 — Existência: o lote_id deve existir na aba Base_Referencia da planilha.


import pandas as pd
import logging
import sys

# Leitura do dataset:
try:
    BASE_LOTES = pd.read_csv("data/processed/base_lotes_referencia.csv")
except FileNotFoundError: 
    logging.error("Não foi possivel encontrar o arquivo.")
    sys.exit()
except Exception as e:
    logging.error(f"Algo ocorreu de errado ao encontrar o arquivo:/n{e}")
    sys.exit()

if not BASE_LOTES.empty:
    logging.info("Base de lotes para referência encontrada!")


# Função que checa se o lote do relatório existe na base de lotes:
def verificar_existencia_lote(lote: str) -> bool:
    if lote in BASE_LOTES['lote_id'].values:
        logging.info(f"Lote '{lote}' encontrado na base de dados.")
        return True
    else:
        logging.warning(f"Lote '{lote}' não encontrado.")
        return False


# Função que verifica se o lote existente está ativo:
def verificar_status_lote(lote: str):
    if verificar_existencia_lote(lote):
        # Buscamos pelo status
        resultado = BASE_LOTES.loc[BASE_LOTES['lote_id'] == lote, 'status_cadastro']
        status = resultado.item() 
        logging.info(f"O status do lote '{lote}' é: {status}")

        if status == 'Ativo':
            return True
        else:
            return False
    return None