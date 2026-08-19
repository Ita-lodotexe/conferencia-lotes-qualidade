"""Motor de classificação da Aula 22 — Dashboard Excel e Relatórios.

Reaproveita os módulos existentes de RN01–RN07 (numeração BotCity) e
implementa apenas o que é novo para a Aula 22:

  - RegistroValidado (dataclass) — não existia no projeto.
  - RN11 (duplicidade por dia)   — não existia no projeto.
  - RN12 (formato de data)       — não existia no projeto.
  - CAMPOS_OBRIGATORIOS_LOTE     — conjunto de 5 campos obrigatórios da
    Aula 22, DIFERENTE do CAMPOS_OBRIGATORIOS de validacao.py (7 campos,
    usado pelo fluxo BotCity). Não alteramos validacao.py de propósito:
    ele continua servindo o fluxo antigo sem risco de regressão.

Reaproveitamento direto, sem alteração de lógica:
  - valida_estrutura(df)                    -> RN01 (Aula 22)
  - normalizar_status() / validar_status()  -> RN06/RN07 (normalização) e
                                                 RN09 (ambíguo) da Aula 22
  - verificar_existencia_lote/status_lote   -> RN05 (Aula 22)
  - lote_conforme_rn07()                    -> RN10 (Aula 22) — a lógica
    "REPROVADO sem observação" é idêntica, só muda o rótulo do relatório.
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from src.modules.validacao import valida_estrutura, _esta_vazio
from src.modules.normalizacao_status import normalizar_status, validar_status
from src.modules.verificacao_lotes import (
    verificar_existencia_lote,
    verificar_status_lote,
)
from src.modules.observacao import lote_conforme_rn07

logger = logging.getLogger("aula22.classificacao")

# RN01–RN04 (Aula 22): campos obrigatórios — 5 campos, confirmados
# empiricamente contra o Gabarito_Instrutor (produto, linha, status,
# responsavel, lote_id, em rotação de 5 em 5 dias). NÃO é o mesmo
# conjunto do CAMPOS_OBRIGATORIOS de validacao.py (7 campos, fluxo
# BotCity antigo) — propositalmente separado para não regredir aquele
# fluxo.
CAMPOS_OBRIGATORIOS_LOTE = ["lote_id", "produto", "linha", "status", "responsavel"]

CLASSIFICACOES = ("Válido", "Divergência", "Ambíguo", "Erro de Entrada")

FORMATO_DATA_ESPERADO = "%d/%m/%Y"


@dataclass
class RegistroValidado:
    """Um registro (lote) já classificado em uma das 4 categorias."""

    dia: str                 # nome da aba de origem, ex.: "Insp_15_06_2026"
    data_referencia: str     # data do dia de coleta, ex.: "15/06/2026"
    linha_planilha: int      # índice da linha na aba de origem (para rastreio)
    lote_id: str
    produto: str
    linha: str
    turno: str
    status_original: str
    status_normalizado: str | None
    responsavel: str
    data_lote: str            # valor bruto da coluna "data" do registro
    observacao: str
    ocorrencia_no_dia: int     # 1ª, 2ª, 3ª... ocorrência do lote_id naquele dia
    classificacao: str         # um de CLASSIFICACOES
    regra: str                 # ex.: "RN05", "RN11", "RN12", "RN01-04"
    motivo: str                # descrição legível, sem jargão de código

    def to_dict(self) -> dict:
        return {
            "dia": self.dia,
            "data_referencia": self.data_referencia,
            "linha_planilha": self.linha_planilha,
            "lote_id": self.lote_id,
            "produto": self.produto,
            "linha": self.linha,
            "turno": self.turno,
            "status_original": self.status_original,
            "status_normalizado": self.status_normalizado,
            "responsavel": self.responsavel,
            "data_lote": self.data_lote,
            "observacao": self.observacao,
            "ocorrencia_no_dia": self.ocorrencia_no_dia,
            "classificacao": self.classificacao,
            "regra": self.regra,
            "motivo": self.motivo,
        }


def _texto(valor) -> str:
    """Normaliza célula para string vazia em vez de NaN/None, sem alterar conteúdo."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip()


def validar_campos_obrigatorios_lote(registro: dict) -> list[str]:
    """RN01–RN04 (Aula 22): retorna os campos obrigatórios vazios do registro."""
    return [campo for campo in CAMPOS_OBRIGATORIOS_LOTE if _esta_vazio(registro.get(campo))]


def validar_data_referencia(valor) -> tuple[bool, str]:
    """RN12: valida se a data está presente e no formato DD/MM/AAAA.

    Returns:
        (valido, motivo) — valido=True se a data está presente e é uma
        data real no formato DD/MM/AAAA.
    """
    if _esta_vazio(valor):
        return False, "data ausente"

    texto = str(valor).strip()
    try:
        datetime.strptime(texto, FORMATO_DATA_ESPERADO)
        return True, ""
    except ValueError:
        return False, f"formato inválido ('{texto}', esperado DD/MM/AAAA)"


def _contar_ocorrencias_por_dia(registros_do_dia: list[dict]) -> list[int]:
    """RN11: retorna, na ordem das linhas, o nº de ocorrência do lote_id no dia.

    lote_id vazio nunca conta como duplicidade (isso é tratado pela RN01-04).
    """
    contador: Counter = Counter()
    ocorrencias: list[int] = []
    for registro in registros_do_dia:
        lote_id = _texto(registro.get("lote_id"))
        if lote_id == "":
            ocorrencias.append(1)  # não aplica RN11; RN01-04 cuida disso
            continue
        contador[lote_id] += 1
        ocorrencias.append(contador[lote_id])
    return ocorrencias


def classificar_registro(
    registro: dict,
    ocorrencia_no_dia: int,
    base_referencia: pd.DataFrame,
) -> RegistroValidado:
    """Aplica RN01–RN12 (Aula 22), em ordem de precedência, a um registro.

    Ordem escolhida (cada registro cai em exatamente 1 categoria):
      1. RN01–RN04 — campo obrigatório vazio          -> Erro de Entrada
      2. RN12      — data ausente/formato inválido    -> Erro de Entrada
      3. RN11      — duplicidade no dia (2ª+ ocorr.)  -> Divergência
      4. RN05      — lote não cadastrado / inativo    -> Divergência
      5. RN09      — status não reconhecível          -> Ambíguo
      6. RN10      — REPROVADO sem observação         -> Divergência
      7. (nenhuma das anteriores)                     -> Válido (RN08)
    """
    dia = registro.get("_dia", "")
    data_referencia = registro.get("_data_referencia", "")
    linha_planilha = registro.get("_linha_planilha", -1)

    lote_id = _texto(registro.get("lote_id"))
    produto = _texto(registro.get("produto"))
    linha = _texto(registro.get("linha"))
    turno = _texto(registro.get("turno"))
    status_original = _texto(registro.get("status"))
    responsavel = _texto(registro.get("responsavel"))
    data_lote = _texto(registro.get("data"))
    observacao = _texto(registro.get("observacao"))

    base_kwargs = dict(
        dia=dia,
        data_referencia=data_referencia,
        linha_planilha=linha_planilha,
        lote_id=lote_id,
        produto=produto,
        linha=linha,
        turno=turno,
        status_original=status_original,
        responsavel=responsavel,
        data_lote=data_lote,
        observacao=observacao,
        ocorrencia_no_dia=ocorrencia_no_dia,
    )

    # 1) RN01-04 — campos obrigatórios
    campos_vazios = validar_campos_obrigatorios_lote(registro)
    if campos_vazios:
        campo = campos_vazios[0]
        logger.warning("RN01-04: lote '%s' (%s) com campo obrigatório vazio: %s", lote_id or "(vazio)", dia, campo)
        return RegistroValidado(
            **base_kwargs,
            status_normalizado=None,
            classificacao="Erro de Entrada",
            regra="RN01-RN04",
            motivo=f"Campo obrigatório '{campo}' vazio",
        )

    # 2) RN12 — data
    data_valida, motivo_data = validar_data_referencia(registro.get("data"))
    if not data_valida:
        logger.warning("RN12: lote '%s' (%s) com data inválida: %s", lote_id, dia, motivo_data)
        return RegistroValidado(
            **base_kwargs,
            status_normalizado=None,
            classificacao="Erro de Entrada",
            regra="RN12",
            motivo=motivo_data,
        )

    # 3) RN11 — duplicidade no dia
    if ocorrencia_no_dia > 1:
        logger.warning("RN11: lote '%s' duplicado no dia %s (%dª ocorrência)", lote_id, dia, ocorrencia_no_dia)
        return RegistroValidado(
            **base_kwargs,
            status_normalizado=normalizar_status(status_original),
            classificacao="Divergência",
            regra="RN11",
            motivo=f"Lote duplicado na planilha ({ocorrencia_no_dia}ª ocorrência)",
        )

    # 4) RN05 — existência / status na Base_Referencia
    existe = verificar_existencia_lote(base_referencia, lote_id)
    if not existe:
        return RegistroValidado(
            **base_kwargs,
            status_normalizado=normalizar_status(status_original),
            classificacao="Divergência",
            regra="RN05",
            motivo="Lote não cadastrado na Base_Referencia",
        )

    ativo = verificar_status_lote(base_referencia, lote_id)
    if ativo is False:
        return RegistroValidado(
            **base_kwargs,
            status_normalizado=normalizar_status(status_original),
            classificacao="Divergência",
            regra="RN05",
            motivo="Lote cadastrado, porém inativo na Base_Referencia",
        )

    # 5) RN06/RN07 (normalização) + RN09 (ambíguo)
    resultado_status = validar_status(status_original)
    status_normalizado = resultado_status["status_normalizado"]
    if resultado_status["ambiguo"]:
        return RegistroValidado(
            **base_kwargs,
            status_normalizado=status_normalizado,
            classificacao="Ambíguo",
            regra="RN09",
            motivo=f"Status '{status_original}' não reconhecível",
        )

    # 6) RN10 — REPROVADO sem observação (reaproveita lote_conforme_rn07 direto)
    conforme = lote_conforme_rn07(
        {"lote_id": lote_id, "status": status_normalizado, "observacao": observacao}
    )
    if not conforme:
        motivo = "REPROVADO sem observação"
        if status_original.strip().upper() != status_normalizado:
            motivo = f"status '{status_original}' sem observação — normalizado p/ {status_normalizado}"
        return RegistroValidado(
            **base_kwargs,
            status_normalizado=status_normalizado,
            classificacao="Divergência",
            regra="RN10",
            motivo=motivo,
        )

    # 7) Válido
    return RegistroValidado(
        **base_kwargs,
        status_normalizado=status_normalizado,
        classificacao="Válido",
        regra="RN08",
        motivo="Registro conforme",
    )


def classificar_lotes(
    registros_por_dia: dict[str, list[dict]],
    base_referencia: pd.DataFrame,
) -> list[RegistroValidado]:
    """Classifica todos os registros, aplicando RN11 (duplicidade) por dia.

    Args:
        registros_por_dia: dict {nome_da_aba: [registros brutos...]}, na
            ordem original de leitura. Cada registro já deve conter
            "_dia", "_data_referencia" e "_linha_planilha" (ver
            aula22_preprocessador.py).
        base_referencia: DataFrame com colunas lote_id/status_cadastro.

    Returns:
        Lista de RegistroValidado, na mesma ordem de leitura original.
    """
    resultado: list[RegistroValidado] = []
    for dia, registros in registros_por_dia.items():
        ocorrencias = _contar_ocorrencias_por_dia(registros)
        for registro, ocorrencia in zip(registros, ocorrencias):
            resultado.append(classificar_registro(registro, ocorrencia, base_referencia))
    return resultado
