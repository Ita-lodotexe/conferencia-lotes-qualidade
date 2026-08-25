"""Configuração dos bots de orquestração, centralizada a partir do .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# === Flags de Execução ===
MAESTRO_ENABLED: bool = os.getenv("MAESTRO_ENABLED", "false").lower() == "true"
VAULT_ENABLED: bool = os.getenv("VAULT_ENABLED", "false").lower() == "true"

# === Caminhos do Sistema ===
PASTA_ENTRADA: str = os.getenv("PASTA_ENTRADA", "data/processed")
PASTA_SAIDA: str = os.getenv("PASTA_SAIDA", "data/output")
ARQUIVO_CSV_ENTRADA: str = os.getenv("ARQUIVO_CSV_ENTRADA", "dados_relatorio.csv")
CAMINHO_BASE_REFERENCIA: str = os.getenv(
    "CAMINHO_BASE_REFERENCIA", "data/processed/base_lotes_referencia.csv"
)

# === Credenciais de Conexão do SDK BotCity Maestro ===
BOTCITY_WORKSPACE: str | None = os.getenv("BOTCITY_WORKSPACE")
BOTCITY_SERVER: str = os.getenv("BOTCITY_SERVER", "")
BOTCITY_LOGIN: str | None = os.getenv("BOTCITY_LOGIN")
BOTCITY_KEY: str | None = os.getenv("BOTCITY_KEY")

# === DataPool (Fila de Itens) ===
DATAPOOL_LABEL: str = os.getenv("DATAPOOL_LABEL", "FilaAuditoriaLotes-Eqp04")

# === Labels das Automações no Painel Maestro (Arquitetura Multi-Bot 3+) ===
BOTCITY_DISPATCHER_LABEL: str = os.getenv("BOTCITY_DISPATCHER_LABEL", "italo-dispatcher-v1")
BOTCITY_PERFORMER_LABEL: str = os.getenv("BOTCITY_PERFORMER_LABEL", "italo-performer-v1")
BOTCITY_REPORTER_LABEL: str = os.getenv("BOTCITY_REPORTER_LABEL", "italo-reporter-v1")
BOTCITY_ACTIVITY_LABEL: str = os.getenv("BOTCITY_ACTIVITY_LABEL", BOTCITY_PERFORMER_LABEL)

# === Credentials Vault (ERP) ===
VAULT_CREDENCIAL_ERP_LABEL: str = "credencial_erp_eqp04"
VAULT_CREDENCIAL_ERP_KEY_USUARIO: str = "usuario"
VAULT_CREDENCIAL_ERP_KEY_SENHA: str = "senha"
