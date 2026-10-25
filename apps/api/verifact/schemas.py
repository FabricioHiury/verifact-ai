from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from verifact.models import Classification, Status


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AnalysisOut(ORMModel):
    id: str
    title: str
    status: Status
    stage: str
    error_code: str | None
    error: str | None
    limitations: list[str]
    revision: int
    created_at: datetime
    updated_at: datetime


class AnalysisList(BaseModel):
    items: list[AnalysisOut]
    total: int


class URLInput(BaseModel):
    url: str = Field(max_length=2048)
    permitted: Literal[True]


class SpeakerOut(ORMModel):
    id: str
    cluster: str
    manual_name: str | None


class SpeakerPatch(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    segment_ids: list[str] = Field(default_factory=list, max_length=1000)


class SegmentOut(ORMModel):
    id: str
    start_time: float
    end_time: float
    text: str
    speaker_id: str | None
    manual_speaker_id: str | None


class EvidenceOut(BaseModel):
    id: str
    stance: str
    excerpt: str
    assessment: str
    url: str
    title: str
    publisher: str
    publication_date: str | None
    retrieved_at: datetime
    applicable_period: str | None
    source_type: str


class VerdictOut(ORMModel):
    classification: Classification
    reasoning: str
    limitations: list[str]
    model: str
    prompt_version: str


class SourceOut(ORMModel):
    id: str
    url: str
    title: str
    publisher: str
    publication_date: str | None
    retrieved_at: datetime
    applicable_period: str | None
    source_type: str
    content_hash: str
    excerpt: str


class ResearchQueryOut(ORMModel):
    id: str
    query: str
    purpose: str
    outcome: str
    created_at: datetime
    sources: list[SourceOut] = Field(default_factory=list)


class ClaimOut(BaseModel):
    id: str
    statement: str
    context: str
    topic: str
    start_time: float
    end_time: float
    speaker_id: str | None
    verdict: VerdictOut | None
    evidence: list[EvidenceOut]
    research_queries: list[ResearchQueryOut]


class HealthOut(BaseModel):
    status: str
    name: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorOut(BaseModel):
    error: ErrorDetail
