"""
Testes unitários das validações de estrutura e campos obrigatórios.
Cobre RN01 (valida_estrutura) e RN02 (valida_campos_obrigatorios) do PDD v0.2 seção 12.
Executar da raiz do projeto com:  python -m pytest -v
"""

import numpy as np
import pandas as pd

from src.modules.validacao import valida_campos_obrigatorios, valida_estrutura


def _planilha_valida() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "lote_id": "L001",
                "produto": "Monitor 24pol",
                "linha": "LT-03",
                "turno": "A",
                "status": "OK",
                "responsavel": "Ana Souza",
                "data": "2025-11-01",
                "observacao": "",
            }
        ]
    )


def test_estrutura_completa_nao_retorna_erro():
    assert valida_estrutura(_planilha_valida()) == []


def test_estrutura_faltando_uma_coluna():
    df = _planilha_valida().drop(columns=["status"])
    assert valida_estrutura(df) == ["status"]


def test_estrutura_faltando_varias_colunas():
    df = _planilha_valida().drop(columns=["status", "data"])
    assert set(valida_estrutura(df)) == {"status", "data"}


def test_campos_obrigatorios_todos_preenchidos():
    assert valida_campos_obrigatorios(_planilha_valida()) == []


def test_campo_vazio_texto_em_branco():
    df = _planilha_valida()
    df.loc[0, "responsavel"] = "   "
    assert valida_campos_obrigatorios(df) == [{"linha": 2, "campo": "responsavel"}]


def test_campo_vazio_none():
    df = _planilha_valida()
    df.loc[0, "produto"] = None
    assert valida_campos_obrigatorios(df) == [{"linha": 2, "campo": "produto"}]


def test_campo_vazio_nan():
    df = _planilha_valida()
    df.loc[0, "lote_id"] = np.nan
    assert valida_campos_obrigatorios(df) == [{"linha": 2, "campo": "lote_id"}]


def test_observacao_vazia_nao_e_erro_na_rn02():
    df = _planilha_valida()
    df.loc[0, "observacao"] = ""
    assert valida_campos_obrigatorios(df) == []


def test_multiplas_linhas_com_campos_vazios():
    df = pd.concat([_planilha_valida(), _planilha_valida()], ignore_index=True)
    df.loc[0, "turno"] = None
    df.loc[1, "data"] = ""
    ocorrencias = valida_campos_obrigatorios(df)
    assert {"linha": 2, "campo": "turno"} in ocorrencias
    assert {"linha": 3, "campo": "data"} in ocorrencias
    assert len(ocorrencias) == 2