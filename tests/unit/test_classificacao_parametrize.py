"""Parametrize com ≥5 cenários de classificar_registro — entregável 3 da Aula 23.

Cada cenário usa um ID descritivo para facilitar diagnóstico no relatório
do pytest: em vez de ver `FAILED test_classificacao[APROVADO-1-Válido-RN08]`
(valores como ID, longo e difícil de ler), o relatório mostra
`FAILED test_classificacao[lote_valido_aprovado]`.

Cobre pelo menos uma regra de cada classificação + o cenário de
precedência mais crítico (campo vazio + status ambíguo → Erro de
Entrada prevalece, não Ambíguo).
"""

import pytest

from src.aula22_classificacao import classificar_registro

pytestmark = pytest.mark.unit


def _registro(**overrides):
    """Registro base válido — cada cenário altera apenas o necessário."""
    base = {
        "lote_id": "L001",
        "produto": "TV55",
        "linha": "L1",
        "turno": "A",
        "status": "APROVADO",
        "responsavel": "Ana",
        "data": "15/06/2026",
        "observacao": "",
        "_dia": "Insp_15_06_2026",
        "_data_referencia": "15/06/2026",
        "_linha_planilha": 4,
    }
    base.update(overrides)
    return base


# -----------------------------------------------------------------------
# Cenários: (registro_overrides, ocorrencia_no_dia, classificacao, regra)
#
# O mínimo exigido é 5; incluímos 15 para cobrir todas as regras e os
# cenários de precedência mais importantes. Cada um tem um ID descritivo.
# -----------------------------------------------------------------------

CENARIOS = [
    # --- Válido (RN08) ---
    pytest.param(
        {}, 1, "Válido", "RN08",
        id="lote_valido_aprovado",
    ),
    pytest.param(
        {"status": "OK"}, 1, "Válido", "RN08",
        id="lote_valido_ok_normalizado",
    ),
    pytest.param(
        {"status": "REPROVADO", "observacao": "Defeito na tela"}, 1, "Válido", "RN08",
        id="lote_reprovado_com_observacao_valido",
    ),

    # --- Erro de Entrada (RN01-RN04, RN12) ---
    pytest.param(
        {"lote_id": ""}, 1, "Erro de Entrada", "RN01-RN04",
        id="erro_lote_id_vazio",
    ),
    pytest.param(
        {"produto": ""}, 1, "Erro de Entrada", "RN01-RN04",
        id="erro_produto_vazio",
    ),
    pytest.param(
        {"data": "2026-06-15"}, 1, "Erro de Entrada", "RN12",
        id="erro_data_formato_iso",
    ),
    pytest.param(
        {"data": ""}, 1, "Erro de Entrada", "RN12",
        id="erro_data_ausente",
    ),

    # --- Divergência (RN05, RN10, RN11) ---
    pytest.param(
        {"lote_id": "L999"}, 1, "Divergência", "RN05",
        id="divergencia_lote_nao_cadastrado",
    ),
    pytest.param(
        {"lote_id": "L002"}, 1, "Divergência", "RN05",
        id="divergencia_lote_inativo",
    ),
    pytest.param(
        {"status": "REPROVADO", "observacao": ""}, 1, "Divergência", "RN10",
        id="divergencia_reprovado_sem_observacao",
    ),
    pytest.param(
        {}, 2, "Divergência", "RN11",
        id="divergencia_lote_duplicado_no_dia",
    ),

    # --- Ambíguo (RN09) ---
    pytest.param(
        {"status": "EM AJUSTE"}, 1, "Ambíguo", "RN09",
        id="ambiguo_status_nao_reconhecido",
    ),
    pytest.param(
        {"status": "APROVADO PARCIAL"}, 1, "Ambíguo", "RN09",
        id="ambiguo_aprovado_parcial",
    ),

    # --- Precedência ---
    pytest.param(
        {"lote_id": "", "status": "EM AJUSTE"}, 2, "Erro de Entrada", "RN01-RN04",
        id="precedencia_campo_vazio_sobre_ambiguo_e_duplicidade",
    ),
    pytest.param(
        {"lote_id": "L999", "status": "EM AJUSTE"}, 1, "Divergência", "RN05",
        id="precedencia_lote_inexistente_sobre_ambiguo",
    ),
]


@pytest.mark.parametrize(
    "overrides, ocorrencia_no_dia, classificacao_esperada, regra_esperada",
    CENARIOS,
)
def test_classificacao_por_regra(
    base_referencia,
    overrides,
    ocorrencia_no_dia,
    classificacao_esperada,
    regra_esperada,
):
    """Um único teste parametrizado para todos os cenários de classificação."""
    registro = _registro(**overrides)
    resultado = classificar_registro(registro, ocorrencia_no_dia, base_referencia)

    assert resultado.classificacao == classificacao_esperada, (
        f"classificacao={resultado.classificacao!r} != {classificacao_esperada!r} "
        f"(regra obtida: {resultado.regra}, motivo: {resultado.motivo})"
    )
    assert resultado.regra == regra_esperada, (
        f"regra={resultado.regra!r} != {regra_esperada!r} "
        f"(classificacao obtida: {resultado.classificacao})"
    )
