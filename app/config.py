"""Centralized configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
AI_ENABLED: bool = os.getenv("AI_ENABLED", "true").lower() in ("true", "1", "yes")
DATABASE_PATH: str = os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "guardian.db"))
FEED_PATH: str = os.getenv("FEED_PATH", str(BASE_DIR / "data" / "seed_events.json"))
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
