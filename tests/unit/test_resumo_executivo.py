"""Testes de `src/resumo_executivo.py` — resumo_executivo.md (Aula 24, Seção 5.4).

Usa OperationalIndicators calculados a partir de listas sintéticas de
RegistroValidado (mesmo padrão de tests/unit/test_operational_indicators.py)
para garantir que o texto reflete exatamente os números recebidos, sem
recalcular nada e sem código de regra "solto".
"""
import re

import pytest

from src.aula22_classificacao import RegistroValidado
from src.operational_indicators import REGRAS_DESCRICAO, calcular_indicadores
from src.resumo_executivo import gerar_resumo_executivo

pytestmark = pytest.mark.unit

SECOES_OBRIGATORIAS = [
    "## Visão Geral",
    "## Indicadores Principais",
    "## Destaque",
    "## Ganho Estimado de Tempo",
    "## Observação",
]

PADRAO_CODIGO_REGRA = re.compile(r"RN\d{2}(?:-RN\d{2})?")


def _registro(classificacao: str, regra: str, lote_id: str = "L001") -> RegistroValidado:
    return RegistroValidado(
        dia="Insp_15_06_2026",
        data_referencia="15/06/2026",
        linha_planilha=1,
        lote_id=lote_id,
        produto="TV",
        linha="Linha 1",
        turno="Manhã",
        status_original="OK",
        status_normalizado="APROVADO",
        responsavel="Fulano",
        data_lote="15/06/2026",
        observacao="",
        ocorrencia_no_dia=1,
        classificacao=classificacao,
        regra=regra,
        motivo="motivo de teste",
    )


@pytest.fixture
def registros_com_divergencia():
    return (
        [_registro("Válido", "RN08") for _ in range(5)]
        + [_registro("Divergência", "RN05") for _ in range(3)]
        + [_registro("Ambíguo", "RN09")]
        + [_registro("Erro de Entrada", "RN01-RN04")]
    )


def test_todas_as_5_secoes_aparecem(registros_com_divergencia):
    indicadores = calcular_indicadores(registros_com_divergencia)
    texto = gerar_resumo_executivo(indicadores)

    for secao in SECOES_OBRIGATORIAS:
        assert secao in texto


def test_visao_geral_cita_total_e_periodo_de_10_dias(registros_com_divergencia):
    indicadores = calcular_indicadores(registros_com_divergencia)
    texto = gerar_resumo_executivo(indicadores)

    secao_visao_geral = texto.split("## Visão Geral")[1].split("##")[0]
    assert str(indicadores.total_registros) in secao_visao_geral
    assert "10 dias" in secao_visao_geral


def test_nenhum_codigo_de_regra_aparece_sem_o_nome_legivel_ao_lado(registros_com_divergencia):
    """Critério de aceite: 'RN05' sozinho não deve aparecer — só é aceitável
    junto do nome legível (REGRAS_DESCRICAO) na mesma linha."""
    indicadores = calcular_indicadores(registros_com_divergencia)
    texto = gerar_resumo_executivo(indicadores)

    for linha in texto.splitlines():
        for match in PADRAO_CODIGO_REGRA.finditer(linha):
            codigo = match.group()
            nome = REGRAS_DESCRICAO.get(codigo)
            assert nome is not None and nome in linha, (
                f"código de regra {codigo!r} aparece sem o nome legível ao lado na linha: {linha!r}"
            )


def test_texto_muda_conforme_os_numeros_do_indicador_de_entrada(registros_com_divergencia):
    """Garante que o texto não é fixo com números fake: indicadores
    diferentes (mais um registro válido) devem produzir textos diferentes."""
    indicadores_a = calcular_indicadores(registros_com_divergencia)
    indicadores_b = calcular_indicadores(registros_com_divergencia + [_registro("Válido", "RN08")])

    texto_a = gerar_resumo_executivo(indicadores_a)
    texto_b = gerar_resumo_executivo(indicadores_b)

    assert texto_a != texto_b
    assert str(indicadores_a.total_registros) in texto_a
    assert str(indicadores_b.total_registros) in texto_b
    assert indicadores_a.total_registros != indicadores_b.total_registros


def test_numeros_do_resumo_batem_exatamente_com_o_objeto_recebido(registros_com_divergencia):
    indicadores = calcular_indicadores(registros_com_divergencia)
    texto = gerar_resumo_executivo(indicadores)

    assert str(indicadores.total_registros) in texto
    assert f"{indicadores.pct_validos:.1f}%" in texto
    assert f"{indicadores.pct_divergencias:.1f}%" in texto
    assert f"{indicadores.pct_ambiguos:.1f}%" in texto
    assert f"{indicadores.pct_erros_entrada:.1f}%" in texto
    assert f"{indicadores.ganho_estimado_minutos:.1f}" in texto
    assert indicadores.regra_mais_acionada_nome in texto
    assert str(indicadores.regra_mais_acionada_qtd) in texto


def test_premissas_do_ganho_estimado_aparecem_explicitas(registros_com_divergencia):
    indicadores = calcular_indicadores(
        registros_com_divergencia,
        tempo_manual_min_por_registro=7.5,
        tempo_automatizado_min_por_registro=0.5,
    )
    texto = gerar_resumo_executivo(indicadores)
    secao_ganho = texto.split("## Ganho Estimado de Tempo")[1].split("##")[0]

    assert "7.5" in secao_ganho
    assert "0.5" in secao_ganho
    assert f"{indicadores.ganho_estimado_minutos:.1f}" in secao_ganho


def test_regra_mais_acionada_none_nao_quebra_e_avisa_explicitamente_no_destaque():
    registros = [_registro("Válido", "RN08") for _ in range(4)]
    indicadores = calcular_indicadores(registros)
    assert indicadores.regra_mais_acionada is None  # pré-condição deste teste

    texto = gerar_resumo_executivo(indicadores)
    secao_destaque = texto.split("## Destaque")[1].split("##")[0]

    assert "nenhum" in secao_destaque.lower() or "não" in secao_destaque.lower()
    assert not PADRAO_CODIGO_REGRA.search(secao_destaque)


def test_observacao_deixa_claro_que_e_estimativa_didatica(registros_com_divergencia):
    indicadores = calcular_indicadores(registros_com_divergencia)
    texto = gerar_resumo_executivo(indicadores)
    secao_observacao = texto.split("## Observação")[1]

    assert "estimativa" in secao_observacao.lower()
    assert "não" in secao_observacao.lower()
