"""RN07 (Observação Obrigatória em Lote Reprovado)."""

import pandas as pd

STATUS_REPROVADO = {"reprovado", "nok"}

def lote_conforme_rn07(info_lote: dict) -> bool:
    status_bruto = info_lote.get("status")
    obs_bruta = info_lote.get("observacao")

    status = "" if pd.isna(status_bruto) else str(status_bruto).strip().lower()
    observacao = "" if pd.isna(obs_bruta) else str(obs_bruta).strip().lower()

    if status not in STATUS_REPROVADO:
        return True

    return bool(observacao)
