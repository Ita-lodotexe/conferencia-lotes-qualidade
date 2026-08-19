"""Encaminhamento de registros Ambíguo (RN09) para o modelo de ML (Seção 3.3).

Só os registros com classificacao == "Ambíguo" chegam aqui — Válido,
Divergência e Erro de Entrada já têm uma decisão fechada e não passam
pelo modelo. Mesmo entre os Ambíguos, só uma parte é elegível: ver
STATUS_AMBIGUO_PARA_ML abaixo.
"""
from __future__ import annotations

from src.aula22_classificacao import RegistroValidado
from src.ml_client import MLClient

# status_normalizado (RN09) é texto livre — "EM AJUSTE", "CANCELADO",
# "REPROV.", "APROVADO PARCIAL", "AGUARDANDO REINSPEÇÃO" ou qualquer
# outra string não reconhecida pela RN04. Só "EM AJUSTE" e "CANCELADO"
# têm correspondência clara com as 5 categorias que o modelo conhece
# (APROVADO/REPROVADO/PENDENTE/EM_AJUSTE/CANCELADO); os demais não
# devem ser enviados ao modelo — enviar, por exemplo, "REPROV." como se
# fosse REPROVADO seria o bot inventando um significado que a RN09 não
# capturou. Esses casos ficam Ambíguo para revisão humana, sem chamar a
# API — não é o fallback de falha (REVISAO_ML_OFFLINE), é uma decisão
# de "não aplicável", tratada e testada separadamente.
STATUS_AMBIGUO_PARA_ML = {
    "EM AJUSTE": "EM_AJUSTE",
    "CANCELADO": "CANCELADO",
}

TURNOS_VALIDOS = {"A", "B", "C"}


def _resultado(
    lote_id: str,
    entrou_no_ml: bool,
    classe_ml: str | None = None,
    probabilidade_ml: float | None = None,
    decisao_ml: str | None = None,
    latencia_ms: float | None = None,
    motivo: str | None = None,
) -> dict:
    """Forma estável de retorno — todo caminho de processar_item_ambiguo
    passa por aqui, para alimentar a 9ª aba do Excel e o log estruturado
    (próximo commit) sem variação de formato entre os caminhos."""
    return {
        "lote_id": lote_id,
        "entrou_no_ml": entrou_no_ml,
        "classe_ml": classe_ml,
        "probabilidade_ml": probabilidade_ml,
        "decisao_ml": decisao_ml,
        "latencia_ms": latencia_ms,
        "motivo": motivo,
    }


def processar_item_ambiguo(registro: RegistroValidado, ml_client: MLClient) -> dict:
    """Decide se `registro` é elegível para o modelo e, se for, consulta
    `ml_client`. Nunca lança — API fora do ar cai no fallback
    REVISAO_ML_OFFLINE, e o processamento do lote continua.
    """
    turno = (registro.turno or "").strip().upper()
    if turno not in TURNOS_VALIDOS:
        return _resultado(
            registro.lote_id,
            entrou_no_ml=False,
            motivo=f"turno inválido para o modelo: '{registro.turno}'",
        )

    status_normalizado = (registro.status_normalizado or "").strip().upper()
    status_ml = STATUS_AMBIGUO_PARA_ML.get(status_normalizado)
    if status_ml is None:
        return _resultado(
            registro.lote_id,
            entrou_no_ml=False,
            motivo="status não mapeado para o modelo",
        )

    tem_observacao = bool(registro.observacao.strip())
    resultado_ml = ml_client.classificar(
        lote_id=registro.lote_id,
        status=status_ml,
        turno=turno,
        tem_observacao=tem_observacao,
    )

    if resultado_ml is None:
        return _resultado(
            registro.lote_id,
            entrou_no_ml=True,
            classe_ml="REVISAO_ML_OFFLINE",
            motivo="API de ML indisponível — bot continuou processando",
        )

    return _resultado(
        registro.lote_id,
        entrou_no_ml=True,
        classe_ml=resultado_ml.get("classe_predita"),
        probabilidade_ml=resultado_ml.get("probabilidade"),
        decisao_ml=resultado_ml.get("decisao"),
        latencia_ms=resultado_ml.get("latencia_ms"),
    )


def processar_registros_ambiguos(
    registros: list[RegistroValidado], ml_client: MLClient
) -> list[dict]:
    """Aplica processar_item_ambiguo a cada registro Ambíguo de `registros`,
    calculado uma única vez — mesmo padrão de src/operational_indicators.py."""
    return [
        processar_item_ambiguo(registro, ml_client)
        for registro in registros
        if registro.classificacao == "Ambíguo"
    ]
