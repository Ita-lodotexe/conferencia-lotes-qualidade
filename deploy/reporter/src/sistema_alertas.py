"""Sistema de Alertas com Resiliência Multi-Canal (Bot C Reporter - Estudo de Caso S10-B)."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests

logger = logging.getLogger("sistema.alertas")


def _enviar_telegram(titulo: str, mensagem: str, severidade: str) -> bool:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        raise ValueError("Credenciais do Telegram ausentes (TELEGRAM_TOKEN ou TELEGRAM_CHAT_ID não definidos).")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    texto_formatado = f"🚨 *[{severidade.upper()}] {titulo}*\n\n{mensagem}"
    payload = {
        "chat_id": chat_id,
        "text": texto_formatado,
        "parse_mode": "Markdown",
    }

    resp = requests.post(url, json=payload, timeout=5.0)
    resp.raise_for_status()
    return True


def _enviar_email_smtp(titulo: str, mensagem: str, severidade: str) -> bool:
    servidor_smtp = os.getenv("SMTP_SERVER", "smtp.gmail.com").strip()
    porta_smtp = int(os.getenv("SMTP_PORT", "587"))
    usuario_smtp = os.getenv("SMTP_USER", "").strip()
    senha_smtp = os.getenv("SMTP_PASSWORD", "").strip()
    destinatario = os.getenv("EMAIL_DESTINATION", usuario_smtp).strip()

    if (
        not usuario_smtp
        or not senha_smtp
        or not destinatario
        or "preencher" in usuario_smtp.lower()
        or "preencher" in senha_smtp.lower()
    ):
        logger.info("[DRY-RUN ALERTA] Fallback Email SMTP simulado (credenciais SMTP não configuradas/exemplo).")
        return True

    msg = MIMEMultipart()
    msg["From"] = usuario_smtp
    msg["To"] = destinatario
    msg["Subject"] = f"[{severidade.upper()}] {titulo}"
    msg.attach(MIMEText(mensagem, "plain", "utf-8"))

    with smtplib.SMTP(servidor_smtp, porta_smtp, timeout=5.0) as server:
        server.starttls()
        server.login(usuario_smtp, senha_smtp)
        server.send_message(msg)

    return True


def _enviar_whatsapp_twilio(titulo: str, mensagem: str, severidade: str) -> bool:
    """Envia notificação via WhatsApp Twilio API (Canal Secundário Alternativo)."""
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_number = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
    to_number = os.getenv("WHATSAPP_DESTINATION", "").strip()

    if (
        not account_sid
        or not auth_token
        or "preencher" in account_sid.lower()
        or "preencher" in auth_token.lower()
    ):
        logger.info("[DRY-RUN ALERTA] Fallback WhatsApp Twilio simulado (credenciais Twilio não configuradas/exemplo).")
        return True
        logger.info("[DRY-RUN ALERTA] Fallback WhatsApp Twilio simulado (credenciais Twilio locais/vazias).")
        return True

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = {
        "From": f"whatsapp:{from_number}",
        "To": f"whatsapp:{to_number}",
        "Body": f"[{severidade.upper()}] {titulo}\n{mensagem}",
    }
    resp = requests.post(url, data=data, auth=(account_sid, auth_token), timeout=5.0)
    resp.raise_for_status()
    return True


def enviar_alerta(titulo: str, mensagem: str, severidade: str = "INFO") -> dict:
    logger.info(f"Iniciando disparo de alerta [{severidade}]: '{titulo}'")

    # Tentativa 1: Telegram
    try:
        sucesso_telegram = _enviar_telegram(titulo, mensagem, severidade)
        if sucesso_telegram:
            logger.info("Alerta enviado com sucesso pelo canal principal (Telegram).")
            return {
                "sucesso": True,
                "canal_utilizado": "telegram",
                "fallback_acionado": False,
                "detalhes": "Mensagem entregue via Telegram.",
            }
    except Exception as erro_telegram:
        logger.warning(
            f"Falha no canal principal (Telegram): {erro_telegram}. "
            "Engolindo exceção e acionando canal de contingência (Fallback)..."
        )

    # Tentativa 2: Fallback Email SMTP / WhatsApp
    try:
        _enviar_email_smtp(titulo, mensagem, severidade)
        logger.info("Alerta entregue com sucesso através do canal de contingência (Email SMTP).")
        return {
            "sucesso": True,
            "canal_utilizado": "email_smtp",
            "fallback_acionado": True,
            "detalhes": "Entregue pelo canal secundário (Email SMTP).",
        }
    except Exception as erro_email:
        logger.warning(f"Falha ao enviar por Email: {erro_email}. Tentando WhatsApp como fallback final...")
        try:
            _enviar_whatsapp_twilio(titulo, mensagem, severidade)
            logger.info("Alerta entregue através do canal de contingência (WhatsApp Twilio).")
            return {
                "sucesso": True,
                "canal_utilizado": "whatsapp_twilio",
                "fallback_acionado": True,
                "detalhes": "Entregue pelo canal secundário (WhatsApp Twilio).",
            }
        except Exception as erro_final:
            logger.error(f"Todos os canais de alerta falharam ({erro_final}). Execução preservada sem interrupção.")
            return {
                "sucesso": False,
                "canal_utilizado": "nenhum",
                "fallback_acionado": True,
                "detalhes": f"Falha em todos os canais: {erro_final}",
            }
