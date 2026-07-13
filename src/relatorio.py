# Arquivo de geração de relatório, testando a implementação de todas as linhas do
# relatório aplicando as funções dos módulos para validar as regras
# de negócio - RN01 ao RN07.

import pandas as pd
import logging

console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('logs/relatorio.log', encoding="utf-8", mode='w')
logging.basicConfig(
    handlers=[console_handler, file_handler],
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S',
    format='%(asctime)s  | %(levelname)s | %(funcName)s | %(message)s',
)


# Funções para validar RN01 e RN02
from modules.validacao import valida_estrutura, valida_campos_obrigatorios

# Função para validar RN03
from modules.verificacao_lotes import verificar_status_lote

# Funções para validar RN04 e RN05
from modules.normalizacao_status import normalizar_status, validar_status

# Função para validar RN06
from modules.observacao import lote_conforme_rn07


def gerar_relatorio(relatorio: pd.DataFrame):
    logging.info("Iniciando geração do relatório ...")

    # Início da validação de estrutura: RN01 e RN02
    logging.info("=======================================================================") 
    logging.info("                       Validando RN01 e RN02 ...")
    logging.info("=======================================================================") 
    campos_faltantes = valida_estrutura(relatorio)
    if len(campos_faltantes) > 0:
        logging.info("Existem campos faltantes ou não formatados no relatório, encerrando sistema.")
        logging.info(f"CAMPOS FALTANDO:\n{campos_faltantes}")
        return
    
    campos_obrigatorios_vazios = valida_campos_obrigatorios(relatorio)

    if len(campos_obrigatorios_vazios) > 0:
        logging.info(f"Existem campos vazios nas seguintes linhas:\n{campos_obrigatorios_vazios}")
    else:
        logging.info(f"Sem campos vazios nesse relatório")
    logging.info("=======================================================================") 
    logging.info("                    Fim da validação de RN01 e RN02.")
    logging.info("=======================================================================") 


    # Início da validação de lotes: RN03
    logging.info("=======================================================================") 
    logging.info("                          Validando RN03 ...") 
    logging.info("=======================================================================") 
    lotes_incorretos = []
    lotes_relatorio = relatorio['lote_id'].dropna()
    for lote in lotes_relatorio:
        if verificar_status_lote(lote):
            pass
        else:
            lotes_incorretos.append(lote)
    logging.info("=======================================================================") 
    logging.info("                      Fim da validação de RN03.")
    logging.info("=======================================================================") 


    # Início da validação de lotes: RN04 e RN05
    logging.info("=======================================================================")
    logging.info("                        Validando RN04 e RN05 ...") 
    logging.info("=======================================================================")
    status_relatorio = relatorio['status']
    for status in status_relatorio:
        validar_status(status)
    logging.info("=======================================================================") 
    logging.info("                   Fim da validação das RN04 e RN05.")
    logging.info("=======================================================================") 

if __name__ == '__main__':
    df = pd.read_csv('data/processed/dados_relatorio.csv')    
    gerar_relatorio(df)