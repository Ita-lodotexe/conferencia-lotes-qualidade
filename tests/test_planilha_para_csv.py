"""Testes do preprocessor da planilha oficial (Issue #26).

Os testes rodam contra a planilha real em dados_referencia/, porque o
valor deste módulo é justamente lidar com o formato humano específico
dela (títulos, rodapé, legenda de cores, nota do professor). Um XLSX
sintético testaria um formato que não é o do exercício.
"""

import logging

import pandas as pd
import pytest

from scripts import planilha_para_csv as prep
from scripts.planilha_para_csv import (
    PreprocessorError,
    carregar_aba_base,
    carregar_aba_inspecao,
)
from src.modules.validacao import COLUNAS_ESPERADAS

PLANILHA = prep.PLANILHA_ENTRADA


def test_carregar_aba_inspecao_retorna_25_lotes():
    df = carregar_aba_inspecao(PLANILHA)

    assert len(df) == 25
    assert list(df.columns) == COLUNAS_ESPERADAS

    # O rodapé "Total de registros: 25" e a legenda de cores ficam depois
    # do corte e não podem virar lotes.
    assert not df["lote_id"].str.contains("Total de registros").any()
    assert not df["lote_id"].str.contains("LEGENDA").any()

    # A linha de lote_id vazio (erro proposital) tem de sobreviver ao corte:
    # é ela que dispara RN02 + RN03 na demo.
    assert (df["lote_id"] == "").sum() == 1


def test_carregar_aba_base_retorna_23_registros():
    df = carregar_aba_base(PLANILHA)

    assert len(df) == 23
    assert list(df.columns) == prep.COLUNAS_ESPERADAS_BASE

    # A nota do professor está na coluna lote_id da última linha da aba —
    # tem de ficar fora dos dados.
    assert not df["lote_id"].str.contains("NOTA AO REVISOR").any()

    # LG-2026-00103 foi removido de propósito da base (RN03 intencional).
    assert "LG-2026-00103" not in df["lote_id"].values
    assert "LG-2026-00101" in df["lote_id"].values


def test_normalizacao_nan_para_string_vazia():
    """Célula vazia do Excel precisa virar "" e nunca a string "nan"."""
    df = pd.DataFrame({"a": ["x", None], "b": [float("nan"), "y"]})

    normalizado = prep._normalizar_dataframe(df, ["a", "b"])

    assert normalizado.loc[1, "a"] == ""
    assert normalizado.loc[0, "b"] == ""
    assert "nan" not in normalizado.values

    # E o mesmo vale para a planilha real: a coluna observacao é a mais
    # esparsa (só 5 das 25 linhas preenchidas).
    inspecao = carregar_aba_inspecao(PLANILHA)
    assert (inspecao["observacao"] == "nan").sum() == 0
    assert (inspecao["observacao"] == "").sum() > 0


def test_planilha_ausente_retorna_erro(monkeypatch, caplog):
    monkeypatch.setattr(prep.os.path, "exists", lambda caminho: False)

    caplog.set_level(logging.INFO)
    assert prep.main() == 1
    assert any(
        r.levelno == logging.ERROR and "não encontrada" in r.message for r in caplog.records
    )


def test_aba_sem_colunas_esperadas_relevanta_preprocessor_error(tmp_path):
    caminho = tmp_path / "planilha_invalida.xlsx"
    # Duas linhas de lixo antes do header, para o skiprows=2 cair no header
    # errado de propósito.
    df_fake = pd.DataFrame({"coluna_errada": ["a", "b", "c"], "outra": [1, 2, 3]})
    with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
        df_fake.to_excel(writer, sheet_name=prep.ABA_INSPECAO, index=False)

    with pytest.raises(PreprocessorError) as erro:
        carregar_aba_inspecao(str(caminho))

    assert prep.ABA_INSPECAO in str(erro.value)


def test_execucao_completa_produz_dois_csvs(monkeypatch, tmp_path):
    csv_fila = tmp_path / "saida" / "lotes_auditoria.csv"
    csv_base = tmp_path / "saida" / "base_lotes_referencia.csv"
    monkeypatch.setattr(prep, "CSV_FILA_SAIDA", str(csv_fila))
    monkeypatch.setattr(prep, "CSV_BASE_SAIDA", str(csv_base))

    assert prep.main() == 0

    assert csv_fila.is_file()
    assert csv_base.is_file()

    df_fila = pd.read_csv(csv_fila, dtype=str, keep_default_na=False)
    df_base = pd.read_csv(csv_base, dtype=str, keep_default_na=False)

    assert len(df_fila) == 25
    assert len(df_base) == 23
    assert list(df_fila.columns) == COLUNAS_ESPERADAS
    assert list(df_base.columns) == prep.COLUNAS_ESPERADAS_BASE
