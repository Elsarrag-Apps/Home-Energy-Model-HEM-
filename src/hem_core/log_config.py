import logging.config
from typing import Any

log_config: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "level": "INFO",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}


def setup_logging(log_level: str) -> None:
    log_config["root"]["level"] = log_level
    logging.config.dictConfig(log_config)
