"""Testes para `src/relatorio.py` (Issue #5 — relatório de divergências)."""

import pandas as pd
import pytest

import src.relatorio as relatorio_modulo
from src.relatorio import gerar_relatorio


@pytest.fixture(autouse=True)
def base_referencia(monkeypatch):
    """Substitui o carregamento da base de referência por um DataFrame
    controlado, sem depender do CSV real em disco."""
    df = pd.DataFrame(
        {
            "lote_id": ["LOTE001", "LOTE002", "LOTE003", "LOTE004"],
            "status_cadastro": ["Ativo", "Inativo", "Ativo", "Ativo"],
        }
    )
    monkeypatch.setattr(relatorio_modulo, "carregar_base_referencia", lambda caminho: df)
    return df


def _linha(**overrides):
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


def test_planilha_conforme_nao_gera_divergencias(base_referencia, tmp_path):
    df = pd.DataFrame([_linha(lote_id="LOTE001"), _linha(lote_id="LOTE003")])

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    assert resultado["divergencias"] == []
    assert resultado["resumo"]["total_lotes"] == 2
    assert resultado["resumo"]["lotes_com_divergencia"] == 0
    assert resultado["resumo"]["lotes_conformes"] == 2


def test_estrutura_invalida_gera_apenas_divergencia_rn01(tmp_path):
    df = pd.DataFrame([{"lote_id": "LOTE001", "status": "APROVADO"}])

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    assert len(resultado["divergencias"]) == 1
    assert resultado["divergencias"][0]["regra"] == "RN01"
    assert resultado["resumo"]["estrutura_valida"] is False


def test_campo_obrigatorio_vazio_gera_divergencia_rn02(base_referencia, tmp_path):
    df = pd.DataFrame([_linha(lote_id="LOTE001", produto="")])

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    regras = [d["regra"] for d in resultado["divergencias"]]
    assert "RN02" in regras


def test_lote_inexistente_gera_divergencia_rn03(base_referencia, tmp_path):
    df = pd.DataFrame([_linha(lote_id="LOTE999")])

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    assert resultado["divergencias"][0]["regra"] == "RN03"
    assert "não encontrado" in resultado["divergencias"][0]["descricao"]


def test_lote_inativo_gera_divergencia_rn03(base_referencia, tmp_path):
    df = pd.DataFrame([_linha(lote_id="LOTE002")])

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    assert resultado["divergencias"][0]["regra"] == "RN03"
    assert "inativo" in resultado["divergencias"][0]["descricao"]


def test_status_ambiguo_gera_divergencia_rn06(base_referencia, tmp_path):
    df = pd.DataFrame([_linha(lote_id="LOTE001", status="REPROV.")])

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    regras = [d["regra"] for d in resultado["divergencias"]]
    assert "RN06" in regras


def test_lote_reprovado_sem_observacao_gera_divergencia_rn07(base_referencia, tmp_path):
    df = pd.DataFrame([_linha(lote_id="LOTE001", status="REPROVADO", observacao="")])

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    regras = [d["regra"] for d in resultado["divergencias"]]
    assert "RN07" in regras


def test_lote_reprovado_com_observacao_nao_gera_divergencia_rn07(base_referencia, tmp_path):
    df = pd.DataFrame(
        [_linha(lote_id="LOTE001", status="REPROVADO", observacao="Fora da validade.")]
    )

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    regras = [d["regra"] for d in resultado["divergencias"]]
    assert "RN07" not in regras


def test_observacao_vazia_via_csv_gera_divergencia_rn07(base_referencia, tmp_path):
    """Regressão: `pd.read_csv` lê campo vazio como NaN (float), não "".
    `lote_conforme_rn07` faz `str(observacao) or ""`, e `str(nan)` é a
    string não-vazia "nan" — sem normalizar NaN para None antes de
    chamar essa função, a divergência RN07 passaria batido."""
    import io

    csv = (
        "lote_id,produto,linha,turno,status,responsavel,data,observacao\n"
        "LOTE001,Monitor,LT-01,A,REPROVADO,Fulano,2026-07-10,\n"
    )
    df = pd.read_csv(io.StringIO(csv))
    assert pd.isna(df.loc[0, "observacao"])

    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    regras = [d["regra"] for d in resultado["divergencias"]]
    assert "RN07" in regras


def test_base_referencia_ausente_gera_divergencia_infra_sem_estourar(monkeypatch, tmp_path):
    def _levanta_erro(caminho):
        raise FileNotFoundError(f"[Errno 2] {caminho}")

    monkeypatch.setattr(relatorio_modulo, "carregar_base_referencia", _levanta_erro)

    df = pd.DataFrame([_linha(lote_id="LOTE001")])
    resultado = gerar_relatorio(df, str(tmp_path / "relatorio.xlsx"))

    assert resultado["divergencias"][0]["regra"] == "INFRA"
    assert resultado["resumo"]["estrutura_valida"] is False


def test_arquivo_xlsx_gerado_tem_abas_resumo_e_divergencias(base_referencia, tmp_path):
    caminho = tmp_path / "relatorio.xlsx"
    df = pd.DataFrame([_linha(lote_id="LOTE001"), _linha(lote_id="LOTE999")])

    gerar_relatorio(df, str(caminho))

    planilhas = pd.read_excel(caminho, sheet_name=None)
    assert set(planilhas.keys()) == {"Resumo", "Divergencias"}
    assert list(planilhas["Divergencias"].columns) == ["regra", "lote_id", "linha", "descricao"]
    assert len(planilhas["Divergencias"]) == 1
