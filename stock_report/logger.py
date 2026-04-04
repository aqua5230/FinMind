from __future__ import annotations

import logging

from stock_report.config import settings


LOG_FORMAT = "%(asctime)s %(levelname)s %(module)s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_ROOT_LOGGER_NAME = "stock_report"


def _configure_root_logger() -> logging.Logger:
    logger = logging.getLogger(_ROOT_LOGGER_NAME)
    level = logging.DEBUG if settings.debug else logging.INFO

    if not hasattr(_configure_root_logger, "_initialized"):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
        logger.addHandler(handler)
        logger.propagate = False
        _configure_root_logger._initialized = True

    logger.setLevel(level)
    for handler in logger.handlers:
        handler.setLevel(level)
    return logger


def get_logger(name: str) -> logging.Logger:
    _configure_root_logger()
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    return logger
