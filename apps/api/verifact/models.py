from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class AnalysisCancelled(Exception):
    """Cooperative cancellation at a heavyweight-operation admission boundary."""


class Status(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"


class Classification(StrEnum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    PARTIALLY_TRUE = "PARTIALLY_TRUE"
    MISLEADING_CONTEXT = "MISLEADING_CONTEXT"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_CHECKABLE = "NOT_CHECKABLE"


class Base(DeclarativeBase):
    pass


class Entity(Base):
    __abstract__ = True
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Analysis(Entity):
    __tablename__ = "analyses"
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default=Status.QUEUED, index=True)
    stage: Mapped[str] = mapped_column(String(32), default="INGESTING")
    source_url: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    pipeline_version: Mapped[str] = mapped_column(String(40), default="1")
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class MediaAsset(Entity):
    __tablename__ = "media_assets"
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), unique=True)
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int]
    mime_type: Mapped[str] = mapped_column(String(64))
    duration: Mapped[float]
    codecs: Mapped[list[str]] = mapped_column(JSON)


class Speaker(Entity):
    __tablename__ = "speakers"
    __table_args__ = (UniqueConstraint("analysis_id", "cluster"),)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    cluster: Mapped[str] = mapped_column(String(100))
    manual_name: Mapped[str | None] = mapped_column(String(120))
    correction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TranscriptSegment(Entity):
    __tablename__ = "transcript_segments"
    __table_args__ = (
        UniqueConstraint("analysis_id", "chunk", "ordinal"),
        CheckConstraint("end_time >= start_time AND start_time >= 0"),
    )
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    chunk: Mapped[int]
    ordinal: Mapped[int]
    start_time: Mapped[float]
    end_time: Mapped[float]
    text: Mapped[str] = mapped_column(Text)
    words: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list)
    speaker_id: Mapped[str | None] = mapped_column(ForeignKey("speakers.id"))
    manual_speaker_id: Mapped[str | None] = mapped_column(ForeignKey("speakers.id"))
    model: Mapped[str] = mapped_column(String(255))


class Claim(Entity):
    __tablename__ = "claims"
    __table_args__ = (UniqueConstraint("analysis_id", "segment_id", "statement"),)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    segment_id: Mapped[str] = mapped_column(ForeignKey("transcript_segments.id"))
    statement: Mapped[str] = mapped_column(Text)
    context: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str] = mapped_column(String(120), default="")
    checkable: Mapped[bool] = mapped_column(default=True)


class ResearchQuery(Entity):
    __tablename__ = "research_queries"
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    query: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str] = mapped_column(String(40))
    outcome: Mapped[str] = mapped_column(Text, default="PENDING")


class Source(Entity):
    __tablename__ = "sources"
    query_id: Mapped[str] = mapped_column(ForeignKey("research_queries.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String(255))
    publication_date: Mapped[str | None] = mapped_column(String(80))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    applicable_period: Mapped[str | None] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(40))
    content_hash: Mapped[str] = mapped_column(String(64))
    excerpt: Mapped[str] = mapped_column(Text)


class Evidence(Entity):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("claim_id", "source_id"),)
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"))
    stance: Mapped[str] = mapped_column(String(24))
    excerpt: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(255))
    assessment: Mapped[str] = mapped_column(Text)


class Verdict(Entity):
    __tablename__ = "verdicts"
    claim_id: Mapped[str] = mapped_column(ForeignKey("claims.id"), unique=True)
    classification: Mapped[str] = mapped_column(String(32))
    reasoning: Mapped[str] = mapped_column(Text)
    limitations: Mapped[list[str]] = mapped_column(JSON)
    evidence_ids: Mapped[list[str]] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(40))


class AgentExecution(Entity):
    __tablename__ = "agent_executions"
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    agent: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(255))
    prompt_version: Mapped[str] = mapped_column(String(40))
    input_hash: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(40))
    duration_seconds: Mapped[float]


class ProcessingCheckpoint(Entity):
    __tablename__ = "processing_checkpoints"
    __table_args__ = (UniqueConstraint("analysis_id", "stage", "unit", "version"),)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    stage: Mapped[str] = mapped_column(String(40))
    unit: Mapped[str] = mapped_column(String(100))
    version: Mapped[str] = mapped_column(String(64))
    artifact: Mapped[str | None] = mapped_column(String(255))


class Report(Entity):
    __tablename__ = "reports"
    __table_args__ = (UniqueConstraint("analysis_id", "revision"),)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), index=True)
    revision: Mapped[int]
    html_key: Mapped[str] = mapped_column(String(255))
    pdf_key: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)


Index("ix_transcript_timeline", TranscriptSegment.analysis_id, TranscriptSegment.start_time)
