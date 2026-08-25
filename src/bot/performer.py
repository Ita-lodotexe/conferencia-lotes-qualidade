"""Bot B — Performer (Auditoria e Validação de Lotes via Regras de Negócio).

Responsabilidades:
1. Obtém credenciais seguras do ERP via Credentials Vault (src/bot/vault_client.py).
2. Carrega a base de referência com retry e backoff linear (3 tentativas, 1s/2s/3s).
3. Consome itens da fila (DataPool) do Maestro.
4. Aplica as regras de negócio RN01 a RN07 (src/bot/avaliador.py).
5. Enriquece divergências com causa provável via ClassificadorDivergencia (ML).
6. Registra o status de cada item (report_done / report_error com ErrorType.BUSINESS/SYSTEM).
7. Encaminha itens irrecuperáveis por DADO para data/output/dead_letter.jsonl.
8. Itens com base de referência indisponível recebem status PENDENTE_REVISAO (não dead letter).
9. Dispara o Bot C (Reporter) via sdk.create_task() para consolidação e alertas.
10. Finaliza a task do Performer no Maestro.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

from src.bot import config
from src.bot.bot import setup_logger
from src.bot.vault_client import obter_credencial_erp, VaultError
from src.bot.avaliador import avaliar_lote
from src.bot.sistema_alertas import enviar_alerta
from src.classificador_divergencia import classificar_divergencia
from src.modules.validacao import COLUNAS_ESPERADAS
from src.modules.verificacao_lotes import carregar_base_referencia

try:
    from botcity.maestro import (
        AutomationTaskFinishStatus,
        BotMaestroSDK,
        ErrorType,
    )
except ImportError:
    BotMaestroSDK = None
    AutomationTaskFinishStatus = None
    ErrorType = None


class PerformerError(Exception):
    """Exceção levantada para erros no fluxo do Bot B Performer."""


# ── Retry com backoff linear para infraestrutura crítica (S10-B §3.3) ────────

_RETRY_TENTATIVAS: int = 3
_RETRY_BACKOFF_BASE_S: float = 1.0  # backoff linear: tentativa × base → 1s, 2s, 3s

_logger_retry = logging.getLogger("performer.retry")


def carregar_base_com_retry() -> pd.DataFrame | None:
    """Carrega a base de referência com retry e backoff linear.

    Retenta _RETRY_TENTATIVAS vezes com espera linear de
    tentativa × _RETRY_BACKOFF_BASE_S segundos entre cada tentativa.

    Retorna None se todas as tentativas falharem — a falha é tratada
    pelo caller como PENDENTE_REVISAO, sem propagar exceção ao pipeline.
    Ao esgotar todas as tentativas, dispara alerta ERRO via sistema_alertas.
    """
    caminho = Path(config.CAMINHO_BASE_REFERENCIA)
    alternativas = [
        Path("data/processed/base_lotes_referencia.csv"),
        Path("data/dev/base_lotes_referencia_dev.csv"),
    ]

    for tentativa in range(1, _RETRY_TENTATIVAS + 1):
        try:
            caminho_efetivo = caminho
            if not caminho_efetivo.is_file():
                for alt in alternativas:
                    if alt.is_file():
                        caminho_efetivo = alt
                        break
            base = carregar_base_referencia(str(caminho_efetivo))
            if tentativa > 1:
                _logger_retry.info(
                    f"[RETRY {tentativa}/{_RETRY_TENTATIVAS}] Base de referência carregada com sucesso."
                )
            return base
        except Exception as e:
            espera = tentativa * _RETRY_BACKOFF_BASE_S
            if tentativa < _RETRY_TENTATIVAS:
                _logger_retry.warning(
                    f"[RETRY {tentativa}/{_RETRY_TENTATIVAS}] Falha ao carregar base de referência "
                    f"({type(e).__name__}: {e}). "
                    f"Backoff linear: aguardando {espera:.0f}s antes da próxima tentativa..."
                )
                time.sleep(espera)
            else:
                _logger_retry.error(
                    f"[RETRY {tentativa}/{_RETRY_TENTATIVAS}] Todas as tentativas esgotadas. "
                    "Base de referência persistentemente indisponível. "
                    "Acionando fallback PENDENTE_REVISAO e disparando alerta ERRO."
                )
                enviar_alerta(
                    titulo="ERRO CRÍTICO: Base de Referência Indisponível",
                    mensagem=(
                        f"O Bot B (Performer) tentou carregar a base de referência de lotes "
                        f"{_RETRY_TENTATIVAS} vezes com backoff linear "
                        f"({_RETRY_BACKOFF_BASE_S:.0f}s/tentativa) sem sucesso. "
                        "Todos os itens serão marcados como PENDENTE_REVISAO até que "
                        "a base seja restaurada."
                    ),
                    severidade="ERRO",
                )
    return None  # todas as tentativas esgotadas


# ── Dead Letter — itens irrecuperáveis por motivo de DADO (S10-B §3.3) ───────

_CAMINHO_DEAD_LETTER = Path(config.PASTA_SAIDA) / "dead_letter.jsonl"

_logger_dl = logging.getLogger("performer.dead_letter")


def registrar_dead_letter(lote: dict, motivo: str, detalhes: str = "") -> None:
    """Grava item irrecuperável por motivo de dado no arquivo dead_letter.jsonl.

    Dead letter destina-se a falhas de DADO (ErrorType.BUSINESS): lotes não
    cadastrados, observação ausente em reprovado, campos obrigatórios vazios, etc.
    Falhas de INFRAESTRUTURA (base indisponível, rede) são cobertas pelo retry
    com backoff e resultam em PENDENTE_REVISAO — não vão para dead letter.

    O arquivo é criado em data/output/dead_letter.jsonl (JSONL: um JSON por linha).
    Falhas ao persistir o dead letter são logadas e nunca propagadas ao pipeline.
    """
    try:
        os.makedirs(_CAMINHO_DEAD_LETTER.parent, exist_ok=True)
        registro = {
            "lote_id": lote.get("lote_id", "desconhecido"),
            "motivo_negocio": motivo,
            "detalhes": detalhes,
            "dados_item": lote,
        }
        with open(_CAMINHO_DEAD_LETTER, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
        _logger_dl.warning(
            f"[DEAD LETTER] Lote '{lote.get('lote_id')}' registrado — motivo de dado: {motivo}."
        )
    except Exception as e:
        _logger_dl.error(
            f"[DEAD LETTER] Falha ao persistir dead letter para lote "
            f"'{lote.get('lote_id')}': {e}. Pipeline não interrompido."
        )


# ── Orquestração: Bot B → Bot C ───────────────────────────────────────────────


def disparar_bot_c(sdk: "BotMaestroSDK | None", dados_resumo: dict) -> "str | None":
    """Dispara a execução do Bot C (Reporter) via Maestro create_task()."""
    if not config.MAESTRO_ENABLED or sdk is None:
        logging.info(
            f"[DRY-RUN ORQUESTRAÇÃO] Bot B disparando Bot C ('{config.BOTCITY_REPORTER_LABEL}')."
        )
        return "task-mock-reporter-001"

    try:
        task_c = sdk.create_task(
            activity_label=config.BOTCITY_REPORTER_LABEL,
            parameters={
                "origem": "bot_b_performer",
                "total_processados": dados_resumo.get("total_processados", 0),
                "total_divergencias": dados_resumo.get("total_com_divergencia", 0),
                "total_pendentes_revisao": dados_resumo.get("total_pendentes_revisao", 0),
            },
        )
        task_c_id = str(task_c.id)
        logging.info(
            f"Bot B disparou com sucesso o Bot C "
            f"(Task ID: {task_c_id}, Activity: {config.BOTCITY_REPORTER_LABEL})."
        )
        return task_c_id
    except Exception as e:
        logging.error(f"Falha ao criar task do Bot C no Maestro: {e}")
        return None


# ── Modos de Execução ─────────────────────────────────────────────────────────


def executar_auditoria_local(base_ref: "pd.DataFrame | None") -> dict:
    """Executa o processamento em modo local / dry-run.

    base_ref=None significa que a base de referência está indisponível após
    todos os retries — todos os itens receberão status PENDENTE_REVISAO.
    """
    caminho_csv = Path(config.PASTA_ENTRADA) / config.ARQUIVO_CSV_ENTRADA
    if not caminho_csv.is_file():
        alternativas = [
            Path("dados_entrada/dados_relatorio.csv"),
            Path("dados_entrada/lotes_auditoria.csv"),
            Path("data/processed/dados_relatorio.csv"),
            Path("data/processed/base_lotes_referencia.csv"),
        ]
        for alt in alternativas:
            if alt.is_file():
                caminho_csv = alt
                break

    df = pd.read_csv(caminho_csv, dtype=str, keep_default_na=False)

    resumo: dict = {
        "total_processados": 0,
        "total_conformes": 0,
        "total_com_divergencia": 0,
        "total_pendentes_revisao": 0,
        "divergencias_detalhadas": [],
    }

    for i, linha in df.reset_index(drop=True).iterrows():
        lote = {col: linha.get(col, "") for col in COLUNAS_ESPERADAS}
        resumo["total_processados"] += 1

        if base_ref is None:
            # Base de referência indisponível após retries → PENDENTE_REVISAO
            resumo["total_pendentes_revisao"] += 1
            classif_ml = classificar_divergencia(lote.get("observacao", ""))
            resumo["divergencias_detalhadas"].append({
                "linha": i + 2,
                "lote_id": lote.get("lote_id"),
                "status_auditoria": "PENDENTE_REVISAO",
                "regra": "INFRA",
                "campo": "base_referencia",
                "descricao": (
                    "Base de referência indisponível após todas as tentativas de retry. "
                    "Item aguarda revisão manual."
                ),
                "origem_decisao": classif_ml["origem_decisao"],
                "confianca_ml": classif_ml["confianca_ml"],
                "causa_provavel": "base_indisponivel",
            })
            logging.warning(
                f"[DRY-RUN] Lote '{lote.get('lote_id')}': PENDENTE_REVISAO (base indisponível)"
            )
            continue

        divergencias = avaliar_lote(lote, base_ref)
        if not divergencias:
            resumo["total_conformes"] += 1
            logging.info(f"[DRY-RUN] Lote '{lote.get('lote_id')}': CONFORME")
            continue

        # Divergência detectada pelas regras de negócio (RN01-RN07)
        resumo["total_com_divergencia"] += 1
        regras = ", ".join(d["regra"] for d in divergencias)
        logging.warning(f"[DRY-RUN] Lote '{lote.get('lote_id')}': DIVERGÊNCIA ({regras})")

        classif_ml = classificar_divergencia(lote.get("observacao", ""))

        for div in divergencias:
            resumo["divergencias_detalhadas"].append({
                "linha": i + 2,
                "lote_id": lote.get("lote_id"),
                "status_auditoria": "DIVERGENCIA",
                "origem_decisao": classif_ml["origem_decisao"],
                "confianca_ml": classif_ml["confianca_ml"],
                "causa_provavel": classif_ml["causa_provavel"],
                **div,
            })

        # Dead letter: falha irrecuperável por dado (não por infraestrutura)
        registrar_dead_letter(
            lote=lote,
            motivo=regras,
            detalhes=f"Divergências detectadas pelas regras: {regras}",
        )

    return resumo


def executar_auditoria_maestro(sdk: "BotMaestroSDK", base_ref: "pd.DataFrame | None") -> dict:
    """Executa o processamento consumindo a fila do BotCity Maestro.

    base_ref=None → itens recebem ErrorType.SYSTEM + PENDENTE_REVISAO (infraestrutura).
    divergências de dado → ErrorType.BUSINESS + dead_letter.jsonl.
    """
    task = sdk.create_task(
        activity_label=config.BOTCITY_PERFORMER_LABEL,
        parameters={
            "origem": "orquestracao_performer",
            "datapool": config.DATAPOOL_LABEL,
        },
    )
    task_id = str(task.id)
    logging.info(f"Task iniciada no Maestro: ID {task_id}")

    datapool = sdk.get_datapool(label=config.DATAPOOL_LABEL)
    resumo: dict = {
        "task_id": task_id,
        "total_processados": 0,
        "total_conformes": 0,
        "total_com_divergencia": 0,
        "total_pendentes_revisao": 0,
        "divergencias_detalhadas": [],
    }

    while datapool.has_next():
        item = datapool.next(task_id=task_id)
        if item is None:
            break

        resumo["total_processados"] += 1
        lote = {col: str(item.get_value(col, "")) for col in COLUNAS_ESPERADAS}

        try:
            if base_ref is None:
                # Infraestrutura indisponível → SYSTEM error, não dead letter
                resumo["total_pendentes_revisao"] += 1
                item.report_error(
                    error_type=ErrorType.SYSTEM,
                    finish_message=(
                        "Base de referência indisponível após retries — PENDENTE_REVISAO."
                    ),
                )
                classif_ml = classificar_divergencia(lote.get("observacao", ""))
                resumo["divergencias_detalhadas"].append({
                    "lote_id": lote.get("lote_id"),
                    "status_auditoria": "PENDENTE_REVISAO",
                    "regra": "INFRA",
                    "campo": "base_referencia",
                    "descricao": "Base de referência indisponível após retries.",
                    "origem_decisao": classif_ml["origem_decisao"],
                    "confianca_ml": 0.0,
                    "causa_provavel": "base_indisponivel",
                })
                continue

            divergencias = avaliar_lote(lote, base_ref)
            if not divergencias:
                item.report_done(
                    finish_message=f"Lote {lote.get('lote_id')} em conformidade."
                )
                resumo["total_conformes"] += 1
            else:
                regras = ", ".join(d["regra"] for d in divergencias)
                # Falha de DADO → BUSINESS → dead letter
                item.report_error(
                    error_type=ErrorType.BUSINESS,
                    finish_message=f"Divergências detectadas: {regras}",
                )
                resumo["total_com_divergencia"] += 1

                registrar_dead_letter(
                    lote=lote,
                    motivo=regras,
                    detalhes=f"Divergências: {regras}",
                )

                classif_ml = classificar_divergencia(lote.get("observacao", ""))
                for div in divergencias:
                    resumo["divergencias_detalhadas"].append({
                        "lote_id": lote.get("lote_id"),
                        "status_auditoria": "DIVERGENCIA",
                        "origem_decisao": classif_ml["origem_decisao"],
                        "confianca_ml": classif_ml["confianca_ml"],
                        "causa_provavel": classif_ml["causa_provavel"],
                        **div,
                    })

        except Exception as e:
            logging.error(f"Erro de sistema no lote {lote.get('lote_id')}: {e}")
            item.report_error(
                error_type=ErrorType.SYSTEM,
                finish_message=f"Erro de sistema: {type(e).__name__}",
            )

    sdk.finish_task(
        task_id=task_id,
        status=AutomationTaskFinishStatus.SUCCESS,
        message=(
            f"Processamento concluído: {resumo['total_conformes']}/{resumo['total_processados']} "
            f"conformes, {resumo['total_com_divergencia']} divergências, "
            f"{resumo['total_pendentes_revisao']} pendentes de revisão."
        ),
    )
    return resumo


# ── Ponto de entrada principal ────────────────────────────────────────────────


def executar_performer() -> int:
    logger = setup_logger("performer")
    logger.info("=== Iniciando Bot B — Performer Validador de Lotes ===")

    try:
        usuario, _ = obter_credencial_erp()
        logger.info(f"Sessão ERP autorizada para: {usuario}")
    except VaultError as e:
        logger.error(f"Falha de autenticação no Vault: {e}")
        return 1

    # Carrega base de referência com retry e backoff linear
    # Retorna None se base indisponível — pipeline continua com PENDENTE_REVISAO
    base_ref = carregar_base_com_retry()
    if base_ref is None:
        logger.warning(
            "Base de referência indisponível após todos os retries. "
            "Pipeline continua: todos os itens receberão status PENDENTE_REVISAO."
        )
        # Não interrompe — a resiliência exige que o lote continue sendo processado

    sdk = None
    if config.MAESTRO_ENABLED:
        if BotMaestroSDK is None:
            logger.error("SDK botcity-maestro-sdk não instalado.")
            return 1
        try:
            sdk = BotMaestroSDK(
                server=config.BOTCITY_SERVER,
                login=config.BOTCITY_LOGIN,
                key=config.BOTCITY_KEY,
            )
            sdk.login()
            resumo = executar_auditoria_maestro(sdk, base_ref)
        except Exception as e:
            logger.error(f"Erro na execução com Maestro: {e}")
            return 1
    else:
        resumo = executar_auditoria_local(base_ref)

    logger.info(
        f"Auditoria concluída: {resumo['total_processados']} processados, "
        f"{resumo.get('total_conformes', 0)} conformes, "
        f"{resumo.get('total_com_divergencia', 0)} divergências, "
        f"{resumo.get('total_pendentes_revisao', 0)} pendentes de revisão."
    )

    # Salva resumo intermediário para o Bot C
    caminho_inter = Path(tempfile.gettempdir()) / "resumo_auditoria_lotes.json"
    caminho_inter.write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Bot B dispara Bot C (Reporter) — cadeia de orquestração A→B→C
    disparar_bot_c(sdk, resumo)

    return 0


if __name__ == "__main__":
    sys.exit(executar_performer())
