"""Cliente do Credentials Vault para o Bot B."""

import logging
from src import config

try:
    from botcity.maestro import BotMaestroSDK
except ImportError:
    BotMaestroSDK = None


class VaultError(Exception):
    pass


def obter_credencial_erp() -> tuple[str, str]:
    if not config.VAULT_ENABLED:
        logging.info("Modo local (VAULT_ENABLED=false): usando credencial fictícia.")
        return "bot_local", "senha_dev"

    if BotMaestroSDK is None:
        raise VaultError("SDK botcity-maestro-sdk não instalado.")

    label = config.VAULT_CREDENCIAL_ERP_LABEL

    try:
        sdk = BotMaestroSDK(
            server=config.BOTCITY_SERVER,
            login=config.BOTCITY_LOGIN,
            key=config.BOTCITY_KEY,
        )
        sdk.login()

        usuario = sdk.get_credential(label=label, key=config.VAULT_CREDENCIAL_ERP_KEY_USUARIO)
        senha = sdk.get_credential(label=label, key=config.VAULT_CREDENCIAL_ERP_KEY_SENHA)
    except Exception as e:
        logging.error(f"Falha ao acessar o Vault ({type(e).__name__}): {e}")
        raise VaultError("Falha ao acessar o Vault do Maestro.") from None

    return usuario, senha
