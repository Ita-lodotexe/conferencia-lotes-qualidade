import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from observacao import lote_conforme_rn07


def test_lote_reprovado_sem_observacao_deve_falhar():
    lote = {"status": "REPROVADO", "observacao": ""}
    assert lote_conforme_rn07(lote) is False


def test_lote_reprovado_com_observacao_deve_passar():
    lote = {"status": "REPROVADO", "observacao": "Lote fora da validade."}
    assert lote_conforme_rn07(lote) is True


def test_lote_aprovado_sem_observacao_deve_passar():
    lote = {"status": "APROVADO", "observacao": ""}
    assert lote_conforme_rn07(lote) is True


def test_lote_reprovado_com_observacao_so_espacos_deve_falhar():
    lote = {"status": "reprovado", "observacao": "   "}
    assert lote_conforme_rn07(lote) is False


def test_lote_nok_variacao_de_caixa_sem_observacao_deve_falhar():
    lote = {"status": "nok", "observacao": None}
    assert lote_conforme_rn07(lote) is False


def test_lote_nok_maiusculo_com_observacao_deve_passar():
    lote = {"status": "NOK", "observacao": "Divergência de peso."}
    assert lote_conforme_rn07(lote) is True
