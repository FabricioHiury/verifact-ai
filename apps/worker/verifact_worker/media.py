import json
import math
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class PrerequisiteError(RuntimeError):
    pass


def signature(path: Path, suffix: str) -> str:
    with path.open("rb") as stream:
        head = stream.read(4096)
    if suffix == ".mp3" and (
        head.startswith(b"ID3")
        or any(head[i] == 255 and head[i + 1] & 224 == 224 for i in range(max(0, len(head) - 1)))
    ):
        return "audio/mpeg"
    if suffix == ".mp4" and len(head) > 12 and head[4:8] == b"ftyp":
        return "video/mp4"
    raise ValueError("Assinatura MP3/MP4 inválida")


def probe(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    data: dict[str, Any] = json.loads(result.stdout)
    formats = set(str(data["format"].get("format_name", "")).split(","))
    expected = "mp3" if path.suffix.lower() == ".mp3" else "mp4"
    if expected not in formats:
        raise ValueError("Formato real não corresponde a MP3/MP4 permitido")
    duration = float(data["format"]["duration"])
    if (
        not math.isfinite(duration)
        or duration <= 0
        or not any(s["codec_type"] == "audio" for s in data["streams"])
    ):
        raise ValueError("Mídia precisa de áudio e duração válida")
    return data


def chunks(duration: float, seconds: int, overlap: int) -> Iterator[tuple[int, float, float]]:
    if not math.isfinite(duration) or duration <= 0 or not 0 <= overlap < seconds:
        raise ValueError("Invalid chunk parameters")
    index = 0
    start = 0.0
    while start < duration:
        end = min(duration, start + seconds)
        yield index, start, end
        if end >= duration:
            break
        index += 1
        start += seconds - overlap


def aligned_segments(
    segments: list[dict[str, Any]], offset: float, end: float, owned_start: float, owned_end: float
) -> list[dict[str, Any]]:
    output = []
    for segment in segments:
        words = segment.get("words") or []
        if words:
            selected = [
                w
                for w in words
                if owned_start <= offset + (float(w["start"]) + float(w["end"])) / 2 < owned_end
            ]
            if not selected:
                continue
            text = "".join(str(w["word"]) for w in selected).strip()
            start_time = max(0, offset + float(selected[0]["start"]))
            end_time = min(end, offset + float(selected[-1]["end"]))
            words_out = [
                {**w, "start": offset + float(w["start"]), "end": offset + float(w["end"])}
                for w in selected
            ]
        else:
            start_time = max(0, offset + float(segment["start"]))
            end_time = min(end, offset + float(segment["end"]))
            if not owned_start <= (start_time + end_time) / 2 < owned_end:
                continue
            text = str(segment["text"]).strip()
            words_out = []
        if text and end_time >= start_time:
            output.append(
                {"start_time": start_time, "end_time": end_time, "text": text, "words": words_out}
            )
    return output
