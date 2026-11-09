"""A real HTTP server on 127.0.0.1 that plays the auth service's JWKS endpoint.

A socket rather than a stub, so the tests cover what PyJWKClient actually
does on the wire (timeouts, status codes, bodies), not what we assume.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


class JwksServer:
    def __init__(self) -> None:
        self.status = 200
        self.body: bytes = b'{"keys": []}'
        self.requests: list[dict[str, str]] = []
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def do_GET(self) -> None:  # noqa: N802 - the stdlib's naming
                server.requests.append(dict(self.headers))
                self.send_response(server.status)
                self.send_header("Content-Type", "application/jwk-set+json")
                self.send_header("Content-Length", str(len(server.body)))
                self.end_headers()
                self.wfile.write(server.body)

            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                pass

        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self._httpd.server_port}/.well-known/jwks.json"

    def serve(self, *keys: dict[str, str]) -> None:
        self.status = 200
        self.body = json.dumps({"keys": list(keys)}).encode()

    def run(self) -> Iterator[JwksServer]:
        # A short poll interval, so shutdown() returns in milliseconds, not 0.5 s.
        thread = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
        )
        thread.start()
        try:
            yield self
        finally:
            self._httpd.shutdown()
            self._httpd.server_close()

    def stop(self) -> None:
        """The auth service goes down: connections are refused from now on."""
        self._httpd.shutdown()
        self._httpd.server_close()
