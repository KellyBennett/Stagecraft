"""A reusable loopback alignment session. No arbitrary file endpoints."""
import io
import json
import socket
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .camera import solve
from .project import load, write_json


def align(project, timeout=900, open_browser=True, announce=None, paths=None):
    path, data = load(project)
    token = secrets.token_urlsafe(32)
    finished = False

    class DeadlineReader(socket.SocketIO):
        def readinto(self, buffer):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Alignment session expired")
            self._sock.settimeout(remaining)
            return super().readinto(buffer)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.rfile.close()
            # Recalculate before every receive so trickled bytes cannot renew
            # the session timeout while headers or a POST body are incomplete.
            self.rfile = io.BufferedReader(DeadlineReader(self.connection, "rb"))

        def log_message(self, *args):
            pass

        def respond(self, code, body, mime="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}" and urlsplit(self.path).path.startswith(f"/{token}/")

        def do_GET(self):
            if not self.authorized():
                return self.respond(404, b'{}')
            route = urlsplit(self.path).path.rsplit("/", 1)[-1]
            if route == "":
                return self.respond(200, (Path(__file__).parent / "web/index.html").read_bytes(), "text/html; charset=utf-8")
            if route == "image.png":
                return self.respond(200, (path / "image.png").read_bytes(), "image/png")
            if route == "state":
                current = paths.owned() if paths else load(path)[1]
                return self.respond(200, json.dumps({**current, **(paths.describe() if paths else {})}).encode())
            self.respond(404, b'{}')

        def do_POST(self):
            nonlocal finished
            route = urlsplit(self.path).path
            if not self.authorized() or route not in (f"/{token}/alignment", f"/{token}/finish"):
                return self.respond(404, b'{}')
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if self.headers.get("Origin") not in (None, expected_origin):
                return self.respond(403, b'{}')
            try:
                current = paths.owned() if paths else load(path)[1]
                if route.endswith('/finish'):
                    if not isinstance(current.get('alignment'), dict):
                        raise ValueError('Save an alignment before finishing')
                    finished = True
                    return self.respond(200, b'{"finished": true}')
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Invalid alignment size")
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError("Alignment must be an object")
                camera = solve(data["width"], data["height"], value)
                if paths:
                    paths.save_alignment(value)
                else:
                    write_json(path / "project.json", {**current, "alignment": value})
            except (OSError, ValueError, TypeError, KeyError) as exc:
                return self.respond(422, json.dumps({"error": str(exc)}).encode())
            self.respond(200, json.dumps({"saved": True, "lens_mm": camera["lens_mm"]}).encode())

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 0.25
    url = f"http://127.0.0.1:{server.server_port}/{token}/"
    try:
        if announce:
            announce({"status": "needs_human", "url": url, "timeout_seconds": timeout, **(paths.describe() if paths else {})})
        if open_browser:
            webbrowser.open(url)
        deadline = time.monotonic() + timeout
        while not finished and time.monotonic() < deadline:
            server.handle_request()
        if not finished:
            raise TimeoutError("Alignment timed out; run stagecraft align to resume")
    finally:
        server.server_close()
    return {"status": "aligned", "project": str(path)}
