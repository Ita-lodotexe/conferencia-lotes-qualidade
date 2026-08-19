"""Gerador do resumo_executivo.md — Aula 24, Seção 5.4.

Recebe o mesmo OperationalIndicators que alimenta o relatório Excel
(src/aula22_relatorio.py) e devolve o texto em Markdown, em linguagem de
negócio — sem nomes de função, classe, coluna ou código de regra "solto".
Este módulo não grava nada em disco e não conhece a API: quem chama
decide se o texto vai para um arquivo, para uma resposta HTTP, ou os dois
(mesmo padrão de gerar_log_execucao() em src/aula22_relatorio.py).
"""
from __future__ import annotations

from src.operational_indicators import OperationalIndicators

PERIODO_DIAS = 10

OBSERVACAO_GANHO_ESTIMADO = (
    "O ganho de tempo acima é uma estimativa didática, calculada a partir de "
    "premissas de tempo simplificadas — não é uma medição real de produção."
)


def _formatar_qtd_pct(qtd: int, pct: float) -> str:
    return f"{qtd} ({pct:.1f}%)"


def gerar_resumo_executivo(indicadores: OperationalIndicators) -> str:
    """Formata `indicadores` como Markdown de negócio (Seção 5.4).

    Não recalcula nada: todos os números vêm dos campos de `indicadores`,
    garantindo que o texto bata exatamente com o relatório Excel gerado a
    partir do mesmo objeto (ver src/aula22_relatorio.py).
    """
    linhas = [
        "# Resumo Executivo — Conferência de Lotes",
        "",
        "## Visão Geral",
        (
            f"No período analisado ({PERIODO_DIAS} dias), foram processados "
            f"{indicadores.total_registros} registros de conferência de lotes."
        ),
        "",
        "## Indicadores Principais",
        f"- Registros válidos: {_formatar_qtd_pct(indicadores.qtd_validos, indicadores.pct_validos)}",
        f"- Divergências: {_formatar_qtd_pct(indicadores.qtd_divergencias, indicadores.pct_divergencias)}",
        f"- Ambíguos (necessitam revisão humana): {_formatar_qtd_pct(indicadores.qtd_ambiguos, indicadores.pct_ambiguos)}",
        f"- Erros de entrada: {_formatar_qtd_pct(indicadores.qtd_erros_entrada, indicadores.pct_erros_entrada)}",
        f"- Taxa de qualidade da entrada: {indicadores.taxa_qualidade_entrada:.1f}%",
        f"- Taxa de revisão humana: {indicadores.taxa_revisao_humana:.1f}%",
        f"- Taxa de retrabalho: {indicadores.taxa_retrabalho:.1f}%",
        "",
        "## Destaque",
    ]

    if indicadores.regra_mais_acionada is None:
        linhas.append(
            "Nenhuma divergência, ambiguidade ou erro de entrada foi registrada no período — "
            "não há um problema recorrente a destacar."
        )
    else:
        linhas.append(
            f"O problema mais recorrente no período foi \"{indicadores.regra_mais_acionada_nome}\", "
            f"responsável por {indicadores.regra_mais_acionada_qtd} ocorrência(s)."
        )

    linhas += [
        "",
        "## Ganho Estimado de Tempo",
        (
            f"A automação da conferência representa um ganho estimado de "
            f"{indicadores.ganho_estimado_minutos:.1f} minutos no período, considerando as "
            f"seguintes premissas: conferência manual levaria em média "
            f"{indicadores.tempo_manual_min_por_registro:.1f} minuto(s) por registro, contra "
            f"{indicadores.tempo_automatizado_min_por_registro:.1f} minuto(s) por registro com a automação."
        ),
        "",
        "## Observação",
        OBSERVACAO_GANHO_ESTIMADO,
    ]

    return "\n".join(linhas) + "\n"
