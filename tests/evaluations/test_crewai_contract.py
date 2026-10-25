"""Real CrewAI execution over a mocked local HTTP transport; no real fact check."""

from unittest.mock import Mock, patch

import httpx
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from verifact.models import AgentExecution, Analysis
from verifact_worker.reasoning import ExtractedClaims, reason


def test_crewai_uses_only_local_structured_transport(database):
    analysis = Analysis(title="Synthetic CrewAI fixture")
    database.add(analysis)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    transport = Mock()
    transport.get.return_value = httpx.Response(
        200, json={"models": []}, request=httpx.Request("GET", "http://localhost:11434/api/ps")
    )
    transport.post.return_value = httpx.Response(
        200,
        json={
            "message": {"content": '{"claims":[]}'},
            "done_reason": "stop",
            "prompt_eval_count": 100,
            "eval_count": 10,
        },
        request=httpx.Request("POST", "http://localhost:11434/api/chat"),
    )
    client = Mock()
    client.__enter__ = Mock(return_value=transport)
    client.__exit__ = Mock(return_value=False)
    with (
        patch("verifact_worker.reasoning.factory", return_value=maker),
        patch("verifact_worker.reasoning.httpx.Client", return_value=client) as constructor,
    ):
        result, model = reason(
            analysis.id,
            "ClaimExtractorAgent",
            "Extraia afirmações factuais; sem afirmação retorne lista vazia",
            {"text": "Bom dia."},
            ExtractedClaims,
        )
    assert result.claims == []
    assert constructor.call_args.kwargs["base_url"] == "http://localhost:11434"
    payload = transport.post.call_args.kwargs["json"]
    assert payload["format"] == ExtractedClaims.model_json_schema()
    assert payload["keep_alive"] == 0
    assert payload["think"] is False
    assert payload["options"]["num_ctx"] == 4096
    execution = database.scalar(select(AgentExecution))
    assert execution.outcome == "SCHEMA_VALIDATED"
    assert execution.model == model


def test_fallback_attempts_are_counted_and_auditable(database, monkeypatch):
    from verifact.config import settings
    from verifact_worker.reasoning import LocalOllama

    analysis = Analysis(title="Synthetic fallback fixture")
    database.add(analysis)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    transport = Mock()
    request = httpx.Request("POST", "http://localhost:11434/api/chat")
    transport.get.return_value = httpx.Response(200, json={"models": []}, request=request)
    transport.post.side_effect = [
        httpx.Response(500, json={"error": "synthetic OOM"}, request=request),
        httpx.Response(200, json={"message": {"content": '{"claims":[]}'}}, request=request),
    ]
    client = Mock()
    client.__enter__ = Mock(return_value=transport)
    client.__exit__ = Mock(return_value=False)
    with (
        patch("verifact_worker.reasoning.factory", return_value=maker),
        patch("verifact_worker.reasoning.httpx.Client", return_value=client),
    ):
        result = LocalOllama(
            ExtractedClaims.model_json_schema(), analysis.id, "ClaimExtractorAgent"
        ).call("synthetic")
    assert result == '{"claims":[]}'
    executions = list(database.scalars(select(AgentExecution).order_by(AgentExecution.created_at)))
    assert len(executions) == 2
    assert [e.model for e in executions] == [
        settings().ollama_model,
        settings().ollama_fallback_model,
    ]
    assert executions[0].outcome == "FAILED"


def test_cancelled_analysis_cannot_start_another_inference(database):
    import pytest
    from verifact.models import AnalysisCancelled, Status
    from verifact_worker.reasoning import LocalOllama

    analysis = Analysis(title="Synthetic cancelled inference", status=Status.CANCEL_REQUESTED)
    database.add(analysis)
    database.commit()
    maker = sessionmaker(database.get_bind(), expire_on_commit=False)
    with (
        patch("verifact_worker.reasoning.factory", return_value=maker),
        patch("verifact_worker.reasoning.httpx.Client") as transport,
    ):
        with pytest.raises(AnalysisCancelled):
            LocalOllama(
                ExtractedClaims.model_json_schema(), analysis.id, "ClaimExtractorAgent"
            ).call("synthetic")
        transport.assert_not_called()
    assert database.scalar(select(AgentExecution)) is None
