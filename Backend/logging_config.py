# Backend/logging_config.py
"""
統一的 logging 設定，取代散落在各處的 print()。
只用 Python 內建的 logging 模組，不引入額外套件。
"""
import logging
import os


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,  # basicConfig 若偵測到 root logger 已有 handler（例如 pytest 自己裝的）預設會直接跳過
    )
