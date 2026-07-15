# Arquivo de geração de relatório, testando a implementação de todas as linhas do
# relatório aplicando as funções dos módulos para validar as regras
# de negócio - RN01 ao RN07.

import pandas as pd
import logging
from datetime import datetime

console_handler = logging.StreamHandler()
file_handler = logging.FileHandler('logs/relatorio.log', encoding="utf-8", mode='w')
logging.basicConfig(
    handlers=[console_handler, file_handler],
    level=logging.INFO,
    datefmt='%d-%m-%Y %H:%M:%S',
    format='%(asctime)s  | %(levelname)s | %(funcName)s | %(message)s',
)


# Funções para validar RN01 e RN02
from modules.validacao import valida_estrutura, valida_campos_obrigatorios

# Função para validar RN03
from modules.verificacao_lotes import verificar_status_lote

# Funções para validar RN04 e RN05
from modules.normalizacao_status import validar_status

# Função para validar RN07
from modules.observacao import lote_conforme_rn07


def encontrar_divergencias(relatorio: pd.DataFrame):
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
    
    rn02 = valida_campos_obrigatorios(relatorio)

    if len(rn02) > 0:
        logging.info(f"Existem campos vazios nas seguintes linhas:\n{rn02}")
    else:
        logging.info(f"Sem campos vazios nesse relatório")
    logging.info("=======================================================================") 
    logging.info("                    Fim da validação de RN01 e RN02.")
    logging.info("=======================================================================") 

    # Transformando em dicionario para tratamento em cada regra
    dicionario_relatorio = relatorio.to_dict('records')

    rn03 = []
    rn06 = []
    rn07 = []
    for index, lote in enumerate(dicionario_relatorio):
        logging.info("=======================================================================") 
        logging.info(f"                Validando regras para {lote['lote_id']}") 
        logging.info("=======================================================================") 

        # Início da validação de lotes: RN03
        if not verificar_status_lote(lote['lote_id']):
            rn03.append(lote)

        # Início da validação de lotes: RN04 e RN05
        status_validados = validar_status(lote['status'])
        print(status_validados)
        if not status_validados['valido']:
            rn06.append(lote)

        # Início da validação de observação: RN07
        info_lote = {'lote_id':lote['lote_id'], 'status':lote['status'], 'observacao':lote['observacao']}
        logging.info(f'INFO DO LOTE:{info_lote}')
        if not lote_conforme_rn07(info_lote):
            rn07.append(lote)
        logging.info("=======================================================================") 
        logging.info(f"                Fim da validação para {lote['lote_id']}")
        logging.info("=======================================================================") 
        logging.info(f'LOTES VALIDADOS: {index+1}')

    logging.warning(f'FALHANDO NA RN02:\n{rn02}')
    logging.warning(f'FALHANDO NA RN03:\n{rn03}')
    logging.warning(f'FALHANDO NA RN06:\n{rn06}')
    logging.warning(f'FALHANDO NA RN07:\n{rn07}')

    # Chama a função de consolidação
    gerar_relatorio_excel(
        df_original=relatorio, 
        rn02=rn02, 
        rn03=rn03, 
        rn06=rn06, 
        rn07=rn07, 
        caminho_saida=f"data/processed/{datetime.now().strftime('%d-%m-%Y')}-relatorio_divergencias.xlsx"
    )


def gerar_relatorio_excel(df_original: pd.DataFrame, rn02: list, rn03: list, rn06: list, rn07: list, caminho_saida: str):
    """
    Consolida as divergências e gera um Excel apenas com os lotes problemáticos.
    """
    logging.info("Iniciando a consolidação do relatório Excel...")
    
    df_relatorio = df_original.copy()
    df_relatorio['Motivo_Divergencia'] = ""
    
    # Consolidação da RN02 (Campos vazios)
    for erro in rn02:
        idx_pandas = erro.get('linha')
        campo = erro.get('campo')
        
        if idx_pandas in df_relatorio.index:
            df_relatorio.loc[idx_pandas, 'Motivo_Divergencia'] += f"RN02 (Campo '{campo}' vazio); "

    # Consolidação das demais RNs (Usando lote_id)
    ids_rn03 = [lote.get('lote_id') for lote in rn03 if pd.notna(lote.get('lote_id'))]
    ids_rn06 = [lote.get('lote_id') for lote in rn06 if pd.notna(lote.get('lote_id'))]
    ids_rn07 = [lote.get('lote_id') for lote in rn07 if pd.notna(lote.get('lote_id'))]

    if ids_rn03:
        df_relatorio.loc[df_relatorio['lote_id'].isin(ids_rn03), 'Motivo_Divergencia'] += "RN03 (Lote inexistente); "
    
    if ids_rn06:
        df_relatorio.loc[df_relatorio['lote_id'].isin(ids_rn06), 'Motivo_Divergencia'] += "RN06 (Status ambíguo); "
        
    if ids_rn07:
        df_relatorio.loc[df_relatorio['lote_id'].isin(ids_rn07), 'Motivo_Divergencia'] += "RN07 (Reprovado sem observação); "

    # Limpeza final
    df_relatorio['Motivo_Divergencia'] = df_relatorio['Motivo_Divergencia'].str.strip("; ")

    # Filtro de Ocorrências
    df_final = df_relatorio[df_relatorio['Motivo_Divergencia'] != ""]

    # Exportação
    if not df_final.empty:
        try:
            colunas = ['lote_id', 'Motivo_Divergencia'] + [col for col in df_final.columns if col not in ['lote_id', 'Motivo_Divergencia']]
            df_final = df_final[colunas]
            
            df_final.to_excel(caminho_saida, index=False)
            logging.info(f"Relatório exportado com sucesso para '{caminho_saida}'. ({len(df_final)} divergências encontradas).")
        except Exception as e:
            logging.error(f"Erro ao salvar arquivo Excel: {e}")
    else:
        logging.info("Nenhuma divergência real encontrada. Excel não gerado.")

    return df_final







if __name__ == '__main__':
    df = pd.read_csv('data/processed/dados_relatorio.csv')    
    encontrar_divergencias(df)