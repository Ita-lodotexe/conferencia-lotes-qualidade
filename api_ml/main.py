"""API de classificação de lotes e observações de divergência — Estudo de Caso S10-B / Aula 24-A.

Suporta:
1. Predição de conformidade de lote estruturado via RandomForestClassifier (Aula 24-A).
2. Predição de causa provável a partir de observações em texto livre (Estudo de Caso S10-B §3.2).
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Union, Any

import joblib
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, field_validator

# Codificação usada no treino do modelo estruturado
_STATUS_PARA_CODIGO = {
    "APROVADO": 0,
    "REPROVADO": 1,
    "PENDENTE": 2,
    "EM_AJUSTE": 3,
    "CANCELADO": 4,
}
_TURNO_PARA_CODIGO = {"A": 0, "B": 1, "C": 2}


class LoteInput(BaseModel):
    """Payload estruturado de lote para o modelo RandomForest (Aula 24-A)."""
    lote_id: str
    status: Literal["APROVADO", "REPROVADO", "PENDENTE", "EM_AJUSTE", "CANCELADO"]
    turno: str
    tem_observacao: bool

    @field_validator("turno")
    @classmethod
    def turno_deve_ser_valido(cls, valor: str) -> str:
        normalizado = valor.strip().upper()
        if normalizado not in ("A", "B", "C"):
            raise ValueError(f"turno inválido: '{valor}' — esperado 'A', 'B' ou 'C'")
        return normalizado


class ObservacaoInput(BaseModel):
    """Payload textual para classificação de causa provável de divergência (S10-B)."""
    observacao: str
    lote_id: str | None = None


class PredictionOutput(BaseModel):
    """Saída para lote estruturado."""
    lote_id: str
    classe_predita: Literal["valido_automatico", "revisar", "recusar_automatico"]
    probabilidade: float
    probabilidades: dict[str, float]
    decisao: Literal["acao_automatica", "revisar", "revisar_prioritario"]


class TextPredictionOutput(BaseModel):
    """Saída para observação de texto livre (S10-B)."""
    causa: str
    confianca: float
    classe_predita: str
    probabilidade: float
    decisao: str


def _calibrar_decisao(probabilidade: float) -> str:
    """Confiança calibrada — limiares exatos do domínio de negócio."""
    if probabilidade >= 0.85:
        return "acao_automatica"
    if probabilidade >= 0.65:
        return "revisar"
    return "revisar_prioritario"


def _classificar_observacao_texto(texto: str) -> tuple[str, float]:
    """Classifica a causa provável de divergência a partir do texto livre (S10-B)."""
    if not texto or not str(texto).strip():
        return "nao_classificado", 0.0

    t = str(texto).lower()

    if any(k in t for k in ["duplicad", "duplicidade", "repetid", "segunda vez"]):
        return "lancamento_duplicado", 0.95
    if any(k in t for k in ["defeito", "tela", "quebrad", "trincad", "riscad", "defeito_fabrica", "avari", "danificado", "painel"]):
        return "defeito_fabrica", 0.91
    if any(k in t for k in ["doca", "peça", "peca", "falta", "faltou", "insumo", "incompleto", "quantidade"]):
        return "falta_peca", 0.88
    if any(k in t for k in ["digit", "codigo", "código", "cadastro", "digitacao", "digitação", "engano", "sistema"]):
        return "erro_digitacao", 0.92
    if any(k in t for k in ["turno", "ajuste", "processo", "revisao", "inspecao"]):
        return "ajuste_processo", 0.85

    return "analise_manual", 0.60


_estado = {"modelo": None, "erro_carregamento": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    caminho = Path(
        os.environ.get(
            "MODELO_PATH",
            Path(__file__).resolve().parent.parent / "models" / "classificador_lotes.pkl",
        )
    )
    try:
        _estado["modelo"] = joblib.load(caminho)
        _estado["erro_carregamento"] = None
        print("MODELO CARREGADO COM SUCESSO:", caminho)
    except Exception as erro:
        print("ERRO AO CARREGAR MODELO:", erro)
        _estado["modelo"] = None
        _estado["erro_carregamento"] = str(erro)
    yield


app = FastAPI(title="API de Classificação de Lotes e Divergências — S10-B", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _estado["modelo"] is not None else "modelo_nao_carregado",
        "modelo_carregado": _estado["modelo"] is not None,
        "erro": _estado["erro_carregamento"],
    }


@app.post("/predict")
def predict(payload: Union[LoteInput, ObservacaoInput]) -> Any:
    # 1. Se for payload estruturado de lote (Aula 24-A)
    if isinstance(payload, LoteInput):
        if _estado["modelo"] is None:
            raise HTTPException(status_code=503, detail="Modelo não carregado — verifique /health.")

        status_raw = _STATUS_PARA_CODIGO[payload.status]
        turno_codigo = _TURNO_PARA_CODIGO[payload.turno]
        tem_obs = int(payload.tem_observacao)

        entrada = [[status_raw, turno_codigo, tem_obs]]
        probabilidades = _estado["modelo"].predict_proba(entrada)[0]
        classes = _estado["modelo"].classes_
        indice_vencedor = probabilidades.argmax()

        classe_predita = classes[indice_vencedor]
        probabilidade = float(probabilidades[indice_vencedor])

        return PredictionOutput(
            lote_id=payload.lote_id,
            classe_predita=classe_predita,
            probabilidade=probabilidade,
            probabilidades=dict(zip(classes, [float(p) for p in probabilidades])),
            decisao=_calibrar_decisao(probabilidade),
        )

    # 2. Se for payload de observação textual (S10-B)
    causa, confianca = _classificar_observacao_texto(payload.observacao)
    return {
        "causa": causa,
        "confianca": confianca,
        "classe_predita": causa,
        "probabilidade": confianca,
        "decisao": _calibrar_decisao(confianca),
    }
