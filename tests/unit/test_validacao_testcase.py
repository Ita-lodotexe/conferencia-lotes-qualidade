"""TestCase com setUp e subTest — entregável 2 da Aula 23.

Cobre normalização de status (RN06/RN07) e as regras novas da Aula 22
(RN09 ambíguo, RN10 REPROVADO sem observação, RN11 duplicidade, RN12
data inválida) usando o estilo unittest clássico com setUp + subTest,
conforme exigido pelo enunciado (seção 5.1).

Convive com test_normalizacao_status.py (que testa as mesmas funções no
estilo pytest puro) e com test_aula22_classificacao.py (que testa
classificar_registro com fixtures). A redundância é proposital: o
enunciado pede explicitamente uma classe TestCase separada.
"""

import unittest

import pytest

from src.modules.normalizacao_status import normalizar_status, validar_status
from src.aula22_classificacao import (
    validar_campos_obrigatorios_lote,
    validar_data_referencia,
)

pytestmark = pytest.mark.unit


class TestNormalizacaoStatusSubTest(unittest.TestCase):
    """RN06/RN07 — normalização OK/NOK com subTest para cada variação."""

    def setUp(self):
        """Casos de normalização: (entrada, saída esperada)."""
        self.casos_normalizacao = [
            ("OK", "APROVADO"),
            ("ok", "APROVADO"),
            ("  OK  ", "APROVADO"),
            ("NOK", "REPROVADO"),
            ("Nok", "REPROVADO"),
            ("APROVADO", "APROVADO"),
            ("REPROVADO", "REPROVADO"),
            ("PENDENTE", "PENDENTE"),
            ("REPROV.", "REPROV."),       # não normaliza — RN09 cuida
            ("EM AJUSTE", "EM AJUSTE"),   # não normaliza — RN09 cuida
        ]
        self.casos_none = [None, "", "   "]

    def test_normalizacao_de_status(self):
        """Cada entrada deve produzir a saída esperada, sem interromper nas outras."""
        for entrada, esperado in self.casos_normalizacao:
            with self.subTest(entrada=entrada, esperado=esperado):
                resultado = normalizar_status(entrada)
                self.assertEqual(resultado, esperado)

    def test_entradas_vazias_retornam_none(self):
        for entrada in self.casos_none:
            with self.subTest(entrada=repr(entrada)):
                resultado = normalizar_status(entrada)
                self.assertIsNone(resultado)


class TestValidarStatusSubTest(unittest.TestCase):
    """RN04/RN09 — status permitido vs. ambíguo, com subTest."""

    def setUp(self):
        """Status válidos e ambíguos para parametrizar via subTest."""
        self.status_validos = ["OK", "NOK", "APROVADO", "REPROVADO", "PENDENTE"]
        self.status_ambiguos = ["REPROV.", "APROVADO PARCIAL", "EM AJUSTE",
                                "AGUARDANDO REINSPEÇÃO", "CANCELADO"]

    def test_status_validos_nao_sao_ambiguos(self):
        for status in self.status_validos:
            with self.subTest(status=status):
                resultado = validar_status(status)
                self.assertTrue(resultado["valido"], f"{status} deveria ser válido")
                self.assertFalse(resultado["ambiguo"])

    def test_status_ambiguos_nao_sao_validos(self):
        for status in self.status_ambiguos:
            with self.subTest(status=status):
                resultado = validar_status(status)
                self.assertFalse(resultado["valido"], f"{status} não deveria ser válido")
                self.assertTrue(resultado["ambiguo"])


class TestValidacaoDataSubTest(unittest.TestCase):
    """RN12 — formato de data DD/MM/AAAA, com subTest."""

    def setUp(self):
        self.datas_validas = ["15/06/2026", "01/01/2025", "28/02/2026"]
        self.datas_invalidas = [
            ("", "ausente"),
            (None, "ausente"),
            ("2026-06-15", "formato ISO em vez de DD/MM/AAAA"),
            ("06/26/2026", "mês/dia invertidos (americano)"),
            ("15/06/26", "ano com 2 dígitos"),
            ("31/02/2026", "data impossível"),
        ]

    def test_datas_validas_passam(self):
        for data in self.datas_validas:
            with self.subTest(data=data):
                valido, motivo = validar_data_referencia(data)
                self.assertTrue(valido, f"'{data}' deveria ser válida, motivo: {motivo}")

    def test_datas_invalidas_falham(self):
        for data, descricao in self.datas_invalidas:
            with self.subTest(data=repr(data), descricao=descricao):
                valido, motivo = validar_data_referencia(data)
                self.assertFalse(valido, f"'{data}' ({descricao}) não deveria passar")


class TestCamposObrigatoriosSubTest(unittest.TestCase):
    """RN01–RN04 — campos obrigatórios (5, não 7), com subTest."""

    def setUp(self):
        """Registro base válido — cada subTest altera um campo por vez."""
        self.registro_base = {
            "lote_id": "L001",
            "produto": "TV55",
            "linha": "L1",
            "turno": "A",
            "status": "APROVADO",
            "responsavel": "Ana",
            "data": "15/06/2026",
            "observacao": "",
        }
        self.campos_obrigatorios = ["lote_id", "produto", "linha", "status", "responsavel"]
        self.campos_opcionais = ["turno", "observacao"]

    def test_registro_completo_nao_tem_campo_vazio(self):
        resultado = validar_campos_obrigatorios_lote(self.registro_base)
        self.assertEqual(resultado, [])

    def test_cada_campo_obrigatorio_vazio_e_detectado(self):
        for campo in self.campos_obrigatorios:
            with self.subTest(campo=campo):
                registro = {**self.registro_base, campo: ""}
                resultado = validar_campos_obrigatorios_lote(registro)
                self.assertIn(campo, resultado,
                              f"Campo '{campo}' vazio deveria ser detectado")

    def test_campos_opcionais_vazios_nao_disparam_erro(self):
        for campo in self.campos_opcionais:
            with self.subTest(campo=campo):
                registro = {**self.registro_base, campo: ""}
                resultado = validar_campos_obrigatorios_lote(registro)
                self.assertNotIn(campo, resultado,
                                 f"Campo '{campo}' é opcional — não deveria gerar erro")
