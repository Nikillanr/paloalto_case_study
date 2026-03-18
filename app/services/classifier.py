from typing import Literal

from app.services.ai_client import AIClient

Category = Literal["phishing", "data_breach", "local_hazard", "scam", "general"]
Severity = Literal["low", "medium", "high", "critical"]


def _fallback_category(description: str) -> Category:
    text = description.lower()
    if any(word in text for word in ["otp", "password", "verify", "link", "email"]):
        return "phishing"
    if any(word in text for word in ["leak", "breach", "database", "dump", "exposed"]):
        return "data_breach"
    if any(word in text for word in ["fire", "flood", "accident", "hazard", "earthquake"]):
        return "local_hazard"
    if any(word in text for word in ["scam", "fraud", "fake", "impersonation", "upi"]):
        return "scam"
    return "general"


def _fallback_severity(description: str) -> Severity:
    text = description.lower()
    if any(word in text for word in ["urgent", "multiple", "ongoing", "breach", "ransom"]):
        return "high"
    if any(word in text for word in ["critical", "hospital", "citywide", "shutdown"]):
        return "critical"
    if any(word in text for word in ["attempt", "single", "warning"]):
        return "medium"
    return "low"


def _checklist_for(category: Category) -> list[str]:
    if category == "phishing":
        return [
            "Do not click links or download attachments from the message.",
            "Report the sender and message in your email client.",
            "Reset your password and enable MFA if any credential was entered.",
        ]
    if category == "data_breach":
        return [
            "Rotate passwords for impacted accounts immediately.",
            "Enable MFA and review recent account sign-ins.",
            "Monitor financial and personal accounts for suspicious activity.",
        ]
    if category == "local_hazard":
        return [
            "Follow official local authority alerts and routes.",
            "Share your status with your trusted safety circle.",
            "Avoid unverified social media instructions.",
        ]
    if category == "scam":
        return [
            "Stop communication and preserve screenshots or call records.",
            "Block and report the account/number on the platform used.",
            "Contact your bank immediately if money or details were shared.",
        ]
    return [
        "Verify the incident source before acting.",
        "Use unique passwords and MFA across important accounts.",
        "Share only necessary details with trusted contacts.",
    ]


def analyze_incident(title: str, description: str, ai_enabled: bool = True) -> dict:
    client = AIClient()

    if ai_enabled and client.available():
        try:
            ai_result = client.classify_incident(title=title, description=description)
            category = ai_result.get("category", "general")
            severity = ai_result.get("severity", "medium")
            summary = ai_result.get(
                "summary",
                "Review this incident carefully and follow immediate safety actions.",
            )
            checklist = ai_result.get("checklist", _checklist_for(category))

            if category not in {"phishing", "data_breach", "local_hazard", "scam", "general"}:
                raise ValueError("Invalid category")
            if severity not in {"low", "medium", "high", "critical"}:
                raise ValueError("Invalid severity")
            if not isinstance(checklist, list) or len(checklist) != 3:
                raise ValueError("Checklist must have exactly three items")

            return {
                "category": category,
                "severity": severity,
                "summary": summary,
                "checklist": checklist,
                "source": "ai",
            }
        except Exception:
            pass

    category = _fallback_category(description)
    severity = _fallback_severity(description)
    summary = (
        f"Potential {category.replace('_', ' ')} incident reported in {description[:80]}"
        if description
        else "Potential security incident reported."
    )
    return {
        "category": category,
        "severity": severity,
        "summary": summary,
        "checklist": _checklist_for(category),
        "source": "fallback",
    }
