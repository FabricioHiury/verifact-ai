from collections.abc import Iterator
from pathlib import Path
from typing import Any, NoReturn

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from verifact.config import settings
from verifact.db import factory
from verifact.models import (
    Analysis,
    Claim,
    Evidence,
    MediaAsset,
    Report,
    ResearchQuery,
    Source,
    Speaker,
    TranscriptSegment,
    Verdict,
)
from verifact.storage import check_disk, publish

from verifact_worker.reasoning import Summary, reason


def deny_resource(url: str, **kwargs: object) -> NoReturn:
    raise ValueError("External/local resources are disabled for report rendering")


def generate(analysis_id: str) -> None:
    cfg = settings()
    with factory()() as db:
        analysis = db.get(Analysis, analysis_id)
        assert analysis
        revision = analysis.revision
        existing = db.scalar(
            select(Report).where(Report.analysis_id == analysis_id, Report.revision == revision)
        )
        if existing and (existing.pdf_key or not cfg.pdf_enabled):
            return
        counts = list(
            db.execute(
                select(Verdict.classification)
                .join(Claim, Claim.id == Verdict.claim_id)
                .where(Claim.analysis_id == analysis_id)
            )
        )
    summary, _ = reason(
        analysis_id,
        "ReportWriterAgent",
        "Escreva uma introdução metodológica em português brasileiro. Apenas explique que as afirmações foram avaliadas individualmente, evidências precisam de revisão e não há ranking ou certeza garantida. Não invente fatos",
        {"claims_assessed": len(counts)},
        Summary,
    )
    cfg.report_output_dir.mkdir(parents=True, exist_ok=True)
    html_path = cfg.report_output_dir / f"{analysis_id}-{revision}.html"
    pdf_path = cfg.report_output_dir / f"{analysis_id}-{revision}.pdf"
    environment = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    with factory()() as db:
        analysis = db.get(Analysis, analysis_id)
        media = db.scalar(select(MediaAsset).where(MediaAsset.analysis_id == analysis_id))
        speakers = list(db.scalars(select(Speaker).where(Speaker.analysis_id == analysis_id)))

        def entries() -> Iterator[dict[str, Any]]:
            for claim in db.scalars(
                select(Claim)
                .where(Claim.analysis_id == analysis_id)
                .order_by(Claim.created_at)
                .execution_options(yield_per=20)
            ):
                segment = db.get(TranscriptSegment, claim.segment_id)
                verdict = db.scalar(select(Verdict).where(Verdict.claim_id == claim.id))
                evidence = list(
                    db.execute(
                        select(Evidence, Source).join(Source).where(Evidence.claim_id == claim.id)
                    )
                )
                sources = list(
                    db.scalars(
                        select(Source).join(ResearchQuery).where(ResearchQuery.claim_id == claim.id)
                    )
                )
                yield {
                    "claim": claim,
                    "segment": segment,
                    "verdict": verdict,
                    "evidence": evidence,
                    "sources": sources,
                }

        check_disk()
        environment.get_template("report.html").stream(
            analysis=analysis,
            media=media,
            speakers=speakers,
            entries=entries(),
            summary=summary.summary,
        ).dump(str(html_path), encoding="utf-8")
    html_key = f"{analysis_id}/report-{revision}.html"
    publish(html_path, html_key)
    pdf_key = None
    if cfg.pdf_enabled:
        try:
            from weasyprint import HTML

            HTML(filename=str(html_path), url_fetcher=deny_resource).write_pdf(str(pdf_path))
            pdf_key = f"{analysis_id}/report-{revision}.pdf"
            publish(pdf_path, pdf_key)
        except (ImportError, OSError):
            with factory()() as db:
                analysis = db.get(Analysis, analysis_id)
                assert analysis
                analysis.limitations = [
                    *analysis.limitations,
                    "PDF indisponível: instale dependências nativas do WeasyPrint e retome",
                ]
                db.commit()
    with factory()() as db:
        record = db.scalar(
            select(Report).where(Report.analysis_id == analysis_id, Report.revision == revision)
        )
        if record:
            record.html_key, record.pdf_key, record.summary = html_key, pdf_key, summary.summary
        else:
            db.add(
                Report(
                    analysis_id=analysis_id,
                    revision=revision,
                    html_key=html_key,
                    pdf_key=pdf_key,
                    summary=summary.summary,
                )
            )
        db.commit()
