"""Bounded CONNECT proxy. Resolve once, reject non-public DNS, then pin the socket."""

import ipaddress
import os
import select
import socket
import socketserver
import time
from http.server import BaseHTTPRequestHandler
from threading import BoundedSemaphore
from urllib.parse import urlsplit

LIMIT = int(os.environ.get("DOWNLOAD_MAX_BYTES", "10737418240"))
TIMEOUT = int(os.environ.get("DOWNLOAD_TIMEOUT", "300"))
SLOTS = BoundedSemaphore(4)


def target(host: str, port: int) -> str:
    if port not in (80, 443):
        raise ValueError("Port rejected")
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError("Non-public destination rejected")
    return str(addresses[0][4][0])


class Proxy(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        # Do not log media URLs, tokens in signed URLs, or user content.
        pass

    def do_CONNECT(self) -> None:
        if not SLOTS.acquire(blocking=False):
            self.send_error(503)
            return
        try:
            parsed = urlsplit("https://" + self.path)
            if not parsed.hostname or parsed.username or parsed.password or parsed.path:
                raise ValueError("Invalid CONNECT target")
            port = parsed.port or 443
            address = target(parsed.hostname, port)
            with socket.create_connection((address, port), timeout=15) as remote:
                self.send_response(200, "Connection established")
                self.end_headers()
                started = time.monotonic()
                transferred = 0
                while time.monotonic() - started < TIMEOUT:
                    readable, _, _ = select.select([self.connection, remote], [], [], 1)
                    for source in readable:
                        data = source.recv(65536)
                        if not data:
                            return
                        transferred += len(data)
                        if transferred > LIMIT:
                            return
                        destination = remote if source is self.connection else self.connection
                        destination.sendall(data)
        except (ValueError, OSError):
            self.close_connection = True
        finally:
            SLOTS.release()
            self.close_connection = True

    def do_GET(self) -> None:
        # TLS-only origin traffic: prevents ambiguous absolute-form HTTP parsing.
        self.send_error(403, "HTTPS CONNECT required")


class Server(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    with Server(("0.0.0.0", 8888), Proxy) as server:
        server.serve_forever()
