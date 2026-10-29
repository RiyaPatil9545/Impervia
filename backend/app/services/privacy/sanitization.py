
from app.ml.pii_detection.detector import PIISpan
from app.ml.risk_assessment.assessor import RiskDecision
from app.ml.sensitive_content.detector import SensitiveSpan


class SanitizerService:
    """
    Handles in-memory text redaction, separation of academic queries
    from sensitive content, and generation of privacy-aware redirection notices.
    """

    REDACTION_MAP = {
        "email": "[REDACTED_EMAIL]",
        "phone_number": "[REDACTED_PHONE]",
        "person_name": "[REDACTED_NAME]",
        "student_id": "[REDACTED_STUDENT_ID]",
        "national_id": "[REDACTED_NATIONAL_ID]",
        "financial": "[REDACTED_FINANCIAL_INFO]",
        "ip_address": "[REDACTED_IP]",
    }

    def mask_pii(self, text: str, spans: list[PIISpan]) -> str:
        """
        Replace identified PII spans with privacy tokens in reverse index order.
        """
        if not text or not spans:
            return text

        # Sort spans by start index descending to maintain valid offsets during slicing
        sorted_spans = sorted(spans, key=lambda s: s.start, reverse=True)
        sanitized = text
        for span in sorted_spans:
            token = self.REDACTION_MAP.get(span.category, "[REDACTED_PERSONAL_INFO]")
            sanitized = sanitized[: span.start] + token + sanitized[span.end :]
        return sanitized

    def separate(
        self,
        full_text: str,
        academic_query: str | None,
        pii_spans: list[PIISpan],
    ) -> tuple[str, str]:
        """
        Separates academic query from sensitive context.
        Returns (sanitized_academic_query, privacy_notice).
        """
        target_academic = academic_query or full_text
        sanitized_academic = self.mask_pii(target_academic, pii_spans)

        notice = (
            "Notice: Impervia detected personal or sensitive information in your message. "
            "To safeguard your privacy, the personal details have been isolated and will not "
            "be forwarded to the Academic AI. Your academic question will be processed safely."
        )
        return sanitized_academic.strip(), notice

    def generate_redirection_response(
        self,
        decision: RiskDecision,
        sensitive_spans: list[SensitiveSpan],
        pii_spans: list[PIISpan],
    ) -> str:
        """
        Produces a supportive, privacy-protective response redirecting the user safely.
        """
        has_crisis = any(s.category == "mental_health" and s.severity == "high" for s in sensitive_spans)
        has_mental_health = any(s.category == "mental_health" for s in sensitive_spans)
        has_financial = any(p.category == "financial" for p in pii_spans)
        has_national_id = any(p.category == "national_id" for p in pii_spans)

        if has_crisis:
            return (
                "It sounds like you are going through a very difficult time. Impervia is an "
                "automated academic assistant and cannot provide medical or crisis support. "
                "Please connect with caring professionals who can help:\n"
                "- National Crisis Lifeline (US/Canada): Call or text 988\n"
                "- Crisis Text Line: Text HOME to 741741\n"
                "- International Resources: https://findahelpline.com\n"
                "- Your university or campus counseling center\n"
                "Your safety and wellbeing matter. Please reach out to one of these services right away."
            )

        if has_financial or has_national_id:
            return (
                "Impervia Privacy Notice: Your message contains highly sensitive personal "
                "identifiers (such as financial information or national IDs). To protect your security "
                "and prevent identity theft, this message was blocked and will not be processed. "
                "Please never share payment details or official government IDs with AI assistants."
            )

        if has_mental_health:
            return (
                "Impervia noticed that you may be feeling stressed or overwhelmed. While we understand "
                "that academic life can be challenging, Impervia is dedicated exclusively to academic "
                "subjects (such as computer science, mathematics, sciences, and humanities) and does "
                "not process or store personal emotional disclosures. If you would like help with an "
                "academic assignment, feel free to ask your academic question!"
            )

        return (
            "Impervia is designed to assist you with academic coursework, problem solving, and "
            "subject explanations. Your message appears to contain personal or non-academic content. "
            "To preserve your privacy, please submit an academic question related to your studies."
        )


sanitizer_service = SanitizerService()
