import os
import logging
import requests
from requests.exceptions import RequestException, Timeout

logger = logging.getLogger(__name__)

def classificar_observacao(observacao: str) -> dict:
    """
    Tenta classificar a observação via ML.
    Garante o retorno seguro de um fallback em caso de qualquer falha externa.
    """
    # 1. Feature Flag: Desliga o ML completamente sem alterar código
    ml_enabled = os.getenv("ML_ENABLED", "false").lower() == "true"
    
    if not ml_enabled:
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback", # Rastreabilidade exigida[cite: 2]
            "confianca_ml": 0.0
        }

    confianca_minima = float(os.getenv("ML_CONFIANCA_MINIMA", "0.75"))
    endpoint = os.getenv("ML_ENDPOINT", "http://localhost:8000/predict")
    
    try:
        # 2. Timeout curto: impede que lentidão no ML trave o loop principal do bot[cite: 2]
        response = requests.post(
            endpoint, 
            json={"observacao": observacao}, 
            timeout=3.0 
        )
        response.raise_for_status()
        
        resultado = response.json()
        confianca = float(resultado.get("confianca", 0.0))
        
        # 3. Validação de confiança: descarta respostas abaixo do limiar configurável[cite: 2]
        if confianca < confianca_minima:
            logger.warning(f"ML Fallback: Confiança ({confianca}) abaixo do limiar ({confianca_minima})")
            return {
                "causa_provavel": "nao_classificado",
                "origem_decisao": "fallback",
                "confianca_ml": confianca
            }
            
        return {
            "causa_provavel": resultado.get("causa", "nao_classificado"),
            "origem_decisao": "ml",
            "confianca_ml": confianca
        }
        
    except Timeout:
        # Fallback 1: ML lento[cite: 2]
        logger.warning("ML Fallback: Timeout ao contactar o serviço de classificação.")
    except RequestException as e:
        # Fallback 2: Serviço de ML fora do ar ou rede indisponível[cite: 2]
        logger.warning(f"ML Fallback: Serviço indisponível. Erro: {e}")
    except Exception as e:
        # Fallback 3: Proteção absoluta para que nenhuma exceção vaze[cite: 2]
        logger.error(f"ML Fallback: Erro inesperado no processamento do modelo. Erro: {e}")
        
    # Retorno padrão de fallback caso caia em qualquer exceção acima
    return {
        "causa_provavel": "nao_classificado",
        "origem_decisao": "fallback",
        "confianca_ml": 0.0
    }