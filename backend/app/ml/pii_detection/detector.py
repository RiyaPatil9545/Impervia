import re
from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import PrivacyAction


@dataclass
class PIISpan:
    category: str
    start: int
    end: int
    text: str
    confidence: Decimal
    action: PrivacyAction = PrivacyAction.masked


class BasePIIDetector:
    """Base interface for PII detection engines."""

    def detect(self, text: str) -> list[PIISpan]:
        raise NotImplementedError


class RuleBasedPIIDetector(BasePIIDetector):
    """
    Explainable, deterministic baseline PII detector.
    Detects emails, phone numbers, IP addresses, student IDs, national IDs,
    credit cards, and common self-identifying name introduction patterns.
    """

    # Email pattern (RFC 5322 compatible)
    EMAIL_REGEX = re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,7}\b",
        re.IGNORECASE,
    )

    # Phone number patterns: International, standard 10-digit, formatted with dashes/parentheses
    PHONE_REGEX = re.compile(
        r"(?:(?:\+|00)\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,4}[\s.-]?\d{4}\b",
    )

    # IP address (IPv4 and basic IPv6)
    IPV4_REGEX = re.compile(
        r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
    )

    # Credit card numbers (13 to 19 digits with spaces or hyphens)
    CREDIT_CARD_REGEX = re.compile(
        r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b(?:\d{4}[-\s]?){3}\d{1,3}\b"
    )

    # SSN / Aadhaar / National ID patterns
    SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    AADHAAR_REGEX = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")

    # Student ID / Roll number / Registration number patterns
    STUDENT_ID_REGEX = re.compile(
        r"\b(?:student\s*id|roll\s*(?:no|number)|prn|reg(?:istration)?\s*(?:no|number)|enrollment\s*no)\s*[:#-]?\s*([A-Za-z0-9\-_]{4,15})\b",
        re.IGNORECASE,
    )

    # Self-identifying person name introductions
    NAME_INTRO_REGEX = re.compile(
        r"\b(?:my\s+name\s+is|i\s+am|i'm|this\s+is|call\s+me)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b",
    )

    def detect(self, text: str) -> list[PIISpan]:
        spans: list[PIISpan] = []
        if not text:
            return spans

        # 1. Emails
        for match in self.EMAIL_REGEX.finditer(text):
            spans.append(
                PIISpan(
                    category="email",
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    confidence=Decimal("0.98"),
                )
            )

        # 2. Credit Cards
        for match in self.CREDIT_CARD_REGEX.finditer(text):
            raw = re.sub(r"[\s-]", "", match.group())
            if 13 <= len(raw) <= 19 and raw.isdigit():
                spans.append(
                    PIISpan(
                        category="financial",
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        confidence=Decimal("0.90"),
                    )
                )

        # 3. National IDs (SSN / Aadhaar)
        for match in self.SSN_REGEX.finditer(text):
            spans.append(
                PIISpan(
                    category="national_id",
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    confidence=Decimal("0.95"),
                )
            )
        for match in self.AADHAAR_REGEX.finditer(text):
            spans.append(
                PIISpan(
                    category="national_id",
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    confidence=Decimal("0.92"),
                )
            )

        # 4. Student / Institutional IDs
        for match in self.STUDENT_ID_REGEX.finditer(text):
            spans.append(
                PIISpan(
                    category="student_id",
                    start=match.start(),
                    end=match.end(),
                    text=match.group(),
                    confidence=Decimal("0.92"),
                )
            )

        # 5. IP Addresses
        for match in self.IPV4_REGEX.finditer(text):
            # Avoid matching version numbers like 1.0.0.0 if preceded by 'v' or 'version'
            start = match.start()
            prefix = text[max(0, start - 8) : start].lower()
            if "version" not in prefix and not prefix.endswith("v"):
                spans.append(
                    PIISpan(
                        category="ip_address",
                        start=match.start(),
                        end=match.end(),
                        text=match.group(),
                        confidence=Decimal("0.90"),
                    )
                )

        # 6. Phone Numbers (avoiding overlapping with previously found spans)
        for match in self.PHONE_REGEX.finditer(text):
            matched_text = match.group().strip()
            digits_only = re.sub(r"\D", "", matched_text)
            # Require at least 10 digits for a phone number
            if 10 <= len(digits_only) <= 15:
                # Ensure not already overlapped with CC or SSN
                if not any(s.start <= match.start() and s.end >= match.end() for s in spans):
                    spans.append(
                        PIISpan(
                            category="phone_number",
                            start=match.start(),
                            end=match.end(),
                            text=match.group(),
                            confidence=Decimal("0.88"),
                        )
                    )

        # 7. Name Introductions
        for match in self.NAME_INTRO_REGEX.finditer(text):
            name_part = match.group(1)
            # Filter out common non-name words
            if name_part.lower() not in {"a", "an", "the", "student", "asking", "wondering", "working", "stuck", "confused", "trying"}:
                start_idx = match.start(1)
                end_idx = match.end(1)
                spans.append(
                    PIISpan(
                        category="person_name",
                        start=start_idx,
                        end=end_idx,
                        text=name_part,
                        confidence=Decimal("0.80"),
                    )
                )

        # Sort spans by starting index
        spans.sort(key=lambda x: x.start)
        return self._deduplicate_spans(spans)

    def _deduplicate_spans(self, spans: list[PIISpan]) -> list[PIISpan]:
        """Resolve overlapping spans by preferring longer / higher confidence matches."""
        if not spans:
            return []
        resolved: list[PIISpan] = []
        for span in spans:
            if not resolved:
                resolved.append(span)
                continue
            prev = resolved[-1]
            if span.start < prev.end:
                # Overlap! Keep the one with higher confidence or longer length
                if span.confidence > prev.confidence:
                    resolved[-1] = span
            else:
                resolved.append(span)
        return resolved


pii_detector = RuleBasedPIIDetector()
