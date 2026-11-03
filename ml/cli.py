"""Versioned JSON stdin/stdout protocol for the incident evaluator."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from typing import Any, TextIO

from ml.engine import run_incident_evaluation


_REQUIRED_FIELDS = {"schemaVersion", "feed_items", "cargo_value", "incident_id"}


class ProtocolError(ValueError):
    """Raised when stdin does not contain a supported protocol request."""


def _reject_nonstandard_constant(value: str) -> None:
    raise ProtocolError(f"invalid JSON constant: {value}")


def _read_request(stdin: TextIO) -> dict[str, Any]:
    raw_request = stdin.read()
    if not raw_request.strip():
        raise ProtocolError("stdin must contain a JSON request object")

    try:
        request = json.loads(raw_request, parse_constant=_reject_nonstandard_constant)
    except (json.JSONDecodeError, ProtocolError) as exc:
        raise ProtocolError(f"invalid JSON request: {exc}") from exc

    if not isinstance(request, Mapping):
        raise ProtocolError("request must be a JSON object")

    missing = sorted(_REQUIRED_FIELDS.difference(request))
    if missing:
        raise ProtocolError(f"missing required field(s): {', '.join(missing)}")

    unknown = sorted(set(request).difference(_REQUIRED_FIELDS))
    if unknown:
        raise ProtocolError(f"unsupported field(s): {', '.join(unknown)}")

    version = request["schemaVersion"]
    if isinstance(version, bool) or version != 1 or not isinstance(version, int):
        raise ProtocolError("schemaVersion must be the integer 1")

    if not isinstance(request["feed_items"], list):
        raise ProtocolError("feed_items must be a JSON array")

    incident_id = request["incident_id"]
    if not isinstance(incident_id, str) or not incident_id.strip():
        raise ProtocolError("incident_id must be a nonempty string")

    return dict(request)


def main(
    argv: list[str] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the CLI protocol and return a process exit code."""
    if argv is None:
        argv = sys.argv[1:]
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    if argv:
        print("request error: command-line arguments are not supported", file=stderr)
        return 2

    try:
        request = _read_request(stdin)
    except ProtocolError as exc:
        print(f"request error: {exc}", file=stderr)
        return 2

    try:
        result = run_incident_evaluation(
            request["feed_items"],
            cargo_value=request["cargo_value"],
            incident_id=request["incident_id"],
        )
        response = json.dumps(result, separators=(",", ":"), allow_nan=False)
    except Exception as exc:
        print(f"evaluation error: {type(exc).__name__}: {exc}", file=stderr)
        return 1

    stdout.write(response)
    stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
