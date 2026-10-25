"""One heavyweight model per subprocess; no HTTP server imports."""

import json
import os
import sys
from pathlib import Path
from typing import Any


def transcribe(path: str, model: str, provider: str, language: str) -> dict[str, Any]:
    if provider == "mlx":
        import mlx_whisper

        result = mlx_whisper.transcribe(
            path, path_or_hf_repo=model, language=language, word_timestamps=True, verbose=False
        )
        return {"segments": result["segments"], "model": model}
    from faster_whisper import WhisperModel

    engine = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=2, num_workers=1)
    segments, _ = engine.transcribe(path, language=language, word_timestamps=True)
    return {
        "model": model,
        "segments": [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "words": [{"start": w.start, "end": w.end, "word": w.word} for w in s.words or []],
            }
            for s in segments
        ],
    }


def diarize(path: str, model: str) -> dict[str, Any]:
    from pyannote.audio import Pipeline

    pipeline = Pipeline.from_pretrained(model, token=os.environ.get("HUGGINGFACE_TOKEN"))
    if pipeline is None:
        raise RuntimeError("Community-1 pipeline could not be loaded")
    result: Any = pipeline(path)
    annotation = result.exclusive_speaker_diarization
    return {
        "turns": [
            {"start": turn.start, "end": turn.end, "cluster": speaker}
            for turn, _, speaker in annotation.itertracks(yield_label=True)
        ]
    }


def main() -> None:
    request = json.loads(Path(sys.argv[1]).read_text())
    output = Path(sys.argv[2])
    if request["operation"] == "transcribe":
        result = transcribe(
            request["path"], request["model"], request["provider"], request["language"]
        )
    else:
        result = diarize(request["path"], request["model"])
    output.write_text(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
