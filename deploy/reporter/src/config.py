"""Configuração do Bot C (Reporter)."""

import os
from dotenv import load_dotenv

load_dotenv()

MAESTRO_ENABLED: bool = os.getenv("MAESTRO_ENABLED", "true").lower() == "true"
PASTA_SAIDA: str = os.getenv("PASTA_SAIDA", "data/output")

BOTCITY_WORKSPACE: str | None = os.getenv("BOTCITY_WORKSPACE", "lg-cmdi")
BOTCITY_SERVER: str = os.getenv("BOTCITY_SERVER", "https://lgcmdi.botcity.dev")
BOTCITY_LOGIN: str | None = os.getenv("BOTCITY_LOGIN", "lg-cmdi")
BOTCITY_KEY: str | None = os.getenv("BOTCITY_KEY", "LG-_YXRK5VAHBCJTNWODGSTQ")

BOTCITY_DISPATCHER_LABEL: str = os.getenv("BOTCITY_DISPATCHER_LABEL", "italo-dispatcher-v1")
BOTCITY_PERFORMER_LABEL: str = os.getenv("BOTCITY_PERFORMER_LABEL", "italo-performer-v1")
BOTCITY_REPORTER_LABEL: str = os.getenv("BOTCITY_REPORTER_LABEL", "italo-reporter-v1")
