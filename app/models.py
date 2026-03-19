"""Pydantic schemas for request/response validation."""

from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel, Field


# --------------- Request schemas ---------------

class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    location: str = Field(..., min_length=2, max_length=200)
    use_ai: Optional[bool] = None  # None = auto (AI if available), True = force AI, False = force fallback


class IncidentUpdate(BaseModel):
    status: Optional[Literal["new", "verified", "resolved", "dismissed"]] = None
    severity: Optional[Literal["critical", "high", "medium", "low"]] = None


class FeedImportRequest(BaseModel):
    max_items: int = Field(default=50, ge=1, le=500)
    reset_existing: bool = False
    use_ai: Optional[bool] = None


class ReanalyzeRequest(BaseModel):
    use_ai: Optional[bool] = None


# --------------- Analysis result ---------------

class AnalysisResult(BaseModel):
    category: str
    severity: Literal["critical", "high", "medium", "low"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    summary: str
    checklist: list[str]
    source: Literal["ai", "fallback"]
    reasoning: str


# --------------- Response schemas ---------------

class Incident(BaseModel):
    id: int
    title: str
    description: str
    location: str
    category: str
    severity: str
    confidence: float
    summary: str
    checklist: list[str]
    source: str
    reasoning: str
    entry_mode: str
    status: str
    created_at: str
    updated_at: str


class FeedEvent(BaseModel):
    title: str
    description: str
    location: str
    source: str = "unknown"
    reported_at: str = ""


class Stats(BaseModel):
    total: int
    by_severity: dict[str, int]
    by_category: dict[str, int]
    by_source: dict[str, int]
    avg_confidence: float
