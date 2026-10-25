import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.middleware.trustedhost import TrustedHostMiddleware

from verifact.config import settings
from verifact.db import factory, session
from verifact.limits import BodyLimitMiddleware
from verifact.models import (
    Analysis,
    Claim,
    Evidence,
    MediaAsset,
    Report,
    ResearchQuery,
    Source,
    Speaker,
    Status,
    TranscriptSegment,
    Verdict,
    now,
)
from verifact.schemas import (
    AnalysisList,
    AnalysisOut,
    ClaimOut,
    ErrorOut,
    EvidenceOut,
    HealthOut,
    ResearchQueryOut,
    SegmentOut,
    SourceOut,
    SpeakerOut,
    SpeakerPatch,
    URLInput,
    VerdictOut,
)
from verifact.security import UnsafeURL, social_provider
from verifact.storage import check_disk, local_path, publish

logging.getLogger("httpx").setLevel(logging.WARNING)
cfg = settings()
app = FastAPI(
    title=cfg.app_name,
    version="0.1.0",
    debug=cfg.app_debug,
    responses={
        400: {"model": ErrorOut},
        404: {"model": ErrorOut},
        409: {"model": ErrorOut},
        422: {"model": ErrorOut},
        503: {"model": ErrorOut},
    },
)
app.add_middleware(
    BodyLimitMiddleware,
    max_bytes=((cfg.media_max_size_mb or cfg.storage_budget_mb) * 1024 * 1024) + 1024 * 1024,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
origins = [f"http://{host}:{cfg.web_port}" for host in ("localhost", "127.0.0.1")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)
DB = Annotated[Session, Depends(session)]
prefix = "/api/v1"


@app.middleware("http")
async def local_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
    origin = request.headers.get("origin")
    if origin and origin not in origins:
        return JSONResponse(
            {"error": {"code": "ORIGIN_REJECTED", "message": "Origem não permitida"}},
            status_code=403,
        )
    if request.method == "POST":
        limit = (cfg.media_max_size_mb or cfg.storage_budget_mb) * 1024 * 1024
        try:
            length = int(request.headers.get("content-length", "0"))
        except ValueError:
            length = limit + 1
        if length > limit + 1024 * 1024:
            return JSONResponse(
                {"error": {"code": "UPLOAD_TOO_LARGE", "message": "Upload excede orçamento"}},
                status_code=413,
            )
        if request.url.path == prefix + "/analyses/uploads":
            try:
                await asyncio.to_thread(check_disk, length)
            except ValueError:
                return JSONResponse(
                    {
                        "error": {
                            "code": "STORAGE_BUDGET",
                            "message": "Espaço ou orçamento de armazenamento insuficiente",
                        }
                    },
                    status_code=413,
                )

    return await call_next(request)


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        {"error": {"code": f"HTTP_{exc.status_code}", "message": str(exc.detail)}},
        status_code=exc.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Dados inválidos; confira campos, limites e permissões",
            }
        },
        status_code=422,
    )


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("verifact").error("request_failed type=%s", type(exc).__name__)
    return JSONResponse(
        {
            "error": {
                "code": "SERVICE_ERROR",
                "message": "Serviço indisponível; consulte o estado persistido",
            }
        },
        status_code=503,
    )


def get_analysis(db: Session, identifier: str) -> Analysis:
    item = db.get(Analysis, identifier)
    if not item:
        raise HTTPException(404, "Análise não encontrada")
    return item


def enqueue(identifier: str) -> None:
    from verifact_worker.celery_app import app as celery

    try:
        celery.send_task("verifact.process", args=[identifier], retry=False)
    except Exception as exc:
        # QUEUED is the durable outbox; periodic dispatch recovers broker outages.
        logging.getLogger("verifact").warning("dispatch_deferred type=%s", type(exc).__name__)


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", name=cfg.app_name)


@app.post(prefix + "/analyses/uploads", response_model=AnalysisOut, status_code=202)
def upload(response: Response, db: DB, file: UploadFile = File(...)) -> Analysis:
    from verifact_worker.media import probe, signature

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".mp3", ".mp4"):
        raise HTTPException(415, "Envie MP3 ou MP4")
    allowed_mime = {
        ".mp3": {"audio/mpeg", "audio/mp3", "application/octet-stream"},
        ".mp4": {"video/mp4", "audio/mp4", "application/octet-stream"},
    }
    if file.content_type not in allowed_mime[suffix]:
        raise HTTPException(415, "MIME incompatível")
    identifier = str(uuid4())
    key = f"{identifier}/original{suffix}"
    path = local_path(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        check_disk()
        with path.open("wb") as output:
            while block := file.file.read(1024 * 1024):
                size += len(block)
                if cfg.media_max_size_mb and size > cfg.media_max_size_mb * 1024 * 1024:
                    raise ValueError("Arquivo excede limite configurado")
                check_disk(len(block))
                digest.update(block)
                output.write(block)
        mime = signature(path, suffix)
        metadata = probe(path)
        publish(path, key)
        analysis = Analysis(id=identifier, title=Path(file.filename or "Mídia").name[:255])
        db.add(analysis)
        db.flush()
        db.add(
            MediaAsset(
                analysis_id=identifier,
                filename=analysis.title,
                storage_key=key,
                sha256=digest.hexdigest(),
                size_bytes=size,
                mime_type=mime,
                duration=float(metadata["format"]["duration"]),
                codecs=[str(s.get("codec_name", "unknown")) for s in metadata["streams"]],
            )
        )
        db.commit()
        db.refresh(analysis)
    except Exception as exc:
        db.rollback()
        path.unlink(missing_ok=True)
        if isinstance(exc, ValueError):
            raise HTTPException(422, str(exc)) from exc
        raise HTTPException(422, "Não foi possível validar ou armazenar a mídia") from exc
    finally:
        file.file.close()
    enqueue(identifier)
    response.headers["Location"] = f"{prefix}/analyses/{identifier}/status"
    return analysis


@app.post(prefix + "/analyses/from-url", response_model=AnalysisOut, status_code=202)
def from_url(body: URLInput, response: Response, db: DB) -> Analysis:
    try:
        provider = social_provider(body.url)
    except UnsafeURL as exc:
        raise HTTPException(422, str(exc)) from exc
    item = Analysis(title=f"Vídeo público: {provider}", source_url=body.url)
    db.add(item)
    db.commit()
    db.refresh(item)
    enqueue(item.id)
    response.headers["Location"] = f"{prefix}/analyses/{item.id}/status"
    return item


@app.get(prefix + "/analyses", response_model=AnalysisList)
def analyses(
    db: DB, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)
) -> AnalysisList:
    items = db.scalars(
        select(Analysis).order_by(Analysis.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return AnalysisList(
        items=[AnalysisOut.model_validate(x) for x in items],
        total=db.scalar(select(func.count()).select_from(Analysis)) or 0,
    )


@app.get(prefix + "/analyses/{id}", response_model=AnalysisOut)
@app.get(prefix + "/analyses/{id}/status", response_model=AnalysisOut)
def analysis(id: str, db: DB) -> Analysis:
    return get_analysis(db, id)


@app.get(prefix + "/analyses/{id}/events")
def events(id: str, db: DB) -> StreamingResponse:
    get_analysis(db, id)

    async def stream() -> AsyncIterator[str]:
        previous = ""
        for _ in range(300):

            def read() -> str:
                with factory()() as current:
                    item = get_analysis(current, id)
                    return AnalysisOut.model_validate(item).model_dump_json()

            data = await asyncio.to_thread(read)
            if data != previous:
                yield f"id: {json.loads(data)['updated_at']}\nevent: status\ndata: {data}\n\n"
                previous = data
            else:
                yield ": heartbeat\n\n"
            if json.loads(data)["status"] in (
                "COMPLETED",
                "PARTIALLY_COMPLETED",
                "FAILED",
                "CANCELLED",
                "PAUSED",
            ):
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get(prefix + "/analyses/{id}/media")
def media(id: str, db: DB) -> FileResponse:
    get_analysis(db, id)
    asset = db.scalar(select(MediaAsset).where(MediaAsset.analysis_id == id))
    if not asset:
        raise HTTPException(404, "Mídia indisponível")
    return FileResponse(local_path(asset.storage_key), media_type=asset.mime_type)


@app.get(prefix + "/analyses/{id}/transcript", response_model=list[SegmentOut])
def transcript(
    id: str, db: DB, offset: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)
) -> list[TranscriptSegment]:
    get_analysis(db, id)
    return list(
        db.scalars(
            select(TranscriptSegment)
            .where(TranscriptSegment.analysis_id == id)
            .order_by(TranscriptSegment.start_time)
            .offset(offset)
            .limit(limit)
        )
    )


@app.get(prefix + "/analyses/{id}/speakers", response_model=list[SpeakerOut])
def speakers(id: str, db: DB) -> list[Speaker]:
    get_analysis(db, id)
    return list(
        db.scalars(select(Speaker).where(Speaker.analysis_id == id).order_by(Speaker.cluster))
    )


@app.patch(prefix + "/analyses/{id}/speakers/{speaker_id}", response_model=SpeakerOut)
def correct_speaker(id: str, speaker_id: str, body: SpeakerPatch, db: DB) -> Speaker:
    item = get_analysis(db, id)
    if item.status in (Status.RUNNING, Status.CANCEL_REQUESTED):
        raise HTTPException(409, "Aguarde o processamento terminar ou cancele antes de corrigir")
    speaker = db.get(Speaker, speaker_id)
    if not speaker or speaker.analysis_id != id:
        raise HTTPException(404, "Interlocutor não encontrado")
    segments = []
    for segment_id in body.segment_ids:
        segment = db.get(TranscriptSegment, segment_id)
        if not segment or segment.analysis_id != id:
            raise HTTPException(422, "Trecho não pertence à análise")
        segments.append(segment)
    changed = False
    if "name" in body.model_fields_set:
        name = (body.name or "").strip() or None
        if name != speaker.manual_name:
            speaker.manual_name = name
            changed = True
    for segment in segments:
        if segment.manual_speaker_id != speaker_id:
            segment.manual_speaker_id = speaker_id
            changed = True
    if changed:
        speaker.correction_at = now()
        item.revision += 1
        item.updated_at = now()
    db.commit()
    db.refresh(speaker)
    return speaker


def claim_view(db: Session, claim: Claim) -> ClaimOut:
    segment = db.get(TranscriptSegment, claim.segment_id)
    if segment is None:
        raise HTTPException(409, "Trecho de origem ausente")
    verdict = db.scalar(select(Verdict).where(Verdict.claim_id == claim.id))
    evidence = []
    for ev, source in db.execute(
        select(Evidence, Source)
        .join(Source, Evidence.source_id == Source.id)
        .where(Evidence.claim_id == claim.id)
    ):
        evidence.append(
            EvidenceOut(
                id=ev.id,
                stance=ev.stance,
                excerpt=ev.excerpt,
                assessment=ev.assessment,
                url=source.url,
                title=source.title,
                publisher=source.publisher,
                publication_date=source.publication_date,
                retrieved_at=source.retrieved_at,
                applicable_period=source.applicable_period,
                source_type=source.source_type,
            )
        )
    return ClaimOut(
        id=claim.id,
        statement=claim.statement,
        context=claim.context,
        topic=claim.topic,
        start_time=segment.start_time,
        end_time=segment.end_time,
        speaker_id=segment.manual_speaker_id or segment.speaker_id,
        verdict=VerdictOut.model_validate(verdict) if verdict else None,
        evidence=evidence,
        research_queries=[
            ResearchQueryOut(
                **ResearchQueryOut.model_validate(q).model_dump(exclude={"sources"}),
                sources=[
                    SourceOut.model_validate(source)
                    for source in db.scalars(select(Source).where(Source.query_id == q.id))
                ],
            )
            for q in db.scalars(
                select(ResearchQuery)
                .where(ResearchQuery.claim_id == claim.id)
                .order_by(ResearchQuery.created_at)
            )
        ],
    )


@app.get(prefix + "/analyses/{id}/claims", response_model=list[ClaimOut])
def claims(
    id: str,
    db: DB,
    classification: str | None = None,
    speaker: str | None = None,
    topic: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[ClaimOut]:
    get_analysis(db, id)
    query = select(Claim).join(TranscriptSegment).where(Claim.analysis_id == id)
    if classification:
        query = query.join(Verdict).where(Verdict.classification == classification)
    if speaker:
        query = query.where(
            func.coalesce(TranscriptSegment.manual_speaker_id, TranscriptSegment.speaker_id)
            == speaker
        )
    if topic:
        query = query.where(Claim.topic.ilike("%" + topic + "%"))
    return [
        claim_view(db, item)
        for item in db.scalars(
            query.order_by(TranscriptSegment.start_time, Claim.id).offset(offset).limit(limit)
        )
    ]


@app.get(prefix + "/claims/{id}", response_model=ClaimOut)
def claim(id: str, db: DB) -> ClaimOut:
    item = db.get(Claim, id)
    if not item:
        raise HTTPException(404, "Afirmação não encontrada")
    return claim_view(db, item)


def report_record(db: Session, id: str) -> Report:
    item = get_analysis(db, id)
    record = db.scalar(
        select(Report).where(Report.analysis_id == id, Report.revision == item.revision)
    )
    if not record:
        raise HTTPException(409, "Relatório ainda não gerado ou desatualizado; retome a análise")
    return record


@app.get(prefix + "/analyses/{id}/report", response_class=HTMLResponse)
def report_html(id: str, db: DB) -> HTMLResponse:
    return HTMLResponse(
        local_path(report_record(db, id).html_key).read_text(),
        headers={
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'"
        },
    )


@app.get(prefix + "/analyses/{id}/report.pdf")
def report_pdf(id: str, db: DB) -> FileResponse:
    record = report_record(db, id)
    if not record.pdf_key:
        raise HTTPException(409, "PDF indisponível; confira pré-requisitos e retome")
    return FileResponse(
        local_path(record.pdf_key), media_type="application/pdf", filename=f"verifact-{id}.pdf"
    )


@app.post(prefix + "/analyses/{id}/cancel", response_model=AnalysisOut)
def cancel(id: str, db: DB) -> Analysis:
    item = get_analysis(db, id)
    if item.status == Status.RUNNING:
        item.status = Status.CANCEL_REQUESTED
    elif item.status in (Status.QUEUED, Status.PAUSED, Status.FAILED):
        item.status = Status.CANCELLED
    db.commit()
    db.refresh(item)
    return item


@app.post(prefix + "/analyses/{id}/resume", response_model=AnalysisOut, status_code=202)
def resume(id: str, response: Response, db: DB) -> Analysis:
    item = get_analysis(db, id)
    if item.status in (Status.RUNNING, Status.CANCEL_REQUESTED):
        raise HTTPException(409, "Análise ativa; não é possível duplicar execução")
    item.status = Status.QUEUED
    item.error = item.error_code = None
    db.commit()
    db.refresh(item)
    enqueue(id)
    response.headers["Location"] = f"{prefix}/analyses/{id}/status"
    return item
