"""AI analysis pipeline — tries Groq LLM, falls back to rule-based classifier."""

from __future__ import annotations
import asyncio
import json
import logging
import httpx
from app import config
from app.models import AnalysisResult
from app.services.classifier import classify

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a community safety analyst AI. Given a safety report, analyze it and return a JSON object with these fields:

- category: one of "phishing", "data_breach", "scam", "local_hazard", "network_security", "general"
- severity: one of "critical", "high", "medium", "low"
- confidence: a float between 0.0 and 1.0 indicating your confidence in this classification
- summary: a concise 2-3 sentence summary of the incident and its impact
- checklist: an array of 3-5 actionable steps the community should take
- reasoning: a brief explanation of why you chose this category and severity

Respond ONLY with valid JSON. No markdown, no explanation outside the JSON."""

# Track whether daily limit has been hit so we stop wasting retries
_daily_limit_hit = False


def _ai_available() -> bool:
    return bool(config.GROQ_API_KEY) and config.AI_ENABLED and not _daily_limit_hit


async def _call_groq(title: str, description: str, location: str) -> AnalysisResult:
    """Call Groq API (OpenAI-compatible) with retry on rate limit."""
    global _daily_limit_hit

    user_prompt = (
        f"Analyze this community safety report:\n\n"
        f"Title: {title}\n"
        f"Description: {description}\n"
        f"Location: {location}\n\n"
        f"Return your analysis as JSON."
    )

    max_retries = 3

    for attempt in range(max_retries):
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )

            if resp.status_code == 429:
                # Check if it's a daily limit (no point retrying)
                try:
                    body = resp.json()
                    error_msg = body.get("error", {}).get("message", "")
                except Exception:
                    error_msg = ""
                if "per day" in error_msg.lower() or "tpd" in error_msg.lower():
                    _daily_limit_hit = True
                    raise Exception("Groq daily token limit reached. Switch to Fallback mode or wait for reset.")

                # Regular rate limit — wait and retry
                wait = float(resp.headers.get("retry-after", 2 * (attempt + 1)))
                log.info("Rate limited by Groq, waiting %.1fs (attempt %d/%d)", wait, attempt + 1, max_retries)
                await asyncio.sleep(wait)
                continue

            resp.raise_for_status()
            break
    else:
        raise Exception("Groq rate limit exceeded after retries")

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)

    # Validate required fields
    required = {"category", "severity", "confidence", "summary", "checklist", "reasoning"}
    if not required.issubset(parsed.keys()):
        raise ValueError(f"AI response missing fields: {required - parsed.keys()}")

    # Clamp confidence
    conf = max(0.0, min(1.0, float(parsed["confidence"])))

    return AnalysisResult(
        category=parsed["category"],
        severity=parsed["severity"],
        confidence=round(conf, 2),
        summary=parsed["summary"],
        checklist=parsed["checklist"][:5],
        source="ai",
        reasoning=parsed["reasoning"],
    )


async def analyze(
    title: str, description: str, location: str,
    use_ai: bool | None = None,
) -> AnalysisResult:
    """Analyze an incident.

    use_ai=None  → auto: AI if available, else fallback
    use_ai=True  → force AI (raises if unavailable)
    use_ai=False → force fallback
    """
    if use_ai is False:
        return classify(title, description, location)

    if use_ai is True or _ai_available():
        try:
            return await _call_groq(title, description, location)
        except Exception as e:
            log.warning("AI analysis failed: %s — %s", type(e).__name__, e)
            if use_ai is True:
                raise  # User explicitly asked for AI — surface the error
            pass  # Auto mode — fall through to fallback

    return classify(title, description, location)
