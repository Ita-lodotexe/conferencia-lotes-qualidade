"""Testes para `src/bot/performer.py` (Issue #21 — consumo da fila).

Nenhum teste toca o Maestro real: o SDK é sempre substituído por mock.
Os dois critérios centrais sob teste são a resiliência do loop (falha em
um item não aborta os demais) e a sanitização de exceções do SDK (nenhum
dado sensível pode chegar ao log).
"""

import json
import logging
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.bot import config, performer

TASK_ID = 4242

LOTES_DA_FILA = [
    # (lote_id, status, observacao, turno) — espelha dados_entrada/lotes_auditoria.csv
    ("L001", "APROVADO", "", "MANHA"),
    ("L002", "REPROVADO", "Costura irregular na barra", "TARDE"),
    ("L003", "APROVADO", "", "NOITE"),
    ("", "APROVADO", "", "MANHA"),          # lote_id vazio  -> RN02 + RN03
    ("L005", "REPROV.", "", "TARDE"),       # status ambíguo -> RN06
    ("L006", "REPROVADO", "", "MANHA"),     # sem observação -> RN07
    ("L007", "APROVADO", "", ""),           # turno vazio    -> RN02 + RN03 (inativo)
]


@pytest.fixture
def base_ref():
    return pd.read_csv(performer.BASE_REFERENCIA_FALLBACK)


@pytest.fixture(autouse=True)
def isola_ambiente(monkeypatch):
    """Impede que o .env real (MAESTRO_ENABLED/VAULT_ENABLED=true) faça
    qualquer teste contatar o Maestro."""
    monkeypatch.setattr(config, "MAESTRO_ENABLED", False)
    monkeypatch.setattr(config, "VAULT_ENABLED", False)
    monkeypatch.setattr(config, "BOTCITY_SERVER", "https://lgcmdi.botcity.dev")
    monkeypatch.setattr(config, "BOTCITY_LOGIN", "login-fake")
    monkeypatch.setattr(config, "BOTCITY_KEY", "key-fake")
    monkeypatch.setattr(config, "BOTCITY_ACTIVITY_LABEL", "performer-lotes-teste")


def _fake_item(lote_id, status, observacao, turno):
    valores = {
        "lote_id": lote_id,
        "produto": "Produto Teste",
        "linha": "LINHA_A",
        "turno": turno,
        "status": status,
        "responsavel": "Fulano",
        "data": "2026-07-15",
        "observacao": observacao,
    }
    item = MagicMock()
    item.get_value.side_effect = lambda chave, default="": valores.get(chave, default)
    return item


def _fake_datapool(itens):
    datapool = MagicMock()
    datapool.has_next.side_effect = [True] * len(itens) + [False]
    datapool.next.side_effect = list(itens)
    return datapool


def _fake_sdk(datapool):
    sdk = MagicMock()
    sdk.create_task.return_value = MagicMock(id=TASK_ID)
    sdk.get_datapool.return_value = datapool
    return sdk


def _monta_cenario_maestro(monkeypatch, itens=None):
    """Prepara modo Maestro com SDK mockado. Retorna (sdk, datapool, itens)."""
    monkeypatch.setattr(config, "MAESTRO_ENABLED", True)
    itens = itens if itens is not None else [_fake_item(*dados) for dados in LOTES_DA_FILA]
    datapool = _fake_datapool(itens)
    sdk = _fake_sdk(datapool)
    monkeypatch.setattr(performer, "BotMaestroSDK", MagicMock(return_value=sdk))
    return sdk, datapool, itens


def _resumo_do_artefato():
    with open(f"/tmp/resumo_performer_{TASK_ID}.json", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def test_dry_run_nao_chama_sdk(monkeypatch, tmp_path, caplog):
    sdk_classe_mock = MagicMock()
    monkeypatch.setattr(performer, "BotMaestroSDK", sdk_classe_mock)
    monkeypatch.setattr(config, "PASTA_ENTRADA", str(tmp_path))

    # L001 conforme, L002 conforme (reprovado com observação), L007 inativo -> RN03
    (tmp_path / performer.ARQUIVO_CSV).write_text(
        "lote_id,produto,linha,turno,status,responsavel,data,observacao\n"
        "L001,Camiseta,LINHA_A,MANHA,APROVADO,Ana,2026-07-15,\n"
        "L002,Calça,LINHA_B,TARDE,REPROVADO,Bruno,2026-07-15,Costura irregular\n"
        "L007,Bermuda,LINHA_C,MANHA,APROVADO,Fabio,2026-07-17,\n",
        encoding="utf-8",
    )

    caplog.set_level(logging.INFO)
    resultado = performer.main()

    assert resultado == 0
    sdk_classe_mock.assert_not_called()

    mensagens = " | ".join(r.message for r in caplog.records)
    assert "3 processados" in mensagens
    assert "2 conformes" in mensagens
    assert "1 com divergência" in mensagens
    assert "0 erros de sistema" in mensagens


def test_fluxo_completo_com_maestro_mockado(monkeypatch, base_ref):
    sdk, datapool, itens = _monta_cenario_maestro(monkeypatch)

    resultado = performer._executar_com_maestro(base_ref)

    assert resultado == 0
    assert sdk.create_task.call_count == 1
    assert datapool.next.call_count == 7

    reportados = sum(
        item.report_done.call_count + item.report_error.call_count for item in itens
    )
    assert reportados == 7

    assert sdk.post_artifact.call_count == 1
    assert sdk.finish_task.call_count == 1

    resumo = _resumo_do_artefato()
    assert resumo["total_processados"] == 7
    assert resumo["total_erros_sistema"] == 0
    # L001, L002 e L003 estão conformes; os outros quatro têm divergência.
    assert resumo["total_conformes"] == 3
    assert resumo["total_com_divergencia"] == 4
    assert resumo["task_id"] == TASK_ID


def test_item_invalido_nao_aborta_loop(monkeypatch, base_ref):
    sdk, datapool, itens = _monta_cenario_maestro(monkeypatch)

    chamadas = {"n": 0}
    avaliar_real = performer.avaliar_lote

    def avaliar_com_falha(lote, base):
        chamadas["n"] += 1
        if chamadas["n"] == 3:
            raise RuntimeError("falha inesperada ao avaliar")
        return avaliar_real(lote, base)

    monkeypatch.setattr(performer, "avaliar_lote", avaliar_com_falha)

    resultado = performer._executar_com_maestro(base_ref)

    assert resultado == 0
    # O loop seguiu até o fim da fila, apesar da exceção no 3º item.
    assert datapool.next.call_count == 7

    # O 3º item foi marcado como erro de sistema.
    itens[2].report_error.assert_called_once()
    assert itens[2].report_error.call_args.kwargs["error_type"] == performer.ErrorType.SYSTEM
    itens[2].report_done.assert_not_called()

    # Os itens seguintes continuaram sendo processados normalmente.
    assert itens[6].report_done.call_count + itens[6].report_error.call_count == 1

    resumo = _resumo_do_artefato()
    assert resumo["total_erros_sistema"] == 1
    assert resumo["total_processados"] == 7
    assert sdk.finish_task.call_count == 1


def test_pasta_entrada_ausente_emite_alerta_e_encerra(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(config, "MAESTRO_ENABLED", True)
    monkeypatch.setattr(config, "PASTA_ENTRADA", str(tmp_path / "inexistente"))

    sdk = MagicMock()
    sdk.create_task.return_value = MagicMock(id=TASK_ID)
    monkeypatch.setattr(performer, "BotMaestroSDK", MagicMock(return_value=sdk))

    caplog.set_level(logging.INFO)
    resultado = performer.main()

    assert resultado == 1
    sdk.alert.assert_called_once()
    assert sdk.alert.call_args.kwargs["alert_type"] == performer.AlertType.ERROR
    # A task criada só para o alerta é encerrada, não fica órfã.
    sdk.finish_task.assert_called_once()


def test_erro_de_login_relevanta_performer_error_sanitizada(monkeypatch, base_ref, caplog):
    monkeypatch.setattr(config, "MAESTRO_ENABLED", True)

    mensagem_sensivel = "401 Unauthorized: senha=vazou"
    sdk = MagicMock()
    sdk.login.side_effect = Exception(mensagem_sensivel)
    monkeypatch.setattr(performer, "BotMaestroSDK", MagicMock(return_value=sdk))

    caplog.set_level(logging.INFO)

    with pytest.raises(performer.PerformerError):
        performer._executar_com_maestro(base_ref)

    for record in caplog.records:
        assert "vazou" not in record.message
        assert mensagem_sensivel not in record.message


def test_falha_de_post_artifact_nao_derruba_finalizacao(monkeypatch, base_ref, caplog):
    sdk, _datapool, _itens = _monta_cenario_maestro(monkeypatch)
    sdk.post_artifact.side_effect = Exception("500 Internal Server Error")

    caplog.set_level(logging.INFO)
    resultado = performer._executar_com_maestro(base_ref)

    assert resultado == 0
    sdk.finish_task.assert_called_once()
    assert any("Falha ao postar artefato" in r.message for r in caplog.records)
