"""Testes da API de classificação de lotes (Exercício 24-A, Seção 3.2/4.7).

Usa fastapi.testclient.TestClient sobre api_ml.main.app, com o modelo
real carregado via lifespan (o .pkl gerado por train_model.py precisa
existir em models/classificador_lotes.pkl para estes testes rodarem).
"""
import api_ml.main as api_ml_main
import pytest
from fastapi.testclient import TestClient

from api_ml.main import app, _calibrar_decisao

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


class TestCalibrarDecisao:
    """As 3 faixas dos limiares 0.85/0.65 (Seção 3.2) — o teste de
    payload válido só exercita a faixa em que o modelo real caiu, então
    aqui testamos _calibrar_decisao() diretamente para cobrir as outras
    duas sem depender da sorte de qual classe o RandomForest prevê."""

    def test_probabilidade_alta_e_acao_automatica(self):
        assert _calibrar_decisao(0.85) == "acao_automatica"
        assert _calibrar_decisao(0.99) == "acao_automatica"

    def test_probabilidade_media_e_revisar(self):
        assert _calibrar_decisao(0.65) == "revisar"
        assert _calibrar_decisao(0.84) == "revisar"

    def test_probabilidade_baixa_e_revisar_prioritario(self):
        assert _calibrar_decisao(0.0) == "revisar_prioritario"
        assert _calibrar_decisao(0.64) == "revisar_prioritario"


def test_predict_com_payload_valido_retorna_200_e_decisao_calibrada(client):
    resposta = client.post(
        "/predict",
        json={"lote_id": "L001", "status": "APROVADO", "turno": "A", "tem_observacao": False},
    )

    assert resposta.status_code == 200
    corpo = resposta.json()

    assert corpo["lote_id"] == "L001"
    assert corpo["classe_predita"] in ("valido_automatico", "revisar", "recusar_automatico")
    assert set(corpo["probabilidades"].keys()) == {
        "valido_automatico", "revisar", "recusar_automatico",
    }
    assert corpo["probabilidade"] == pytest.approx(
        corpo["probabilidades"][corpo["classe_predita"]]
    )
    # A decisão tem que ser exatamente a calibração dos mesmos limiares
    # 0.85/0.65 aplicada à probabilidade retornada — sem hard-code do
    # resultado esperado, para o teste não quebrar se o modelo mudar.
    assert corpo["decisao"] == _calibrar_decisao(corpo["probabilidade"])


def test_predict_com_turno_invalido_retorna_422(client):
    resposta = client.post(
        "/predict",
        json={"lote_id": "L002", "status": "APROVADO", "turno": "X", "tem_observacao": False},
    )

    assert resposta.status_code == 422


def test_health_com_modelo_carregado_retorna_status_ok(client):
    resposta = client.get("/health")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "ok"
    assert corpo["modelo_carregado"] is True
    assert corpo["erro"] is None


@pytest.fixture
def cliente_com_modelo_ausente(monkeypatch, tmp_path):
    """Simula em automatizado o que o Formulário de Revisão por Pares
    pede manualmente ("renomear o .pkl e checar a resposta"): aponta
    MODELO_PATH para um caminho que não existe. lifespan lê a env var a
    cada novo `with TestClient(app)` (startup), então isso troca o
    modelo carregado só para este teste — restaura o estado original em
    seguida, para não vazar para os outros testes deste arquivo, que
    dependem do modelo real carregado.
    """
    estado_original = dict(api_ml_main._estado)
    monkeypatch.setenv("MODELO_PATH", str(tmp_path / "nao_existe.pkl"))

    with TestClient(app) as client:
        yield client

    api_ml_main._estado["modelo"] = estado_original["modelo"]
    api_ml_main._estado["erro_carregamento"] = estado_original["erro_carregamento"]


def test_health_com_modelo_ausente_nao_derruba_o_processo(cliente_com_modelo_ausente):
    """A API sobe normalmente mesmo com o .pkl inacessível — só fica com
    modelo_carregado=False, em vez de derrubar o processo no startup."""
    resposta = cliente_com_modelo_ausente.get("/health")

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "modelo_nao_carregado"
    assert corpo["modelo_carregado"] is False
    assert corpo["erro"] is not None


def test_predict_com_modelo_ausente_retorna_503_em_vez_de_500(cliente_com_modelo_ausente):
    resposta = cliente_com_modelo_ausente.post(
        "/predict",
        json={"lote_id": "L001", "status": "APROVADO", "turno": "A", "tem_observacao": False},
    )

    assert resposta.status_code == 503
    assert "não carregado" in resposta.json()["detail"]


def test_predict_com_observacao_texto_retorna_causa_e_confianca(client):
    """Verifica que o endpoint /predict aceita payload de observação em texto livre (S10-B)."""
    # 1. Erro de digitação
    resp1 = client.post("/predict", json={"observacao": "digitei errado o codigo"})
    assert resp1.status_code == 200
    dados1 = resp1.json()
    assert dados1["causa"] == "erro_digitacao"
    assert dados1["confianca"] >= 0.75
    assert dados1["classe_predita"] == "erro_digitacao"

    # 2. Falta de peça na doca
    resp2 = client.post("/predict", json={"observacao": "faltou peça na doca 3"})
    assert resp2.status_code == 200
    dados2 = resp2.json()
    assert dados2["causa"] == "falta_peca"
    assert dados2["confianca"] >= 0.75

    # 3. Lançamento duplicado
    resp3 = client.post("/predict", json={"observacao": "lançamento duplicado por engano"})
    assert resp3.status_code == 200
    dados3 = resp3.json()
    assert dados3["causa"] == "lancamento_duplicado"
    assert dados3["confianca"] >= 0.75

    # 4. Observação vazia
    resp4 = client.post("/predict", json={"observacao": ""})
    assert resp4.status_code == 200
    dados4 = resp4.json()
    assert dados4["causa"] == "nao_classificado"
    assert dados4["confianca"] == 0.0

