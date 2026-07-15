"""
Testes para o módulo `src/modules/verificacao_lotes.py`.

Observação importante sobre a arquitetura testada:
O módulo lê o CSV e pode chamar `sys.exit()` no momento da IMPORTAÇÃO
(fora de qualquer função). Isso torna o módulo difícil de testar de forma
isolada, porque não dá pra "chamar uma função com mock" sem antes já ter
pago o custo de um sys.exit() real caso o arquivo não exista. Os testes
abaixo contornam isso com `importlib.reload`, mas o ideal (ver README)
seria mover essa leitura para dentro de uma função.

Execute com: pytest -v  (a partir da raiz do projeto)
"""

import importlib
import sys
import pandas as pd
import pytest
import logging

from src.modules import verificacao_lotes as modulo


@pytest.fixture(autouse=True)
def restaurar_base_lotes():
    """Garante que cada teste comece com o DataFrame original e não
    vaze estado (mutações) de um teste para o outro."""
    original = modulo.BASE_LOTES.copy()
    yield
    modulo.BASE_LOTES = original


@pytest.fixture
def base_padrao(monkeypatch):
    """Substitui BASE_LOTES por um conjunto de dados controlado,
    conhecido, sem depender do CSV real em disco."""
    df = pd.DataFrame({
        "lote_id": ["LOTE001", "LOTE002", "LOTE003"],
        "status_cadastro": ["Ativo", "Inativo", "Ativo"],
    })
    monkeypatch.setattr(modulo, "BASE_LOTES", df)
    return df


# ---------------------------------------------------------------------
# RN03 — Existência do lote
# ---------------------------------------------------------------------

def test_lote_existente_retorna_true(base_padrao, caplog):
    caplog.set_level(logging.INFO)
    assert modulo.verificar_existencia_lote("LOTE001") is True
    assert "encontrado" in caplog.text.lower()


def test_lote_inexistente_retorna_false(base_padrao, caplog):
    assert modulo.verificar_existencia_lote("LOTE999") is False
    assert "não encontrado" in caplog.text.lower()


def test_existencia_e_case_sensitive(base_padrao):
    """Documenta um comportamento (possível ponto cego): a busca
    diferencia maiúsculas/minúsculas. 'lote001' != 'LOTE001'."""
    assert modulo.verificar_existencia_lote("lote001") is False


def test_string_vazia_nao_existe(base_padrao):
    assert modulo.verificar_existencia_lote("") is False


# ---------------------------------------------------------------------
# Status do lote (depende da existência)
# ---------------------------------------------------------------------

def test_status_lote_ativo_retorna_true(base_padrao):
    assert modulo.verificar_status_lote("LOTE001") is True


def test_status_lote_inativo_retorna_false(base_padrao):
    assert modulo.verificar_status_lote("LOTE002") is False


def test_status_lote_inexistente_retorna_none(base_padrao):
    """Quando o lote não existe, a função deve retornar None
    (nem True, nem False) e não deve levantar exceção."""
    assert modulo.verificar_status_lote("LOTE999") is None


def test_status_outros_valores_alem_de_ativo_conta_como_falso(monkeypatch):
    """Ponto cego: qualquer status diferente de 'Ativo' (ex.: 'Suspenso',
    'Pendente', 'ativo' em minúsculas) é tratado como se fosse 'Inativo'.
    Isso pode mascarar erros de digitação na planilha de origem."""
    df = pd.DataFrame({
        "lote_id": ["LOTE010"],
        "status_cadastro": ["Suspenso"],
    })
    monkeypatch.setattr(modulo, "BASE_LOTES", df)
    assert modulo.verificar_status_lote("LOTE010") is False


# ---------------------------------------------------------------------
# Casos de borda que expõem falhas reais do código atual
# ---------------------------------------------------------------------

def test_lote_duplicado_quebra_a_funcao(monkeypatch):
    """BUG real: se houver lote_id duplicado na base (dado que a RN03
    não impede), `.item()` levanta ValueError porque espera exatamente
    um valor. Isso deixaria o sistema fora do ar em produção diante de
    um problema de qualidade de dados, em vez de tratar graciosamente."""
    df = pd.DataFrame({
        "lote_id": ["LOTE001", "LOTE001"],
        "status_cadastro": ["Ativo", "Inativo"],
    })
    monkeypatch.setattr(modulo, "BASE_LOTES", df)
    with pytest.raises(ValueError):
        modulo.verificar_status_lote("LOTE001")


def test_lote_none_e_tratado_silenciosamente_como_nao_encontrado(base_padrao):
    """Ponto cego mais sutil que um erro: a função NÃO valida o tipo de
    entrada e NÃO levanta exceção para None. Ela simplesmente devolve
    False, como se fosse um lote_id qualquer que não existe. Ou seja,
    um bug de código que gera `lote = None` em algum lugar acima na
    pilha vai silenciosamente virar 'lote não encontrado' no log, em
    vez de estourar um erro que apontaria a causa real."""
    assert modulo.verificar_existencia_lote(None) is False


def test_base_lotes_sem_coluna_esperada_levanta_keyerror(monkeypatch):
    """Se a planilha de origem mudar o nome da coluna (ex.: 'id_lote'
    em vez de 'lote_id'), a função falha com KeyError e não com uma
    mensagem de negócio clara."""
    df = pd.DataFrame({"id_lote": ["LOTE001"], "status": ["Ativo"]})
    monkeypatch.setattr(modulo, "BASE_LOTES", df)
    with pytest.raises(KeyError):
        modulo.verificar_existencia_lote("LOTE001")


# ---------------------------------------------------------------------
# Comportamento no momento da importação (leitura do CSV)
# ---------------------------------------------------------------------

def test_encerra_execucao_quando_arquivo_nao_existe(tmp_path, monkeypatch):
    """Confirma que, sem o CSV no caminho esperado, o módulo chama
    sys.exit() ao ser (re)importado — hoje esse é o único tratamento
    de erro existente para 'arquivo ausente'."""
    monkeypatch.chdir(tmp_path)  # diretório sem data/processed/*.csv
    try:
        with pytest.raises(SystemExit):
            importlib.reload(modulo)
    finally:
        # Restaura o módulo para um estado válido para os testes seguintes.
        monkeypatch.undo()
        importlib.reload(modulo)


def test_encerra_execucao_quando_arquivo_esta_corrompido_ou_vazio(tmp_path, monkeypatch):
    """Cobre o segundo `except Exception`. Um CSV vazio (ou corrompido)
    não gera FileNotFoundError, e sim um erro de parsing do pandas —
    cai no branch genérico, que também chama sys.exit().

    Bônus: essa mensagem de erro tem um bug de digitação no código
    original (`:/n` em vez de `:\\n`), então o "\\n" aparece literalmente
    na tela em vez de quebrar linha. Vale corrigir no fonte."""
    pasta = tmp_path / "data" / "processed"
    pasta.mkdir(parents=True)
    (pasta / "base_lotes_referencia.csv").write_text("")  # arquivo vazio

    monkeypatch.chdir(tmp_path)
    try:
        with pytest.raises(SystemExit):
            importlib.reload(modulo)
    finally:
        monkeypatch.undo()
        importlib.reload(modulo)


def test_carrega_base_lotes_com_sucesso_quando_arquivo_existe():
    """Teste de integração simples: com o CSV de verdade no lugar
    (ver data/processed/base_lotes_referencia.csv), o módulo importa
    sem erros e BASE_LOTES não fica vazio."""
    assert not modulo.BASE_LOTES.empty
    assert "lote_id" in modulo.BASE_LOTES.columns
    assert "status_cadastro" in modulo.BASE_LOTES.columns