import logging
import sys

import structlog

from fuzzforge_modules_sdk.api.constants import PATH_TO_LOGS


class Formatter(logging.Formatter):
    """TODO."""

    def format(self, record: logging.LogRecord) -> str:
        """TODO."""
        record.exc_info = None
        return super().format(record)


def configure() -> None:
    """TODO."""
    fmt: str = "%(message)s"
    level = logging.DEBUG
    PATH_TO_LOGS.parent.mkdir(exist_ok=True, parents=True)
    PATH_TO_LOGS.unlink(missing_ok=True)
    handler_file = logging.FileHandler(filename=PATH_TO_LOGS, mode="a")
    handler_file.setFormatter(fmt=Formatter(fmt=fmt))
    handler_file.setLevel(level=level)
    handler_stderr = logging.StreamHandler(stream=sys.stderr)
    handler_stderr.setFormatter(fmt=Formatter(fmt=fmt))
    handler_stderr.setLevel(level=level)
    logger: logging.Logger = logging.getLogger()
    logger.setLevel(level=level)
    logger.addHandler(handler_file)
    logger.addHandler(handler_stderr)
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
    )
