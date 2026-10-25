"""Inspect downloader configuration without downloading or touching media."""

import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_youtube_runtime_is_local_and_downloads_remain_restricted(monkeypatch):
    class StopBeforeDownload(Exception):
        pass

    downloader = Mock(side_effect=StopBeforeDownload)
    monkeypatch.setitem(sys.modules, "yt_dlp", SimpleNamespace(YoutubeDL=downloader))
    monkeypatch.setattr(sys, "argv", ["entrypoint.py", "https://www.youtube.com/watch?v=test"])
    script = Path(__file__).parents[2] / "infrastructure/docker/downloader/entrypoint.py"
    with pytest.raises(StopBeforeDownload):
        runpy.run_path(str(script), run_name="__main__")
    options = downloader.call_args.args[0]
    assert options["js_runtimes"] == {"node": {"path": "/usr/local/bin/node"}}
    assert options["remote_components"] == set()
    assert options["proxy"] == "http://download-proxy:8888"
    assert options["noplaylist"] is True
    assert options["concurrent_fragment_downloads"] == 1
    assert options["external_downloader"] == {"default": "native"}
    assert "cookiefile" not in options
    assert "Youtube" in options["allowed_extractors"]
