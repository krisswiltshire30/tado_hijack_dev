"""Logging utilities for Tado Hijack."""

from __future__ import annotations

import logging
import re
from typing import Any

# Common sensitive URL parameter patterns for Tado
_URL_PARAM_PATTERNS = [
    re.compile(r"user_code=[^& ]+", re.IGNORECASE),
    re.compile(r"access_token=[^& ]+", re.IGNORECASE),
    re.compile(r"refresh_token=[^& ]+", re.IGNORECASE),
    re.compile(r"password=[^& ]+", re.IGNORECASE),
    re.compile(r"username=[^& ]+", re.IGNORECASE),
    re.compile(r"email=[^& ]+", re.IGNORECASE),
]


def redact(data: Any) -> str:
    """Redact sensitive information from the input string or object."""
    if not isinstance(data, str):
        data = str(data)

    for p in _URL_PARAM_PATTERNS:
        data = p.sub(lambda m: m.group(0).split("=")[0] + "=REDACTED", data)

    data = re.sub(r"homes/\d+", "homes/REDACTED", data, flags=re.IGNORECASE)
    data = re.sub(r"\b[A-Z]{2}\d{8,12}\b", "SN_REDACTED", data)

    json_keys = "user_code|password|access_token|refresh_token|username|email|serialNo|shortSerialNo"
    data = re.sub(
        r'(["\'])(' + json_keys + r')\1\s*[:=]\s*(["\'])(.*?)\3',
        r"\1\2\1: \3REDACTED\3",
        data,
        flags=re.IGNORECASE,
    )

    return str(data)


class TadoRedactionFilter(logging.Filter):
    """Filter to redact sensitive information from logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact sensitive info in the log record message and arguments."""
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)

        if record.args and isinstance(record.args, tuple):
            # Only allocate new list if redaction is needed
            new_args: list[Any] | None = None
            for i, arg in enumerate(record.args):
                if not isinstance(arg, int | float | bool | type(None)):
                    # First redaction needed - copy args and continue
                    if new_args is None:
                        new_args = list(record.args[:i])
                    new_args.append(redact(arg))
                elif new_args is not None:
                    # Already copying, keep primitives as-is
                    new_args.append(arg)

            if new_args is not None:
                record.args = tuple(new_args)

        return True


def get_redacted_logger(name: str) -> logging.Logger:
    """Get a logger with the redaction filter attached."""
    logger = logging.getLogger(name)
    logger.addFilter(TadoRedactionFilter())
    return logger
