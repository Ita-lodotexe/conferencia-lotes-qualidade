"""Testes para `avaliar_lote()` de `src/relatorio.py` (Issue #21).

`avaliar_lote` é a orquestração de RN02-RN07 sobre um único lote,
compartilhada entre o relatório de divergências (Issue #5) e o Performer
(Issue #21) — os dois precisam avaliar um lote exatamente da mesma forma.
"""

import pandas as pd
import pytest

from src.relatorio import avaliar_lote


@pytest.fixture
def base_referencia():
    return pd.DataFrame(
        {
            "lote_id": ["LOTE001", "LOTE002", "LOTE003"],
            "status_cadastro": ["Ativo", "Inativo", "Ativo"],
        }
    )


def _lote(**overrides):
    base = {
        "lote_id": "LOTE001",
        "produto": "Monitor 24pol",
        "linha": "LT-03",
        "turno": "A",
        "status": "APROVADO",
        "responsavel": "Fulano",
        "data": "2026-07-10",
        "observacao": "",
    }
    base.update(overrides)
    return base


def _regras(divergencias):
    return [d["regra"] for d in divergencias]


def test_lote_conforme_nao_gera_divergencia(base_referencia):
    assert avaliar_lote(_lote(), base_referencia) == []


def test_lote_id_vazio_gera_divergencia_rn02(base_referencia):
    divergencias = avaliar_lote(_lote(lote_id=""), base_referencia)

    assert "RN02" in _regras(divergencias)
    rn02 = [d for d in divergencias if d["regra"] == "RN02"]
    assert rn02[0]["campo"] == "lote_id"


def test_lote_inexistente_na_base_gera_divergencia_rn03(base_referencia):
    divergencias = avaliar_lote(_lote(lote_id="LOTE999"), base_referencia)

    assert _regras(divergencias) == ["RN03"]
    assert "não encontrado" in divergencias[0]["descricao"]


def test_lote_inativo_na_base_gera_divergencia_rn03(base_referencia):
    divergencias = avaliar_lote(_lote(lote_id="LOTE002"), base_referencia)

    assert _regras(divergencias) == ["RN03"]
    assert "inativo" in divergencias[0]["descricao"]


def test_status_ambiguo_gera_divergencia_rn06(base_referencia):
    divergencias = avaliar_lote(_lote(status="REPROV."), base_referencia)

    assert "RN06" in _regras(divergencias)
    rn06 = [d for d in divergencias if d["regra"] == "RN06"]
    assert "REPROV." in rn06[0]["descricao"]


def test_reprovado_sem_observacao_gera_divergencia_rn07(base_referencia):
    divergencias = avaliar_lote(_lote(status="REPROVADO", observacao=""), base_referencia)

    assert _regras(divergencias) == ["RN07"]


def test_reprovado_com_observacao_nao_gera_divergencia_rn07(base_referencia):
    divergencias = avaliar_lote(
        _lote(status="REPROVADO", observacao="Costura irregular."), base_referencia
    )

    assert divergencias == []


def test_status_nok_normalizado_antes_da_rn07(base_referencia):
    """RN07 recebe o status já normalizado pela RN05: 'NOK' vira
    'REPROVADO', então a falta de observação tem de ser detectada."""
    divergencias = avaliar_lote(_lote(status="NOK", observacao=""), base_referencia)

    assert _regras(divergencias) == ["RN07"]


def test_lote_com_multiplos_problemas_gera_multiplas_divergencias(base_referencia):
    divergencias = avaliar_lote(
        _lote(lote_id="", turno="", status="REPROV.", observacao=""), base_referencia
    )

    regras = _regras(divergencias)
    assert regras.count("RN02") == 2  # lote_id e turno vazios
    assert "RN03" in regras  # lote_id vazio não existe na base
    assert "RN06" in regras  # 'REPROV.' é ambíguo
    assert len(divergencias) >= 4


def test_observacao_nan_de_csv_gera_divergencia_rn07(base_referencia):
    """`pd.read_csv` lê campo vazio como NaN; avaliar_lote precisa tratar
    isso como observação ausente, não como o texto 'nan'."""
    divergencias = avaliar_lote(
        _lote(status="REPROVADO", observacao=float("nan")), base_referencia
    )

    assert _regras(divergencias) == ["RN07"]
