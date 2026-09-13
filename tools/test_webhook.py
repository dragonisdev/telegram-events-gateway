"""Tiny local HTTP endpoint for manually exercising the gateway."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/events":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_error(400, "Expected a JSON request body")
            return

        print(json.dumps(body, indent=2, ensure_ascii=False), flush=True)
        self.send_response(204)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


if __name__ == "__main__":
    address = ("127.0.0.1", 8787)
    print(f"Listening for POST requests at http://{address[0]}:{address[1]}/events")
    server = ThreadingHTTPServer(address, WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped local webhook receiver")
    finally:
        server.server_close()
