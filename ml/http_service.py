"""Minimal HTTP boundary for the existing versioned incident evaluator."""

from __future__ import annotations

import json
import hmac
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import StringIO
from typing import Any, Callable

from ml.cli import ProtocolError, _read_request
from ml.engine import run_incident_evaluation


MAX_REQUEST_BYTES = 1_048_576
MAX_CONCURRENT_EVALUATIONS = 2


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, separators=(",", ":"), allow_nan=False).encode("utf-8")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8082,
    evaluate: Callable[..., dict[str, Any]] = run_incident_evaluation,
    token: str | None = None,
) -> ThreadingHTTPServer:
    """Build a server; evaluator injection keeps HTTP behavior testable."""
    if token is None:
        token = os.environ.get("AEGISCHAIN_EVALUATOR_TOKEN")
    if (
        not isinstance(token, str)
        or len(token.encode("utf-8")) < 32
        or "\r" in token
        or "\n" in token
    ):
        raise ValueError("AEGISCHAIN_EVALUATOR_TOKEN must be at least 32 UTF-8 bytes and contain no line breaks")
    expected_token = token.encode("utf-8")
    evaluation_slots = threading.BoundedSemaphore(MAX_CONCURRENT_EVALUATIONS)

    class Handler(BaseHTTPRequestHandler):
        server_version = "AegisChainEvaluator/1"
        sys_version = ""

        def log_message(self, _format: str, *_args: object) -> None:
            # Avoid writing request paths or payload metadata into application logs.
            return

        def _send_json(self, status: int, body: Any) -> None:
            encoded = _json_bytes(body)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def _unauthorized(self) -> None:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Bearer realm="AegisChain evaluator"')
            self.send_header("Content-Type", "application/json; charset=utf-8")
            body = _json_bytes({"error": {"code": "unauthorized", "message": "Valid bearer authentication is required"}})
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
            del explain
            safe_message = "Method not allowed" if code == 405 else "HTTP request failed"
            self._send_json(code, {"error": {"code": "http_error", "message": safe_message}})

        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._send_json(200, {"status": "ok"})
            elif self.path == "/readyz":
                self._send_json(200, {"status": "ready"})
            else:
                self._send_json(404, {"error": {"code": "not_found", "message": "Endpoint not found"}})

        def do_POST(self) -> None:
            if self.path != "/internal/v1/evaluate":
                self._send_json(404, {"error": {"code": "not_found", "message": "Endpoint not found"}})
                return

            authorization = self.headers.get("Authorization", "")
            scheme, separator, presented_token = authorization.partition(" ")
            if (
                not separator
                or scheme.lower() != "bearer"
                or not presented_token
                or not hmac.compare_digest(presented_token.encode("utf-8"), expected_token)
            ):
                self._unauthorized()
                return

            if not evaluation_slots.acquire(blocking=False):
                self._send_json(503, {"error": {"code": "busy", "message": "Evaluator is at capacity; retry later"}})
                return

            try:
                raw_length = self.headers.get("Content-Length")
                try:
                    content_length = int(raw_length) if raw_length is not None else -1
                except ValueError:
                    content_length = -1
                if content_length < 0:
                    self._send_json(400, {"error": {"code": "invalid_request", "message": "A valid Content-Length header is required"}})
                    return
                if content_length > MAX_REQUEST_BYTES:
                    self._send_json(413, {"error": {"code": "request_too_large", "message": "Request exceeds the 1 MiB limit"}})
                    return

                raw = self.rfile.read(content_length)
                try:
                    request = _read_request(StringIO(raw.decode("utf-8")))
                except (UnicodeDecodeError, ProtocolError) as exc:
                    self._send_json(400, {"error": {"code": "invalid_request", "message": str(exc)}})
                    return

                try:
                    response = evaluate(
                        request["feed_items"],
                        cargo_value=request["cargo_value"],
                        incident_id=request["incident_id"],
                    )
                except ValueError as exc:
                    self._send_json(422, {"error": {"code": "invalid_evaluation_input", "message": str(exc)}})
                    return
                except Exception:
                    self._send_json(500, {"error": {"code": "evaluation_failed", "message": "Incident evaluation failed"}})
                    return

                try:
                    encoded = _json_bytes(response)
                except (TypeError, ValueError):
                    self._send_json(500, {"error": {"code": "invalid_evaluator_output", "message": "Evaluator produced an invalid response"}})
                    return

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(encoded)
            finally:
                evaluation_slots.release()

        def do_OPTIONS(self) -> None:
            self._send_json(405, {"error": {"code": "method_not_allowed", "message": "Method not allowed"}})

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    default_host = "0.0.0.0" if "VCAP_APPLICATION" in os.environ else "127.0.0.1"
    host = os.environ.get("HOST", default_host)
    port = int(os.environ.get("PORT", "8082"))
    try:
        server = create_server(host, port)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
