# Validação da RN07 - observação obrigatória em lote reprovado.
import pandas as pd
import logging 
STATUS_REPROVADO = {"reprovado", "nok"}


def lote_conforme_rn07(info_lote: dict) -> bool:
    """
    RN07 — Observação obrigatória para status REPROVADO.
    
    Pressupõe que o campo "status" já passou pela RN05 (Normalização),
    então espera encontrar "REPROVADO" e não variações como "NOK".
    
    Args:
        info_lote: dicionário com pelo menos as chaves "status" e "observacao".
        
    Returns:
        bool: True se conforme (ou não aplicável), False se violar a regra.
    """
    status_bruto = info_lote.get("status")
    obs_bruta = info_lote.get("observacao")
    
    # Tratamento seguro contra NaN e None
    status = "" if pd.isna(status_bruto) else str(status_bruto).strip().lower()
    observacao = "" if pd.isna(obs_bruta) else str(obs_bruta).strip().lower()
    
    if status not in STATUS_REPROVADO:
        return True
    
    conforme = bool(observacao)
    
    if not conforme:
        lote_id = info_lote.get("lote_id", "Desconhecido")
        logging.warning(f"RN07 Violarada: Lote {lote_id} está REPROVADO mas sem observação.")
        
    return conforme