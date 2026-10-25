"""Submit permitted local media to real services; does not fabricate or wait for results."""

import argparse
from pathlib import Path

import httpx
from verifact.config import settings

parser = argparse.ArgumentParser()
parser.add_argument("file", type=Path)
args = parser.parse_args()
config = settings()
mime = "video/mp4" if args.file.suffix.lower() == ".mp4" else "audio/mpeg"
with args.file.open("rb") as media, httpx.Client(timeout=60, trust_env=False) as client:
    response = client.post(
        f"http://{config.app_host}:{config.app_port}/api/v1/analyses/uploads",
        files={"file": (args.file.name, media, mime)},
    )
    response.raise_for_status()
    analysis = response.json()
    config.media_temp_dir.parent.mkdir(parents=True, exist_ok=True)
    Path("data/live-analysis-id").write_text(analysis["id"])
    print("Submitted:", analysis["id"], analysis["status"])
    print("Inspect with .venv/bin/python scripts/analysis_status.py", analysis["id"])
