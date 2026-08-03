"""Configuração do bot, centralizada a partir do .env da raiz do projeto."""

import os

from dotenv import load_dotenv

load_dotenv()

MAESTRO_ENABLED = os.getenv("MAESTRO_ENABLED", "false").lower() == "true"
VAULT_ENABLED = os.getenv("VAULT_ENABLED", "false").lower() == "true"

PASTA_ENTRADA = os.getenv("PASTA_ENTRADA", "dados_entrada")

BOTCITY_WORKSPACE = os.getenv("BOTCITY_WORKSPACE")
BOTCITY_SERVER: str = os.getenv("BOTCITY_SERVER", "")
BOTCITY_LOGIN = os.getenv("BOTCITY_LOGIN")
BOTCITY_KEY = os.getenv("BOTCITY_KEY")
BOTCITY_ACTIVITY_LABEL: str = os.getenv("BOTCITY_ACTIVITY_LABEL", "")

# Identificadores da credencial do ERP no Credentials Vault
VAULT_CREDENCIAL_ERP_LABEL: str = "credencial_erp_eqp04"
VAULT_CREDENCIAL_ERP_KEY_USUARIO: str = "usuario"
VAULT_CREDENCIAL_ERP_KEY_SENHA: str = "senha"
