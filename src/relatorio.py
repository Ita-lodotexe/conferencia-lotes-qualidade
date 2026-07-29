"""
Módulo de geração do relatório de divergências (Issue #5).

Aplica as regras de negócio RN01-RN07, já implementadas em
``src/modules/``, sobre a planilha de lotes recebida e monta um relatório
de divergências em .xlsx com duas abas: "Resumo" e "Divergencias".

Convênio 005/2025 (INOVA, IFAM, LG Electronics do Brasil).
"""

from __future__ import annotations

import pandas as pd

from src.modules.validacao import valida_campos_obrigatorios, valida_estrutura
from src.modules.verificacao_lotes import verificar_status_lote
from src.modules.normalizacao_status import validar_status
from src.modules.observacao import lote_conforme_rn07

REGRAS_DESCRICAO = {
    "RN01": "Estrutura da planilha",
    "RN02": "Campo obrigatório vazio",
    "RN03": "Existência/status do lote",
    "RN06": "Status ambíguo",
    "RN07": "Observação em lote reprovado",
}


def gerar_relatorio(relatorio: pd.DataFrame, caminho_saida: str) -> dict:
    """Gera o relatório de divergências de uma planilha de lotes.

    Args:
        relatorio: planilha de lotes já carregada em um DataFrame.
        caminho_saida: caminho onde o .xlsx de divergências será escrito.

    Returns:
        dict com "resumo" (métricas agregadas), "divergencias" (lista de
        ocorrências) e "arquivo" (caminho_saida, para conveniência).
    """
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

    for ocorrencia in valida_campos_obrigatorios(relatorio):
        linha = ocorrencia["linha"]
        lote_id = relatorio.loc[linha, "lote_id"]
        divergencias.append(
            {
                "linha": linha,
                "lote_id": lote_id,
                "regra": "RN02",
                "descricao": f"Campo obrigatório '{ocorrencia['campo']}' vazio.",
            }
        )

    for indice, linha in relatorio.iterrows():
        numero_linha = indice + 2
        lote_id = linha.get("lote_id")

        status_lote = verificar_status_lote(lote_id) if pd.notna(lote_id) else None
        if status_lote is None:
            divergencias.append(
                {
                    "linha": numero_linha,
                    "lote_id": lote_id,
                    "regra": "RN03",
                    "descricao": f"Lote '{lote_id}' não encontrado na base de referência.",
                }
            )
        elif status_lote is False:
            divergencias.append(
                {
                    "linha": numero_linha,
                    "lote_id": lote_id,
                    "regra": "RN03",
                    "descricao": f"Lote '{lote_id}' está inativo na base de referência.",
                }
            )

        resultado_status = validar_status(linha.get("status"))
        if resultado_status["ambiguo"]:
            divergencias.append(
                {
                    "linha": numero_linha,
                    "lote_id": lote_id,
                    "regra": "RN06",
                    "descricao": f"Status '{resultado_status['status_original']}' é ambíguo e requer revisão manual.",
                }
            )

        observacao = linha.get("observacao")
        lote_normalizado = {
            "status": resultado_status["status_normalizado"],
            "observacao": None if pd.isna(observacao) else observacao,
        }
        if not lote_conforme_rn07(lote_normalizado):
            divergencias.append(
                {
                    "linha": numero_linha,
                    "lote_id": lote_id,
                    "regra": "RN07",
                    "descricao": "Lote reprovado sem observação preenchida.",
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
