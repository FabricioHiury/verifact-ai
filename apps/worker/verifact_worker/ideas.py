"""Bounded original transcript passages; punctuation proposes, the LLM checks completion."""

import re
from dataclasses import dataclass

MAX_IDEA_CHARS = 4000


@dataclass(frozen=True)
class SpeechPart:
    id: str
    text: str
    start: float
    end: float
    speaker: str | None
    chunk: int


def passage(parts: list[SpeechPart]) -> str:
    return " ".join(part.text.strip() for part in parts)


def boundary(part: SpeechPart, following: SpeechPart | None) -> bool:
    pause = following is not None and following.start - part.end >= 1.5
    if not pause and not re.search(r"[.!?][\"'”’)]*$", part.text.strip()):
        return False
    # Carry qualifications/corrections forward instead of researching the preceding fragment.
    if following and re.match(
        r"^(mas\b|porém\b|no entanto\b|na verdade\b|ou seja\b|quer dizer\b|corrigindo\b|isto é\b)",
        following.text.strip(),
        re.IGNORECASE,
    ):
        return False
    return True


def claim_span(parts: list[SpeechPart], statement: str) -> tuple[str, str]:
    text = passage(parts)
    start = text.find(statement)
    if not statement or start < 0:
        raise ValueError("Afirmação gerada não corresponde à transcrição original")
    end = start + len(statement)
    cursor = 0
    matches = []
    for part in parts:
        stop = cursor + len(part.text.strip())
        if cursor < end and stop > start:
            matches.append(part)
        cursor = stop + 1
    if not matches:
        raise ValueError("Afirmação sem trecho de origem")
    if len({p.speaker for p in matches}) > 1:
        raise ValueError("Afirmação atravessa vozes distintas ou incertas; requer revisão humana")
    return matches[0].id, matches[-1].id
