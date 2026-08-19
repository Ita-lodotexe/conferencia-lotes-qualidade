"""Testes da API de classificação de lotes (Exercício 24-A, Seção 3.2/4.7).

Usa fastapi.testclient.TestClient sobre api_ml.main.app, com o modelo
real carregado via lifespan (o .pkl gerado por train_model.py precisa
existir em models/classificador_lotes.pkl para estes testes rodarem).
"""
import pytest
from fastapi.testclient import TestClient

from api_ml.main import app, _calibrar_decisao

pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    with TestClient(app) as client:
        yield client


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
