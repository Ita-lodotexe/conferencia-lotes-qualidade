"""Camada de indicadores operacionais — Aula 24.

Consolida a lista de ``RegistroValidado`` (produzida por
``src.aula22_classificacao.classificar_lotes``) em uma única fonte de
verdade: a dataclass ``OperationalIndicators``, com os dez indicadores
de negócio definidos na Seção 4 do enunciado da Aula 24.

Este módulo não conhece Excel, Markdown, nem pytest — ele só calcula.
É o mesmo objeto produzido aqui que deve alimentar, sem recálculo, o
relatório Excel de 8 abas e o ``resumo_executivo.md`` (Seções 5.3–5.5),
para evitar que as duas saídas divirjam silenciosamente entre si.

Convênio 005/2025 (INOVA, IFAM, LG Electronics do Brasil).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from src.aula22_classificacao import RegistroValidado

# Descrição legível de cada regra que pode aparecer em RegistroValidado.regra
# (ver src/aula22_classificacao.py::classificar_registro). Usado no indicador 6
# ("regra mais acionada") e, no próximo commit, na aba "Ranking de Regras" e no
# "Dicionário" do relatório Excel.
REGRAS_DESCRICAO: dict[str, str] = {
    "RN01-RN04": "Campo obrigatório vazio (produto, linha, status, responsável ou lote_id)",
    "RN05": "Lote não cadastrado ou inativo na Base_Referencia",
    "RN08": "Registro conforme — nenhuma divergência encontrada",
    "RN09": "Status não reconhecível (ambíguo, requer revisão manual)",
    "RN10": "Status REPROVADO sem observação preenchida",
    "RN11": "Lote duplicado no mesmo dia (2ª ocorrência ou mais)",
    "RN12": "Data de referência ausente ou fora do formato DD/MM/AAAA",
}

# Premissas didáticas do indicador 10 (ganho estimado de tempo). Nunca é uma
# medição real de produção — ver docstring de calcular_indicadores().
TEMPO_MANUAL_MIN_POR_REGISTRO_PADRAO = 3.0
TEMPO_AUTOMATIZADO_MIN_POR_REGISTRO_PADRAO = 0.2


@dataclass
class OperationalIndicators:
    """Os dez indicadores operacionais do dashboard executivo (Seção 4)."""

    # 1. Total de registros
    total_registros: int

    # 2. Registros válidos
    qtd_validos: int
    pct_validos: float

    # 3. Divergências
    qtd_divergencias: int
    pct_divergencias: float

    # 4. Ambíguos
    qtd_ambiguos: int
    pct_ambiguos: float

    # 5. Erros de Entrada
    qtd_erros_entrada: int
    pct_erros_entrada: float

    # 6. Regra mais acionada
    regra_mais_acionada: str | None
    regra_mais_acionada_nome: str | None
    regra_mais_acionada_qtd: int

    # 7. Taxa de qualidade da entrada — referência > 80%
    taxa_qualidade_entrada: float

    # 8. Taxa de revisão humana — referência < 15%
    taxa_revisao_humana: float

    # 9. Taxa de retrabalho — referência < 6%
    taxa_retrabalho: float

    # 10. Ganho estimado de tempo (estimativa didática, nunca medição real)
    ganho_estimado_minutos: float
    tempo_manual_min_por_registro: float
    tempo_automatizado_min_por_registro: float

    # Contagem por regra (código -> quantidade), na ordem de
    # Counter.most_common(), **excluindo RN08 (Válido)** — só regras que
    # representam divergência/ambiguidade/erro entram aqui. É a mesma
    # contagem que alimenta a futura aba "Ranking de Regras"; guardada aqui
    # para não ser recalculada em outro lugar (ver Seção "Erro comum: duas
    # fontes de verdade" do enunciado).
    ranking_regras: list[tuple[str, int]] = field(default_factory=list)


def _percentual(parte: int, total: int) -> float:
    """(parte / total) * 100, com total == 0 retornando 0 em vez de lançar exceção.

    Toda proporção do dashboard passa por esta função — nenhum outro trecho do
    módulo calcula percentual "na mão", garantindo que os indicadores
    percentuais fiquem consistentes entre si e entre o Excel e o resumo
    executivo.
    """
    if total == 0:
        return 0.0
    return (parte / total) * 100


def calcular_indicadores(
    registros: list[RegistroValidado],
    tempo_manual_min_por_registro: float = TEMPO_MANUAL_MIN_POR_REGISTRO_PADRAO,
    tempo_automatizado_min_por_registro: float = TEMPO_AUTOMATIZADO_MIN_POR_REGISTRO_PADRAO,
) -> OperationalIndicators:
    """Consolida ``registros`` nos dez indicadores operacionais.

    Args:
        registros: lista de RegistroValidado já classificados (saída de
            ``classificar_lotes``). Pode ser vazia — nesse caso todos os
            indicadores percentuais retornam 0, sem lançar exceção.
        tempo_manual_min_por_registro: premissa didática de quanto tempo,
            em minutos, uma conferência manual levaria por registro.
            Valor-padrão de 3 minutos, ilustrativo.
        tempo_automatizado_min_por_registro: premissa didática de quanto
            tempo, em minutos, a automação leva por registro. Valor-padrão
            de 0.2 minuto (12 segundos), ilustrativo.

    Returns:
        OperationalIndicators com os dez indicadores da Seção 4. O ganho de
        tempo (indicador 10) é sempre uma **estimativa didática** — não uma
        medição real de produção — e suas premissas (tempo manual e tempo
        automatizado assumidos) ficam explícitas nos campos
        ``tempo_manual_min_por_registro`` e ``tempo_automatizado_min_por_registro``.
    """
    total = len(registros)

    contagem_classificacao = Counter(r.classificacao for r in registros)
    qtd_validos = contagem_classificacao.get("Válido", 0)
    qtd_divergencias = contagem_classificacao.get("Divergência", 0)
    qtd_ambiguos = contagem_classificacao.get("Ambíguo", 0)
    qtd_erros_entrada = contagem_classificacao.get("Erro de Entrada", 0)

    # Indicador 6 — regra mais acionada. Counter.most_common() resolve
    # empates pela ordem de primeira inserção no Counter, que por sua vez
    # segue a ordem de iteração de `registros` — ou seja, em caso de empate,
    # vence a regra que apareceu primeiro na lista de registros. Isso é
    # determinístico e coberto em teste, não um comportamento implícito.
    #
    # RN08 (Válido) é deliberadamente excluída deste ranking: ela marca
    # "nenhum problema encontrado", não uma regra de negócio violada. Se
    # fosse contada junto, dominaria o indicador sempre que a maioria dos
    # registros estivesse correta (o caso normal) — e o indicador 6 existe
    # para apontar o gargalo (a divergência/ambiguidade/erro mais comum),
    # não para dizer "a maioria está válida".
    contagem_regras = Counter(r.regra for r in registros if r.classificacao != "Válido")
    ranking_regras = contagem_regras.most_common()

    if ranking_regras:
        regra_mais_acionada, regra_mais_acionada_qtd = ranking_regras[0]
        regra_mais_acionada_nome = REGRAS_DESCRICAO.get(regra_mais_acionada, regra_mais_acionada)
    else:
        regra_mais_acionada = None
        regra_mais_acionada_nome = None
        regra_mais_acionada_qtd = 0

    ganho_estimado_minutos = total * (
        tempo_manual_min_por_registro - tempo_automatizado_min_por_registro
    )

    return OperationalIndicators(
        total_registros=total,
        qtd_validos=qtd_validos,
        pct_validos=_percentual(qtd_validos, total),
        qtd_divergencias=qtd_divergencias,
        pct_divergencias=_percentual(qtd_divergencias, total),
        qtd_ambiguos=qtd_ambiguos,
        pct_ambiguos=_percentual(qtd_ambiguos, total),
        qtd_erros_entrada=qtd_erros_entrada,
        pct_erros_entrada=_percentual(qtd_erros_entrada, total),
        regra_mais_acionada=regra_mais_acionada,
        regra_mais_acionada_nome=regra_mais_acionada_nome,
        regra_mais_acionada_qtd=regra_mais_acionada_qtd,
        taxa_qualidade_entrada=_percentual(total - qtd_erros_entrada, total),
        taxa_revisao_humana=_percentual(qtd_ambiguos, total),
        taxa_retrabalho=_percentual(qtd_divergencias, total),
        ganho_estimado_minutos=ganho_estimado_minutos,
        tempo_manual_min_por_registro=tempo_manual_min_por_registro,
        tempo_automatizado_min_por_registro=tempo_automatizado_min_por_registro,
        ranking_regras=ranking_regras,
    )
