"""Avaliador de regras de negócio para o Bot B Performer."""

from __future__ import annotations
import pandas as pd

from src.modules.validacao import valida_campos_obrigatorios
from src.modules.verificacao_lotes import verificar_existencia_lote, verificar_status_lote
from src.modules.normalizacao_status import validar_status
from src.modules.observacao import lote_conforme_rn07


def avaliar_lote(lote: dict, base_referencia: pd.DataFrame) -> list[dict]:
    divergencias: list[dict] = []

    # RN02
    df_lote = pd.DataFrame([lote])
    ocorrencias_rn02 = valida_campos_obrigatorios(df_lote)
    for ocorrencia in ocorrencias_rn02:
        divergencias.append({
            "regra": "RN02",
            "campo": ocorrencia["campo"],
            "descricao": f"Campo obrigatório '{ocorrencia['campo']}' vazio.",
        })

    # RN03
    lote_id = lote.get("lote_id")
    if lote_id is not None and not pd.isna(lote_id) and str(lote_id).strip() != "":
        lote_id_str = str(lote_id).strip()
        existe = verificar_existencia_lote(base_referencia, lote_id_str)
        if not existe:
            divergencias.append({
                "regra": "RN03",
                "campo": "lote_id",
                "descricao": f"Lote '{lote_id_str}' não encontrado na base de referência.",
            })
        else:
            ativo = verificar_status_lote(base_referencia, lote_id_str)
            if ativo is False:
                divergencias.append({
                    "regra": "RN03",
                    "campo": "lote_id",
                    "descricao": f"Lote '{lote_id_str}' está inativo na base de referência.",
                })

    # RN04 / RN05 / RN06
    resultado_status = validar_status(lote.get("status"))
    if resultado_status["ambiguo"]:
        divergencias.append({
            "regra": "RN06",
            "campo": "status",
            "descricao": f"Status '{resultado_status['status_original']}' é ambíguo e requer revisão manual.",
        })

    # RN07
    observacao = lote.get("observacao")
    lote_normalizado = {
        "lote_id": lote_id,
        "status": resultado_status["status_normalizado"],
        "observacao": None if pd.isna(observacao) else observacao,
    }
    if not lote_conforme_rn07(lote_normalizado):
        divergencias.append({
            "regra": "RN07",
            "campo": "observacao",
            "descricao": "Lote reprovado sem observação preenchida.",
        })

    return divergencias
