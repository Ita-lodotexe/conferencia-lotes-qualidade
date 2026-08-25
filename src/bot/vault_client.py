"""Cliente do Credentials Vault do BotCity Maestro.

Regra de segurança: credenciais sensíveis nunca devem ser hardcoded nem
expostas em logs ou mensagens de exceção não tratadas.
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
    """Obtém a credencial do ERP como tupla (usuario, senha).

    Em modo local (config.VAULT_ENABLED=False), retorna credenciais fictícias de desenvolvimento.
    Em modo Vault (config.VAULT_ENABLED=True), conecta com o Credentials Vault do Maestro.
    """
    if not config.VAULT_ENABLED:
        logging.info("Modo local (VAULT_ENABLED=false): utilizando credenciais locais seguras de teste.")
        return "bot_local", "senha_dev"

    if BotMaestroSDK is None:
        raise VaultError("SDK botcity-maestro-sdk não está instalado no ambiente.")

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
            f"Falha ao acessar o Credentials Vault ({type(e).__name__}): credencial '{label}' não encontrada ou inválida."
        )
        raise VaultError(
            "Falha ao acessar o Vault do Maestro: verifique BOTCITY_SERVER, BOTCITY_LOGIN e BOTCITY_KEY."
        ) from None

    logging.info(f"Credencial recuperada com sucesso do Vault para o usuário: {usuario}")
    return usuario, senha
