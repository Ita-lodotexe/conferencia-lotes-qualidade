"""Testes para `scripts/dispatcher.py` (Issue #19 — Dispatcher do DataPool).

Regra de ouro sob teste (mesma do vault_client, Issue #17): nenhuma
mensagem sensível vinda do SDK pode aparecer em log, mesmo no caminho
de erro. Também cobre a resiliência do loop de envio: falha em um item
não pode abortar os demais.
"""

import logging
from unittest.mock import MagicMock

import pandas as pd
import pytest

from scripts import dispatcher
from src.bot import config

COLUNAS = dispatcher.COLUNAS_ESPERADAS


def _df_valido(n=3):
    linhas = [
        {
            "lote_id": f"L{i:03d}",
            "produto": "Produto Teste",
            "linha": "LINHA_A",
            "turno": "MANHA",
            "status": "APROVADO",
            "responsavel": "Fulano",
            "data": "2026-07-15",
            "observacao": "",
        }
        for i in range(1, n + 1)
    ]
    return pd.DataFrame(linhas, columns=COLUNAS)


def _mock_credenciais(monkeypatch):
    monkeypatch.setattr(config, "BOTCITY_SERVER", "https://lgcmdi.botcity.dev")
    monkeypatch.setattr(config, "BOTCITY_LOGIN", "login-fake")
    monkeypatch.setattr(config, "BOTCITY_KEY", "key-fake")


def test_dry_run_nao_chama_sdk(monkeypatch):
    monkeypatch.setattr(config, "MAESTRO_ENABLED", False)
    sdk_classe_mock = MagicMock()
    monkeypatch.setattr(dispatcher, "BotMaestroSDK", sdk_classe_mock)

    resultado = dispatcher.enviar_para_fila(_df_valido(3))

    assert resultado == (3, 3, 0)
    sdk_classe_mock.assert_not_called()


def test_modo_maestro_envia_todos_itens_validos(monkeypatch):
    monkeypatch.setattr(config, "MAESTRO_ENABLED", True)
    _mock_credenciais(monkeypatch)

    datapool_mock = MagicMock()
    datapool_mock.create_entry.return_value = MagicMock()
    sdk_instancia_mock = MagicMock()
    sdk_instancia_mock.get_datapool.return_value = datapool_mock
    monkeypatch.setattr(dispatcher, "BotMaestroSDK", MagicMock(return_value=sdk_instancia_mock))

    resultado = dispatcher.enviar_para_fila(_df_valido(3))

    assert datapool_mock.create_entry.call_count == 3
    assert resultado == (3, 3, 0)


def test_item_com_falha_nao_aborta_loop(monkeypatch):
    monkeypatch.setattr(config, "MAESTRO_ENABLED", True)
    _mock_credenciais(monkeypatch)

    datapool_mock = MagicMock()
    datapool_mock.create_entry.side_effect = [
        MagicMock(),
        Exception("falha transitória no servidor"),
        MagicMock(),
    ]
    sdk_instancia_mock = MagicMock()
    sdk_instancia_mock.get_datapool.return_value = datapool_mock
    monkeypatch.setattr(dispatcher, "BotMaestroSDK", MagicMock(return_value=sdk_instancia_mock))

    resultado = dispatcher.enviar_para_fila(_df_valido(3))

    assert datapool_mock.create_entry.call_count == 3
    assert resultado == (3, 2, 1)


def test_erro_de_login_relevanta_dispatcher_error(monkeypatch, caplog):
    monkeypatch.setattr(config, "MAESTRO_ENABLED", True)
    _mock_credenciais(monkeypatch)

    mensagem_sensivel = "401 senha=vazou"
    sdk_instancia_mock = MagicMock()
    sdk_instancia_mock.login.side_effect = Exception(mensagem_sensivel)
    monkeypatch.setattr(dispatcher, "BotMaestroSDK", MagicMock(return_value=sdk_instancia_mock))

    caplog.set_level(logging.INFO)

    with pytest.raises(dispatcher.DispatcherError):
        dispatcher.enviar_para_fila(_df_valido(1))

    for record in caplog.records:
        assert "vazou" not in record.message
        assert mensagem_sensivel not in record.message


def test_csv_com_coluna_faltante_retorna_erro(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(config, "PASTA_ENTRADA", str(tmp_path))

    csv_path = tmp_path / dispatcher.ARQUIVO_CSV
    csv_path.write_text(
        "lote_id,produto,linha,turno,status,responsavel,data\n"
        "L001,Produto,LINHA_A,MANHA,APROVADO,Fulano,2026-07-15\n",
        encoding="utf-8",
    )

    caplog.set_level(logging.INFO)
    resultado = dispatcher.main()

    assert resultado == 1
    assert any("observacao" in record.message for record in caplog.records)
