"""Cliente do Credentials Vault do BotCity Maestro.

Regra de ouro: a senha nunca pode aparecer em código, .env, log, print
ou mensagem de erro.
"""

import logging

from src.bot import config

try:
    from botcity.maestro import BotMaestroSDK
except ImportError:
    BotMaestroSDK = None


class VaultError(Exception):
    """Erro ao acessar o Credentials Vault do Maestro."""


def obter_credencial_erp() -> tuple[str, str]:
    """Obtém a credencial do ERP como (usuario, senha).

    Em modo local (config.VAULT_ENABLED=False) retorna uma credencial
    fictícia, sem tocar no SDK. Em modo Vault (config.VAULT_ENABLED=True)
    busca a credencial real no Credentials Vault do BotCity Maestro.
    """
    if not config.VAULT_ENABLED:
        logging.info("Modo local (VAULT_ENABLED=false): usando credencial fictícia.")
        return "bot_local", "senha_dev"

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
        logging.error(
            f"Falha ao acessar o Vault ({type(e).__name__}): não foi possível obter credencial '{label}'."
        )
        raise VaultError(
            "Falha ao acessar o Vault: verifique BOTCITY_SERVER, BOTCITY_LOGIN e BOTCITY_KEY."
        ) from None

    logging.info(f"Acessando sistema com o usuário: {usuario}")
    return usuario, senha
