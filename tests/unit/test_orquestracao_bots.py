"""Testes unitários para a arquitetura de orquestração multi-bot (Bot A, Bot B, Bot C)."""

import pandas as pd
import pytest
from unittest.mock import MagicMock

from src.bot import config
from src.bot.dispatcher import enviar_itens_fila, disparar_bot_b
from src.bot.performer import disparar_bot_c, executar_auditoria_local
from src.bot.reporter import gerar_planilha_relatorio
from src.bot.avaliador import avaliar_lote


@pytest.fixture
def df_lotes_exemplo():
    return pd.DataFrame([
        {
            "lote_id": "LG-2026-00101",
            "produto": "TV55-4K-B",
            "linha": "L1",
            "turno": "A",
            "status": "APROVADO",
            "responsavel": "Carlos Menezes",
            "data": "14/06/2026",
            "observacao": "",
        },
        {
            "lote_id": "LG-2026-00104",
            "produto": "TV65-OLED",
            "linha": "L1",
            "turno": "C",
            "status": "REPROVADO",
            "responsavel": "Marcos Souza",
            "data": "14/06/2026",
            "observacao": "Defeito na tela",
        }
    ])


@pytest.fixture
def base_referencia_mock():
    return pd.DataFrame([
        {"lote_id": "LG-2026-00101", "status_cadastro": "Ativo"},
        {"lote_id": "LG-2026-00104", "status_cadastro": "Ativo"},
    ])


def test_bot_a_enfileiramento_dry_run(df_lotes_exemplo):
    total_lidos, total_enviados, total_falhas = enviar_itens_fila(df_lotes_exemplo, sdk=None)
    assert total_lidos == 2
    assert total_enviados == 2
    assert total_falhas == 0


def test_bot_a_dispara_bot_b_create_task(monkeypatch):
    monkeypatch.setattr(config, "MAESTRO_ENABLED", True)
    sdk_mock = MagicMock()
    sdk_mock.create_task.return_value = MagicMock(id=101)

    task_id = disparar_bot_b(sdk_mock, total_itens=10)
    assert task_id == "101"
    sdk_mock.create_task.assert_called_once()
    assert sdk_mock.create_task.call_args[1]["activity_label"] == config.BOTCITY_PERFORMER_LABEL


def test_bot_b_dispara_bot_c_create_task(monkeypatch):
    monkeypatch.setattr(config, "MAESTRO_ENABLED", True)
    sdk_mock = MagicMock()
    sdk_mock.create_task.return_value = MagicMock(id=202)

    task_id = disparar_bot_c(sdk_mock, {"total_processados": 10, "total_com_divergencia": 2})
    assert task_id == "202"
    sdk_mock.create_task.assert_called_once()
    assert sdk_mock.create_task.call_args[1]["activity_label"] == config.BOTCITY_REPORTER_LABEL


def test_bot_b_avaliar_lote_regras_negocio(base_referencia_mock):
    # Lote conforme
    lote_ok = {
        "lote_id": "LG-2026-00101",
        "produto": "TV55-4K-B",
        "linha": "L1",
        "turno": "A",
        "status": "APROVADO",
        "responsavel": "Carlos Menezes",
        "data": "14/06/2026",
        "observacao": "",
    }
    divs_ok = avaliar_lote(lote_ok, base_referencia_mock)
    assert len(divs_ok) == 0

    # Lote não cadastrado na base (RN03)
    lote_nao_cadastrado = {
        "lote_id": "LG-9999-99999",
        "produto": "TV55-4K-B",
        "linha": "L1",
        "turno": "A",
        "status": "APROVADO",
        "responsavel": "Carlos Menezes",
        "data": "14/06/2026",
        "observacao": "",
    }
    divs_rn03 = avaliar_lote(lote_nao_cadastrado, base_referencia_mock)
    assert any(d["regra"] == "RN03" for d in divs_rn03)

    # Lote reprovado sem observação (RN07)
    lote_sem_obs = {
        "lote_id": "LG-2026-00104",
        "produto": "TV65-OLED",
        "linha": "L1",
        "turno": "C",
        "status": "REPROVADO",
        "responsavel": "Marcos Souza",
        "data": "14/06/2026",
        "observacao": "",
    }
    divs_rn07 = avaliar_lote(lote_sem_obs, base_referencia_mock)
    assert any(d["regra"] == "RN07" for d in divs_rn07)


def test_bot_c_gerar_planilha_relatorio(tmp_path):
    resumo = {
        "total_processados": 5,
        "total_conformes": 4,
        "total_com_divergencia": 1,
        "divergencias_detalhadas": [
            {
                "lote_id": "LG-2026-00107",
                "regra": "RN07",
                "campo": "observacao",
                "descricao": "Lote reprovado sem observação preenchida.",
            }
        ],
    }
    caminho_saida = tmp_path / "relatorio_teste.xlsx"
    gerar_planilha_relatorio(resumo, str(caminho_saida))
    assert caminho_saida.exists()
