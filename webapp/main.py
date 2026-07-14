"""
Interface web do Bot de Conferência de Lotes (Issue de UI web).

Módulo independente: expõe uma API (FastAPI) que recebe o relatório
original, roda `gerar_relatorio()` (src/relatorio.py) e devolve o resumo
em JSON + o .xlsx de divergências para download. Serve também a página
única (HTML/CSS/JS) em `webapp/static/`.

Convênio 005/2025 (INOVA, IFAM, LG Electronics do Brasil).
"""

from __future__ import annotations

import io
import tempfile
import uuid
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.relatorio import gerar_relatorio

STATIC_DIR = Path(__file__).resolve().parent / "static"
EXTENSOES_ACEITAS = (".xlsx", ".xls", ".csv")

app = FastAPI(title="Bot de Conferência de Lotes")

_relatorios_gerados: dict[str, Path] = {}


def _ler_planilha(nome_arquivo: str, conteudo: bytes) -> pd.DataFrame:
    nome = (nome_arquivo or "").lower()
    buffer = io.BytesIO(conteudo)

    if not nome.endswith(EXTENSOES_ACEITAS):
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Envie um arquivo .xlsx ou .csv.",
        )

    try:
        if nome.endswith(".csv"):
            return pd.read_csv(buffer)
        return pd.read_excel(buffer)
    except Exception as erro:
        raise HTTPException(
            status_code=400,
            detail=f"Não foi possível ler o arquivo enviado: {erro}",
        ) from erro


@app.post("/api/relatorios")
async def criar_relatorio(arquivo: UploadFile = File(...)) -> dict:
    conteudo = await arquivo.read()
    planilha = _ler_planilha(arquivo.filename or "", conteudo)

    if planilha.empty:
        raise HTTPException(status_code=400, detail="A planilha enviada está vazia.")

    relatorio_id = uuid.uuid4().hex
    caminho_saida = Path(tempfile.gettempdir()) / f"relatorio_divergencias_{relatorio_id}.xlsx"

    resultado = gerar_relatorio(planilha, str(caminho_saida))
    _relatorios_gerados[relatorio_id] = caminho_saida

    return {
        "id": relatorio_id,
        "resumo": resultado["resumo"],
        "divergencias": resultado["divergencias"],
    }


@app.get("/api/relatorios/{relatorio_id}/download")
def baixar_relatorio(relatorio_id: str) -> FileResponse:
    caminho = _relatorios_gerados.get(relatorio_id)
    if caminho is None or not caminho.exists():
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    return FileResponse(
        caminho,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="relatorio_divergencias.xlsx",
    )


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
