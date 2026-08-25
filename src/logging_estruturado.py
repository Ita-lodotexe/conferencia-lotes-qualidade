"""Log estruturado das decisões de ML (Seção 3.4).

Cada chamada a processar_item_ambiguo() (src/item_processor.py) emite
uma linha JSON neste logger — pensado para ser consumido por uma
ferramenta de log (grep, jq, Datadog, etc.), não para leitura humana
direta no terminal.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

NOME_LOGGER = "ml.decisoes"

# Campos de negócio que, quando presentes no LogRecord (via `extra=`),
# entram na linha JSON além de timestamp/nivel/mensagem.
CAMPOS_EXTRA = (
    "lote_id",
    "entrou_no_ml",
    "classe_ml",
    "probabilidade_ml",
    "decisao_ml",
    "latencia_ms",
    "motivo",
)


class FormatterJSON(logging.Formatter):
    """Serializa cada LogRecord como uma linha JSON.

    timestamp e nivel/mensagem sempre presentes; os campos de
    CAMPOS_EXTRA só entram quando o registro de log foi emitido com
    `extra={...}` contendo aquele campo — ausência de um campo não
    aparece como null "poluindo" a linha.
    """

    def format(self, record: logging.LogRecord) -> str:
        linha = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "nivel": record.levelname,
            "mensagem": record.getMessage(),
        }
        for campo in CAMPOS_EXTRA:
            if hasattr(record, campo):
                linha[campo] = getattr(record, campo)
        return json.dumps(linha, ensure_ascii=False)


def configurar_logger_decisoes_ml() -> logging.Logger:
    """Cria (ou devolve, se já existir) o logger "ml.decisoes" com um
    StreamHandler + FormatterJSON.

    Idempotente: chamadas repetidas (ex.: cada teste importando o
    módulo) não empilham handlers duplicados, o que faria cada linha
    de log aparecer mais de uma vez.
    """
    logger = logging.getLogger(NOME_LOGGER)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(FormatterJSON())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
