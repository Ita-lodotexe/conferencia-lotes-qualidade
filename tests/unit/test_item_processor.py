"""Testes de src/item_processor.py — mapeamento de status ambíguo para o
modelo de ML e fallback quando a API está fora do ar. ml_client é sempre
um MagicMock aqui (comportamento de MLClient já é coberto por
tests/unit/test_ml_client.py)."""
from unittest.mock import MagicMock

import pytest

from src.aula22_classificacao import RegistroValidado
from src.item_processor import processar_item_ambiguo, processar_registros_ambiguos

pytestmark = pytest.mark.unit


def _registro(
    classificacao: str = "Ambíguo",
    status_normalizado: str = "EM AJUSTE",
    turno: str = "A",
    observacao: str = "",
    lote_id: str = "L001",
    regra: str = "RN09",
) -> RegistroValidado:
    return RegistroValidado(
        dia="Insp_15_06_2026",
        data_referencia="15/06/2026",
        linha_planilha=4,
        lote_id=lote_id,
        produto="TV55",
        linha="L1",
        turno=turno,
        status_original=status_normalizado,
        status_normalizado=status_normalizado,
        responsavel="Ana",
        data_lote="15/06/2026",
        observacao=observacao,
        ocorrencia_no_dia=1,
        classificacao=classificacao,
        regra=regra,
        motivo="motivo de teste",
    )


PREDICAO_ML = {
    "classe_predita": "revisar",
    "probabilidade": 0.7,
    "decisao": "revisar",
    "latencia_ms": 12.3,
}


def test_status_mapeavel_entra_no_ml_com_sucesso():
    registro = _registro(status_normalizado="EM AJUSTE", turno="A", observacao="ajuste solicitado")
    ml_client = MagicMock()
    ml_client.classificar.return_value = PREDICAO_ML

    resultado = processar_item_ambiguo(registro, ml_client)

    assert resultado["entrou_no_ml"] is True
    assert resultado["classe_ml"] == "revisar"
    assert resultado["probabilidade_ml"] == 0.7
    assert resultado["decisao_ml"] == "revisar"
    assert resultado["latencia_ms"] == 12.3
    ml_client.classificar.assert_called_once_with(
        lote_id="L001", status="EM_AJUSTE", turno="A", tem_observacao=True,
    )


def test_cancelado_tambem_e_mapeavel():
    registro = _registro(status_normalizado="CANCELADO", turno="B", observacao="")
    ml_client = MagicMock()
    ml_client.classificar.return_value = PREDICAO_ML

    resultado = processar_item_ambiguo(registro, ml_client)

    assert resultado["entrou_no_ml"] is True
    ml_client.classificar.assert_called_once_with(
        lote_id="L001", status="CANCELADO", turno="B", tem_observacao=False,
    )


def test_status_nao_mapeavel_nao_chama_o_ml():
    registro = _registro(status_normalizado="REPROV.", turno="A")
    ml_client = MagicMock()

    resultado = processar_item_ambiguo(registro, ml_client)

    assert resultado["entrou_no_ml"] is False
    assert resultado["classe_ml"] is None
    assert resultado["motivo"] == "status não mapeado para o modelo"
    ml_client.classificar.assert_not_called()


def test_outros_status_ambiguos_tambem_nao_chamam_o_ml():
    for status_livre in ("APROVADO PARCIAL", "AGUARDANDO REINSPEÇÃO", "QUALQUER COISA"):
        registro = _registro(status_normalizado=status_livre, turno="A")
        ml_client = MagicMock()

        resultado = processar_item_ambiguo(registro, ml_client)

        assert resultado["entrou_no_ml"] is False, status_livre
        ml_client.classificar.assert_not_called()


def test_turno_invalido_nao_chama_o_ml():
    registro = _registro(status_normalizado="EM AJUSTE", turno="X")
    ml_client = MagicMock()

    resultado = processar_item_ambiguo(registro, ml_client)

    assert resultado["entrou_no_ml"] is False
    assert resultado["classe_ml"] is None
    ml_client.classificar.assert_not_called()


def test_ml_client_retorna_none_cai_no_fallback_revisao_ml_offline():
    registro = _registro(status_normalizado="CANCELADO", turno="B")
    ml_client = MagicMock()
    ml_client.classificar.return_value = None

    resultado = processar_item_ambiguo(registro, ml_client)

    assert resultado["entrou_no_ml"] is True
    assert resultado["classe_ml"] == "REVISAO_ML_OFFLINE"
    assert "indisponível" in resultado["motivo"]


def test_processar_registros_ambiguos_filtra_so_os_registros_ambiguos():
    ambiguo = _registro(classificacao="Ambíguo", status_normalizado="EM AJUSTE", lote_id="L001")
    valido = _registro(classificacao="Válido", status_normalizado="APROVADO", lote_id="L002", regra="RN08")
    divergencia = _registro(classificacao="Divergência", status_normalizado="REPROVADO", lote_id="L003", regra="RN05")

    ml_client = MagicMock()
    ml_client.classificar.return_value = PREDICAO_ML

    resultados = processar_registros_ambiguos([ambiguo, valido, divergencia], ml_client)

    assert len(resultados) == 1
    assert resultados[0]["lote_id"] == "L001"
    ml_client.classificar.assert_called_once()
