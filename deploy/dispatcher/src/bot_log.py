"""Logging do Bot A."""

import logging
import os

def setup_logger(nome: str = "dispatcher") -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        formatter = logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
        fh = logging.FileHandler(f"logs/{nome}.log", encoding="utf-8")
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger
