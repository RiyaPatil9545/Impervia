from app.ml.relevance_detection.detector import AcademicRelevanceDetector
from app.models.enums import RelevanceStatus


def test_pure_academic_query():
    detector = AcademicRelevanceDetector()
    text = "Can you derive the quadratic formula and explain its proof step by step?"
    res = detector.analyze(text, has_sensitive=False)

    assert res.has_academic_intent is True
    assert res.status == RelevanceStatus.relevant
    assert res.academic_score >= 0.4
    assert res.academic_text is not None


def test_mixed_academic_and_sensitive_query():
    detector = AcademicRelevanceDetector()
    text = "I am having a panic attack about my exam. Can you explain Dijkstra's algorithm?"
    res = detector.analyze(
        text,
        has_sensitive=True,
        sensitive_texts=["having a panic attack"],
    )

    assert res.has_academic_intent is True
    assert res.status == RelevanceStatus.mixed
    assert "Dijkstra" in res.academic_text
    assert "panic attack" not in res.academic_text


def test_non_academic_personal_venting():
    detector = AcademicRelevanceDetector()
    text = "My boyfriend broke up with me and I have nowhere to sleep tonight."
    res = detector.analyze(text, has_sensitive=True)

    assert res.has_academic_intent is False
    assert res.status == RelevanceStatus.not_relevant


def test_empty_or_whitespace_input():
    detector = AcademicRelevanceDetector()
    res = detector.analyze("   ", has_sensitive=False)
    assert res.status == RelevanceStatus.not_applicable


def test_dbms_normalization_academic_relevance():
    detector = AcademicRelevanceDetector()
    text = "Explain DBMS normalization."
    res = detector.analyze(text, has_sensitive=False)

    assert res.has_academic_intent is True
    assert res.status == RelevanceStatus.relevant
    assert res.academic_score >= 0.8
    assert res.academic_text == "Explain DBMS normalization."


def test_mixed_query_with_exam_stress_separates_academic_portion():
    detector = AcademicRelevanceDetector()
    text = "Explain DBMS normalization. I am feeling very stressed about my exams."
    res = detector.analyze(
        text,
        has_sensitive=True,
        sensitive_texts=["feeling very stressed about my exams"],
    )

    assert res.has_academic_intent is True
    assert res.status == RelevanceStatus.mixed
    assert res.academic_text == "Explain DBMS normalization."
    assert "stressed about my exams" not in res.academic_text
    assert res.non_academic_text == "I am feeling very stressed about my exams."
