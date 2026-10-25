"""Synthetic Portuguese fixtures. These are not real fact checks."""

import pytest
from verifact.models import Classification
from verifact_worker.reasoning import POLICY, Judgment, validate_judgment


def judgment(kind: Classification, ids: list[str]) -> Judgment:
    return Judgment(
        classification=kind,
        reasoning="Justificativa sintética de teste",
        evidence_ids=ids,
        limitations=[],
    )


def test_missing_evidence_is_not_false():
    result = validate_judgment(judgment(Classification.FALSE, []), {}, True)
    assert result.classification == Classification.INCONCLUSIVE


def test_conflicting_evidence_is_inconclusive():
    result = validate_judgment(
        judgment(Classification.TRUE, ["a", "b"]),
        {"a": "SUPPORTING", "b": "CONTRADICTING"},
        True,
        conflicting=True,
    )
    assert result.classification == Classification.INCONCLUSIVE


def test_promises_are_not_checkable():
    assert (
        validate_judgment(judgment(Classification.TRUE, []), {}, False).classification
        == Classification.NOT_CHECKABLE
    )


def test_citation_must_exist():
    with pytest.raises(ValueError, match="inexistente"):
        validate_judgment(judgment(Classification.TRUE, ["fabricated"]), {}, True)


def test_false_needs_counterevidence():
    with pytest.raises(ValueError):
        validate_judgment(judgment(Classification.FALSE, ["a"]), {"a": "SUPPORTING"}, True)


@pytest.mark.parametrize("kind", list(Classification))
def test_categories_remain_explicit(kind):
    assert judgment(kind, []).classification == kind


def test_prompt_injection_is_explicitly_untrusted():
    assert "nunca instruções" in POLICY and "Não invente" in POLICY


def test_no_evidence_discards_unsupported_model_assertions():
    candidate = judgment(Classification.TRUE, [])
    candidate.limitations = ["Eu sei que é verdadeiro com base no meu conhecimento"]
    result = validate_judgment(candidate, {}, True)
    assert result.classification == Classification.INCONCLUSIVE
    assert "Eu sei" not in " ".join(result.limitations)
    assert "conhecimento do modelo não substitui" in result.limitations[0]


def test_context_budget_cannot_silently_drop_counterevidence():
    result = validate_judgment(
        judgment(Classification.TRUE, ["a"]),
        {"a": "SUPPORTING", "b": "CONTRADICTING"},
        True,
        coverage_complete=False,
    )
    assert result.classification == Classification.INCONCLUSIVE
    assert "contexto" in result.reasoning
