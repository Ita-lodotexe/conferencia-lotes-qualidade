"""Validação da RN07 - observação obrigatória em lote reprovado."""

STATUS_REPROVADO = {"reprovado", "nok"}


def lote_conforme_rn07(lote):
    """Verifica se um lote está em conformidade com a RN07.

    RN07: um lote com status REPROVADO (ou NOK) obrigatoriamente precisa
    ter o campo de observação preenchido. Se o lote estiver reprovado e a
    observação estiver vazia (ou contiver apenas espaços em branco), isso
    é uma divergência que o bot deve sinalizar.

    Lotes que não estejam reprovados (ex.: aprovados) sempre estão em
    conformidade com esta regra, independentemente do campo de observação.

    Args:
        lote: dicionário com pelo menos as chaves "status" e "observacao".

    Returns:
        bool: True se o lote está em conformidade com a RN07, False caso
        contrário (reprovado sem observação preenchida).
    """
    status = str(lote.get("status", "")).strip().lower()
    observacao = str(lote.get("observacao", "") or "").strip()

    if status not in STATUS_REPROVADO:
        return True

    return bool(observacao)
