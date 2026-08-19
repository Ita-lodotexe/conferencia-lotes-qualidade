"""Teste de integração da 9ª aba "Decisões de ML" (Exercício 24-A,
Commit 5): confirma que ela só aparece quando `decisoes_ml` é passado
para gerar_relatorio_aula22, e que o número de linhas bate exatamente
com o de "Ambíguos" — é o teste de consistência que o Formulário de
Revisão por Pares pede.
"""
import openpyxl
import pytest

from src.aula22_classificacao import RegistroValidado
from src.aula22_relatorio import gerar_relatorio_aula22
from src.item_processor import processar_registros_ambiguos

pytestmark = pytest.mark.integration

ABAS_COM_ML = [
    "Resumo", "Todos", "Válidos", "Divergências", "Ambíguos", "Erros de Entrada",
    "Ranking de Regras", "Dicionário", "Decisões de ML",
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
def registros_com_varios_ambiguos():
    return [
        _registro("Insp_15_06_2026", "15/06/2026", "L001", "Válido", "RN08"),
        _registro("Insp_15_06_2026", "15/06/2026", "L002", "Divergência", "RN05"),
        _registro(
            "Insp_15_06_2026", "15/06/2026", "L003", "Ambíguo", "RN09",
            status_normalizado="EM AJUSTE",  # mapeável
        ),
        _registro(
            "Insp_15_06_2026", "15/06/2026", "L004", "Ambíguo", "RN09",
            status_normalizado="CANCELADO",  # mapeável
        ),
        _registro(
            "Insp_16_06_2026", "16/06/2026", "L005", "Ambíguo", "RN09",
            status_normalizado="REPROV.",  # não mapeável — não entra no ML
        ),
        _registro("Insp_16_06_2026", "16/06/2026", "", "Erro de Entrada", "RN01-RN04"),
    ]


def test_gerar_relatorio_sem_decisoes_ml_continua_com_8_abas(tmp_path, registros_com_varios_ambiguos):
    """Não quebra o comportamento do Commit 3: quem chama sem saber de ML
    continua recebendo exatamente 8 abas, sem "Decisões de ML"."""
    caminho = tmp_path / "relatorio.xlsx"
    gerar_relatorio_aula22(registros_com_varios_ambiguos, str(caminho))

    wb = openpyxl.load_workbook(caminho)
    assert "Decisões de ML" not in wb.sheetnames
    assert len(wb.sheetnames) == 8


def test_gerar_relatorio_com_decisoes_ml_vazia_ainda_escreve_a_9a_aba(tmp_path, registros_com_varios_ambiguos):
    """decisoes_ml=[] (lista vazia, não None) ainda deve escrever a aba —
    só cabeçalho, sem linhas de dados."""
    caminho = tmp_path / "relatorio.xlsx"
    gerar_relatorio_aula22(registros_com_varios_ambiguos, str(caminho), decisoes_ml=[])

    wb = openpyxl.load_workbook(caminho)
    assert "Decisões de ML" in wb.sheetnames
    assert wb["Decisões de ML"].max_row == 1  # só o cabeçalho


def test_relatorio_com_decisoes_ml_tem_9_abas_e_ambiguos_bate_com_decisoes_ml(
    tmp_path, registros_com_varios_ambiguos
):
    ml_client = _MLClientFalso()
    decisoes_ml = processar_registros_ambiguos(registros_com_varios_ambiguos, ml_client)

    caminho = tmp_path / "relatorio.xlsx"
    gerar_relatorio_aula22(registros_com_varios_ambiguos, str(caminho), decisoes_ml=decisoes_ml)

    wb = openpyxl.load_workbook(caminho)
    assert wb.sheetnames == ABAS_COM_ML

    linhas_ambiguos = wb["Ambíguos"].max_row - 1  # -1 = desconta o cabeçalho
    linhas_decisoes_ml = wb["Decisões de ML"].max_row - 1

    # É literalmente o teste que o Formulário de Revisão por Pares pede:
    # somar linhas da aba "Ambíguos" e comparar com "Decisões de ML".
    assert linhas_ambiguos == linhas_decisoes_ml == 3
    assert len(decisoes_ml) == 3


class _MLClientFalso:
    """Dublê de MLClient — sempre "sucesso", sem rede. O comportamento
    real de MLClient já é coberto por tests/unit/test_ml_client.py."""

    def classificar(self, lote_id, status, turno, tem_observacao) -> dict:
        return {
            "classe_predita": "revisar",
            "probabilidade": 0.7,
            "decisao": "revisar",
            "latencia_ms": 5.0,
        }
