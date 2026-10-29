import re
from dataclasses import dataclass
from decimal import Decimal

from app.models.enums import PrivacyAction


@dataclass
class SensitiveSpan:
    category: str
    start: int
    end: int
    text: str
    confidence: Decimal
    severity: str  # "high", "medium"
    action: PrivacyAction = PrivacyAction.removed


class BaseSensitiveContentDetector:
    """Base interface for sensitive content detection engines."""

    def detect(self, text: str) -> list[SensitiveSpan]:
        raise NotImplementedError


class RuleBasedSensitiveDetector(BaseSensitiveContentDetector):
    """
    Explainable, rule-based sensitive and emotional content detector.
    Categorizes disclosures into mental health / crisis, personal relationships,
    medical conditions, financial hardship, and personal confessions.
    """

    CATEGORIES = {
        "mental_health": {
            "high": [
                r"\b(?:feel(?:ing)?\s+suicidal|kill\s+myself|end\s+my\s+life|want\s+to\s+die|self[\s-]harm)\b",
                r"\b(?:severe\s+depression|can'?t\s+take\s+it\s+anymore|no\s+reason\s+to\s+live)\b",
            ],
            "medium": [
                # Acute non-crisis distress & panic attacks
                r"\b(?:having\s+(?:a\s+)?(?:panic|anxiety)\s+attack|nervous\s+breakdown|crying\s+all\s+(?:day|night))\b",
                # Ordinary stress, exam stress, and feeling stressed
                r"\b(?:feel(?:ing)?\s+(?:very|so|really|extremely|quite|pretty|super)?\s*stressed(?:\s+out)?)\b",
                r"\b(?:stressed\s+out)\b",
                r"\b(?:stressed\s+(?:about|over|by|with)\s+(?:my|the|this)?\s*(?:exam|exams|test|tests|midterm|midterms|final|finals|quiz|grade|grades|assignment|course|school|college|studies|class|classes|gpa))\b",
                r"\b(?:under\s+(?:a\s+lot\s+of|so\s+much|immense|too\s+much|constant|heavy)\s+stress)\b",
                r"\b(?:(?:exam|test|study|academic|school)\s+stress)\b",
                # Overwhelm, coping difficulties, and academic burden
                r"\b(?:feel(?:ing)?\s+(?:very|so|really|extremely|completely|pretty)?\s*overwhelmed(?:\s+(?:by|with|emotionally))?)\b",
                r"\b(?:drowning\s+in\s+(?:work|assignments|study|studies|exams|schoolwork))\b",
                r"\b(?:can'?t\s+cope\s+with\s+(?:the\s+)?(?:stress|pressure|workload|exams|classes|school|studies))\b",
                # Anxiety, fear of failure, personal worries
                r"\b(?:feel(?:ing)?\s+(?:very|so|really|extremely|quite|super)?\s*anxious(?:\s+(?:about|over|for))?)\b",
                r"\b(?:(?:having|dealing\s+with|struggling\s+with)\s+(?:a\s+lot\s+of|so\s+much|severe|bad)?\s*anxiety)\b",
                r"\b(?:(?:test|exam|performance)\s+anxiety)\b",
                r"\b(?:feel(?:ing)?\s+(?:hopeless|worthless|depressed|down|low))\b",
                r"\b(?:(?:very|so|really)?\s*worried\s+(?:sick|about\s+failing|that\s+i(?:'ll|\s+will)?\s+fail))\b",
                r"\b(?:terrified\s+of\s+failing|scared\s+(?:of\s+failing|that\s+i(?:'ll|\s+will)?\s+fail))\b",
                r"\b(?:losing\s+my\s+mind\s+(?:over|about))\b",
                r"\b(?:can'?t\s+sleep\s+(?:because\s+of|due\s+to)\s+(?:stress|exams|pressure|anxiety))\b",
                r"\b(?:burnt\s+out|burning\s+out|mental\s+burnout|mentally\s+exhausted)\b",
            ],
        },
        "relationship": {
            "medium": [
                r"\b(?:my\s+(?:boyfriend|girlfriend|partner|husband|wife)\s+(?:broke\s+up\s+with\s+me|dumped\s+me|cheated\s+on\s+me))\b",
                r"\b(?:going\s+through\s+a\s+(?:divorce|breakup)|parents\s+(?:fighting|getting\s+divorced))\b",
                r"\b(?:domestic\s+abuse|toxic\s+relationship)\b",
            ],
        },
        "health_medical": {
            "medium": [
                r"\b(?:diagnosed\s+with|taking\s+medication\s+for|my\s+psychiatrist\s+prescribed)\b",
                r"\b(?:chronic\s+illness|chemotherapy|positive\s+for\s+covid|sti\s+test|hospitalized)\b",
            ],
        },
        "financial_hardship": {
            "medium": [
                r"\b(?:can'?t\s+afford\s+(?:food|rent|tuition)|facing\s+eviction|bank\s+account\s+is\s+(?:empty|negative))\b",
                r"\b(?:drowning\s+in\s+debt|filed\s+for\s+bankruptcy|loan\s+sharks)\b",
            ],
        },
        "personal_confession": {
            "medium": [
                r"\b(?:i\s+cheated\s+on\s+(?:the|my)\s+(?:exam|test|quiz)|stole\s+the\s+answers|bought\s+my\s+essay)\b",
                r"\b(?:plagiarized\s+my\s+entire\s+paper|bribed\s+the\s+ta)\b",
            ],
        },
    }

    def detect(self, text: str) -> list[SensitiveSpan]:
        spans: list[SensitiveSpan] = []
        if not text:
            return spans

        for category, severities in self.CATEGORIES.items():
            for severity, pattern_list in severities.items():
                confidence = Decimal("0.90") if severity == "high" else Decimal("0.85")
                for pattern in pattern_list:
                    regex = re.compile(pattern, re.IGNORECASE)
                    for match in regex.finditer(text):
                        spans.append(
                            SensitiveSpan(
                                category=category,
                                start=match.start(),
                                end=match.end(),
                                text=match.group(),
                                confidence=confidence,
                                severity=severity,
                                action=PrivacyAction.removed,
                            )
                        )

        # Deduplicate overlapping spans
        spans.sort(key=lambda x: x.start)
        return self._deduplicate_spans(spans)

    def _deduplicate_spans(self, spans: list[SensitiveSpan]) -> list[SensitiveSpan]:
        if not spans:
            return []
        resolved: list[SensitiveSpan] = []
        for span in spans:
            if not resolved:
                resolved.append(span)
                continue
            prev = resolved[-1]
            if span.start < prev.end:
                if span.severity == "high" and prev.severity != "high" or span.confidence > prev.confidence:
                    resolved[-1] = span
            else:
                resolved.append(span)
        return resolved


sensitive_detector = RuleBasedSensitiveDetector()
