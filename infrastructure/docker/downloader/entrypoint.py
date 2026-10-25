"""Public media download in an internal-only network; output stays in one mounted directory."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import yt_dlp

url = sys.argv[1]
output = Path("/output")
maximum = int(os.environ.get("DOWNLOAD_MAX_BYTES", "10737418240"))
options = {
    "proxy": "http://download-proxy:8888",
    "outtmpl": str(output / "download.%(ext)s"),
    "noplaylist": True,
    "format": "bestaudio/best",
    "max_filesize": maximum,
    "socket_timeout": 30,
    "retries": 2,
    "fragment_retries": 2,
    "concurrent_fragment_downloads": 1,
    "hls_prefer_native": True,
    "external_downloader": {"default": "native"},
    "quiet": True,
    "no_warnings": True,
    "cachedir": False,
    "skip_unavailable_fragments": False,
    "overwrites": False,
    "allowed_extractors": [
        "Youtube",
        "YoutubeTab",
        "TikTok",
        "TikTokVM",
        "Instagram",
        "InstagramStory",
    ],
}
# No cookies, credentials, DRM bypass or external executable downloaders.
with yt_dlp.YoutubeDL(options) as downloader:
    info = downloader.extract_info(url, download=True)
    if not info or info.get("_type") in ("playlist", "multi_video"):
        raise ValueError("Only a single public media item is supported")
    downloaded = Path(downloader.prepare_filename(info))
    if not downloaded.is_file() or downloaded.stat().st_size > maximum:
        raise ValueError("Download missing or oversized")
    original = output / "original.mp3"
    # Forced local demuxing protocols prevent ffmpeg from opening remote playlists.
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(downloaded),
            "-vn",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "3",
            str(original),
        ],
        check=True,
        timeout=int(os.environ.get("DOWNLOAD_TIMEOUT", "300")),
    )
    if original.stat().st_size > maximum:
        raise ValueError("Normalized media exceeds budget")
    with original.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    (output / "metadata.json").write_text(
        json.dumps(
            {
                "title": str(info.get("title", "Vídeo público"))[:255],
                "source_url": url,
                "sha256": digest,
            },
            ensure_ascii=False,
        )
    )
    downloaded.unlink()
