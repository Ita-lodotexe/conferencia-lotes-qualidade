"""Testes para o módulo `src/modules/verificacao_lotes.py`.

Execute com: pytest -v  (a partir da raiz do projeto)
"""

import pandas as pd
import pandas.errors
import pytest

from src.modules import verificacao_lotes as modulo

pytestmark = pytest.mark.unit


@pytest.fixture
def base_padrao():
    return pd.DataFrame({
        "lote_id": ["LOTE001", "LOTE002", "LOTE003"],
        "status_cadastro": ["Ativo", "Inativo", "Ativo"],
    })


# ---------------------------------------------------------------------
# RN03 — Existência do lote
# ---------------------------------------------------------------------

def test_lote_existente_retorna_true(base_padrao, caplog):
    import logging

    caplog.set_level(logging.INFO)
    assert modulo.verificar_existencia_lote(base_padrao, "LOTE001") is True
    assert "encontrado" in caplog.text.lower()


def test_lote_inexistente_retorna_false(base_padrao, caplog):
    assert modulo.verificar_existencia_lote(base_padrao, "LOTE999") is False
    assert "não encontrado" in caplog.text.lower()


def test_existencia_e_case_sensitive(base_padrao):
    """Documenta um comportamento (possível ponto cego): a busca
    diferencia maiúsculas/minúsculas. 'lote001' != 'LOTE001'."""
    assert modulo.verificar_existencia_lote(base_padrao, "lote001") is False


def test_string_vazia_nao_existe(base_padrao):
    assert modulo.verificar_existencia_lote(base_padrao, "") is False


# ---------------------------------------------------------------------
# Status do lote (depende da existência)
# ---------------------------------------------------------------------

def test_status_lote_ativo_retorna_true(base_padrao):
    assert modulo.verificar_status_lote(base_padrao, "LOTE001") is True


def test_status_lote_inativo_retorna_false(base_padrao):
    assert modulo.verificar_status_lote(base_padrao, "LOTE002") is False


def test_status_lote_inexistente_retorna_none(base_padrao):
    """Quando o lote não existe, a função deve retornar None
    (nem True, nem False) e não deve levantar exceção."""
    assert modulo.verificar_status_lote(base_padrao, "LOTE999") is None


def test_status_outros_valores_alem_de_ativo_conta_como_falso():
    """Ponto cego: qualquer status diferente de 'Ativo' (ex.: 'Suspenso',
    'Pendente', 'ativo' em minúsculas) é tratado como se fosse 'Inativo'.
    Isso pode mascarar erros de digitação na planilha de origem."""
    df = pd.DataFrame({
        "lote_id": ["LOTE010"],
        "status_cadastro": ["Suspenso"],
    })
    assert modulo.verificar_status_lote(df, "LOTE010") is False


# ---------------------------------------------------------------------
# Casos de borda que expõem falhas reais do código atual
# ---------------------------------------------------------------------

@pytest.mark.regression
@pytest.mark.xfail(
    reason="Bug conhecido: verificar_status_lote usa .item() que levanta "
           "ValueError quando há lote_id duplicado na Base_Referencia — "
           "deveria retornar o status da primeira ocorrência ou sinalizar "
           "duplicidade de forma controlada (sem estourar exceção)",
    raises=ValueError,
    strict=True,
)
def test_lote_duplicado_deveria_ser_tratado_sem_excecao():
    """Comportamento desejado: com lote duplicado na base, a função
    deveria retornar um resultado (True/False) sem levantar exceção.
    Hoje levanta ValueError — por isso este teste é xfail."""
    df = pd.DataFrame({
        "lote_id": ["LOTE001", "LOTE001"],
        "status_cadastro": ["Ativo", "Inativo"],
    })
    # Quando o bug for corrigido, esta linha vai funcionar sem exceção
    # e o teste vai passar (XPASS → strict faz ele virar FAIL, avisando
    # que o xfail pode ser removido)
    resultado = modulo.verificar_status_lote(df, "LOTE001")
    assert resultado in (True, False)


def test_lote_none_e_tratado_silenciosamente_como_nao_encontrado(base_padrao):
    """Ponto cego mais sutil que um erro: a função NÃO valida o tipo de
    entrada e NÃO levanta exceção para None. Ela simplesmente devolve
    False, como se fosse um lote_id qualquer que não existe. Ou seja,
    um bug de código que gera `lote = None` em algum lugar acima na
    pilha vai silenciosamente virar 'lote não encontrado' no log, em
    vez de estourar um erro que apontaria a causa real."""
    assert modulo.verificar_existencia_lote(base_padrao, None) is False


def test_base_lotes_sem_coluna_esperada_levanta_keyerror():
    """Se a planilha de origem mudar o nome da coluna (ex.: 'id_lote'
    em vez de 'lote_id'), a função falha com KeyError e não com uma
    mensagem de negócio clara."""
    df = pd.DataFrame({"id_lote": ["LOTE001"], "status": ["Ativo"]})
    with pytest.raises(KeyError):
        modulo.verificar_existencia_lote(df, "LOTE001")


# ---------------------------------------------------------------------
# carregar_base_referencia — leitura do CSV a partir de um caminho
# ---------------------------------------------------------------------

def test_carregar_base_referencia_levanta_filenotfound_quando_arquivo_nao_existe(tmp_path):
    """Sem sys.exit(): o chamador decide o que fazer com o erro."""
    caminho = tmp_path / "nao-existe.csv"
    with pytest.raises(FileNotFoundError):
        modulo.carregar_base_referencia(str(caminho))


def test_carregar_base_referencia_levanta_excecao_quando_arquivo_corrompido_ou_vazio(tmp_path):
    caminho = tmp_path / "base_lotes_referencia.csv"
    caminho.write_text("")  # arquivo vazio

    with pytest.raises(pandas.errors.EmptyDataError):
        modulo.carregar_base_referencia(str(caminho))


def test_carregar_base_referencia_retorna_dataframe_quando_arquivo_existe(tmp_path):
    caminho = tmp_path / "base_lotes_referencia.csv"
    caminho.write_text("lote_id,status_cadastro\nLOTE001,Ativo\n")

    base = modulo.carregar_base_referencia(str(caminho))

    assert not base.empty
    assert "lote_id" in base.columns
    assert "status_cadastro" in base.columns


# ---------------------------------------------------------------------
# Regras futuras (ainda não implementadas)
# ---------------------------------------------------------------------

@pytest.mark.skip(
    reason="RN13 (tolerância de data ±1 dia útil) ainda não implementada — "
           "regra futura prevista para quando o pipeline processar dados "
           "com atraso de envio (ex.: planilha de sexta chega só na segunda)"
)
def test_tolerancia_de_data_permite_1_dia_util_de_atraso():
    """Quando implementada, a RN13 deve aceitar que a data do registro
    esteja até 1 dia útil antes/depois da data da aba, sem classificar
    como Erro de Entrada."""
    # Arrange: registro do dia 15 (segunda) com data 16 (terça) — 1 dia útil
    # Act: classificar_registro(...)
    # Assert: não deve ser Erro de Entrada por RN12
    pass
