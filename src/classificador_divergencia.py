"""Classificador de divergências via Machine Learning (Estudo de Caso S10-B).

Implementação defensiva blindada com captura global de exceções para garantir
que qualquer falha de contrato/API, rede, decode ou status HTTP retorne fallback
sem interromper a execução do pipeline no BotCity Maestro.
"""

from __future__ import annotations

import logging
import os
import requests

logger = logging.getLogger("classificador.ml")

FALLBACK_PADRAO = {
    "causa_provavel": "nao_classificado",
    "origem_decisao": "fallback",
    "confianca_ml": 0.0,
    "motivo_fallback": "padrao",
}


def classificar_divergencia(observacao: str) -> dict:
    """Classifica uma observação de divergência via endpoint de Machine Learning com blindagem absoluta.

    Regras defensivas (Auditoria e Resiliência S10-B):
    1. Respeita a flag ML_ENABLED. Se falso, retorna fallback imediato.
    2. Requests com timeout de 3.0s para evitar retenção de threads.
    3. Bloco except Exception global absoluto engolindo qualquer falha de contrato/API,
       decode de JSON, status HTTP 400, 422, 500 ou rede.
    4. Valida confiança contra ML_CONFIANCA_MINIMA e descarta predições fracas.

    Args:
        observacao: texto da observação a ser classificada.

    Returns:
        dict com causa_provavel, origem_decisao, confianca_ml e motivo_fallback.
    """
    # 1. Feature flag: Desativação segura
    ml_enabled = os.getenv("ML_ENABLED", "false").strip().lower() == "true"
    if not ml_enabled:
        logger.info("ML Fallback: Módulo de Machine Learning desabilitado via configuração (ML_ENABLED=false).")
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "ml_desabilitado",
        }

    # 2. Resolução de endpoint e limiar
    endpoint = (os.getenv("ML_ENDPOINT") or "http://localhost:8000/predict").strip().rstrip("/")
    if not endpoint.endswith("/predict"):
        endpoint = f"{endpoint}/predict"

    try:
        confianca_minima = float(os.getenv("ML_CONFIANCA_MINIMA", "0.75"))
    except ValueError:
        confianca_minima = 0.75

    payload = {"observacao": observacao or ""}

    # 3. Blindagem Absoluta: Try/Except Global engolindo qualquer erro de contrato/API
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
                f"ML Fallback: Baixa confiança detectada no modelo ({confianca:.2f} < {confianca_minima:.2f}). "
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

    except Exception as e:
        logger.warning(
            f"ML Fallback: Falha de contrato/API ou erro de comunicação com modelo ({type(e).__name__}: {e}). "
            "Forçando retorno seguro de fallback."
        )
        return {
            "causa_provavel": "nao_classificado",
            "origem_decisao": "fallback",
            "confianca_ml": 0.0,
            "motivo_fallback": "falha_contrato_api",
        }


# Alias
classificar_observacao = classificar_divergencia
