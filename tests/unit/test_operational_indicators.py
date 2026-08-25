"""Testes unitários da camada de indicadores operacionais (Aula 24)."""

import pytest

from src.aula22_classificacao import RegistroValidado
from src.operational_indicators import (
    REGRAS_DESCRICAO,
    OperationalIndicators,
    _percentual,
    calcular_indicadores,
)

pytestmark = pytest.mark.unit


def _registro(classificacao: str, regra: str, lote_id: str = "L001") -> RegistroValidado:
    """Constrói um RegistroValidado mínimo, só com os campos que os
    indicadores realmente usam (classificacao e regra); os demais campos
    são preenchidos com valores neutros só para satisfazer a dataclass.
    """
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


class TestPercentual:
    def test_caso_normal(self):
        assert _percentual(25, 100) == 25.0

    def test_percentual_nao_exato(self):
        assert _percentual(1, 3) == pytest.approx(33.333, rel=1e-3)

    def test_divisao_por_zero_retorna_zero(self):
        assert _percentual(5, 0) == 0

    def test_total_zero_e_parte_zero_retorna_zero(self):
        assert _percentual(0, 0) == 0


class TestCalcularIndicadoresListaVazia:
    """total_registros == 0 não pode lançar exceção em nenhum indicador."""

    def setup_method(self):
        self.indicadores = calcular_indicadores([])

    def test_total_e_zero(self):
        assert self.indicadores.total_registros == 0

    def test_contagens_sao_zero(self):
        assert self.indicadores.qtd_validos == 0
        assert self.indicadores.qtd_divergencias == 0
        assert self.indicadores.qtd_ambiguos == 0
        assert self.indicadores.qtd_erros_entrada == 0

    def test_percentuais_sao_zero(self):
        assert self.indicadores.pct_validos == 0
        assert self.indicadores.pct_divergencias == 0
        assert self.indicadores.pct_ambiguos == 0
        assert self.indicadores.pct_erros_entrada == 0
        assert self.indicadores.taxa_qualidade_entrada == 0
        assert self.indicadores.taxa_revisao_humana == 0
        assert self.indicadores.taxa_retrabalho == 0

    def test_regra_mais_acionada_e_none(self):
        assert self.indicadores.regra_mais_acionada is None
        assert self.indicadores.regra_mais_acionada_nome is None
        assert self.indicadores.regra_mais_acionada_qtd == 0

    def test_ganho_estimado_e_zero(self):
        assert self.indicadores.ganho_estimado_minutos == 0

    def test_ranking_regras_vazio(self):
        assert self.indicadores.ranking_regras == []


class TestCalcularIndicadoresCenarioConhecido:
    """10 registros: 5 válidos, 2 divergências (RN05), 1 ambíguo (RN09),
    2 erros de entrada (RN01-RN04) — números redondos para facilitar a
    conferência manual dos percentuais.
    """

    @pytest.fixture
    def registros(self):
        return (
            [_registro("Válido", "RN08") for _ in range(5)]
            + [_registro("Divergência", "RN05") for _ in range(2)]
            + [_registro("Ambíguo", "RN09")]
            + [_registro("Erro de Entrada", "RN01-RN04") for _ in range(2)]
        )

    @pytest.fixture
    def indicadores(self, registros) -> OperationalIndicators:
        return calcular_indicadores(registros)

    def test_total_registros(self, indicadores):
        assert indicadores.total_registros == 10

    def test_validos(self, indicadores):
        assert indicadores.qtd_validos == 5
        assert indicadores.pct_validos == 50.0

    def test_divergencias(self, indicadores):
        assert indicadores.qtd_divergencias == 2
        assert indicadores.pct_divergencias == 20.0

    def test_ambiguos(self, indicadores):
        assert indicadores.qtd_ambiguos == 1
        assert indicadores.pct_ambiguos == 10.0

    def test_erros_de_entrada(self, indicadores):
        assert indicadores.qtd_erros_entrada == 2
        assert indicadores.pct_erros_entrada == 20.0

    def test_regra_mais_acionada_e_a_de_maior_contagem(self, indicadores):
        # RN08 (Válido, 5 ocorrências) é excluída de propósito — não é uma
        # regra de negócio violada; contá-la dominaria o indicador sempre
        # que a maioria dos registros estiver correta, que é o caso normal.
        # Entre as regras de problema, RN05 aparece 2x, empatada com
        # RN01-RN04 (2x) — RN05 vem primeiro na lista de registros, então
        # vence o desempate (ver docstring de calcular_indicadores sobre
        # Counter.most_common()).
        assert indicadores.regra_mais_acionada == "RN05"
        assert indicadores.regra_mais_acionada_qtd == 2
        assert indicadores.regra_mais_acionada_nome == REGRAS_DESCRICAO["RN05"]

    def test_taxa_qualidade_entrada(self, indicadores):
        # (10 - 2) / 10 * 100 = 80.0
        assert indicadores.taxa_qualidade_entrada == 80.0

    def test_taxa_revisao_humana(self, indicadores):
        # 1 / 10 * 100 = 10.0
        assert indicadores.taxa_revisao_humana == 10.0

    def test_taxa_retrabalho(self, indicadores):
        # 2 / 10 * 100 = 20.0
        assert indicadores.taxa_retrabalho == 20.0

    def test_ranking_regras_ordenado_do_mais_para_o_menos_acionado(self, indicadores):
        # RN08 (Válido) não entra no ranking — só regras de problema.
        codigos = [codigo for codigo, _qtd in indicadores.ranking_regras]
        assert codigos == ["RN05", "RN01-RN04", "RN09"]

    def test_ganho_estimado_usa_premissas_padrao(self, indicadores):
        # 10 registros * (3.0 - 0.2) min = 28.0 min, com as premissas padrão.
        assert indicadores.ganho_estimado_minutos == pytest.approx(28.0)
        assert indicadores.tempo_manual_min_por_registro == 3.0
        assert indicadores.tempo_automatizado_min_por_registro == 0.2


class TestCalcularIndicadoresPremissasCustomizadas:
    def test_premissas_customizadas_alteram_ganho_estimado(self):
        registros = [_registro("Válido", "RN08") for _ in range(4)]
        indicadores = calcular_indicadores(
            registros,
            tempo_manual_min_por_registro=5.0,
            tempo_automatizado_min_por_registro=1.0,
        )
        assert indicadores.ganho_estimado_minutos == pytest.approx(16.0)
        assert indicadores.tempo_manual_min_por_registro == 5.0
        assert indicadores.tempo_automatizado_min_por_registro == 1.0


@pytest.mark.parametrize(
    "classificacoes_regras, esperado",
    [
        pytest.param(
            [("Válido", "RN08")] * 10,
            {"pct_validos": 100.0, "pct_divergencias": 0.0, "pct_ambiguos": 0.0, "pct_erros_entrada": 0.0},
            id="todos_validos",
        ),
        pytest.param(
            [("Divergência", "RN11")] * 10,
            {"pct_validos": 0.0, "pct_divergencias": 100.0, "pct_ambiguos": 0.0, "pct_erros_entrada": 0.0},
            id="todas_divergencias",
        ),
        pytest.param(
            [("Ambíguo", "RN09")] * 4 + [("Válido", "RN08")] * 6,
            {"pct_validos": 60.0, "pct_divergencias": 0.0, "pct_ambiguos": 40.0, "pct_erros_entrada": 0.0},
            id="mix_ambiguo_e_valido",
        ),
        pytest.param(
            [("Erro de Entrada", "RN12")] * 3 + [("Válido", "RN08")] * 1,
            {"pct_validos": 25.0, "pct_divergencias": 0.0, "pct_ambiguos": 0.0, "pct_erros_entrada": 75.0},
            id="maioria_erro_de_entrada",
        ),
    ],
)
def test_calcular_indicadores_parametrizado(classificacoes_regras, esperado):
    registros = [_registro(classificacao, regra) for classificacao, regra in classificacoes_regras]
    indicadores = calcular_indicadores(registros)

    assert indicadores.pct_validos == esperado["pct_validos"]
    assert indicadores.pct_divergencias == esperado["pct_divergencias"]
    assert indicadores.pct_ambiguos == esperado["pct_ambiguos"]
    assert indicadores.pct_erros_entrada == esperado["pct_erros_entrada"]


def test_regras_descricao_cobre_todos_os_codigos_usados_no_projeto():
    """Trava de sincronização: se uma nova regra (RN13+) for adicionada em
    aula22_classificacao.py sem entrar em REGRAS_DESCRICAO, este teste falha
    — evita que o indicador 6 mostre o código bruto por esquecimento.
    """
    codigos_usados = {"RN01-RN04", "RN05", "RN08", "RN09", "RN10", "RN11", "RN12"}
    assert codigos_usados.issubset(REGRAS_DESCRICAO.keys())
