"""SQLAlchemy ORM models. Schema is created with `Base.metadata.create_all` (SQLite);
swap the URL in database.py and add Alembic to migrate to another RDBMS later."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    """One investigation: an analysis, a signing, a verification or an integrity-lab run."""

    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    kind: Mapped[str] = mapped_column(String(24))          # analysis | signing | verification | integrity_lab
    title: Mapped[str] = mapped_column(String(200))         # sanitised display filename
    media_type: Mapped[str] = mapped_column(String(10))     # image | video
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    sample_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sample_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # combined evidence interpretation

    assets: Mapped[list[Asset]] = relationship(back_populates="case", cascade="all, delete-orphan", passive_deletes=True, order_by="Asset.created_at")
    analyses: Mapped[list[Analysis]] = relationship(back_populates="case", cascade="all, delete-orphan", passive_deletes=True)
    provenance: Mapped[list[ProvenanceRecord]] = relationship(back_populates="case", cascade="all, delete-orphan", passive_deletes=True, order_by="ProvenanceRecord.created_at")


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    role: Mapped[str] = mapped_column(String(24))           # original | signed | tampered | envelope | manifest
    stored_name: Mapped[str] = mapped_column(String(80))    # generated name inside storage dir
    display_name: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(80))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    phash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)

    case: Mapped[Case] = relationship(back_populates="assets")


class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(24))         # COMPLETED | MODEL_UNAVAILABLE | FAILED
    verdict: Mapped[str] = mapped_column(String(32))        # LIKELY_MANIPULATED | LOW_MANIPULATION_SIGNAL | INCONCLUSIVE
    reason: Mapped[str | None] = mapped_column(String(48), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    threshold: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    case: Mapped[Case] = relationship(back_populates="analyses")


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    operation: Mapped[str] = mapped_column(String(16))      # sign | verify
    status: Mapped[str] = mapped_column(String(32))         # VALID_PROVENANCE | VALID_BUT_UNTRUSTED_SIGNER | ...
    signature_valid: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    signer_trusted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    signer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    case: Mapped[Case] = relationship(back_populates="provenance")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)  # upload | analysis | sign | verify | tamper_test | error | ...
    case_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    result: Mapped[str] = mapped_column(String(48))
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
