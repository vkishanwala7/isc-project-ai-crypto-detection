"""Pydantic schemas for the documented API surface (OpenAPI at /docs)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ProvenanceStatus = Literal["VALID_PROVENANCE", "VALID_BUT_UNTRUSTED_SIGNER", "TAMPERED_OR_INVALID",
                           "NO_PROVENANCE_FOUND", "UNSUPPORTED_OR_UNREADABLE"]
AIVerdict = Literal["LIKELY_MANIPULATED", "LOW_MANIPULATION_SIGNAL", "INCONCLUSIVE"]


class SubsystemStatus(BaseModel):
    ok: bool
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    time: datetime
    subsystems: dict[str, SubsystemStatus]


class AssetOut(BaseModel):
    id: str
    role: str
    display_name: str
    mime: str
    size_bytes: int
    sha256: str
    phash: str | None
    width: int | None
    height: int | None
    duration_s: float | None
    url: str
    download_url: str


class CaseSummaryOut(BaseModel):
    id: str
    created_at: datetime
    kind: str
    title: str
    media_type: str
    is_sample: bool
    sample_label: str | None
    ai_verdict: str | None
    ai_score: float | None
    provenance_status: str | None
    headline: str | None
    tone: str | None
    thumbnail_url: str | None


class CaseListOut(BaseModel):
    items: list[CaseSummaryOut]
    total: int


class CaseDetailOut(CaseSummaryOut):
    sample_source: str | None
    summary: dict | None
    assets: list[AssetOut]
    analyses: list[dict[str, Any]]
    provenance: list[dict[str, Any]]
    timeline: list[dict[str, Any]]
    share_ref: str


class ActivityOut(BaseModel):
    id: int
    ts: datetime
    action: str
    case_id: str | None
    result: str
    details: dict | None


class ActivityListOut(BaseModel):
    items: list[ActivityOut]
    total: int


class DashboardSummary(BaseModel):
    counts: dict[str, int]
    ai_outcomes: dict[str, int]
    provenance_outcomes: dict[str, int]
    activity_series: list[dict[str, Any]] = Field(description="Per-day counts computed from stored audit events")
    recent_cases: list[CaseSummaryOut]
    sample_cases_excluded: bool
