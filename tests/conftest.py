"""Fixtures e configurações compartilhadas pela suíte de testes (Aula 23)."""

import pandas as pd
import pytest


@pytest.fixture
def base_referencia():
    """Base_Referencia mockada — simula um sistema externo.

    Contém 3 lotes: L001 (Ativo), L002 (Inativo), L004 (Ativo).
    L003 não existe de propósito (testa RN05 — lote não cadastrado).
    """
    return pd.DataFrame(
        {
            "lote_id": ["L001", "L002", "L004"],
            "codigo_produto": ["TV", "TV", "TV"],
            "descricao_produto": ["Televisão", "Televisão", "Televisão"],
            "status_cadastro": ["Ativo", "Inativo", "Ativo"],
        }
    )
