"""Loopback-only URL bridge, authenticated per browser foreground window."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from urllib.parse import urlparse

from pawz import APP_ID
from pawz.core.models import BROWSER_PROCESSES

TOKEN_HEADER = f"X-{APP_ID}-Token"


class BrowserBridge:
    def __init__(self, token: str, port: int):
        self.token, self.port = token, port
        self._lock = Lock()
        # The extension pushes on every tab/focus change, so the last URL stays
        # valid until replaced; a time-based expiry dropped site profiles on
        # idle pages (Chromium clamps extension alarms to >= 30 s).
        self._url_by_process: dict[str, str] = {}
        self._server = None

    def domain(self, process: str) -> str:
        with self._lock:
            url = self._url_by_process.get(process, "")
        return (urlparse(url).hostname or "").lower()

    def start(self) -> None:
        bridge = self
        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", f"Content-Type, {TOKEN_HEADER}")
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.end_headers()
            def do_POST(self):
                if self.path != "/active" or self.headers.get(TOKEN_HEADER) != bridge.token:
                    self.send_error(403); return
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 4096:
                    self.send_error(413); return
                try:
                    obj = json.loads(self.rfile.read(size))
                    proc, url = obj["process"], obj["url"]
                    if proc not in BROWSER_PROCESSES or not isinstance(url, str) or (
                            url and not url.startswith(("http://", "https://"))):
                        raise ValueError("Invalid payload")
                    with bridge._lock:
                        bridge._url_by_process[proc] = url
                except (ValueError, KeyError, TypeError):
                    self.send_error(400); return
                self.send_response(204); self.end_headers()
            def log_message(self, *_): pass
        self._server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        Thread(target=self._server.serve_forever, daemon=True).start()

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
