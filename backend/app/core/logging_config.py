import logging
import re
import sys


class PrivacySanitizingFilter(logging.Filter):
    """
    Filter to prevent accidental logging of credentials, tokens, or obvious PII.
    """

    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    BEARER_PATTERN = re.compile(r"Bearer\s+([A-Za-z0-9\-_=]+\.[A-Za-z0-9\-_=]+\.?[A-Za-z0-9\-_+/=]*)", re.IGNORECASE)

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            sanitized = record.msg
            sanitized = self.BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", sanitized)
            sanitized = self.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", sanitized)
            sanitized = self.PHONE_PATTERN.sub("[REDACTED_PHONE]", sanitized)
            record.msg = sanitized
        return True


def setup_logging() -> None:
    logger = logging.getLogger("impervia")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(PrivacySanitizingFilter())
        logger.addHandler(handler)


logger = logging.getLogger("impervia")
