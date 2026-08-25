"""Testes unitários para retry com backoff, dead letter e PENDENTE_REVISAO.

Cobre os requisitos do Estudo de Caso S10-B §3.3:
- Retry com backoff linear para falhas de infraestrutura (base de referência)
- Dead letter para itens irrecuperáveis por motivo de DADO (BUSINESS)
- Status PENDENTE_REVISAO quando a base está indisponível após todos os retries
"""

import json
import os
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def base_referencia_mock():
    return pd.DataFrame([
        {"lote_id": "LG-2026-00101", "status_cadastro": "Ativo"},
        {"lote_id": "LG-2026-00104", "status_cadastro": "Ativo"},
    ])


@pytest.fixture
def lote_divergente():
    return {
        "lote_id": "LG-9999-99999",
        "produto": "TV55-4K-B",
        "linha": "L1",
        "turno": "A",
        "status": "APROVADO",
        "responsavel": "Carlos Menezes",
        "data": "14/06/2026",
        "observacao": "digitei errado o codigo",
    }


@pytest.fixture
def lote_valido():
    return {
        "lote_id": "LG-2026-00101",
        "produto": "TV55-4K-B",
        "linha": "L1",
        "turno": "A",
        "status": "APROVADO",
        "responsavel": "Carlos Menezes",
        "data": "14/06/2026",
        "observacao": "",
    }


# ── Testes de Retry com Backoff Linear ────────────────────────────────────────

class TestRetryComBackoff:
    """Testa o comportamento de retry com backoff linear ao carregar a base de referência."""

    def test_retry_sucesso_na_segunda_tentativa(self, monkeypatch):
        """Simula 1 falha + 1 sucesso: a base é carregada na segunda tentativa."""
        from src.bot import performer

        base_mock = pd.DataFrame([{"lote_id": "L1", "status_cadastro": "Ativo"}])
        chamadas = {"n": 0}

        def carregar_instavel(*args):
            chamadas["n"] += 1
            if chamadas["n"] == 1:
                raise FileNotFoundError("base temporariamente inacessível")
            return base_mock

        monkeypatch.setattr(performer, "carregar_base_referencia", carregar_instavel)
        monkeypatch.setattr(performer.config, "CAMINHO_BASE_REFERENCIA", "base_inexistente.csv")
        monkeypatch.setattr("time.sleep", MagicMock())  # sem espera real no teste

        resultado = performer.carregar_base_com_retry()

        assert resultado is not None
        assert chamadas["n"] == 2  # 1 falha + 1 sucesso

    def test_retry_backoff_linear_dormidas_corretas(self, monkeypatch):
        """Verifica que o sleep é chamado com 1s e 2s (backoff linear)."""
        from src.bot import performer

        monkeypatch.setattr(performer, "carregar_base_referencia",
                            MagicMock(side_effect=FileNotFoundError("falha")))
        monkeypatch.setattr(performer.config, "CAMINHO_BASE_REFERENCIA", "inexistente.csv")

        mock_enviar_alerta = MagicMock(return_value={"sucesso": False})
        monkeypatch.setattr(performer, "enviar_alerta", mock_enviar_alerta)

        sleep_mock = MagicMock()
        monkeypatch.setattr("time.sleep", sleep_mock)

        resultado = performer.carregar_base_com_retry()

        # Verifica backoff linear: tentativa 1 → 1s, tentativa 2 → 2s
        assert sleep_mock.call_count == 2
        assert sleep_mock.call_args_list[0] == call(1.0)
        assert sleep_mock.call_args_list[1] == call(2.0)
        assert resultado is None  # todas as 3 tentativas esgotadas

    def test_retry_esgotado_dispara_alerta_erro(self, monkeypatch):
        """Ao esgotar as tentativas, deve disparar alerta com severidade ERRO."""
        from src.bot import performer

        monkeypatch.setattr(performer, "carregar_base_referencia",
                            MagicMock(side_effect=FileNotFoundError("falha persistente")))
        monkeypatch.setattr(performer.config, "CAMINHO_BASE_REFERENCIA", "inexistente.csv")
        monkeypatch.setattr("time.sleep", MagicMock())

        mock_alerta = MagicMock(return_value={"sucesso": True})
        monkeypatch.setattr(performer, "enviar_alerta", mock_alerta)

        resultado = performer.carregar_base_com_retry()

        assert resultado is None
        mock_alerta.assert_called_once()
        call_kwargs = mock_alerta.call_args[1]
        assert call_kwargs["severidade"] == "ERRO"
        assert "Base de Referência" in call_kwargs["titulo"]

    def test_retry_retorna_none_quando_base_indisponivel(self, monkeypatch):
        """Retornar None é o contrato correto quando todas as tentativas falham."""
        from src.bot import performer

        monkeypatch.setattr(performer, "carregar_base_referencia",
                            MagicMock(side_effect=Exception("rede fora")))
        monkeypatch.setattr(performer.config, "CAMINHO_BASE_REFERENCIA", "inexistente.csv")
        monkeypatch.setattr("time.sleep", MagicMock())
        monkeypatch.setattr(performer, "enviar_alerta", MagicMock())

        resultado = performer.carregar_base_com_retry()
        assert resultado is None


# ── Testes de Dead Letter ─────────────────────────────────────────────────────

class TestDeadLetter:
    """Testa a gravação de itens irrecuperáveis no dead_letter.jsonl."""

    def test_dead_letter_cria_arquivo_jsonl(self, tmp_path, monkeypatch):
        """Um item com falha de dado deve ser gravado em dead_letter.jsonl."""
        from src.bot import performer

        caminho_dl = tmp_path / "dead_letter.jsonl"
        monkeypatch.setattr(performer, "_CAMINHO_DEAD_LETTER", caminho_dl)

        lote = {"lote_id": "LG-9999-99999", "produto": "TV55"}
        performer.registrar_dead_letter(lote, motivo="RN03", detalhes="Lote não encontrado")

        assert caminho_dl.exists()
        linha = json.loads(caminho_dl.read_text(encoding="utf-8").strip())
        assert linha["lote_id"] == "LG-9999-99999"
        assert linha["motivo_negocio"] == "RN03"
        assert linha["detalhes"] == "Lote não encontrado"

    def test_dead_letter_multiplos_itens_acumulam(self, tmp_path, monkeypatch):
        """Múltiplos itens devem acumular no mesmo arquivo (JSONL)."""
        from src.bot import performer

        caminho_dl = tmp_path / "dead_letter.jsonl"
        monkeypatch.setattr(performer, "_CAMINHO_DEAD_LETTER", caminho_dl)

        performer.registrar_dead_letter({"lote_id": "L1"}, "RN02", "campo vazio")
        performer.registrar_dead_letter({"lote_id": "L2"}, "RN03", "não cadastrado")
        performer.registrar_dead_letter({"lote_id": "L3"}, "RN07", "sem observação")

        linhas = caminho_dl.read_text(encoding="utf-8").strip().split("\n")
        assert len(linhas) == 3
        ids = [json.loads(l)["lote_id"] for l in linhas]
        assert ids == ["L1", "L2", "L3"]

    def test_dead_letter_falha_de_io_nao_propaga_excecao(self, monkeypatch):
        """Erro ao gravar no dead letter nunca deve interromper o pipeline."""
        from src.bot import performer

        # Apontar para caminho impossível de criar
        monkeypatch.setattr(performer, "_CAMINHO_DEAD_LETTER",
                            Path("/caminho/impossivel/dead_letter.jsonl"))

        # Não deve levantar exceção
        performer.registrar_dead_letter({"lote_id": "L1"}, "RN03")


# ── Testes de PENDENTE_REVISAO ─────────────────────────────────────────────────

class TestPendenteRevisao:
    """Testa o status PENDENTE_REVISAO quando a base de referência está indisponível."""

    def test_auditoria_local_com_base_none_gera_pendente_revisao(self, monkeypatch, tmp_path):
        """Quando base_ref=None, todos os itens devem ter status_auditoria=PENDENTE_REVISAO."""
        from src.bot import performer

        # CSV de entrada mínimo
        csv_content = "lote_id,produto,linha,turno,status,responsavel,data,observacao\n"
        csv_content += "LG-001,TV55,L1,A,APROVADO,Ana,01/01/2026,\n"
        csv_content += "LG-002,TV65,L1,B,REPROVADO,Bia,01/01/2026,sem obs\n"
        csv_file = tmp_path / "dados_relatorio.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        monkeypatch.setattr(performer.config, "PASTA_ENTRADA", str(tmp_path))
        monkeypatch.setattr(performer.config, "ARQUIVO_CSV_ENTRADA", "dados_relatorio.csv")

        # Patch do dead_letter para não tentar criar arquivo
        monkeypatch.setattr(performer, "_CAMINHO_DEAD_LETTER", tmp_path / "dead_letter.jsonl")
        # ML desabilitado para simplificar
        monkeypatch.setenv("ML_ENABLED", "false")

        resumo = performer.executar_auditoria_local(base_ref=None)

        assert resumo["total_processados"] == 2
        assert resumo["total_pendentes_revisao"] == 2
        assert resumo["total_conformes"] == 0
        assert resumo["total_com_divergencia"] == 0

        for div in resumo["divergencias_detalhadas"]:
            assert div["status_auditoria"] == "PENDENTE_REVISAO"
            assert div["regra"] == "INFRA"
            assert div["causa_provavel"] == "base_indisponivel"

    def test_auditoria_local_com_base_valida_nao_gera_pendente(
        self, monkeypatch, tmp_path, base_referencia_mock
    ):
        """Quando base_ref é válida, não deve haver itens PENDENTE_REVISAO."""
        from src.bot import performer

        csv_content = "lote_id,produto,linha,turno,status,responsavel,data,observacao\n"
        csv_content += "LG-2026-00101,TV55,L1,A,APROVADO,Ana,01/01/2026,\n"
        csv_file = tmp_path / "dados_relatorio.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        monkeypatch.setattr(performer.config, "PASTA_ENTRADA", str(tmp_path))
        monkeypatch.setattr(performer.config, "ARQUIVO_CSV_ENTRADA", "dados_relatorio.csv")
        monkeypatch.setattr(performer, "_CAMINHO_DEAD_LETTER", tmp_path / "dead_letter.jsonl")
        monkeypatch.setenv("ML_ENABLED", "false")

        resumo = performer.executar_auditoria_local(base_ref=base_referencia_mock)

        assert resumo["total_pendentes_revisao"] == 0
        assert resumo["total_conformes"] == 1
