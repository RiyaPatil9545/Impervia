
from app.ml.pii_detection.detector import PIISpan
from app.ml.relevance_detection.detector import RelevanceAnalysisResult
from app.ml.risk_assessment.assessor import RiskAssessor, RiskDecision, risk_assessor
from app.ml.sensitive_content.detector import SensitiveSpan


class RiskService:
    def __init__(self, assessor: RiskAssessor | None = None) -> None:
        self.assessor = assessor or risk_assessor

    def evaluate_risk(
        self,
        pii_spans: list[PIISpan],
        sensitive_spans: list[SensitiveSpan],
        relevance: RelevanceAnalysisResult,
    ) -> RiskDecision:
        return self.assessor.assess(pii_spans, sensitive_spans, relevance)


risk_service = RiskService()
