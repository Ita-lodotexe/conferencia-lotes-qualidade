"""Bot C — Reporter (Consolidação de Relatório, Auditoria ML e Alertas Resilientes).

Responsabilidades (Estudo de Caso S10-B):
1. Consolida as divergências apuradas com as colunas obrigatórias 'origem_decisao' e 'confianca_ml'.
2. Gera o relatório consolidado em Excel (.xlsx).
3. Monitora degradação de ML: se 100% dos itens operarem em fallback, dispara aviso com severidade AVISO.
4. Publica artefatos no Maestro e dispara alertas multi-canal (Telegram -> Email/WhatsApp).
5. Finaliza a task no Maestro.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from pathlib import Path
import pandas as pd

from src.bot import config
from src.bot.bot import setup_logger
from src.bot.sistema_alertas import enviar_alerta

try:
    from botcity.maestro import (
        AutomationTaskFinishStatus,
        BotMaestroSDK,
        AlertBadgeType,
    )
except ImportError:
    BotMaestroSDK = None
    AutomationTaskFinishStatus = None
    AlertBadgeType = None


class ReporterError(Exception):
    """Exceção para erros no Bot C Reporter."""


def gerar_planilha_relatorio(dados_resumo: dict, caminho_saida: str) -> str:
    """Gera o arquivo Excel estruturado garantindo colunas de auditoria de ML."""
    os.makedirs(os.path.dirname(caminho_saida) or ".", exist_ok=True)

    divergencias = dados_resumo.get("divergencias_detalhadas", [])

    # Métricas de ML
    total_div = len(divergencias)
    itens_com_ml = sum(1 for d in divergencias if d.get("origem_decisao") == "ml")
    itens_em_fallback = sum(1 for d in divergencias if d.get("origem_decisao") == "fallback")
    taxa_fallback = (itens_em_fallback / total_div * 100.0) if total_div > 0 else 0.0

    linhas_resumo = [
        {"Métrica": "Total de Lotes Processados", "Valor": dados_resumo.get("total_processados", 0)},
        {"Métrica": "Lotes Conformes (Regras RN01-RN07)", "Valor": dados_resumo.get("total_conformes", 0)},
        {"Métrica": "Lotes com Divergência (Regras RN01-RN07)", "Valor": dados_resumo.get("total_com_divergencia", 0)},
        {"Métrica": "Classificações Concluídas por ML", "Valor": itens_com_ml},
        {"Métrica": "Classificações em Fallback ML", "Valor": itens_em_fallback},
        {"Métrica": "Taxa de Degradação ML (%)", "Valor": f"{taxa_fallback:.1f}%"},
    ]
    df_resumo = pd.DataFrame(linhas_resumo)

    # Colunas obrigatórias do Bloco 5: origem_decisao e confianca_ml
    colunas_obrigatorias = [
        "lote_id",
        "regra",
        "campo",
        "descricao",
        "origem_decisao",
        "confianca_ml",
        "causa_provavel",
    ]

    if not divergencias:
        df_div = pd.DataFrame(columns=colunas_obrigatorias)
    else:
        df_div = pd.DataFrame(divergencias)
        # Garante que todas as colunas obrigatórias existam e estejam preenchidas
        for col in colunas_obrigatorias:
            if col not in df_div.columns:
                df_div[col] = "fallback" if col == "origem_decisao" else (0.0 if col == "confianca_ml" else "")

        # Ordena colunas para padronização
        outras_cols = [c for c in df_div.columns if c not in colunas_obrigatorias]
        df_div = df_div[colunas_obrigatorias + outras_cols]

    with pd.ExcelWriter(caminho_saida, engine="openpyxl") as writer:
        df_resumo.to_excel(writer, sheet_name="Resumo", index=False)
        df_div.to_excel(writer, sheet_name="Divergencias", index=False)

    return caminho_saida


def verificar_alerta_degradacao_ml(dados_resumo: dict) -> bool:
    """Verifica se 100% dos itens operaram em modo de fallback de ML."""
    divergencias = dados_resumo.get("divergencias_detalhadas", [])
    if not divergencias:
        return False

    total = len(divergencias)
    total_fallback = sum(1 for d in divergencias if d.get("origem_decisao") == "fallback")

    if total > 0 and total_fallback == total:
        logging.warning(
            f"ALERTA DE DEGRADAÇÃO: 100% dos itens ({total}/{total}) operaram em modo de fallback de ML. "
            "Disparando aviso para a equipe com severidade AVISO."
        )
        # Disparo com severidade AVISO conforme exigência do Bloco 4
        enviar_alerta(
            titulo="Degradação Crítica: 100% Fallback ML",
            mensagem=(
                f"Atenção equipe: Todos os {total} itens auditados operaram no modo fallback do classificador de ML. "
                "Verifique a integridade do endpoint ML_ENDPOINT ou conectividade."
            ),
            severidade="AVISO",
        )
        return True

    return False


def executar_reporter() -> int:
    logger = setup_logger("reporter")
    logger.info("=== Iniciando Bot C — Reporter, Auditoria e Alertas ===")

    caminho_inter = Path(tempfile.gettempdir()) / "resumo_auditoria_lotes.json"
    if caminho_inter.is_file():
        try:
            dados_resumo = json.loads(caminho_inter.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Não foi possível ler resumo intermediário: {e}")
            dados_resumo = {"total_processados": 0, "total_conformes": 0, "total_com_divergencia": 0, "divergencias_detalhadas": []}
    else:
        dados_resumo = {"total_processados": 0, "total_conformes": 0, "total_com_divergencia": 0, "divergencias_detalhadas": []}

    caminho_excel = os.path.join(config.PASTA_SAIDA, "relatorio_auditoria_lotes.xlsx")
    gerar_planilha_relatorio(dados_resumo, caminho_excel)
    logger.info(f"Relatório Excel de auditoria gerado em: {caminho_excel}")

    # Checagem de Degradação de ML (100% Fallback)
    degradacao_ml = verificar_alerta_degradacao_ml(dados_resumo)

    total_div = dados_resumo.get("total_com_divergencia", 0)

    # Disparo de Alerta Padrão de Fechamento de Auditoria
    if not degradacao_ml:
        enviar_alerta(
            titulo="Auditoria de Lotes Finalizada",
            mensagem=f"Auditoria concluída com sucesso. Total de lotes: {dados_resumo.get('total_processados', 0)}, Divergências: {total_div}.",
            severidade="INFO" if total_div == 0 else "AVISO",
        )

    # Integração com BotCity Maestro
    if config.MAESTRO_ENABLED and BotMaestroSDK is not None:
        try:
            sdk = BotMaestroSDK(
                server=config.BOTCITY_SERVER,
                login=config.BOTCITY_LOGIN,
                key=config.BOTCITY_KEY,
            )
            sdk.login()

            task = sdk.create_task(
                activity_label=config.BOTCITY_REPORTER_LABEL,
                parameters={"origem": "bot_c_reporter"},
            )
            task_id = str(task.id)

            # Publica artefato
            sdk.post_artifact(
                task_id=task_id,
                artifact_name="relatorio_auditoria_lotes.xlsx",
                filepath=caminho_excel,
            )
            logger.info(f"Artefato postado na task {task_id} do Maestro.")

            tipo_alerta = AlertBadgeType.WARN if (total_div > 0 or degradacao_ml) else AlertBadgeType.INFO
            sdk.alert(
                task_id=task_id,
                title="Auditoria de Lotes Concluída",
                message=f"Processamento finalizado. {total_div} divergências encontradas. Degradação ML: {degradacao_ml}.",
                badge=tipo_alerta,
            )

            sdk.finish_task(
                task_id=task_id,
                status=AutomationTaskFinishStatus.SUCCESS,
                message="Relatório e artefatos publicados com sucesso.",
            )
        except Exception as e:
            logger.error(f"Erro na publicação ao Maestro: {e}")
            return 1
    else:
        logger.info("[DRY-RUN] Publicação de artefatos e alertas finalizada com sucesso.")

    return 0


if __name__ == "__main__":
    sys.exit(executar_reporter())
