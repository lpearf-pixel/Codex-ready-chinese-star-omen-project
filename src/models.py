from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ModernIdentification(BaseModel):
    star_name: str
    catalog: str
    catalog_id: str | int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None


class Asterism(BaseModel):
    id: str
    name_cn: str
    system_version: Literal["pre_qin", "han", "jin", "tang", "song", "ming", "qing", "modern_reconstruction"]
    region: Literal["san_yuan", "er_shi_ba_xiu", "other"]
    modern_identifications: list[ModernIdentification]
    source_refs: list[str]
    aliases: list[str] = []
    parent_region: str | None = None
    anchor_star: str | None = None
    notes: str | None = None


class Evidence(BaseModel):
    kb_book_id: str | None = None
    note_id: str | None = None
    relative_path: str | None = None
    card_type: str | None = None
    locator: str | None = None
    anchor_heading: str | None = None
    quote: str | None = None
    manifest_ref: str | None = None
    evidence_level: str | None = None


class Trigger(BaseModel):
    body: str
    event_type: str
    target: str | None = None
    qualifiers: list[str] = []


class OmenRule(BaseModel):
    id: str
    source_text: str
    source_book: str
    trigger: Trigger
    effect_domain: list[Literal["politics", "leadership", "military", "agriculture", "climate", "economy", "public_health", "ritual", "border", "general_omen"]]
    validation_status: Literal["unverified", "partially_verified", "historically_attested", "disputed"]
    source_chapter: str | None = None
    evidence: Evidence | None = None
    severity: Literal["low", "medium", "high", "critical"] | None = None
    time_window: str | None = None
    interpretation: str | None = None
    modern_translation: str | None = None
    linked_cases: list[str] = []
    notes: str | None = None


class CelestialEvent(BaseModel):
    id: str
    datetime_utc: str
    body: str
    event_type: str
    epoch: str


class BacktestRecord(BaseModel):
    id: str
    event_id: str
    matched_rules: list[str]
    review_status: Literal["auto_generated", "manual_reviewed", "rejected", "needs_more_evidence"]
