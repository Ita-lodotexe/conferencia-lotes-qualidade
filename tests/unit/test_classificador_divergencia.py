"""Testes unitários para src/classificador_divergencia.py."""

import pytest
import requests
from requests.exceptions import Timeout, ConnectionError, HTTPError
from unittest.mock import MagicMock

from src.classificador_divergencia import classificar_divergencia, FALLBACK_PADRAO


def test_ml_disabled_retorna_fallback_imediato(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "false")
    mock_post = MagicMock()
    monkeypatch.setattr(requests, "post", mock_post)

    resultado = classificar_divergencia("Defeito na tela")

    assert resultado["origem_decisao"] == "fallback"
    assert resultado["causa_provavel"] == "nao_classificado"
    assert resultado["confianca_ml"] == 0.0
    assert resultado["motivo_fallback"] == "ml_desabilitado"
    mock_post.assert_not_called()


def test_ml_timeout_retorna_fallback(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "true")
    monkeypatch.setattr(requests, "post", MagicMock(side_effect=Timeout("Tempo esgotado")))

    resultado = classificar_divergencia("Defeito na tela")

    assert resultado["origem_decisao"] == "fallback"
    assert resultado["causa_provavel"] == "nao_classificado"
    assert resultado["confianca_ml"] == 0.0
    assert resultado["motivo_fallback"] == "falha_contrato_api"


def test_ml_erro_conexao_retorna_fallback(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "true")
    monkeypatch.setattr(requests, "post", MagicMock(side_effect=ConnectionError("Serviço offline")))

    resultado = classificar_divergencia("Defeito na tela")

    assert resultado["origem_decisao"] == "fallback"
    assert resultado["causa_provavel"] == "nao_classificado"
    assert resultado["confianca_ml"] == 0.0
    assert resultado["motivo_fallback"] == "falha_contrato_api"


def test_ml_erro_contrato_422_ou_500_retorna_fallback(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "true")
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = HTTPError("422 Unprocessable Entity - One-hot encoding expected")
    monkeypatch.setattr(requests, "post", MagicMock(return_value=mock_resp))

    resultado = classificar_divergencia("Defeito na tela")

    assert resultado["origem_decisao"] == "fallback"
    assert resultado["causa_provavel"] == "nao_classificado"
    assert resultado["confianca_ml"] == 0.0
    assert resultado["motivo_fallback"] == "falha_contrato_api"


def test_ml_excecao_inesperada_retorna_fallback(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "true")
    monkeypatch.setattr(requests, "post", MagicMock(side_effect=RuntimeError("Erro desconhecido")))

    resultado = classificar_divergencia("Defeito na tela")

    assert resultado["origem_decisao"] == "fallback"
    assert resultado["causa_provavel"] == "nao_classificado"
    assert resultado["confianca_ml"] == 0.0
    assert resultado["motivo_fallback"] == "falha_contrato_api"


def test_ml_confianca_abaixo_do_limiar_cai_no_fallback(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "true")
    monkeypatch.setenv("ML_CONFIANCA_MINIMA", "0.80")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"causa": "defeito_fabrica", "confianca": 0.65}
    mock_resp.raise_for_status.return_value = None
    monkeypatch.setattr(requests, "post", MagicMock(return_value=mock_resp))

    resultado = classificar_divergencia("Defeito na tela")

    assert resultado["origem_decisao"] == "fallback"
    assert resultado["causa_provavel"] == "nao_classificado"
    assert resultado["confianca_ml"] == 0.65


def test_ml_sucesso_com_alta_confianca(monkeypatch):
    monkeypatch.setenv("ML_ENABLED", "true")
    monkeypatch.setenv("ML_CONFIANCA_MINIMA", "0.75")

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"causa": "defeito_fabrica", "confianca": 0.92}
    mock_resp.raise_for_status.return_value = None
    monkeypatch.setattr(requests, "post", MagicMock(return_value=mock_resp))

    resultado = classificar_divergencia("Defeito na tela")

    assert resultado["origem_decisao"] == "ml"
    assert resultado["causa_provavel"] == "defeito_fabrica"
    assert resultado["confianca_ml"] == 0.92
