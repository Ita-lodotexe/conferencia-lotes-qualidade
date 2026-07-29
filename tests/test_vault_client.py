"""Testes para `src/bot/vault_client.py` (Issue #17 — Credentials Vault).

Regra de ouro sob teste: a senha nunca pode aparecer em log, mesmo no
caminho de erro (inclusive se o próprio SDK ecoar dados sensíveis).
"""

import logging
from unittest.mock import MagicMock

import pytest

from src.bot import config, vault_client
from src.bot.vault_client import VaultError, obter_credencial_erp


def _fake_get_credential(usuario="usuario_erp", senha="senha_secreta"):
    def _get_credential(label, key):
        if key == config.VAULT_CREDENCIAL_ERP_KEY_USUARIO:
            return usuario
        if key == config.VAULT_CREDENCIAL_ERP_KEY_SENHA:
            return senha
        raise AssertionError(f"chave inesperada: {key}")

    return _get_credential


def test_modo_local_retorna_credencial_ficticia(monkeypatch):
    monkeypatch.setattr(config, "VAULT_ENABLED", False)
    sdk_classe_mock = MagicMock()
    monkeypatch.setattr(vault_client, "BotMaestroSDK", sdk_classe_mock)

    resultado = obter_credencial_erp()

    assert resultado == ("bot_local", "senha_dev")
    sdk_classe_mock.assert_not_called()


def test_modo_vault_ativo_retorna_credencial_do_sdk(monkeypatch):
    monkeypatch.setattr(config, "VAULT_ENABLED", True)
    monkeypatch.setattr(config, "BOTCITY_SERVER", "https://lgcmdi.botcity.dev")
    monkeypatch.setattr(config, "BOTCITY_LOGIN", "login-fake")
    monkeypatch.setattr(config, "BOTCITY_KEY", "key-fake")

    sdk_instancia_mock = MagicMock()
    sdk_instancia_mock.get_credential.side_effect = _fake_get_credential()
    sdk_classe_mock = MagicMock(return_value=sdk_instancia_mock)
    monkeypatch.setattr(vault_client, "BotMaestroSDK", sdk_classe_mock)

    resultado = obter_credencial_erp()

    assert resultado == ("usuario_erp", "senha_secreta")
    sdk_instancia_mock.login.assert_called_once()


def test_senha_nao_aparece_em_log_no_caminho_feliz(monkeypatch, caplog):
    monkeypatch.setattr(config, "VAULT_ENABLED", True)
    monkeypatch.setattr(config, "BOTCITY_SERVER", "https://lgcmdi.botcity.dev")
    monkeypatch.setattr(config, "BOTCITY_LOGIN", "login-fake")
    monkeypatch.setattr(config, "BOTCITY_KEY", "key-fake")

    sdk_instancia_mock = MagicMock()
    sdk_instancia_mock.get_credential.side_effect = _fake_get_credential()
    monkeypatch.setattr(vault_client, "BotMaestroSDK", MagicMock(return_value=sdk_instancia_mock))

    caplog.set_level(logging.INFO)
    obter_credencial_erp()

    for record in caplog.records:
        assert "senha_secreta" not in record.message


def test_senha_nao_aparece_em_log_no_caminho_erro(monkeypatch, caplog):
    monkeypatch.setattr(config, "VAULT_ENABLED", True)
    monkeypatch.setattr(config, "BOTCITY_SERVER", "https://lgcmdi.botcity.dev")
    monkeypatch.setattr(config, "BOTCITY_LOGIN", "login-fake")
    monkeypatch.setattr(config, "BOTCITY_KEY", "key-fake")

    mensagem_sensivel = "401 Unauthorized: senha=senha_leaked"
    sdk_instancia_mock = MagicMock()
    sdk_instancia_mock.login.side_effect = Exception(mensagem_sensivel)
    monkeypatch.setattr(vault_client, "BotMaestroSDK", MagicMock(return_value=sdk_instancia_mock))

    caplog.set_level(logging.INFO)
    with pytest.raises(VaultError):
        obter_credencial_erp()

    for record in caplog.records:
        assert "senha_leaked" not in record.message
        assert mensagem_sensivel not in record.message


def test_erro_no_vault_relevanta_vaulterror(monkeypatch):
    monkeypatch.setattr(config, "VAULT_ENABLED", True)
    monkeypatch.setattr(config, "BOTCITY_SERVER", "https://lgcmdi.botcity.dev")
    monkeypatch.setattr(config, "BOTCITY_LOGIN", "login-fake")
    monkeypatch.setattr(config, "BOTCITY_KEY", "key-fake")

    sdk_instancia_mock = MagicMock()
    sdk_instancia_mock.get_credential.side_effect = ValueError("Error during log read. Server returned 404.")
    monkeypatch.setattr(vault_client, "BotMaestroSDK", MagicMock(return_value=sdk_instancia_mock))

    with pytest.raises(VaultError):
        obter_credencial_erp()
