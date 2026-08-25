"""Motor de avaliação de regras de negócio para itens individuais de lote (RN01 a RN07).

Conecta diretamente os módulos de validação legados:
- src.modules.validacao (RN01 e RN02)
- src.modules.verificacao_lotes (RN03)
- src.modules.normalizacao_status (RN04, RN05, RN06)
- src.modules.observacao (RN07)
"""

from __future__ import annotations

import pandas as pd
from src.modules.validacao import valida_campos_obrigatorios, valida_estrutura, COLUNAS_ESPERADAS
from src.modules.verificacao_lotes import (
    verificar_existencia_lote,
    verificar_status_lote,
    carregar_base_referencia,
)
from src.modules.normalizacao_status import normalizar_status, validar_status
from src.modules.observacao import lote_conforme_rn07


def avaliar_lote(lote: dict, base_referencia: pd.DataFrame) -> list[dict]:
    """Avalia um lote individual aplicando as regras de negócio em cascata.

    Args:
        lote: dicionário com as colunas do lote.
        base_referencia: DataFrame com a base de lotes cadastrados.

    Returns:
        Lista de divergências encontradas. Lista vazia indica lote 100% conforme.
    """
    divergencias: list[dict] = []

    # RN02 — Campos obrigatórios
    df_lote = pd.DataFrame([lote])
    ocorrencias_rn02 = valida_campos_obrigatorios(df_lote)
    for ocorrencia in ocorrencias_rn02:
        divergencias.append({
            "regra": "RN02",
            "campo": ocorrencia["campo"],
            "descricao": f"Campo obrigatório '{ocorrencia['campo']}' vazio.",
        })

    # RN03 — Existência e status na base de referência
    lote_id = lote.get("lote_id")
    if lote_id is None or pd.isna(lote_id) or str(lote_id).strip() == "":
        pass  # Tratado pela RN02
    else:
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

    # RN04 / RN05 / RN06 — Validação e normalização de status
    resultado_status = validar_status(lote.get("status"))
    if resultado_status["ambiguo"]:
        divergencias.append({
            "regra": "RN06",
            "campo": "status",
            "descricao": f"Status '{resultado_status['status_original']}' é ambíguo e requer revisão manual.",
        })

    # RN07 — Observação obrigatória para REPROVADO
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
