"""Synthetic Portuguese speech, never evidence for real fact checks."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from verifact.models import (
    Analysis,
    Claim,
    ProcessingCheckpoint,
    Status,
    TranscriptSegment,
    Verdict,
)
from verifact_worker.ideas import MAX_IDEA_CHARS, SpeechPart, boundary, claim_span
from verifact_worker.pipeline import Pipeline
from verifact_worker.reasoning import ExtractedClaim, IdeaClaims


def part(text, identifier="a", speaker=None):
    return SpeechPart(identifier, text, 0, 1, speaker, 0)


def test_punctuation_is_candidate_and_corrections_are_kept_together():
    assert not boundary(part("O total foi"), part("vinte."))
    assert not boundary(part("O total foi vinte."), part("Na verdade, foram dez."))
    assert boundary(part("O total foi vinte."), part("Outra questão."))
    assert boundary(part("O total foi vinte"), SpeechPart("b", "Outra questão", 3, 4, None, 0))
    assert not boundary(
        part("O total foi vinte"), SpeechPart("b", "Mas há uma ressalva", 3, 4, None, 0)
    )


def test_original_quote_can_span_segments_but_not_distinct_speakers():
    pieces = [part("O Brasil tem", "a"), part("26 estados.", "b")]
    assert claim_span(pieces, "O Brasil tem 26 estados.") == ("a", "b")
    with pytest.raises(ValueError):
        claim_span(pieces, "O Brasil tem 27 estados.")
    with pytest.raises(ValueError):
        claim_span(
            [part("O Brasil tem", "a", "s1"), part("26 estados.", "b", "s2")],
            "O Brasil tem 26 estados.",
        )


def test_chunk_local_labels_do_not_discard_the_pending_idea(database):
    item, maker = setup_flow(database)
    with (
        patch("verifact_worker.pipeline.factory", return_value=maker),
        patch(
            "verifact_worker.pipeline.reason",
            return_value=(IdeaClaims(complete=True, claims=[]), "synthetic"),
        ) as llm,
    ):
        flow = Pipeline(item.id, 0)
        flow.extract_passages(
            iter(
                [
                    SpeechPart("a", "O Brasil tem", 0, 1, "chunk-0:voice-0", 0),
                    SpeechPart("b", "26 estados.", 1, 2, "chunk-1:voice-0", 1),
                ]
            ),
            final=True,
        )
        assert llm.call_count == 1
        assert llm.call_args.args[3]["transcript"] == "O Brasil tem 26 estados."


def setup_flow(database):
    item = Analysis(title="Synthetic ideas", status=Status.RUNNING)
    database.add(item)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    return item, maker


def test_incomplete_idea_waits_and_preserves_quote_context_and_resume(database, client):
    item, maker = setup_flow(database)
    first = TranscriptSegment(
        analysis_id=item.id,
        chunk=0,
        ordinal=0,
        start_time=0,
        end_time=3,
        text="O Brasil tem",
        model="synthetic",
    )
    database.add(first)
    database.commit()
    response = IdeaClaims(
        complete=True,
        claims=[
            ExtractedClaim(statement="O Brasil tem 26 estados.", topic="Geografia", checkable=True)
        ],
    )
    with (
        patch("verifact_worker.pipeline.factory", return_value=maker),
        patch("verifact_worker.pipeline.reason", return_value=(response, "synthetic")) as llm,
    ):
        flow = Pipeline(item.id, 0)
        flow.extract(final=False)
        llm.assert_not_called()
        flow = Pipeline(item.id, 0)
        second = TranscriptSegment(
            analysis_id=item.id,
            chunk=1,
            ordinal=0,
            start_time=3,
            end_time=5,
            text="26 estados.",
            model="synthetic",
        )
        database.add(second)
        database.commit()
        flow.extract(final=True)
        claim = database.scalar(select(Claim))
        assert claim is not None
        assert claim.segment_id == first.id and claim.end_segment_id == second.id
        assert claim.transcript_context == "O Brasil tem 26 estados."
        flow.extract(final=True)
        assert llm.call_count == 1
        assert len(list(database.scalars(select(ProcessingCheckpoint)))) == 1
    data = client.get(f"/api/v1/claims/{claim.id}").json()
    assert data["start_time"] == 0 and data["end_time"] == 5
    assert data["transcript_context"] == claim.transcript_context
    assert client.get(f"/api/v1/analyses/{item.id}/claims").status_code == 200


def test_semantic_rejection_waits_for_continuation_and_never_researches_fragment(database):
    item, maker = setup_flow(database)
    responses = [
        (IdeaClaims(complete=False, claims=[]), "synthetic"),
        (IdeaClaims(complete=True, claims=[]), "synthetic"),
    ]
    with (
        patch("verifact_worker.pipeline.factory", return_value=maker),
        patch("verifact_worker.pipeline.reason", side_effect=responses) as llm,
    ):
        flow = Pipeline(item.id, 0)
        flow.extract_passages(
            iter(
                [
                    part("Se compararmos os períodos.", "a"),
                    part("O resultado ainda não foi apresentado.", "b"),
                ]
            ),
            final=True,
        )
        assert llm.call_count == 2
        assert llm.call_args.args[3]["transcript"] == (
            "Se compararmos os períodos. O resultado ainda não foi apresentado."
        )
        assert database.scalar(select(Claim)) is None


@pytest.mark.parametrize("text", ["Fala ainda não concluída", "x" * (MAX_IDEA_CHARS + 1)])
def test_unfinished_or_oversized_idea_is_not_turned_into_claims(database, text):
    item, maker = setup_flow(database)
    with (
        patch("verifact_worker.pipeline.factory", return_value=maker),
        patch(
            "verifact_worker.pipeline.reason",
            return_value=(IdeaClaims(complete=False, claims=[]), "synthetic"),
        ) as llm,
    ):
        flow = Pipeline(item.id, 0)
        flow.extract_passages(iter([part(text)]), final=True)
        if len(text) > MAX_IDEA_CHARS:
            llm.assert_not_called()
    database.expire_all()
    assert database.get(Analysis, item.id).limitations
    assert database.scalar(select(Claim)) is None


def test_media_batches_alternate_models_and_verify_before_next_chunk(database):
    item, maker = setup_flow(database)
    with patch("verifact_worker.pipeline.factory", return_value=maker):
        flow = Pipeline(item.id, 0)
        flow.state.duration = 200
        order = []

        def transcribe():
            order.append("transcribe-0")
            yield 0
            order.append("transcribe-1")
            yield 1

        flow.transcribe = transcribe
        flow.diarize = Mock(side_effect=lambda **kw: order.append("diarize"))
        flow.extract = Mock(side_effect=lambda **kw: order.append("extract"))
        flow.verify = Mock(side_effect=lambda: order.append("verify"))
        flow.process_media()
        assert order == [
            "transcribe-0",
            "diarize",
            "extract",
            "verify",
            "transcribe-1",
            "diarize",
            "extract",
            "verify",
        ]
        assert flow.extract.call_args_list[0].kwargs == {"final": False}
        assert flow.extract.call_args_list[1].kwargs == {"final": True}


def test_opinion_has_no_fabricated_search_or_llm_citations(database):
    item, maker = setup_flow(database)
    segment = TranscriptSegment(
        analysis_id=item.id,
        chunk=0,
        ordinal=0,
        start_time=0,
        end_time=2,
        text="Eu prefiro este plano.",
        model="synthetic",
    )
    database.add(segment)
    database.flush()
    database.add(
        Claim(analysis_id=item.id, segment_id=segment.id, statement=segment.text, checkable=False)
    )
    database.commit()
    with (
        patch("verifact_worker.pipeline.factory", return_value=maker),
        patch("verifact_worker.pipeline.reason") as llm,
        patch("verifact_worker.pipeline.search") as search,
    ):
        Pipeline(item.id, 0).verify()
        llm.assert_not_called()
        search.assert_not_called()
    verdict = database.scalar(select(Verdict))
    assert verdict.classification == "NOT_CHECKABLE"
    assert verdict.evidence_ids == []
    assert verdict.model == "deterministic:not-checkable-v1"


def test_nonliteral_evidence_is_rejected_without_losing_the_analysis(database):
    from verifact.models import Evidence, ResearchQuery, Source
    from verifact_worker.reasoning import Context, EvidenceAssessment, Queries
    from verifact_worker.research import Retrieved

    item, maker = setup_flow(database)
    segment = TranscriptSegment(
        analysis_id=item.id,
        chunk=0,
        ordinal=0,
        start_time=0,
        end_time=2,
        text="O valor foi dez.",
        model="synthetic",
    )
    database.add(segment)
    database.flush()
    database.add(
        Claim(
            analysis_id=item.id,
            segment_id=segment.id,
            statement=segment.text,
            checkable=True,
            transcript_context=segment.text,
        )
    )
    database.commit()
    document = Retrieved(
        "https://example.org/synthetic",
        "Synthetic fixture",
        "example.org",
        None,
        "SECONDARY_OR_UNKNOWN",
        "0" * 64,
        "Documento sintético sem a frase que o modelo inventou.",
    )

    def answer(analysis_id, agent, instruction, data, schema):
        if agent == "ContextAnalystAgent":
            return Context(context="Contexto sintético"), "synthetic"
        if agent == "ResearchPlannerAgent":
            return Queries(
                primary_source="valor dez", falsifying="valor diferente", confirming="contagem dez"
            ), "synthetic"
        assert agent == "EvidenceResearcherAgent"
        return EvidenceAssessment(
            excerpt="Frase inventada que não existe.",
            stance="SUPPORTING",
            assessment="Synthetic invalid quote",
        ), "synthetic"

    with (
        patch("verifact_worker.pipeline.factory", return_value=maker),
        patch("verifact_worker.pipeline.reason", side_effect=answer),
        patch("verifact_worker.pipeline.search", return_value=[document.url]),
        patch("verifact_worker.pipeline.retrieve_results", return_value=[document]),
    ):
        Pipeline(item.id, 0).verify()
    verdict = database.scalar(select(Verdict))
    assert verdict.classification == "INCONCLUSIVE"
    assert verdict.evidence_ids == []
    assert verdict.model == "deterministic:insufficient-evidence-v1"
    assert database.scalar(select(Evidence)) is None
    assert database.scalar(select(Source)) is not None
    assert all("não é literal" in q.outcome for q in database.scalars(select(ResearchQuery)))
