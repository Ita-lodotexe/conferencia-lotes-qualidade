"""Configuração do bot, centralizada a partir do .env da raiz do projeto."""

import os

from dotenv import load_dotenv

load_dotenv()

MAESTRO_ENABLED = os.getenv("MAESTRO_ENABLED", "false").lower() == "true"
VAULT_ENABLED = os.getenv("VAULT_ENABLED", "false").lower() == "true"

PASTA_ENTRADA = os.getenv("PASTA_ENTRADA", "dados_entrada")

BOTCITY_WORKSPACE = os.getenv("BOTCITY_WORKSPACE")
BOTCITY_LOGIN = os.getenv("BOTCITY_LOGIN")
BOTCITY_KEY = os.getenv("BOTCITY_KEY")
