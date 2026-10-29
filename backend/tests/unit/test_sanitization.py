from decimal import Decimal

from app.ml.pii_detection.detector import PIISpan
from app.ml.risk_assessment.assessor import RiskDecision
from app.ml.sensitive_content.detector import SensitiveSpan
from app.models.enums import ProcessingPath, RiskLevel
from app.services.privacy.sanitization import SanitizerService


def test_mask_pii():
    sanitizer = SanitizerService()
    text = "Contact me at alice@example.com or call 9876543210 please."
    spans = [
        PIISpan(category="email", start=14, end=31, text="alice@example.com", confidence=Decimal("0.98")),
        PIISpan(category="phone_number", start=40, end=50, text="9876543210", confidence=Decimal("0.90")),
    ]
    masked = sanitizer.mask_pii(text, spans)

    assert "alice@example.com" not in masked
    assert "9876543210" not in masked
    assert "[REDACTED_EMAIL]" in masked
    assert "[REDACTED_PHONE]" in masked


def test_separate_academic():
    sanitizer = SanitizerService()
    full_text = "I am so anxious. What is integration by parts? Call 9876543210."
    academic_part = "What is integration by parts? Call 9876543210."
    pii_spans = [
        PIISpan(category="phone_number", start=35, end=45, text="9876543210", confidence=Decimal("0.90")),
    ]

    sanitized_query, notice = sanitizer.separate(full_text, academic_part, pii_spans)
    assert "[REDACTED_PHONE]" in sanitized_query
    assert "9876543210" not in sanitized_query
    assert "Notice: Impervia detected personal or sensitive information" in notice


def test_crisis_redirection_response():
    sanitizer = SanitizerService()
    decision = RiskDecision(risk_level=RiskLevel.high, processing_path=ProcessingPath.redirect, reason="Crisis")
    sensitive = [
        SensitiveSpan(category="mental_health", start=0, end=19, text="want to end my life", confidence=Decimal("0.95"), severity="high")
    ]
    resp = sanitizer.generate_redirection_response(decision, sensitive, [])

    assert "988" in resp
    assert "Crisis" in resp
    assert "academic assistant" in resp
