"""API de classificação de lotes — Exercício 24-A (Seção 3.2).

Serve o RandomForestClassifier treinado por train_model.py (raiz do
repositório) por HTTP. O bot de conferência de lotes nunca importa
scikit-learn nem o .pkl diretamente — só fala com esta API, para manter
a separação de responsabilidades (Seção 7): o bot decide o que fazer
com uma predição, esta API só decide o que o modelo prevê.

Isolado em api_ml/ de propósito: vai virar um container próprio no
Commit 3, com seu próprio requirements.txt e Dockerfile, independente
do restante do projeto.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

import joblib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, field_validator

# Codificação usada no treino (train_model.py, raiz do repositório).
# DUPLICADA aqui de propósito, não importada: api_ml/ vai virar um
# container isolado (Commit 3) que pode não ter acesso ao restante do
# repositório no build. Se o encoding do treino mudar, este dicionário
# tem que ser atualizado manualmente — se o projeto crescer, isso pode
# virar um pacote compartilhado entre bot/API/treino, mas por ora a
# duplicação documentada é mais segura que um import cross-serviço frágil.
_STATUS_PARA_CODIGO = {
    "APROVADO": 0,
    "REPROVADO": 1,
    "PENDENTE": 2,
    "EM_AJUSTE": 3,
    "CANCELADO": 4,
}
_TURNO_PARA_CODIGO = {"A": 0, "B": 1, "C": 2}


class LoteInput(BaseModel):
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


class PredictionOutput(BaseModel):
    lote_id: str
    classe_predita: Literal["valido_automatico", "revisar", "recusar_automatico"]
    probabilidade: float
    probabilidades: dict[str, float]
    decisao: Literal["acao_automatica", "revisar", "revisar_prioritario"]


def _calibrar_decisao(probabilidade: float) -> str:
    """Confiança calibrada (Seção 3.2) — limiares exatos do enunciado."""
    if probabilidade >= 0.85:
        return "acao_automatica"
    if probabilidade >= 0.65:
        return "revisar"
    return "revisar_prioritario"


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
    except Exception as erro:
        _estado["modelo"] = None
        _estado["erro_carregamento"] = str(erro)
    yield


app = FastAPI(title="API de Classificação de Lotes — Exercício 24-A", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok" if _estado["modelo"] is not None else "modelo_nao_carregado",
        "modelo_carregado": _estado["modelo"] is not None,
        "erro": _estado["erro_carregamento"],
    }


@app.post("/predict", response_model=PredictionOutput)
def predict(lote: LoteInput) -> PredictionOutput:
    if _estado["modelo"] is None:
        raise HTTPException(status_code=503, detail="Modelo não carregado — verifique /health.")

    status_raw = _STATUS_PARA_CODIGO[lote.status]
    turno_codigo = _TURNO_PARA_CODIGO[lote.turno]
    tem_obs = int(lote.tem_observacao)

    entrada = [[status_raw, turno_codigo, tem_obs]]
    probabilidades = _estado["modelo"].predict_proba(entrada)[0]
    classes = _estado["modelo"].classes_
    indice_vencedor = probabilidades.argmax()

    classe_predita = classes[indice_vencedor]
    probabilidade = float(probabilidades[indice_vencedor])

    return PredictionOutput(
        lote_id=lote.lote_id,
        classe_predita=classe_predita,
        probabilidade=probabilidade,
        probabilidades=dict(zip(classes, [float(p) for p in probabilidades])),
        decisao=_calibrar_decisao(probabilidade),
    )
