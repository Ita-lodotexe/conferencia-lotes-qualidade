"""Classificador de divergências via Machine Learning (Estudo de Caso S10-B).

Implementação defensiva blindada com captura hierárquica de exceções para
garantir que qualquer falha de contrato/API, rede, decode ou status HTTP
retorne fallback sem interromper a execução do pipeline no BotCity Maestro.

Motivos de fallback rastreáveis (item 3.4 do formulário de revisão):
- "ml_desabilitado"   : ML_ENABLED=false
- "timeout"           : resposta do serviço ultrapassou 3.0s
- "servico_offline"   : falha de conexão (ConnectionError) — serviço fora do ar
- "baixa_confianca"   : predição abaixo de ML_CONFIANCA_MINIMA
- "falha_contrato_api": qualquer outro erro (HTTP 400/422/500, JSON malformado, etc.)
"""

from __future__ import annotations

import logging
import os

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import Timeout as RequestsTimeout

logger = logging.getLogger("classificador.ml")

FALLBACK_PADRAO = {
    "causa_provavel": "nao_classificado",
    "origem_decisao": "fallback",
    "confianca_ml": 0.0,
    "motivo_fallback": "padrao",
}


def classificar_divergencia(observacao: str) -> dict:
    """Classifica uma observação de divergência via endpoint de Machine Learning.

    Regras defensivas (S10-B §3.2 e §3.3):
    1. Respeita a flag ML_ENABLED. Se falso, retorna fallback imediato.
    2. Requests com timeout de 3.0s para evitar retenção de threads.
    3. Captura hierárquica de exceções:
       - Timeout           → motivo_fallback: "timeout"
       - ConnectionError   → motivo_fallback: "servico_offline"
       - Exception genérica → motivo_fallback: "falha_contrato_api"
    4. Valida confiança contra ML_CONFIANCA_MINIMA e descarta predições fracas.
    5. Nunca propaga exceção ao bot — sempre retorna dict seguro.

    Args:
        observacao: texto da observação a ser classificada.

    Returns:
        dict com causa_provavel, origem_decisao, confianca_ml e motivo_fallback.
    """
    # 1. Feature flag: Desativação segura
    ml_enabled = os.getenv("ML_ENABLED", "false").strip().lower() == "true"
    if not ml_enabled:
        logger.info(
            "ML Fallback: Módulo desabilitado via ML_ENABLED=false. "
            "Retornando fallback imediato sem chamada de rede."
        )
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "ml_desabilitado",
        }

    # 2. Resolução de endpoint e limiar de confiança
    endpoint = (os.getenv("ML_ENDPOINT") or "http://localhost:8000/predict").strip().rstrip("/")
    if not endpoint.endswith("/predict"):
        endpoint = f"{endpoint}/predict"

    try:
        confianca_minima = float(os.getenv("ML_CONFIANCA_MINIMA", "0.75"))
    except ValueError:
        confianca_minima = 0.75

    payload = {"observacao": observacao or ""}

    # 3. Chamada HTTP com captura hierárquica de exceções
    try:
        response = requests.post(
            endpoint,
            json=payload,
            timeout=3.0,
        )
        response.raise_for_status()

        dados = response.json()
        confianca = float(dados.get("confianca", dados.get("probabilidade", 0.0)))
        causa = dados.get("causa", dados.get("classe_predita", "nao_classificado"))

        # 4. Checagem de limiar de confiança
        if confianca < confianca_minima:
            logger.warning(
                f"ML Fallback [baixa_confianca]: confiança {confianca:.2f} abaixo do limiar "
                f"{confianca_minima:.2f}. Predição '{causa}' descartada."
            )
            return {
                "causa_provavel": "nao_classificado",
                "origem_decisao": "fallback",
                "confianca_ml": confianca,
                "motivo_fallback": "baixa_confianca",
            }

        logger.info(
            f"ML Sucesso: observação classificada como '{causa}' "
            f"com confiança {confianca:.2f}."
        )
        return {
            "causa_provavel": str(causa),
            "origem_decisao": "ml",
            "confianca_ml": confianca,
            "motivo_fallback": None,
        }

    except RequestsTimeout as e:
        # Serviço respondeu além do timeout de 3.0s
        logger.warning(
            f"ML Fallback [timeout]: endpoint excedeu 3.0s ({e}). "
            "Bot não fica bloqueado — retornando fallback seguro."
        )
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "timeout",
        }

    except RequestsConnectionError as e:
        # Serviço completamente fora do ar — conexão recusada ou host inacessível
        logger.warning(
            f"ML Fallback [servico_offline]: não foi possível conectar ao endpoint "
            f"({type(e).__name__}: {e}). Retornando fallback seguro."
        )
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "servico_offline",
        }

    except Exception as e:
        # Falha de contrato da API: HTTP 400/422/500, JSON malformado, etc.
        logger.warning(
            f"ML Fallback [falha_contrato_api]: erro de contrato/API "
            f"({type(e).__name__}: {e}). Forçando retorno seguro."
        )
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "falha_contrato_api",
        }


# Alias para compatibilidade com código legado
classificar_observacao = classificar_divergencia
