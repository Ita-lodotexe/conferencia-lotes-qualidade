"""Validação de ponta a ponta contra o Gabarito_Instrutor real (Aula 22).

Requer o arquivo `inspecao_lotes_10dias.xlsx` (dado de avaliação, não
distribuído no repositório) em `dados_referencia/`. Sem o arquivo, os
testes deste módulo são pulados — a cobertura funcional de cada regra
fica em tests/test_aula22_classificacao.py, com dados sintéticos.
"""

from collections import Counter
from pathlib import Path

import pytest

from src.aula22_classificacao import classificar_lotes
from src.aula22_preprocessador import carregar_planilha_10dias

CAMINHO_PLANILHA = Path(__file__).resolve().parents[1] / "dados_referencia" / "inspecao_lotes_10dias.xlsx"

pytestmark = pytest.mark.skipif(
    not CAMINHO_PLANILHA.exists(),
    reason=f"dataset real não encontrado em {CAMINHO_PLANILHA} — ver docstring do módulo",
)

TOTAL_ESPERADO = 250
DIVERGENCIAS_PROPOSITAIS_ESPERADAS = 100
ESPERADO_POR_DIA = {"Divergência": 5, "Ambíguo": 2, "Erro de Entrada": 3}


@pytest.fixture(scope="module")
def resultado_classificado():
    registros_por_dia, base_referencia = carregar_planilha_10dias(str(CAMINHO_PLANILHA))
    resultado = classificar_lotes(registros_por_dia, base_referencia)
    return registros_por_dia, resultado


def test_total_de_registros_bate_com_gabarito(resultado_classificado):
    registros_por_dia, resultado = resultado_classificado
    assert sum(len(v) for v in registros_por_dia.values()) == TOTAL_ESPERADO
    assert len(resultado) == TOTAL_ESPERADO


def test_total_de_divergencias_propositais_bate_com_gabarito(resultado_classificado):
    _, resultado = resultado_classificado
    contagem = Counter(r.classificacao for r in resultado)
    total_propositais = contagem["Divergência"] + contagem["Ambíguo"] + contagem["Erro de Entrada"]
    assert total_propositais == DIVERGENCIAS_PROPOSITAIS_ESPERADAS
    assert contagem["Válido"] + total_propositais == TOTAL_ESPERADO


def test_distribuicao_diaria_bate_com_gabarito(resultado_classificado):
    registros_por_dia, resultado = resultado_classificado
    for dia in registros_por_dia:
        contagem_dia = Counter(r.classificacao for r in resultado if r.dia == dia)
        for classe, esperado in ESPERADO_POR_DIA.items():
            assert contagem_dia[classe] == esperado, f"{dia}: {classe} esperado={esperado} obtido={contagem_dia[classe]}"
