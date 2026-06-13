"""Minimal SARApp incident server foundation used by the desktop fallback."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

from core.networking.server_info import DEFAULT_LOCAL_SERVER_NAME, HEALTH_PATH, SARAPP_SERVICE_ID


class SARAppServerManager:
    """Owns the local HTTP server and its identity."""

    def __init__(self, host: str, port: int, name: str = DEFAULT_LOCAL_SERVER_NAME):
        self.host = host
        self.port = int(port)
        self.name = name
        self._httpd: Optional[ThreadingHTTPServer] = None

    def health_payload(self) -> dict:
        return {
            "status": "ok",
            "service": SARAPP_SERVICE_ID,
            "name": self.name,
        }

    def make_handler(self):
        manager = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - stdlib handler API
                if self.path.split("?", 1)[0] == HEALTH_PATH:
                    body = json.dumps(manager.health_payload()).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

            def log_message(self, format, *args):  # noqa: A002,N802 - stdlib signature
                # Keep the built-in server quiet when launched from the desktop GUI.
                return

        return Handler

    def serve_forever(self) -> None:
        self._httpd = ThreadingHTTPServer((self.host, self.port), self.make_handler())
        self._httpd.serve_forever()

    def shutdown(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
