"""Testes do motor de classificação RN01-RN12 (Aula 22).

Cobre cada regra isoladamente e a ordem de precedência entre elas
(cada registro cai em exatamente uma das 4 categorias). Usa dados
sintéticos — não depende do dataset real de 10 dias, que não é
distribuído no repositório (ver tests/e2e/test_contra_gabarito.py para
a validação de ponta a ponta contra o gabarito real, quando disponível).

A fixture `base_referencia` vem de tests/conftest.py.
"""

import pytest

from src.aula22_classificacao import RegistroValidado, classificar_lotes, classificar_registro

pytestmark = pytest.mark.unit


def _registro(**overrides):
    base = {
        "lote_id": "L001",
        "produto": "TV55",
        "linha": "L1",
        "turno": "A",
        "status": "APROVADO",
        "responsavel": "Ana",
        "data": "15/06/2026",
        "observacao": None,
        "_dia": "Insp_15_06_2026",
        "_data_referencia": "15/06/2026",
        "_linha_planilha": 4,
    }
    base.update(overrides)
    return base


def test_registro_conforme_e_valido(base_referencia):
    resultado = classificar_registro(_registro(), ocorrencia_no_dia=1, base_referencia=base_referencia)
    assert resultado.classificacao == "Válido"
    assert resultado.regra == "RN08"


@pytest.mark.parametrize("campo", ["lote_id", "produto", "linha", "status", "responsavel"])
def test_campo_obrigatorio_vazio_e_erro_de_entrada(base_referencia, campo):
    resultado = classificar_registro(
        _registro(**{campo: ""}), ocorrencia_no_dia=1, base_referencia=base_referencia
    )
    assert resultado.classificacao == "Erro de Entrada"
    assert resultado.regra == "RN01-RN04"


def test_turno_vazio_nao_e_campo_obrigatorio(base_referencia):
    """turno não está em CAMPOS_OBRIGATORIOS_LOTE — vazio não deve gerar Erro de Entrada."""
    resultado = classificar_registro(_registro(turno=""), ocorrencia_no_dia=1, base_referencia=base_referencia)
    assert resultado.classificacao != "Erro de Entrada"


@pytest.mark.parametrize("data_invalida", ["", None, "31/02/2026", "2026-06-15", "15/06/26"])
def test_data_ausente_ou_formato_invalido_e_erro_de_entrada(base_referencia, data_invalida):
    resultado = classificar_registro(
        _registro(data=data_invalida), ocorrencia_no_dia=1, base_referencia=base_referencia
    )
    assert resultado.classificacao == "Erro de Entrada"
    assert resultado.regra == "RN12"


def test_lote_duplicado_no_dia_e_divergencia_a_partir_da_2a_ocorrencia(base_referencia):
    primeira = classificar_registro(_registro(), ocorrencia_no_dia=1, base_referencia=base_referencia)
    segunda = classificar_registro(_registro(), ocorrencia_no_dia=2, base_referencia=base_referencia)

    assert primeira.classificacao == "Válido"
    assert segunda.classificacao == "Divergência"
    assert segunda.regra == "RN11"


def test_lote_nao_cadastrado_e_divergencia(base_referencia):
    resultado = classificar_registro(
        _registro(lote_id="L999"), ocorrencia_no_dia=1, base_referencia=base_referencia
    )
    assert resultado.classificacao == "Divergência"
    assert resultado.regra == "RN05"


def test_lote_inativo_e_divergencia(base_referencia):
    resultado = classificar_registro(
        _registro(lote_id="L002"), ocorrencia_no_dia=1, base_referencia=base_referencia
    )
    assert resultado.classificacao == "Divergência"
    assert resultado.regra == "RN05"


def test_status_nao_reconhecivel_e_ambiguo(base_referencia):
    resultado = classificar_registro(
        _registro(status="EM AJUSTE"), ocorrencia_no_dia=1, base_referencia=base_referencia
    )
    assert resultado.classificacao == "Ambíguo"
    assert resultado.regra == "RN09"


def test_reprovado_sem_observacao_e_divergencia(base_referencia):
    resultado = classificar_registro(
        _registro(status="REPROVADO", observacao=""), ocorrencia_no_dia=1, base_referencia=base_referencia
    )
    assert resultado.classificacao == "Divergência"
    assert resultado.regra == "RN10"


def test_reprovado_com_observacao_e_valido(base_referencia):
    resultado = classificar_registro(
        _registro(status="REPROVADO", observacao="Defeito na tela"),
        ocorrencia_no_dia=1,
        base_referencia=base_referencia,
    )
    assert resultado.classificacao == "Válido"


def test_ok_normaliza_para_aprovado(base_referencia):
    resultado = classificar_registro(_registro(status="OK"), ocorrencia_no_dia=1, base_referencia=base_referencia)
    assert resultado.classificacao == "Válido"
    assert resultado.status_normalizado == "APROVADO"


def test_precedencia_erro_de_entrada_antes_de_divergencia(base_referencia):
    """lote_id vazio (RN01-04) tem prioridade sobre RN05/RN11, mesmo que o
    restante do registro também dispararia outras regras."""
    resultado = classificar_registro(
        _registro(lote_id="", status="EM AJUSTE"), ocorrencia_no_dia=2, base_referencia=base_referencia
    )
    assert resultado.classificacao == "Erro de Entrada"
    assert resultado.regra == "RN01-RN04"


def test_precedencia_rn05_antes_de_rn09(base_referencia):
    """Lote não cadastrado E com status ambíguo: RN05 decide, não RN09."""
    resultado = classificar_registro(
        _registro(lote_id="L999", status="EM AJUSTE"), ocorrencia_no_dia=1, base_referencia=base_referencia
    )
    assert resultado.classificacao == "Divergência"
    assert resultado.regra == "RN05"


def test_lote_id_vazio_nunca_conta_como_duplicidade(base_referencia):
    """Duas linhas com lote_id vazio no mesmo dia não devem gerar RN11
    (ambas já são Erro de Entrada pela RN01-04)."""
    registros_por_dia = {
        "Insp_15_06_2026": [
            _registro(lote_id=""),
            _registro(lote_id=""),
        ]
    }
    resultado = classificar_lotes(registros_por_dia, base_referencia)
    assert all(r.classificacao == "Erro de Entrada" for r in resultado)
    assert all(r.regra == "RN01-RN04" for r in resultado)


def test_duplicidade_nao_conta_entre_dias_diferentes(base_referencia):
    """RN11 é por dia — o mesmo lote_id em dois dias diferentes não é duplicidade."""
    registros_por_dia = {
        "Insp_15_06_2026": [_registro(_dia="Insp_15_06_2026", _data_referencia="15/06/2026")],
        "Insp_16_06_2026": [_registro(_dia="Insp_16_06_2026", _data_referencia="16/06/2026")],
    }
    resultado = classificar_lotes(registros_por_dia, base_referencia)
    assert len(resultado) == 2
    assert all(r.classificacao == "Válido" for r in resultado)


def test_classificar_lotes_preserva_ordem_e_retorna_registrovalidado(base_referencia):
    registros_por_dia = {"Insp_15_06_2026": [_registro(lote_id="L001"), _registro(lote_id="L004")]}
    resultado = classificar_lotes(registros_por_dia, base_referencia)
    assert len(resultado) == 2
    assert all(isinstance(r, RegistroValidado) for r in resultado)
    assert [r.lote_id for r in resultado] == ["L001", "L004"]


def test_to_dict_expoe_todas_as_chaves_do_registro(base_referencia):
    resultado = classificar_registro(_registro(), ocorrencia_no_dia=1, base_referencia=base_referencia)
    dados = resultado.to_dict()
    assert dados["classificacao"] == "Válido"
    assert dados["lote_id"] == "L001"
    assert set(dados.keys()) >= {
        "dia", "data_referencia", "linha_planilha", "lote_id", "produto",
        "linha", "turno", "status_original", "status_normalizado",
        "responsavel", "data_lote", "observacao", "ocorrencia_no_dia",
        "classificacao", "regra", "motivo",
    }
