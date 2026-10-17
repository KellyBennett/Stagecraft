"""A single-use loopback alignment session. No arbitrary file endpoints."""
import json
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .camera import solve
from .project import load, write_json


def align(project, timeout=900, open_browser=True, announce=None):
    path, data = load(project)
    token = secrets.token_urlsafe(32)
    finished = False

    class Handler(BaseHTTPRequestHandler):
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
                return self.respond(200, json.dumps(data).encode())
            self.respond(404, b'{}')

        def do_POST(self):
            nonlocal finished
            if not self.authorized() or urlsplit(self.path).path != f"/{token}/alignment":
                return self.respond(404, b'{}')
            expected_origin = f"http://127.0.0.1:{self.server.server_port}"
            if self.headers.get("Origin") not in (None, expected_origin):
                return self.respond(403, b'{}')
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Invalid alignment size")
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict):
                    raise ValueError("Alignment must be an object")
                camera = solve(data["width"], data["height"], value)
                write_json(path / "project.json", {**data, "alignment": value})
            except (ValueError, TypeError, KeyError) as exc:
                return self.respond(422, json.dumps({"error": str(exc)}).encode())
            self.respond(200, json.dumps({"saved": True, "lens_mm": camera["lens_mm"]}).encode())
            finished = True

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 0.25
    url = f"http://127.0.0.1:{server.server_port}/{token}/"
    try:
        if announce:
            announce({"status": "needs_human", "url": url, "timeout_seconds": timeout})
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
