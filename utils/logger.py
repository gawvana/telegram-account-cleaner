import logging
import re
import sys
from typing import List, Pattern

# Regular expressions for scrubbing sensitive information
REDACTION_PATTERNS: List[Pattern] = [
    # Telegram Bot Token: 123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
    re.compile(r"\b\d{8,11}:[A-Za-z0-9_-]{34,36}\b"),
    # Phone numbers: +12345678901, +79991234567
    re.compile(r"(?:\+|%2B)?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}"),
    # Telethon Session strings
    re.compile(r"1[a-zA-Z0-9_-]{300,}"),
    # Fernet base64 key
    re.compile(r"[A-Za-z0-9_-]{43}="),
    # 2FA Passwords and explicit codes
    re.compile(r"(?:code|password|2fa|hash|secret|token)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE),
]


class RedactingFormatter(logging.Formatter):
    """Logging formatter that strips credentials, phone numbers, and secrets."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        redacted = original
        for pattern in REDACTION_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted


def setup_logger(name: str = "cleaner", log_level: str = "INFO") -> logging.Logger:
    """Configures and returns a privacy-safe logger with secret redaction."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        formatter = RedactingFormatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s:%(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.propagate = False
    return logger


logger = setup_logger()
