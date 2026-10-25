import socket
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from verifact.config import Settings
from verifact.security import UnsafeURL, public_target, social_provider
from verifact.storage import local_path
from verifact_worker.media import aligned_segments, chunks, signature


def test_config_resource_limits():
    for kwargs in (
        {"max_concurrent_analyses": 2},
        {"search_max_concurrent_requests": 3},
        {"ollama_base_url": "https://hosted.example"},
        {"crewai_sequential_execution": False},
        {"whisper_chunk_overlap_seconds": 180},
    ):
        with pytest.raises(ValidationError):
            Settings(**kwargs)


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "::1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "0.0.0.0"]
)
def test_ssrf_private_dns(address):
    with patch(
        "socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    ):
        with pytest.raises(UnsafeURL):
            public_target("https://public.example/source")


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:pass@example.com",
        "https://example.com:9999",
        "http://youtube.com/watch?v=1",
        "https://youtube.com.evil.test/",
    ],
)
def test_unsafe_social(url):
    with pytest.raises(UnsafeURL):
        social_provider(url)


def test_supported_social():
    assert social_provider("https://youtu.be/abc") == "youtube"
    assert social_provider("https://www.tiktok.com/@public/video/1") == "tiktok"
    assert social_provider("https://www.instagram.com/reel/a/") == "instagram"


def test_no_path_traversal():
    with pytest.raises(ValueError):
        local_path("../../.env")


def test_no_duration_cap():
    spans = list(chunks(3601, 180, 5))
    assert spans[-1][2] == 3601
    assert all(b - a <= 180 for _, a, b in spans)
    assert spans[1][1] == 175
    assert list(chunks(180, 180, 5)) == [(0, 0, 180)]


def test_overlap_word_ownership_preserves_repeated_speech():
    data = [
        {
            "start": 0,
            "end": 5,
            "text": "sim sim",
            "words": [
                {"start": 1, "end": 2, "word": " sim"},
                {"start": 3, "end": 4, "word": " sim"},
            ],
        }
    ]
    left = aligned_segments(data, 175, 180, 175, 177.5)
    right = aligned_segments(data, 175, 180, 177.5, 180)
    assert left[0]["text"] == "sim" and right[0]["text"] == "sim"
    assert right[0]["start_time"] == 178


def test_signature_rejects_disguised_html(tmp_path: Path):
    path = tmp_path / "fake.mp4"
    path.write_text("<html>not media</html>")
    with pytest.raises(ValueError):
        signature(path, ".mp4")


def test_ffprobe_format_must_match_allowed_container(tmp_path):
    from unittest.mock import Mock

    from verifact_worker.media import probe

    path = tmp_path / "disguised.mp3"
    response = Mock(
        stdout='{"format":{"duration":"3","format_name":"matroska,webm"},"streams":[{"codec_type":"audio"}]}'
    )
    with patch("verifact_worker.media.subprocess.run", return_value=response):
        with pytest.raises(ValueError, match="Formato real"):
            probe(path)


def test_trickling_response_cannot_extend_deadline_forever():
    from unittest.mock import Mock

    from verifact.security import fetch_public

    clock = [0.0]
    response = Mock(status=200)
    response.getheader.side_effect = lambda key, default=None: {
        "Content-Encoding": "identity",
        "Content-Type": "text/plain",
    }.get(key, default)

    def trickle(size):
        clock[0] += 2
        return b"x"

    response.read1.side_effect = trickle
    connection = Mock()
    connection.getresponse.return_value = response
    with (
        patch("verifact.security.public_target", return_value=("example.org", 443, "1.1.1.1")),
        patch("verifact.security.PinnedHTTPS", return_value=connection),
        patch("verifact.security.time.monotonic", side_effect=lambda: clock[0]),
    ):
        with pytest.raises(TimeoutError):
            fetch_public("https://example.org", timeout=1)
    connection.close.assert_called_once()
