# Issue #3 — Implementar RN04–RN05: status e normalização OK/NOK
# PDD: docs/pdd/ · seção 12 — Regras de negócio
# 
# from src.modules.normalizacao_status import normalizar_status, validar_status

import logging

STATUS_VALIDOS = {"APROVADO", "REPROVADO", "PENDENTE"}

MAPA_NORMALIZACAO = {
    "OK": "APROVADO",
    "NOK": "REPROVADO",
    
}


def normalizar_status(status):
    """
    RN05 — Normalização.

    SE status for OK, normaliza para APROVADO.
    SE status for NOK, normaliza para REPROVADO.
    Essa normalização deve ocorrer sempre antes da validação da RN04.

    Aceita variações de caixa e espaços nas pontas (' ok ', 'Ok', 'NOK')
    pois a coleta automática não garante formatação consistente.
    Não altera valores que não sejam OK/NOK — inclusive não tenta
    "adivinhar" abreviações como 'REPROV.' (isso é papel da RN06).

    Args:
        status: valor bruto da coluna 'status' da planilha.

    Returns:
        str | None: status normalizado (maiúsculo, sem espaços nas pontas),
        ou None se a entrada for None/vazia (campo vazio é tratado pela RN02,
        não aqui).
    """
    if status is None:
        logging.debug("RN05: Status recebido é None. Retornando None.")
        return None

    status_limpo = str(status).strip().upper()

    if status_limpo == "":
        logging.debug("RN05: Status resultou em string vazia após limpeza. Retornando None.")
        return None

    status_normalizado = MAPA_NORMALIZACAO.get(status_limpo, status_limpo)
    
    if status_normalizado != status_limpo:
        logging.info(f"RN05: Status normalizado de '{status_limpo}' para '{status_normalizado}'.")
    else:
        logging.debug(f"RN05: Status '{status_limpo}' não sofreu alterações no mapeamento.")

    return status_normalizado


def validar_status(status):
    """
    RN04 — Status permitido (aplicada sobre o valor já normalizado pela RN05).

    SE o status, após passar pela RN05, não for APROVADO, REPROVADO ou
    PENDENTE, ENTÃO o caso deve ser encaminhado para a RN06 (ambíguo),
    sem que o bot decida automaticamente sobre ele (ver CA10 do PDD).

    Args:
        status: valor bruto da coluna 'status' da planilha.

    Returns:
        dict com:
            - status_original (str | None): valor como veio na planilha
            - status_normalizado (str | None): resultado da RN05
            - valido (bool): True se está em STATUS_VALIDOS (RN04 satisfeita)
            - ambiguo (bool): True se deve ser encaminhado à RN06

    Exemplos (baseados na planilha inspecao_lotes_dia.xlsx):
        validar_status("OK")                -> normalizado 'APROVADO', valido=True
        validar_status("NOK")               -> normalizado 'REPROVADO', valido=True
        validar_status("PENDENTE")          -> valido=True
        validar_status("REPROV.")           -> valido=False, ambiguo=True  (RN06)
        validar_status("APROVADO PARCIAL")  -> valido=False, ambiguo=True  (RN06)
    """
    status_normalizado = normalizar_status(status)
    valido = status_normalizado in STATUS_VALIDOS

    if valido:
        logging.info(f"RN04: Status '{status_normalizado}' (original: '{status}') validado com sucesso.")
    else:
        logging.warning(
            f"RN04: Status '{status_normalizado}' (original: '{status}') não reconhecido. "
            "Classificado como ambíguo e encaminhado para RN06."
        )

    return {
        "status_original": status,
        "status_normalizado": status_normalizado,
        "valido": valido,
        "ambiguo": not valido,
    }