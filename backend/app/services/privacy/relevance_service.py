
from app.ml.relevance_detection.detector import (
    AcademicRelevanceDetector,
    RelevanceAnalysisResult,
    academic_relevance_detector,
)


class RelevanceService:
    def __init__(self, detector: AcademicRelevanceDetector | None = None) -> None:
        self.detector = detector or academic_relevance_detector

    def assess_relevance(self, text: str, has_sensitive: bool = False) -> RelevanceAnalysisResult:
        return self.detector.analyze(text, has_sensitive=has_sensitive)


relevance_service = RelevanceService()
