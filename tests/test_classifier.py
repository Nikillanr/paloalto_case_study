"""Classifier unit tests — validates fallback rule-based classification logic."""

import pytest
from app.services.classifier import classify


def test_classify_phishing():
    result = classify(
        title="Phishing email targeting employees",
        description="Staff received suspicious emails asking to verify credentials through a fake login page.",
        location="Bengaluru",
    )
    assert result.category == "phishing"
    assert result.source == "fallback"
    assert result.confidence > 0.3


def test_classify_data_breach():
    result = classify(
        title="Customer records leaked from database",
        description="Unauthorized access exposed personal data including emails and phone numbers from the company database.",
        location="Mumbai",
    )
    assert result.category == "data_breach"
    assert result.confidence > 0.3


def test_classify_scam():
    result = classify(
        title="UPI payment fraud reported",
        description="Victims are being tricked into transferring money via fake UPI payment requests from scam callers.",
        location="Delhi",
    )
    assert result.category == "scam"


def test_classify_local_hazard():
    result = classify(
        title="Gas leak in residential area",
        description="Emergency services responding to a major gas leak. Residents should evacuate immediately.",
        location="Pune",
    )
    assert result.category == "local_hazard"
    assert result.severity in ("critical", "high")


def test_classify_network_security():
    result = classify(
        title="Ransomware attack on government systems",
        description="Multiple systems encrypted by ransomware. Active attack spreading through the network.",
        location="Lucknow",
    )
    assert result.category == "network_security"
    assert result.severity in ("critical", "high")


def test_severity_detection():
    # Critical-level indicators
    result = classify(
        title="Emergency evacuation ordered",
        description="Immediate evacuation required. Widespread chemical spill threatens life-threatening exposure.",
        location="Chennai",
    )
    assert result.severity == "critical"


def test_confidence_in_valid_range():
    """Confidence should always be between 0 and 1."""
    for title, desc in [
        ("Phishing attack", "Credential harvesting via fake login page"),
        ("Gas leak", "Emergency evacuation due to gas leak"),
        ("Random text", "Nothing specific about any category here at all"),
    ]:
        result = classify(title, desc, "Test City")
        assert 0.0 <= result.confidence <= 1.0


def test_checklist_not_empty():
    result = classify(
        title="Some safety incident",
        description="A community safety report has been filed about potential issues.",
        location="Jaipur",
    )
    assert len(result.checklist) >= 3


def test_reasoning_explains_classification():
    result = classify(
        title="Phishing campaign via email",
        description="Deceptive emails asking users to verify their password through a spoofed login page.",
        location="Hyderabad",
    )
    assert "phishing" in result.reasoning.lower()
    assert result.reasoning != ""


def test_unknown_input_defaults_to_general():
    result = classify(
        title="Xyz abc",
        description="Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod.",
        location="Unknown",
    )
    assert result.category == "general"
    assert result.confidence < 0.5
