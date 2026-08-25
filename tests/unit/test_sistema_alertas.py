"""Testes unitários para o sistema de alertas multi-canal e monitoramento de degradação ML."""

import os
import pandas as pd
import pytest
import requests
from unittest.mock import MagicMock

from src.bot.sistema_alertas import enviar_alerta
from src.bot.reporter import gerar_planilha_relatorio, verificar_alerta_degradacao_ml


def test_telegram_sucesso_sem_fallback(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake_token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_post = MagicMock(return_value=mock_resp)
    monkeypatch.setattr(requests, "post", mock_post)

    resultado = enviar_alerta("Teste de Sucesso", "Mensagem", severidade="INFO")

    assert resultado["sucesso"] is True
    assert resultado["canal_utilizado"] == "telegram"
    assert resultado["fallback_acionado"] is False


def test_telegram_falha_cai_no_fallback_email_sem_interromper(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "token_invalido_revogado")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456")

    # Simula token do Telegram revogado/excluído (401)
    monkeypatch.setattr(
        "src.bot.sistema_alertas._enviar_telegram",
        MagicMock(side_effect=requests.exceptions.HTTPError("401 Unauthorized - Token Revogado")),
    )
    monkeypatch.setattr(
        "src.bot.sistema_alertas._enviar_email_smtp",
        MagicMock(return_value=True),
    )

    resultado = enviar_alerta("Alerta com Falha no Telegram", "Corpo do alerta", severidade="AVISO")

    # Verifica que o erro foi absorvido e o canal secundário respondeu com sucesso
    assert resultado["sucesso"] is True
    assert resultado["canal_utilizado"] == "email_smtp"
    assert resultado["fallback_acionado"] is True


def test_todos_canais_falham_preserva_execucao(monkeypatch):
    monkeypatch.setattr(
        "src.bot.sistema_alertas._enviar_telegram",
        MagicMock(side_effect=RuntimeError("Telegram fora do ar")),
    )
    monkeypatch.setattr(
        "src.bot.sistema_alertas._enviar_email_smtp",
        MagicMock(side_effect=RuntimeError("SMTP fora do ar")),
    )
    monkeypatch.setattr(
        "src.bot.sistema_alertas._enviar_whatsapp_twilio",
        MagicMock(side_effect=RuntimeError("WhatsApp fora do ar")),
    )

    resultado = enviar_alerta("Teste Falha Geral", "Mensagem", severidade="CRITICO")

    # Garante que nenhuma exceção vazou e o retorno relata falha controlada
    assert resultado["sucesso"] is False
    assert resultado["canal_utilizado"] == "nenhum"
    assert resultado["fallback_acionado"] is True


def test_alerta_degradacao_dispara_quando_100_porcento_em_fallback(monkeypatch):
    mock_alerta = MagicMock(return_value={"sucesso": True})
    monkeypatch.setattr("src.bot.reporter.enviar_alerta", mock_alerta)

    dados_resumo = {
        "total_processados": 3,
        "total_com_divergencia": 3,
        "divergencias_detalhadas": [
            {"lote_id": "L1", "regra": "RN03", "origem_decisao": "fallback", "confianca_ml": 0.0},
            {"lote_id": "L2", "regra": "RN07", "origem_decisao": "fallback", "confianca_ml": 0.0},
            {"lote_id": "L3", "regra": "RN02", "origem_decisao": "fallback", "confianca_ml": 0.0},
        ],
    }

    disparou = verificar_alerta_degradacao_ml(dados_resumo)
    assert disparou is True
    mock_alerta.assert_called_once()
    assert mock_alerta.call_args[1]["severidade"] == "AVISO"


def test_alerta_degradacao_nao_dispara_com_itens_ml(monkeypatch):
    mock_alerta = MagicMock()
    monkeypatch.setattr("src.bot.reporter.enviar_alerta", mock_alerta)

    dados_resumo = {
        "total_processados": 3,
        "total_com_divergencia": 3,
        "divergencias_detalhadas": [
            {"lote_id": "L1", "regra": "RN03", "origem_decisao": "ml", "confianca_ml": 0.88},
            {"lote_id": "L2", "regra": "RN07", "origem_decisao": "fallback", "confianca_ml": 0.0},
        ],
    }

    disparou = verificar_alerta_degradacao_ml(dados_resumo)
    assert disparou is False
    mock_alerta.assert_not_called()


def test_relatorio_excel_contem_colunas_origem_decisao_e_confianca_ml(tmp_path):
    dados_resumo = {
        "total_processados": 2,
        "total_conformes": 1,
        "total_com_divergencia": 1,
        "divergencias_detalhadas": [
            {
                "lote_id": "LG-2026-00104",
                "regra": "RN07",
                "campo": "observacao",
                "descricao": "Lote reprovado sem observação",
                "origem_decisao": "ml",
                "confianca_ml": 0.91,
                "causa_provavel": "defeito_fabrica",
            }
        ],
    }

    caminho_saida = tmp_path / "relatorio_teste.xlsx"
    gerar_planilha_relatorio(dados_resumo, str(caminho_saida))

    assert caminho_saida.exists()

    df_div = pd.read_excel(caminho_saida, sheet_name="Divergencias")
    assert "origem_decisao" in df_div.columns
    assert "confianca_ml" in df_div.columns
    assert df_div["origem_decisao"].iloc[0] == "ml"
    assert df_div["confianca_ml"].iloc[0] == 0.91
