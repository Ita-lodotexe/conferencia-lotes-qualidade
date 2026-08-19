"""Testes de src/logging_estruturado.py — FormatterJSON e idempotência de
configurar_logger_decisoes_ml().

Evita depender da captura de stderr do processo (capsys) para não
competir com o próprio plugin de logging do pytest: troca o `.stream`
do handler por um io.StringIO isolado para cada teste.
"""
import io
import json
import logging

import pytest

from src.logging_estruturado import NOME_LOGGER, configurar_logger_decisoes_ml

pytestmark = pytest.mark.unit


@pytest.fixture
def logger_com_buffer():
    """configurar_logger_decisoes_ml(), com o stream do handler trocado
    por um io.StringIO isolado — restaura o stream original ao final."""
    logger = configurar_logger_decisoes_ml()
    handler = logger.handlers[0]
    stream_original = handler.stream
    buffer = io.StringIO()
    handler.stream = buffer
    yield logger, buffer
    handler.stream = stream_original


def test_configurar_logger_devolve_logger_com_nome_esperado():
    logger = configurar_logger_decisoes_ml()
    assert logger.name == NOME_LOGGER


def test_log_emitido_e_json_valido_com_os_campos_esperados(logger_com_buffer):
    logger, buffer = logger_com_buffer

    logger.info(
        "decisão de ML processada para o lote",
        extra={
            "lote_id": "L001",
            "entrou_no_ml": True,
            "classe_ml": "revisar",
            "probabilidade_ml": 0.71,
            "decisao_ml": "revisar",
            "latencia_ms": 12.3,
            "motivo": None,
        },
    )

    linha = json.loads(buffer.getvalue().strip().splitlines()[-1])

    assert linha["nivel"] == "INFO"
    assert "timestamp" in linha
    assert linha["lote_id"] == "L001"
    assert linha["entrou_no_ml"] is True
    assert linha["classe_ml"] == "revisar"
    assert linha["probabilidade_ml"] == 0.71
    assert linha["decisao_ml"] == "revisar"
    assert linha["latencia_ms"] == 12.3


def test_configurar_logger_e_idempotente_nao_duplica_handlers():
    logger_1 = configurar_logger_decisoes_ml()
    quantidade_apos_primeira_chamada = len(logger_1.handlers)

    logger_2 = configurar_logger_decisoes_ml()
    logger_3 = configurar_logger_decisoes_ml()

    assert logger_2 is logger_1 is logger_3
    # O que importa é não crescer a cada chamada — não o valor absoluto,
    # que depende de quantos outros módulos já chamaram esta função antes
    # (ex.: src/item_processor.py, ao ser importado).
    assert len(logger_2.handlers) == quantidade_apos_primeira_chamada
    assert len(logger_3.handlers) == quantidade_apos_primeira_chamada
