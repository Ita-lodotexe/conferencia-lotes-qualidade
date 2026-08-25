"""Classificador de divergências via Machine Learning (Bot B Performer - Estudo de Caso S10-B).

Implementação defensiva blindada com captura hierárquica de exceções para
garantir que qualquer falha de contrato/API, rede, decode ou status HTTP
retorne fallback sem interromper a execução do pipeline no BotCity Maestro.

Motivos de fallback rastreáveis:
- "ml_desabilitado"   : ML_ENABLED=false
- "timeout"           : resposta do serviço ultrapassou 3.0s
- "servico_offline"   : falha de conexão (ConnectionError)
- "baixa_confianca"   : predição abaixo de ML_CONFIANCA_MINIMA
- "falha_contrato_api": erro de contrato HTTP 4xx/5xx ou decode
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
    """Classifica uma observação de divergência com blindagem absoluta e retorno seguro de fallback."""
    ml_enabled = os.getenv("ML_ENABLED", "false").strip().lower() == "true"
    if not ml_enabled:
        logger.info("ML Fallback: Módulo de Machine Learning desabilitado via configuração (ML_ENABLED=false).")
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "ml_desabilitado",
        }

    endpoint = (os.getenv("ML_ENDPOINT") or "http://localhost:8000/predict").strip().rstrip("/")
    if not endpoint.endswith("/predict"):
        endpoint = f"{endpoint}/predict"

    try:
        confianca_minima = float(os.getenv("ML_CONFIANCA_MINIMA", "0.75"))
    except ValueError:
        confianca_minima = 0.75

    payload = {"observacao": observacao or ""}

    try:
        response = requests.post(endpoint, json=payload, timeout=3.0)
        response.raise_for_status()

        dados = response.json()
        confianca = float(dados.get("confianca", dados.get("probabilidade", 0.0)))
        causa = dados.get("causa", dados.get("classe_predita", "nao_classificado"))

        if confianca < confianca_minima:
            logger.warning(
                f"ML Fallback [baixa_confianca]: Baixa confiança detectada no modelo ({confianca:.2f} < {confianca_minima:.2f}). "
                f"Predição '{causa}' descartada e direcionada para revisão."
            )
            return {
                "causa_provavel": "nao_classificado",
                "origem_decisao": "fallback",
                "confianca_ml": confianca,
                "motivo_fallback": "baixa_confianca",
            }

        logger.info(f"ML Sucesso: Observação classificada como '{causa}' com confiança de {confianca:.2f}.")
        return {
            "causa_provavel": str(causa),
            "origem_decisao": "ml",
            "confianca_ml": confianca,
            "motivo_fallback": None,
        }

    except RequestsTimeout as e:
        logger.warning(f"ML Fallback [timeout]: endpoint excedeu 3.0s ({e}). Retornando fallback seguro.")
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "timeout",
        }

    except RequestsConnectionError as e:
        logger.warning(f"ML Fallback [servico_offline]: não foi possível conectar ao endpoint ({type(e).__name__}: {e}).")
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "servico_offline",
        }

    except Exception as e:
        logger.warning(
            f"ML Fallback [falha_contrato_api]: Falha de contrato/API ({type(e).__name__}: {e}). "
            "Forçando retorno seguro de fallback."
        )
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "falha_contrato_api",
        }


classificar_observacao = classificar_divergencia
