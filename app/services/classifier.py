"""Rule-based fallback classifier with weighted keyword scoring.

Provides deterministic incident analysis when the AI pipeline is unavailable,
producing category, severity, confidence, summary, checklist, and reasoning.
"""

from __future__ import annotations
import re
from app.models import AnalysisResult

# ── Keyword weights per category ──────────────────────────────────────────

CATEGORY_KEYWORDS: dict[str, dict[str, int]] = {
    "phishing": {
        "phishing": 10, "credential": 8, "password": 8, "login": 7,
        "verify your": 9, "suspicious email": 9, "otp": 7, "click the link": 8,
        "account verification": 8, "payroll": 6, "reset password": 7,
        "spoof": 7, "impersonat": 6, "pretending": 5, "urgent action": 6,
        "deceptive email": 8, "fake login": 9, "harvest": 7,
    },
    "data_breach": {
        "breach": 10, "leaked": 9, "exposed": 8, "records": 6,
        "database": 5, "dump": 8, "personal data": 7, "compromised data": 9,
        "unauthorized access": 8, "data theft": 9, "stolen data": 9,
        "credit card": 7, "patient records": 8, "healthcare data": 8,
        "password dump": 9, "dark web": 8,
    },
    "scam": {
        "scam": 10, "fraud": 9, "impersonat": 8, "fake": 7, "trick": 6,
        "lottery": 8, "prize": 6, "too good to be true": 8, "ponzi": 9,
        "advance fee": 8, "job offer scam": 9, "upi": 7, "money transfer": 6,
        "tech support": 7, "refund": 6, "romance scam": 8,
        "investment fraud": 9, "fake offer": 8,
    },
    "local_hazard": {
        "chemical": 8, "spill": 7, "fire": 9, "gas leak": 10, "flood": 8,
        "construction": 5, "collapse": 8, "evacuat": 9, "hazard": 7,
        "toxic": 8, "electrical": 6, "power outage": 5, "water contamin": 8,
        "explosion": 9, "road block": 4, "structural damage": 7,
    },
    "network_security": {
        "malware": 10, "ransomware": 10, "wifi": 6, "ddos": 8,
        "vulnerability": 7, "exploit": 8, "trojan": 9, "botnet": 8,
        "man-in-the-middle": 9, "mitm": 9, "unauthorized network": 8,
        "firewall": 5, "intrusion": 8, "port scan": 7, "brute force": 8,
        "zero-day": 9, "public wifi": 7, "vpn": 4,
    },
}

# ── Severity keyword sets ─────────────────────────────────────────────────

SEVERITY_KEYWORDS: dict[str, dict[str, int]] = {
    "critical": {
        "immediate": 10, "emergency": 10, "widespread": 9, "all users": 8,
        "evacuate": 10, "active attack": 10, "mass": 8, "explosion": 9,
        "life-threatening": 10, "ransomware": 8, "confirmed breach": 9,
    },
    "high": {
        "urgent": 8, "multiple": 6, "confirmed": 7, "active": 6,
        "targeting": 7, "credential": 6, "ongoing": 7, "significant": 6,
        "spreading": 8, "compromised": 7, "critical infrastructure": 8,
    },
    "medium": {
        "potential": 5, "reported": 4, "suspected": 5, "warning": 5,
        "advisory": 4, "monitor": 4, "caution": 5, "investigation": 4,
    },
    "low": {
        "minor": 3, "isolated": 3, "outdated": 2, "resolved": 2,
        "informational": 2, "routine": 2, "awareness": 3,
    },
}

# ── Category-specific checklists ──────────────────────────────────────────

CHECKLISTS: dict[str, list[str]] = {
    "phishing": [
        "Do NOT click any links or download attachments from the suspicious message",
        "Report the message to your IT/security team or email provider",
        "If you entered credentials, change your password immediately",
        "Enable multi-factor authentication (MFA) on affected accounts",
        "Alert colleagues who may have received the same message",
    ],
    "data_breach": [
        "Change passwords for any accounts that may be affected",
        "Enable multi-factor authentication on all sensitive accounts",
        "Monitor bank statements and credit reports for unauthorized activity",
        "Be vigilant for follow-up phishing attempts using leaked information",
        "Consider placing a fraud alert with credit bureaus if financial data was exposed",
    ],
    "scam": [
        "Do NOT send money, gift cards, or personal information to the scammer",
        "Block the scammer's phone number, email, or social media profile",
        "Report the scam to local cybercrime authorities (e.g., cybercrime.gov.in)",
        "Warn friends and family about the scam so they are not targeted",
        "If money was sent, contact your bank immediately to attempt reversal",
    ],
    "local_hazard": [
        "Follow instructions from local emergency services immediately",
        "Evacuate the area if advised or if you sense danger",
        "Call emergency services (112 or local number) if not already alerted",
        "Avoid the affected area and keep a safe distance",
        "Check on vulnerable neighbors (elderly, disabled, children)",
    ],
    "network_security": [
        "Disconnect affected devices from the network immediately",
        "Run a full antivirus/antimalware scan on all devices",
        "Change passwords for accounts accessed from the compromised network",
        "Avoid using public WiFi without a trusted VPN",
        "Report the incident to your organization's IT security team",
    ],
    "general": [
        "Stay informed through official and verified news sources",
        "Report suspicious activity to local authorities",
        "Avoid spreading unverified information on social media",
        "Follow community guidelines and support those affected",
    ],
}

# ── Human-readable category labels ────────────────────────────────────────

CATEGORY_LABELS: dict[str, str] = {
    "phishing": "phishing attempt",
    "data_breach": "data breach",
    "scam": "scam or fraud scheme",
    "local_hazard": "local safety hazard",
    "network_security": "network security threat",
    "general": "community safety concern",
}

# ── Impact descriptors by severity ────────────────────────────────────────

SEVERITY_IMPACT: dict[str, str] = {
    "critical": "This poses an immediate and severe risk requiring urgent action",
    "high": "This represents a significant threat that should be addressed promptly",
    "medium": "This is a moderate concern that warrants monitoring and caution",
    "low": "This is a low-level concern but should still be noted for awareness",
}


def _score_text(text: str, keywords: dict[str, int]) -> tuple[float, list[str]]:
    """Score text against weighted keyword dict. Returns (score, matched_keywords)."""
    text_lower = text.lower()
    total = 0.0
    matches = []
    for keyword, weight in keywords.items():
        if keyword.lower() in text_lower:
            total += weight
            matches.append(keyword)
    return total, matches


def _detect_category(text: str) -> tuple[str, float, list[str]]:
    """Return (category, confidence, matched_keywords)."""
    best_cat = "general"
    best_score = 0.0
    best_matches: list[str] = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        score, matches = _score_text(text, keywords)
        if score > best_score:
            best_score = score
            best_cat = category
            best_matches = matches

    # Confidence: ratio of achieved score to max possible, scaled
    if best_cat != "general" and best_cat in CATEGORY_KEYWORDS:
        max_possible = sum(CATEGORY_KEYWORDS[best_cat].values())
        confidence = min(0.95, max(0.3, best_score / max_possible * 2.5))
    else:
        confidence = 0.25

    return best_cat, round(confidence, 2), best_matches


def _detect_severity(text: str) -> tuple[str, list[str]]:
    """Return (severity, matched_factors)."""
    # Check from highest to lowest priority
    for level in ["critical", "high", "medium", "low"]:
        score, matches = _score_text(text, SEVERITY_KEYWORDS[level])
        if score > 0:
            return level, matches

    return "medium", []


def _extract_entities(text: str) -> dict[str, list[str]]:
    """Extract key entities from text for richer summaries."""
    text_lower = text.lower()
    entities: dict[str, list[str]] = {"targets": [], "methods": [], "assets": []}

    # Targets
    target_patterns = [
        (r"employees?\b", "employees"), (r"users?\b", "users"),
        (r"residents?\b", "residents"), (r"customers?\b", "customers"),
        (r"patients?\b", "patients"), (r"students?\b", "students"),
        (r"citizens?\b", "citizens"), (r"businesses?\b", "businesses"),
    ]
    for pattern, label in target_patterns:
        if re.search(pattern, text_lower):
            entities["targets"].append(label)

    # Methods / attack vectors
    method_patterns = [
        (r"email", "email"), (r"sms|text message", "SMS"),
        (r"whatsapp", "WhatsApp"), (r"phone call", "phone call"),
        (r"website|portal|url|link", "malicious link"),
        (r"social media", "social media"), (r"qr code", "QR code"),
    ]
    for pattern, label in method_patterns:
        if re.search(pattern, text_lower):
            entities["methods"].append(label)

    # Assets at risk
    asset_patterns = [
        (r"password|credential|login", "credentials"),
        (r"bank|financial|payment|upi", "financial data"),
        (r"personal data|personal info|pii", "personal information"),
        (r"medical|health|patient", "health records"),
        (r"credit card|debit card", "payment cards"),
        (r"infrastructure|system|server", "systems/infrastructure"),
    ]
    for pattern, label in asset_patterns:
        if re.search(pattern, text_lower):
            entities["assets"].append(label)

    return entities


def _generate_summary(
    title: str, description: str, location: str,
    category: str, severity: str, matched_keywords: list[str],
) -> str:
    """Generate a detailed, contextual summary based on extracted information."""
    entities = _extract_entities(f"{title} {description}")
    cat_label = CATEGORY_LABELS.get(category, "community safety concern")
    impact = SEVERITY_IMPACT.get(severity, SEVERITY_IMPACT["medium"])

    # Build who/what/where components
    who = ""
    if entities["targets"]:
        who = f" targeting {_join_list(entities['targets'][:3])}"

    method = ""
    if entities["methods"]:
        method = f" via {_join_list(entities['methods'][:2])}"

    assets = ""
    if entities["assets"]:
        assets = f", potentially compromising {_join_list(entities['assets'][:3])}"

    # Extract first meaningful sentence from description
    core_detail = _first_sentence(description)

    # Build the summary
    summary = (
        f"A {severity}-severity {cat_label} has been reported in {location}"
        f"{who}{method}. {core_detail}{assets}. {impact}."
    )

    # Clean up double periods or comma-period
    summary = summary.replace("..", ".").replace(".,", ",")

    return summary


def _join_list(items: list[str]) -> str:
    """Join list items with commas and 'and'."""
    if len(items) == 0:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _first_sentence(text: str) -> str:
    """Extract the first sentence from text."""
    match = re.match(r"^(.+?[.!?])\s", text)
    return match.group(1) if match else (text[:150] + "..." if len(text) > 150 else text)


def classify(title: str, description: str, location: str) -> AnalysisResult:
    """Analyze an incident using rule-based heuristics. Always succeeds."""
    combined = f"{title} {description}"

    category, confidence, cat_matches = _detect_category(combined)
    severity, sev_factors = _detect_severity(combined)
    summary = _generate_summary(title, description, location, category, severity, cat_matches)
    checklist = CHECKLISTS.get(category, CHECKLISTS["general"])

    # Build detailed reasoning explanation
    if cat_matches:
        reasoning = (
            f"Classified as '{category}' based on {len(cat_matches)} keyword indicators: "
            f"{', '.join(cat_matches[:5])}. "
            f"Confidence score of {confidence:.0%} derived from weighted keyword match ratio. "
        )
    else:
        reasoning = (
            "No strong category indicators found; classified as 'general'. "
            f"Low confidence ({confidence:.0%}) indicates this report may need manual review. "
        )

    if sev_factors:
        reasoning += (
            f"Severity assessed as '{severity}' based on urgency indicators: "
            f"{', '.join(sev_factors[:3])}."
        )
    else:
        reasoning += (
            f"Severity defaulted to '{severity}' — no explicit urgency indicators detected. "
            f"Manual review recommended to verify severity assessment."
        )

    return AnalysisResult(
        category=category,
        severity=severity,
        confidence=confidence,
        summary=summary,
        checklist=checklist,
        source="fallback",
        reasoning=reasoning,
    )
