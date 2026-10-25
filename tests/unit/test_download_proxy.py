"""Test proxy DNS policy without real network or Docker."""

import importlib.util
import socket
from pathlib import Path
from unittest.mock import patch

import pytest

spec = importlib.util.spec_from_file_location(
    "download_proxy", Path(__file__).parents[2] / "infrastructure/docker/downloader/proxy.py"
)
assert spec and spec.loader
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "192.168.1.1"]
)
def test_proxy_rejects_private_dns(address):
    with patch(
        "socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    ):
        with pytest.raises(ValueError):
            proxy.target("public.example", 443)


def test_proxy_pins_public_ip_and_rejects_unapproved_ports():
    with patch(
        "socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.1.1.1", 443))],
    ):
        assert proxy.target("public.example", 443) == "1.1.1.1"
    with pytest.raises(ValueError):
        proxy.target("public.example", 6379)
