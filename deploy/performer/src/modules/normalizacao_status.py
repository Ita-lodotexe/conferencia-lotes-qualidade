"""RN04 e RN05 (Status Válidos e Normalização)."""

import logging

STATUS_VALIDOS = {"APROVADO", "REPROVADO", "PENDENTE"}
MAPA_NORMALIZACAO = {"OK": "APROVADO", "NOK": "REPROVADO"}

def normalizar_status(status):
    if status is None:
        return None
    status_limpo = str(status).strip().upper()
    if status_limpo == "":
        return None
    return MAPA_NORMALIZACAO.get(status_limpo, status_limpo)


def validar_status(status):
    status_normalizado = normalizar_status(status)
    valido = status_normalizado in STATUS_VALIDOS
    return {
        "status_original": status,
        "status_normalizado": status_normalizado,
        "valido": valido,
        "ambiguo": not valido,
    }
