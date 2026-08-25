"""Testes de src/ml_client.py — cliente HTTP + circuit breaker.

Nunca sobe servidor real: httpx.post é mockado com unittest.mock.patch
em todos os testes.
"""
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.ml_client import MLClient

pytestmark = pytest.mark.unit

PAYLOAD_PREDICAO = {
    "lote_id": "L001",
    "classe_predita": "revisar",
    "probabilidade": 0.7,
    "probabilidades": {"valido_automatico": 0.2, "revisar": 0.7, "recusar_automatico": 0.1},
    "decisao": "revisar",
}


def _resposta_ok(payload: dict) -> MagicMock:
    resposta = MagicMock()
    resposta.status_code = 200
    resposta.json.return_value = payload
    resposta.raise_for_status.return_value = None
    return resposta


def _resposta_erro_http(status_code: int) -> MagicMock:
    resposta = MagicMock()
    resposta.status_code = status_code
    resposta.raise_for_status.side_effect = httpx.HTTPStatusError(
        f"status {status_code}", request=MagicMock(), response=MagicMock(status_code=status_code)
    )
    return resposta


class TestClassificarSucesso:
    @patch("httpx.post")
    def test_retorna_dict_com_os_campos_da_predicao_e_latencia_ms(self, mock_post):
        mock_post.return_value = _resposta_ok(PAYLOAD_PREDICAO)
        cliente = MLClient(base_url="http://api-ml:8000")

        resultado = cliente.classificar(lote_id="L001", status="REPROVADO", turno="A", tem_observacao=True)

        assert resultado is not None
        assert resultado["classe_predita"] == "revisar"
        assert resultado["decisao"] == "revisar"
        assert isinstance(resultado["latencia_ms"], float)
        assert resultado["latencia_ms"] >= 0
        mock_post.assert_called_once()

    @patch("httpx.post")
    def test_monta_payload_e_url_corretos(self, mock_post):
        mock_post.return_value = _resposta_ok(PAYLOAD_PREDICAO)
        cliente = MLClient(base_url="http://api-ml:8000/")

        cliente.classificar(lote_id="L001", status="REPROVADO", turno="A", tem_observacao=True)

        args, kwargs = mock_post.call_args
        assert args[0] == "http://api-ml:8000/predict"
        assert kwargs["json"] == {
            "lote_id": "L001", "status": "REPROVADO", "turno": "A", "tem_observacao": True,
        }


class TestClassificarFalha:
    @patch("httpx.post", side_effect=httpx.ConnectError("conexão recusada"))
    def test_erro_de_conexao_retorna_none_sem_lancar(self, mock_post):
        cliente = MLClient(base_url="http://api-ml:8000")

        resultado = cliente.classificar(lote_id="L001", status="REPROVADO", turno="A", tem_observacao=True)

        assert resultado is None

    @patch("httpx.post", side_effect=httpx.TimeoutException("timeout"))
    def test_timeout_retorna_none_sem_lancar(self, mock_post):
        cliente = MLClient(base_url="http://api-ml:8000")

        resultado = cliente.classificar(lote_id="L002", status="REPROVADO", turno="B", tem_observacao=False)

        assert resultado is None

    @patch("httpx.post")
    def test_status_5xx_retorna_none_sem_lancar(self, mock_post):
        mock_post.return_value = _resposta_erro_http(500)
        cliente = MLClient(base_url="http://api-ml:8000")

        resultado = cliente.classificar(lote_id="L003", status="APROVADO", turno="C", tem_observacao=False)

        assert resultado is None


class TestCircuitBreaker:
    @patch("httpx.post", side_effect=httpx.ConnectError("conexão recusada"))
    def test_circuito_abre_apos_falhas_consecutivas_e_bloqueia_a_sexta_chamada(self, mock_post):
        cliente = MLClient(base_url="http://api-ml:8000", max_falhas_consecutivas=5)

        for _ in range(5):
            resultado = cliente.classificar(lote_id="L001", status="REPROVADO", turno="A", tem_observacao=True)
            assert resultado is None

        assert cliente.circuito_aberto is True
        assert mock_post.call_count == 5

        # 6ª chamada: circuito já aberto — não deve bater na rede de novo.
        resultado_sexta_chamada = cliente.classificar(
            lote_id="L001", status="REPROVADO", turno="A", tem_observacao=True
        )

        assert resultado_sexta_chamada is None
        assert mock_post.call_count == 5  # não aumentou — a 6ª chamada não chegou a chamar httpx.post

    @patch("httpx.post")
    def test_sucesso_intercalado_zera_o_contador_de_falhas_consecutivas(self, mock_post):
        cliente = MLClient(base_url="http://api-ml:8000", max_falhas_consecutivas=3)

        mock_post.side_effect = httpx.ConnectError("falha 1")
        assert cliente.classificar(lote_id="L1", status="REPROVADO", turno="A", tem_observacao=True) is None

        mock_post.side_effect = None
        mock_post.return_value = _resposta_ok(PAYLOAD_PREDICAO)
        assert cliente.classificar(lote_id="L1", status="REPROVADO", turno="A", tem_observacao=True) is not None

        mock_post.side_effect = httpx.ConnectError("falha 2")
        assert cliente.classificar(lote_id="L1", status="REPROVADO", turno="A", tem_observacao=True) is None

        # Só 1 falha consecutiva (a de antes do sucesso não conta) — circuito
        # continua fechado mesmo com max_falhas_consecutivas=3 e 2 falhas totais.
        assert cliente.circuito_aberto is False

    def test_resetar_circuito_permite_novas_tentativas(self):
        cliente = MLClient(base_url="http://api-ml:8000", max_falhas_consecutivas=1)

        with patch("httpx.post", side_effect=httpx.ConnectError("falha")):
            cliente.classificar(lote_id="L1", status="REPROVADO", turno="A", tem_observacao=True)
        assert cliente.circuito_aberto is True

        cliente.resetar_circuito()
        assert cliente.circuito_aberto is False

        with patch("httpx.post") as mock_post:
            mock_post.return_value = _resposta_ok(PAYLOAD_PREDICAO)
            resultado = cliente.classificar(lote_id="L1", status="REPROVADO", turno="A", tem_observacao=True)

        assert resultado is not None
