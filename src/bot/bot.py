"""Configuração e utilitários de logging dos bots."""

import logging
import os


def setup_logger(nome: str = "execucao") -> logging.Logger:
    os.makedirs("logs", exist_ok=True)

    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")

        file_handler = logging.FileHandler(f"logs/{nome}.log", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger
