import http.client
import ipaddress
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit


class UnsafeURL(ValueError):
    pass


def public_target(url: str) -> tuple[str, int, str]:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise UnsafeURL("URL pública HTTP(S) sem credenciais necessária")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port != (443 if parsed.scheme == "https" else 80):
        raise UnsafeURL("Porta remota não permitida")
    addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise UnsafeURL("Destino sem endereço")
    for address in addresses:
        if not ipaddress.ip_address(address[4][0]).is_global:
            raise UnsafeURL("Destino interno ou reservado não permitido")
    return parsed.hostname, port, str(addresses[0][4][0])


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, port: int, timeout: float):
        super().__init__(hostname, port, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        # Pin the validated address while keeping TLS hostname verification and SNI.
        raw = socket.create_connection((self.address, self.port), self.timeout)
        self.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=self.host)


@dataclass
class Document:
    url: str
    content: bytes
    content_type: str


def fetch_public(url: str, *, timeout: int = 30, max_bytes: int = 2_000_000) -> Document:
    deadline = time.monotonic() + timeout
    for _ in range(6):
        host, port, address = public_target(url)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Tempo total de recuperação excedido")
        parsed = urlsplit(url)
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = PinnedHTTPS(host, address, port, remaining)
        else:
            connection = http.client.HTTPConnection(address, port, timeout=remaining)
        try:
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            connection.request(
                "GET",
                path,
                headers={
                    "Host": host,
                    "User-Agent": "VerifactAI/0.1 (local research)",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise UnsafeURL("Redirecionamento sem destino")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise OSError(f"Fonte indisponível: HTTP {response.status}")
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise ValueError("Conteúdo comprimido não suportado")
            chunks = []
            size = 0
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Tempo total de recuperação excedido")
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                block = response.read1(min(65536, max_bytes - size + 1))
                if not block:
                    break
                chunks.append(block)
                size += len(block)
                if size > max_bytes:
                    raise ValueError("Documento excede orçamento de bytes")
            return Document(url, b"".join(chunks), response.getheader("Content-Type", ""))
        finally:
            connection.close()
    raise UnsafeURL("Redirecionamentos em excesso")


def social_provider(url: str) -> str:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
    ):
        raise UnsafeURL("Use URL pública HTTPS")
    for provider, domains in {
        "youtube": ("youtube.com", "youtu.be"),
        "tiktok": ("tiktok.com",),
        "instagram": ("instagram.com",),
    }.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return provider
    raise UnsafeURL("Plataforma não suportada")
