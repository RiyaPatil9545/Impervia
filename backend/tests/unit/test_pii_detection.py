from decimal import Decimal

from app.ml.pii_detection.detector import RuleBasedPIIDetector


def test_email_detection():
    detector = RuleBasedPIIDetector()
    text = "Please reach out to alice.smith@university.edu or student_99@gmail.com for notes."
    spans = detector.detect(text)

    categories = [s.category for s in spans]
    assert "email" in categories
    assert len([s for s in spans if s.category == "email"]) == 2
    assert spans[0].text == "alice.smith@university.edu"
    assert spans[0].confidence >= Decimal("0.90")


def test_phone_number_detection():
    detector = RuleBasedPIIDetector()
    text = "Call me at +1 (555) 123-4567 or 9876543210 regarding the assignment."
    spans = detector.detect(text)

    phone_spans = [s for s in spans if s.category == "phone_number"]
    assert len(phone_spans) >= 1
    assert any("9876543210" in s.text for s in phone_spans)


def test_ip_address_detection():
    detector = RuleBasedPIIDetector()
    text = "The web server crashed at IP 192.168.1.100 while testing version 2.0."
    spans = detector.detect(text)

    ip_spans = [s for s in spans if s.category == "ip_address"]
    assert len(ip_spans) == 1
    assert ip_spans[0].text == "192.168.1.100"


def test_student_and_national_ids():
    detector = RuleBasedPIIDetector()
    text = "My Student ID: CS-2024-998 and SSN: 123-45-6789."
    spans = detector.detect(text)

    categories = {s.category for s in spans}
    assert "student_id" in categories
    assert "national_id" in categories


def test_credit_card_detection():
    detector = RuleBasedPIIDetector()
    text = "Pay using card 4111-2222-3333-4444 for registration."
    spans = detector.detect(text)

    card_spans = [s for s in spans if s.category == "financial"]
    assert len(card_spans) == 1
    assert "4111-2222-3333-4444" in card_spans[0].text


def test_name_introduction_detection():
    detector = RuleBasedPIIDetector()
    text = "Hello, my name is John Doe and I need help with math."
    spans = detector.detect(text)

    name_spans = [s for s in spans if s.category == "person_name"]
    assert len(name_spans) == 1
    assert "John Doe" in name_spans[0].text


def test_clean_input_no_false_positives():
    detector = RuleBasedPIIDetector()
    text = "What is the time complexity of QuickSort in Big-O notation?"
    spans = detector.detect(text)
    assert len(spans) == 0
