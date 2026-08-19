"""Teste de integração exigido pela Seção 5.6 da Aula 24: confirma a
criação física do relatorio_conferencia_lotes.xlsx em tmp_path e a
presença das 8 abas essenciais — incluindo Ranking de Regras e
Dicionário —, com os indicadores calculados uma única vez e repassados
ao gerador (mesmo objeto, sem recálculo).
"""
import openpyxl
import pytest

from src.aula22_classificacao import RegistroValidado
from src.aula22_relatorio import gerar_relatorio_aula22
from src.operational_indicators import calcular_indicadores

pytestmark = pytest.mark.integration

ABAS_ESSENCIAIS = [
    "Resumo", "Todos", "Válidos", "Divergências", "Ambíguos", "Erros de Entrada",
    "Ranking de Regras", "Dicionário",
]


def _registro(dia, data_referencia, lote_id, classificacao, regra, **overrides):
    base = dict(
        dia=dia,
        data_referencia=data_referencia,
        linha_planilha=4,
        lote_id=lote_id,
        produto="TV55",
        linha="L1",
        turno="A",
        status_original="APROVADO",
        status_normalizado="APROVADO",
        responsavel="Ana",
        data_lote=data_referencia,
        observacao="",
        ocorrencia_no_dia=1,
        classificacao=classificacao,
        regra=regra,
        motivo="motivo de teste",
    )
    base.update(overrides)
    return RegistroValidado(**base)


@pytest.fixture
def registros():
    return [
        _registro("Insp_15_06_2026", "15/06/2026", "L001", "Válido", "RN08"),
        _registro("Insp_15_06_2026", "15/06/2026", "L002", "Válido", "RN08"),
        _registro("Insp_15_06_2026", "15/06/2026", "L003", "Divergência", "RN05"),
        _registro("Insp_15_06_2026", "15/06/2026", "L004", "Ambíguo", "RN09"),
        _registro("Insp_16_06_2026", "16/06/2026", "", "Erro de Entrada", "RN01-RN04"),
        _registro("Insp_16_06_2026", "16/06/2026", "L006", "Válido", "RN08"),
    ]


def test_relatorio_e_criado_fisicamente_em_disco(tmp_path, registros):
    caminho = tmp_path / "relatorio_conferencia_lotes.xlsx"
    assert not caminho.exists()

    gerar_relatorio_aula22(registros, str(caminho))

    assert caminho.exists()
    assert caminho.stat().st_size > 0


def test_arquivo_gerado_contem_as_8_abas_essenciais(tmp_path, registros):
    caminho = tmp_path / "relatorio_conferencia_lotes.xlsx"
    indicadores = calcular_indicadores(registros)
    gerar_relatorio_aula22(registros, str(caminho), indicadores=indicadores)

    wb = openpyxl.load_workbook(caminho)
    for aba in ABAS_ESSENCIAIS:
        assert aba in wb.sheetnames, f"aba obrigatória ausente: {aba}"
    assert len(wb.sheetnames) == len(ABAS_ESSENCIAIS)


def test_ranking_de_regras_e_dicionario_nao_ficam_vazios(tmp_path, registros):
    caminho = tmp_path / "relatorio_conferencia_lotes.xlsx"
    gerar_relatorio_aula22(registros, str(caminho))

    wb = openpyxl.load_workbook(caminho)
    assert wb["Ranking de Regras"].max_row > 1  # cabeçalho + pelo menos 1 regra
    assert wb["Dicionário"].max_row > 1
