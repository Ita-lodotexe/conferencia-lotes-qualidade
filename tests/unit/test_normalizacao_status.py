# tests/test_issue_03.py
# Testes referentes à Issue #3 — RN04 e RN05

import pytest
from src.modules.normalizacao_status import normalizar_status, validar_status

pytestmark = pytest.mark.unit


class TestNormalizarStatusRN05:
    """RN05 — OK vira APROVADO, NOK vira REPROVADO, antes de qualquer validação."""

    @pytest.mark.regression
    def test_ok_normaliza_para_aprovado(self):
        assert normalizar_status("OK") == "APROVADO"

    @pytest.mark.regression
    def test_nok_normaliza_para_reprovado(self):
        assert normalizar_status("NOK") == "REPROVADO"

    def test_case_insensitive(self):
        assert normalizar_status("ok") == "APROVADO"
        assert normalizar_status("Nok") == "REPROVADO"

    def test_remove_espacos_nas_pontas(self):
        assert normalizar_status("  OK  ") == "APROVADO"

    def test_status_ja_valido_nao_e_alterado(self):
        assert normalizar_status("APROVADO") == "APROVADO"
        assert normalizar_status("REPROVADO") == "REPROVADO"
        assert normalizar_status("PENDENTE") == "PENDENTE"

    def test_status_nao_normalizavel_permanece_intacto(self):
        # RN05 só conhece OK/NOK; abreviações não são "adivinhadas" aqui.
        # Quem decide o destino desses casos é a RN04 (-> RN06).
        assert normalizar_status("REPROV.") == "REPROV."
        assert normalizar_status("APROVADO PARCIAL") == "APROVADO PARCIAL"

    def test_none_retorna_none(self):
        assert normalizar_status(None) is None

    def test_string_vazia_retorna_none(self):
        assert normalizar_status("") is None
        assert normalizar_status("   ") is None


class TestValidarStatusRN04:
    """RN04 — só passa quem, após normalizado, for APROVADO/REPROVADO/PENDENTE."""

    def test_ok_e_valido_apos_normalizacao(self):
        # Caso real: LG-2026-00105
        resultado = validar_status("OK")
        assert resultado["status_normalizado"] == "APROVADO"
        assert resultado["valido"] is True
        assert resultado["ambiguo"] is False

    def test_nok_e_valido_apos_normalizacao(self):
        # Caso real: LG-2026-00107
        resultado = validar_status("NOK")
        assert resultado["status_normalizado"] == "REPROVADO"
        assert resultado["valido"] is True
        assert resultado["ambiguo"] is False

    def test_pendente_e_valido(self):
        resultado = validar_status("PENDENTE")
        assert resultado["valido"] is True
        assert resultado["ambiguo"] is False

    def test_reprov_abreviado_e_ambiguo(self):
        # Caso real: LG-2026-00112 — deve ir para RN06, não ser decidido aqui
        resultado = validar_status("REPROV.")
        assert resultado["valido"] is False
        assert resultado["ambiguo"] is True

    def test_aprovado_parcial_e_ambiguo(self):
        # Caso real: LG-2026-00118 — deve ir para RN06, não ser decidido aqui
        resultado = validar_status("APROVADO PARCIAL")
        assert resultado["valido"] is False
        assert resultado["ambiguo"] is True

    def test_status_original_e_preservado_no_retorno(self):
        # Importante para o relatório de divergências rastrear o valor cru
        resultado = validar_status("nok")
        assert resultado["status_original"] == "nok"
        assert resultado["status_normalizado"] == "REPROVADO"

    def test_status_none_e_ambiguo_mas_nao_e_papel_desta_funcao_decidir_isso(self):
        # Campo vazio é responsabilidade da RN02 (Issue #1). Aqui só garantimos
        # que a função não quebra e não classifica None como válido.
        resultado = validar_status(None)
        assert resultado["valido"] is False
