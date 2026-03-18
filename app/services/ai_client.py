import json
import os
from typing import Any

import httpx


class AIClient:
    """Optional OpenAI client; callers should always be prepared to fallback."""

    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def available(self) -> bool:
        return bool(self.api_key)

    def classify_incident(self, title: str, description: str) -> dict[str, Any]:
        if not self.available():
            raise RuntimeError("OPENAI_API_KEY is not configured")

        prompt = (
            "You are a cybersecurity triage assistant. "
            "Return strict JSON with keys: category, severity, summary, checklist. "
            "category must be one of phishing,data_breach,local_hazard,scam,general. "
            "severity must be one of low,medium,high,critical. "
            "checklist must be exactly 3 concise imperative steps."
        )

        with httpx.Client(timeout=15) as client:
            response = client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {
                            "role": "user",
                            "content": f"Title: {title}\nDescription: {description}",
                        },
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            payload = response.json()

        content = payload["choices"][0]["message"]["content"]
        return json.loads(content)
