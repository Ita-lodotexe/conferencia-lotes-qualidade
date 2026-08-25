"""Configuração do Bot B (Performer)."""

import os
from dotenv import load_dotenv

load_dotenv()

MAESTRO_ENABLED: bool = os.getenv("MAESTRO_ENABLED", "true").lower() == "true"
VAULT_ENABLED: bool = os.getenv("VAULT_ENABLED", "false").lower() == "true"

PASTA_ENTRADA: str = os.getenv("PASTA_ENTRADA", "data/processed")
ARQUIVO_CSV_ENTRADA: str = os.getenv("ARQUIVO_CSV_ENTRADA", "dados_relatorio.csv")
CAMINHO_BASE_REFERENCIA: str = os.getenv("CAMINHO_BASE_REFERENCIA", "data/processed/base_lotes_referencia.csv")

BOTCITY_WORKSPACE: str | None = os.getenv("BOTCITY_WORKSPACE", "lg-cmdi")
BOTCITY_SERVER: str = os.getenv("BOTCITY_SERVER", "https://lgcmdi.botcity.dev")
BOTCITY_LOGIN: str | None = os.getenv("BOTCITY_LOGIN", "lg-cmdi")
BOTCITY_KEY: str | None = os.getenv("BOTCITY_KEY", "LG-_YXRK5VAHBCJTNWODGSTQ")

DATAPOOL_LABEL: str = os.getenv("DATAPOOL_LABEL", "FilaAuditoriaLotes-Eqp04")
BOTCITY_DISPATCHER_LABEL: str = os.getenv("BOTCITY_DISPATCHER_LABEL", "italo-dispatcher-v1")
BOTCITY_PERFORMER_LABEL: str = os.getenv("BOTCITY_PERFORMER_LABEL", "italo-performer-v1")
BOTCITY_REPORTER_LABEL: str = os.getenv("BOTCITY_REPORTER_LABEL", "italo-reporter-v1")

VAULT_CREDENCIAL_ERP_LABEL: str = "credencial_erp_eqp04"
VAULT_CREDENCIAL_ERP_KEY_USUARIO: str = "usuario"
VAULT_CREDENCIAL_ERP_KEY_SENHA: str = "senha"

# Configurações ML
ML_ENABLED: bool = os.getenv("ML_ENABLED", "true").lower() == "true"
ML_CONFIANCA_MINIMA: float = float(os.getenv("ML_CONFIANCA_MINIMA", "0.75"))
ML_ENDPOINT: str = os.getenv("ML_ENDPOINT", "http://127.0.0.1:8000")
