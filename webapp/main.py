"""
Interface web do projeto (Aula 22 — Dashboard Excel e Relatórios).

Recebe o upload de `inspecao_lotes_10dias.xlsx`, roda o mesmo pipeline
do README (carregar_planilha_10dias -> classificar_lotes ->
gerar_relatorio_aula22), expõe o resultado por API e serve o frontend
(upload + preview + download) em webapp/static/.
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from src.aula22_classificacao import classificar_lotes
from src.aula22_preprocessador import carregar_planilha_10dias
from src.aula22_relatorio import gerar_relatorio_aula22

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Conferência de Lotes — Dashboard Aula 22")

EXTENSOES_ACEITAS = (".xlsx", ".xls")

# id -> {"arquivo": Path do .xlsx gerado, "resumo": dict, "log": str}
_dashboards_gerados: dict[str, dict] = {}


def _classificar_upload(nome_arquivo: str, conteudo: bytes) -> list:
    """Salva o upload num arquivo temporário e roda o pipeline de classificação.

    carregar_planilha_10dias lê de um caminho em disco (via
    pd.ExcelFile), não de bytes em memória — por isso o passo
    intermediário de escrever num arquivo temporário.

    No Windows, um arquivo aberto por um handle (o do
    NamedTemporaryFile) não pode ser reaberto por outro processo/handle
    (o do pandas) enquanto o primeiro não for fechado — daí o
    PermissionError [Errno 13] quando isso é feito dentro do mesmo
    bloco "with". Por isso aqui: criamos com delete=False, fechamos
    explicitamente antes de chamar carregar_planilha_10dias, e
    apagamos manualmente no final (bloco finally).
    """
    nome = (nome_arquivo or "").lower()
    if not nome.endswith(EXTENSOES_ACEITAS):
        raise HTTPException(
            status_code=400,
            detail="Formato não suportado. Envie um arquivo .xlsx ou .xls.",
        )

    arquivo_temporario = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    try:
        arquivo_temporario.write(conteudo)
        arquivo_temporario.close()  # libera o handle antes do pandas reabrir o arquivo (necessário no Windows)

        try:
            registros_por_dia, base_referencia = carregar_planilha_10dias(arquivo_temporario.name)
        except ValueError as erro:
            raise HTTPException(status_code=400, detail=str(erro)) from erro
        except Exception as erro:
            raise HTTPException(
                status_code=400,
                detail=f"Não foi possível ler o arquivo enviado: {erro}",
            ) from erro
    finally:
        try:
            Path(arquivo_temporario.name).unlink(missing_ok=True)
        except PermissionError:
            # No Windows, pandas/openpyxl às vezes mantém o handle do
            # arquivo aberto internamente (via ExcelFile não fechado)
            # mesmo depois de já termos lido os dados. Isso não afeta o
            # resultado — é só um arquivo temporário que o SO limpa
            # sozinho mais tarde — então não deixamos isso quebrar a
            # resposta ao usuário.
            pass

    return classificar_lotes(registros_por_dia, base_referencia)


@app.post("/api/aula22/dashboard")
async def criar_dashboard(arquivo: UploadFile = File(...)) -> dict:
    conteudo = await arquivo.read()
    registros = _classificar_upload(arquivo.filename or "", conteudo)

    if not registros:
        raise HTTPException(status_code=400, detail="Nenhum registro encontrado na planilha enviada.")

    dashboard_id = uuid.uuid4().hex
    caminho_saida = Path(tempfile.gettempdir()) / f"relatorio_conferencia_lotes_{dashboard_id}.xlsx"

    resultado = gerar_relatorio_aula22(registros, str(caminho_saida))

    resumo = resultado["resumo"]
    evolucao_por_dia = [{"dia": dia, **valores} for dia, valores in resumo["evolucao_por_dia"].items()]

    _dashboards_gerados[dashboard_id] = {
        "arquivo": caminho_saida,
        "resumo": resumo,
        "log": resultado["log"],
    }

    return {
        "id": dashboard_id,
        "total": resumo["total"],
        "por_classificacao": resumo["por_classificacao"],
        "percentual": resumo["percentual"],
        "evolucao_por_dia": evolucao_por_dia,
    }


@app.get("/api/aula22/dashboard/{dashboard_id}/download")
def baixar_dashboard(dashboard_id: str) -> FileResponse:
    dados = _dashboards_gerados.get(dashboard_id)
    if dados is None or not dados["arquivo"].exists():
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    return FileResponse(
        dados["arquivo"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="relatorio_conferencia_lotes.xlsx",
    )


@app.get("/api/aula22/dashboard/{dashboard_id}/log")
def obter_log(dashboard_id: str) -> PlainTextResponse:
    dados = _dashboards_gerados.get(dashboard_id)
    if dados is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado.")

    return PlainTextResponse(dados["log"])


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")