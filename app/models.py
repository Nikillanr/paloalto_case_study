from pydantic import BaseModel, Field
from typing import Literal

Severity = Literal["low", "medium", "high", "critical"]
Status = Literal["new", "verified", "ignored", "resolved"]
Category = Literal["phishing", "data_breach", "local_hazard", "scam", "general"]


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=120)
    description: str = Field(..., min_length=10, max_length=2000)
    location: str = Field(..., min_length=2, max_length=120)


class IncidentUpdate(BaseModel):
    status: Status | None = None
    severity: Severity | None = None


class Incident(BaseModel):
    id: int
    title: str
    description: str
    location: str
    category: Category
    severity: Severity
    status: Status
    summary: str
    checklist: list[str]
    source: Literal["ai", "fallback"]
    entry_mode: Literal["feed", "manual"] = "manual"


class FeedImportRequest(BaseModel):
    reset_existing: bool = False
    max_items: int | None = Field(default=None, ge=1, le=500)
