import enum


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    system = "system"


class StorageStatus(str, enum.Enum):
    sanitized_text = "sanitized_text"
    assistant_response = "assistant_response"
    system_notice = "system_notice"


class RiskLevel(str, enum.Enum):
    low = "low"
    mixed = "mixed"
    high = "high"


class RelevanceStatus(str, enum.Enum):
    relevant = "relevant"
    not_relevant = "not_relevant"
    mixed = "mixed"
    unclear = "unclear"
    not_applicable = "not_applicable"


class ProcessingPath(str, enum.Enum):
    pass_through = "pass_through"
    sanitize = "sanitize"
    separate = "separate"
    redirect = "redirect"


class FindingType(str, enum.Enum):
    pii = "pii"
    sensitive_content = "sensitive_content"


class PrivacyAction(str, enum.Enum):
    masked = "masked"
    removed = "removed"
    ignored = "ignored"
    retained = "retained"


class GenerationStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
