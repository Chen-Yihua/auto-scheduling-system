"""logging 層級由 LOG_LEVEL 決定，預設 INFO。"""
import logging
import os


def setup_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,  # 已有 handler 時（例如 pytest）basicConfig 預設會略過
    )
