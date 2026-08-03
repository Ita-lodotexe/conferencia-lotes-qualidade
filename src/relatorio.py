"""
Módulo de geração do relatório de divergências (Issue #5).

Aplica as regras de negócio RN01-RN07, já implementadas em
``src/modules/``, sobre a planilha de lotes recebida e monta um relatório
de divergências em .xlsx com duas abas: "Resumo" e "Divergencias".

Convênio 005/2025 (INOVA, IFAM, LG Electronics do Brasil).
"""

from __future__ import annotations

import pandas as pd

from src.modules.validacao import (
    COLUNAS_ESPERADAS,
    valida_campos_obrigatorios,
    valida_estrutura,
)
from src.modules.verificacao_lotes import carregar_base_referencia, verificar_status_lote
from src.modules.normalizacao_status import validar_status
from src.modules.observacao import lote_conforme_rn07

CAMINHO_BASE_REFERENCIA = "data/processed/base_lotes_referencia.csv"

REGRAS_DESCRICAO = {
    "INFRA": "Erro de infraestrutura",
    "RN01": "Estrutura da planilha",
    "RN02": "Campo obrigatório vazio",
    "RN03": "Existência/status do lote",
    "RN06": "Status ambíguo",
    "RN07": "Observação em lote reprovado",
}


def avaliar_lote(lote: dict, base_referencia: pd.DataFrame) -> list[dict]:
    """Aplica RN02-RN07 sobre um único lote e retorna divergências.

    RN01 (estrutura) não é aplicável a um único lote — é responsabilidade
    do chamador validar que todas as chaves esperadas estão presentes
    antes de invocar esta função. RN02-RN07 são aplicadas em ordem:
    campos obrigatórios, existência do lote, normalização/validação de
    status (incluindo RN06 ambíguo), e observação em reprovado.

    Args:
        lote: dict com pelo menos as chaves de COLUNAS_ESPERADAS
            (lote_id, produto, linha, turno, status, responsavel, data,
            observacao). Valores como string vazia ou None são tratados
            como "vazio" nas regras que dependem disso.
        base_referencia: DataFrame carregado via carregar_base_referencia,
            com pelo menos as colunas lote_id e status_cadastro.

    Returns:
        Lista de divergências. Cada divergência é um dict com chaves
        'regra' (RN02-RN07), 'campo' (quando aplicável), 'descricao'.
        Lista vazia significa lote 100% conforme.
    """
    divergencias: list[dict] = []

    # RN02 — reaproveita a validação de campos obrigatórios do módulo de
    # validação, para manter a mesma semântica de "vazio" (None, NaN ou
    # texto em branco) usada no restante do projeto.
    for ocorrencia in valida_campos_obrigatorios(pd.DataFrame([lote])):
        divergencias.append(
            {
                "regra": "RN02",
                "campo": ocorrencia["campo"],
                "descricao": f"Campo obrigatório '{ocorrencia['campo']}' vazio.",
            }
        )

    lote_id = lote.get("lote_id")

    # RN03 — existência e situação cadastral do lote na base de referência.
    status_lote = verificar_status_lote(base_referencia, lote_id) if pd.notna(lote_id) else None
    if status_lote is None:
        divergencias.append(
            {
                "regra": "RN03",
                "campo": "lote_id",
                "descricao": f"Lote '{lote_id}' não encontrado na base de referência.",
            }
        )
    elif status_lote is False:
        divergencias.append(
            {
                "regra": "RN03",
                "campo": "lote_id",
                "descricao": f"Lote '{lote_id}' está inativo na base de referência.",
            }
        )

    # RN04/RN05/RN06 — validar_status normaliza (RN05) e classifica como
    # ambíguo (RN06) tudo o que não é status permitido (RN04).
    resultado_status = validar_status(lote.get("status"))
    if resultado_status["ambiguo"]:
        divergencias.append(
            {
                "regra": "RN06",
                "campo": "status",
                "descricao": f"Status '{resultado_status['status_original']}' é ambíguo e requer revisão manual.",
            }
        )

    # RN07 — recebe o status já normalizado ('REPROVADO'), nunca o valor
    # bruto, para não depender das variações aceitas pela RN05.
    observacao = lote.get("observacao")
    lote_normalizado = {
        "lote_id": lote_id,
        "status": resultado_status["status_normalizado"],
        "observacao": None if pd.isna(observacao) else observacao,
    }
    if not lote_conforme_rn07(lote_normalizado):
        divergencias.append(
            {
                "regra": "RN07",
                "campo": "observacao",
                "descricao": "Lote reprovado sem observação preenchida.",
            }
        )

    return divergencias


def gerar_relatorio(relatorio: pd.DataFrame, caminho_saida: str) -> dict:
    """Gera o relatório de divergências de uma planilha de lotes.

    Args:
        relatorio: planilha de lotes já carregada em um DataFrame.
        caminho_saida: caminho onde o .xlsx de divergências será escrito.

    Returns:
        dict com "resumo" (métricas agregadas), "divergencias" (lista de
        ocorrências) e "arquivo" (caminho_saida, para conveniência).
    """
    try:
        base_referencia = carregar_base_referencia(CAMINHO_BASE_REFERENCIA)
    except Exception as erro:
        divergencias = [
            {
                "linha": None,
                "lote_id": None,
                "regra": "INFRA",
                "descricao": f"Não foi possível carregar a base de referência de lotes: {erro}",
            }
        ]
        resumo = _monta_resumo(relatorio, divergencias, estrutura_valida=False)
        _exporta_divergencias(divergencias, resumo, caminho_saida)
        return {"resumo": resumo, "divergencias": divergencias, "arquivo": caminho_saida}

    campos_faltantes = valida_estrutura(relatorio)

    if campos_faltantes:
        divergencias = [
            {
                "linha": None,
                "lote_id": None,
                "regra": "RN01",
                "descricao": f"Colunas ausentes na planilha: {', '.join(campos_faltantes)}.",
            }
        ]
        resumo = _monta_resumo(relatorio, divergencias, estrutura_valida=False)
        _exporta_divergencias(divergencias, resumo, caminho_saida)
        return {"resumo": resumo, "divergencias": divergencias, "arquivo": caminho_saida}

    divergencias = []

    avaliacoes = []
    for indice, linha in relatorio.iterrows():
        lote = {coluna: linha.get(coluna) for coluna in COLUNAS_ESPERADAS}
        avaliacoes.append((indice, lote.get("lote_id"), avaliar_lote(lote, base_referencia)))

    # As duas passadas abaixo preservam o formato histórico do relatório:
    # as divergências RN02 vêm primeiro e referenciam o índice do
    # DataFrame, enquanto as demais vêm depois e referenciam o número da
    # linha na planilha (índice + 2).
    for indice, lote_id, divergencias_do_lote in avaliacoes:
        for divergencia in divergencias_do_lote:
            if divergencia["regra"] != "RN02":
                continue
            divergencias.append(
                {
                    "linha": indice,
                    "lote_id": lote_id,
                    "regra": divergencia["regra"],
                    "descricao": divergencia["descricao"],
                }
            )

    for indice, lote_id, divergencias_do_lote in avaliacoes:
        for divergencia in divergencias_do_lote:
            if divergencia["regra"] == "RN02":
                continue
            divergencias.append(
                {
                    "linha": indice + 2,
                    "lote_id": lote_id,
                    "regra": divergencia["regra"],
                    "descricao": divergencia["descricao"],
                }
            )

    resumo = _monta_resumo(relatorio, divergencias, estrutura_valida=True)
    _exporta_divergencias(divergencias, resumo, caminho_saida)
    return {"resumo": resumo, "divergencias": divergencias, "arquivo": caminho_saida}


def _monta_resumo(relatorio: pd.DataFrame, divergencias: list[dict], estrutura_valida: bool) -> dict:
    total_lotes = len(relatorio)
    lotes_com_divergencia = len({d["lote_id"] for d in divergencias if d["lote_id"] is not None})

    divergencias_por_regra = {regra: 0 for regra in REGRAS_DESCRICAO}
    for divergencia in divergencias:
        divergencias_por_regra[divergencia["regra"]] += 1

    return {
        "estrutura_valida": estrutura_valida,
        "total_lotes": total_lotes,
        "lotes_com_divergencia": lotes_com_divergencia,
        "lotes_conformes": max(total_lotes - lotes_com_divergencia, 0) if estrutura_valida else 0,
        "total_divergencias": len(divergencias),
        "divergencias_por_regra": divergencias_por_regra,
    }


def _exporta_divergencias(divergencias: list[dict], resumo: dict, caminho_saida: str) -> None:
    colunas_divergencias = ["regra", "lote_id", "linha", "descricao"]
    df_divergencias = pd.DataFrame(divergencias, columns=colunas_divergencias)

    linhas_resumo = [
        {"metrica": "Estrutura válida", "valor": "Sim" if resumo["estrutura_valida"] else "Não"},
        {"metrica": "Total de lotes", "valor": resumo["total_lotes"]},
        {"metrica": "Lotes conformes", "valor": resumo["lotes_conformes"]},
        {"metrica": "Lotes com divergência", "valor": resumo["lotes_com_divergencia"]},
        {"metrica": "Total de divergências", "valor": resumo["total_divergencias"]},
    ]
    for regra, descricao in REGRAS_DESCRICAO.items():
        linhas_resumo.append(
            {
                "metrica": f"Divergências {regra} ({descricao})",
                "valor": resumo["divergencias_por_regra"][regra],
            }
        )
    df_resumo = pd.DataFrame(linhas_resumo)

    with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
        df_resumo.to_excel(writer, sheet_name="Resumo", index=False)
        df_divergencias.to_excel(writer, sheet_name="Divergencias", index=False)


if __name__ == "__main__":
    df = pd.read_csv("data/processed/dados_relatorio.csv")
    resultado = gerar_relatorio(df, "data/relatorio_divergencias.xlsx")
    print(resultado["resumo"])
