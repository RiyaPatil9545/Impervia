from app.ml.sensitive_content.detector import RuleBasedSensitiveDetector


def test_crisis_mental_health_detection():
    detector = RuleBasedSensitiveDetector()
    text = "I feel hopeless and want to end my life, I cannot take this anymore."
    spans = detector.detect(text)

    assert len(spans) >= 1
    categories = [s.category for s in spans]
    assert "mental_health" in categories
    assert any(s.severity == "high" for s in spans)


def test_emotional_distress_detection():
    detector = RuleBasedSensitiveDetector()
    text = "I am having a panic attack and feeling extremely anxious before my exam."
    spans = detector.detect(text)

    assert len(spans) >= 1
    assert any(s.category == "mental_health" for s in spans)


def test_relationship_disclosures():
    detector = RuleBasedSensitiveDetector()
    text = "My boyfriend broke up with me yesterday and I have been crying all day."
    spans = detector.detect(text)

    categories = {s.category for s in spans}
    assert "relationship" in categories


def test_health_and_financial_disclosures():
    detector = RuleBasedSensitiveDetector()
    text = "I was diagnosed with chronic illness and my bank account is empty."
    spans = detector.detect(text)

    categories = {s.category for s in spans}
    assert "health_medical" in categories
    assert "financial_hardship" in categories


def test_academic_question_without_sensitive_content():
    detector = RuleBasedSensitiveDetector()
    text = "Can you explain the difference between mitosis and meiosis in biology?"
    spans = detector.detect(text)
    assert len(spans) == 0


def test_ordinary_exam_stress_detection():
    detector = RuleBasedSensitiveDetector()
    text = "Explain DBMS normalization. I am feeling very stressed about my exams."
    spans = detector.detect(text)

    assert len(spans) >= 1
    assert any(s.category == "mental_health" for s in spans)
    # Must be medium severity, NOT high crisis
    assert all(s.severity == "medium" for s in spans)


def test_exam_stress_and_anxiety_expressions():
    detector = RuleBasedSensitiveDetector()
    expressions = [
        "I am so stressed out by my assignments.",
        "Under immense stress due to upcoming midterms.",
        "Dealing with severe test anxiety and can't sleep.",
        "I feel completely overwhelmed by my coursework.",
        "Terrified of failing this semester.",
        "I am burning out from studying all night.",
    ]
    for expr in expressions:
        spans = detector.detect(expr)
        assert len(spans) >= 1, f"Failed to detect ordinary distress in: '{expr}'"
        assert all(s.severity == "medium" for s in spans), f"Distress misclassified as high crisis in: '{expr}'"


def test_technical_engineering_stress_no_false_positives():
    detector = RuleBasedSensitiveDetector()
    technical_texts = [
        "Explain the relationship between shear stress and tensile strain in materials science.",
        "What is the maximum allowable bending stress of a steel beam?",
        "How do we perform stress testing in software engineering?",
    ]
    for tech_text in technical_texts:
        spans = detector.detect(tech_text)
        assert len(spans) == 0, f"False positive detected on technical stress: '{tech_text}'"


def test_suicidal_misspelling_and_crisis_coverage():
    detector = RuleBasedSensitiveDetector()
    crisis_texts = [
        "I am feeling sucidal and don't know what to do.",
        "I have been having sucidal thoughts lately.",
        "i am sucidal.",
        "I want to commit sucide.",
    ]
    for text in crisis_texts:
        spans = detector.detect(text)
        assert len(spans) >= 1, f"Failed to detect crisis in: '{text}'"
        assert any(s.category == "mental_health" and s.severity == "high" for s in spans), (
            f"Expected high-severity crisis for: '{text}'"
        )


def test_plain_stress_variations_medium_severity():
    detector = RuleBasedSensitiveDetector()
    stress_texts = [
        "I am stressed.",
        "I am very stressed.",
        "I'm stressed out.",
        "I am dealing with so much stress right now.",
    ]
    for text in stress_texts:
        spans = detector.detect(text)
        assert len(spans) >= 1, f"Failed to detect stress in: '{text}'"
        assert all(s.severity == "medium" for s in spans), f"Expected medium severity for: '{text}'"
