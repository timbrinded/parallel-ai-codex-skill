#!/usr/bin/env python3
"""Verify Parallel Task webhook signatures against the raw body bytes.

This utility implements the signing shape documented in Parallel's webhook setup docs:
    <webhook_id>.<webhook_timestamp>.<raw_request_body>
then HMAC-SHA256 with the webhook signing secret.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from typing import Iterable, List


DEFAULT_TOLERANCE_SECONDS = 300


def load_body(body_file: str | None) -> bytes:
    if not body_file or body_file == "-":
        return sys.stdin.buffer.read()
    return Path(body_file).read_bytes()


def parse_signature_values(header_value: str) -> List[str]:
    """Extract candidate hex digests from common formats.

    Supported forms:
    - "v1,<hex>"
    - "v1=<hex>"
    - "<hex>"
    - comma-joined combinations of the above
    """
    candidates: List[str] = []
    tokens = [t.strip() for t in header_value.split(",") if t.strip()]
    if not tokens:
        return candidates

    # Handle key=value tokens (e.g., v1=abcd)
    for token in tokens:
      if "=" in token:
        key, value = token.split("=", 1)
        if key.strip().lower().startswith("v") and is_probably_hex(value.strip()):
          candidates.append(value.strip().lower())

    if candidates:
        return dedupe(candidates)

    # Handle "v1,<hex>[,<hex2>]" style
    if tokens[0].lower().startswith("v") and all(is_probably_hex(t) for t in tokens[1:]):
        return dedupe([t.lower() for t in tokens[1:]])

    # Handle direct hex values
    if all(is_probably_hex(t) for t in tokens):
        return dedupe([t.lower() for t in tokens])

    return candidates


def dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for v in values:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def is_probably_hex(value: str) -> bool:
    if len(value) < 32:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def compute_expected_hex(secret: str, webhook_id: str, timestamp: str, body: bytes) -> str:
    prefix = f"{webhook_id}.{timestamp}.".encode("utf-8")
    signed_payload = prefix + body
    return hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Parallel webhook HMAC signature")
    parser.add_argument("--secret", required=True, help="Parallel webhook signing secret")
    parser.add_argument("--webhook-id", required=True, help="Header: parallel-webhook-id")
    parser.add_argument(
        "--timestamp",
        required=True,
        help="Header: parallel-webhook-timestamp (unix epoch seconds, per docs)",
    )
    parser.add_argument(
        "--signature-header",
        required=True,
        help="Header: parallel-webhook-signature",
    )
    parser.add_argument(
        "--body-file",
        default="-",
        help="Raw request body file path, or '-' for stdin (default)",
    )
    parser.add_argument(
        "--tolerance-seconds",
        type=int,
        default=DEFAULT_TOLERANCE_SECONDS,
        help=f"Replay tolerance in seconds (default: {DEFAULT_TOLERANCE_SECONDS})",
    )
    parser.add_argument(
        "--now",
        type=int,
        help="Override current unix epoch seconds (for tests)",
    )
    parser.add_argument("--print-json", action="store_true", help="Print machine-readable result")
    args = parser.parse_args()

    body = load_body(args.body_file)
    candidates = parse_signature_values(args.signature_header)
    if not candidates:
        msg = "Could not parse any candidate hex signatures from --signature-header"
        if args.print_json:
            print(json.dumps({"valid": False, "error": msg}))
        else:
            print(f"INVALID: {msg}")
        return 1

    try:
        ts = int(args.timestamp)
    except ValueError:
        msg = "timestamp must be a unix epoch integer"
        if args.print_json:
            print(json.dumps({"valid": False, "error": msg}))
        else:
            print(f"INVALID: {msg}")
        return 1

    now = args.now if args.now is not None else int(time.time())
    age = abs(now - ts)
    within_tolerance = age <= args.tolerance_seconds

    expected_hex = compute_expected_hex(args.secret, args.webhook_id, args.timestamp, body)
    matched = any(hmac.compare_digest(expected_hex, cand) for cand in candidates)
    valid = matched and within_tolerance

    result = {
        "valid": valid,
        "matched_signature": matched,
        "within_tolerance": within_tolerance,
        "age_seconds": age,
        "candidate_count": len(candidates),
        "expected_hex": expected_hex,
    }

    if args.print_json:
        print(json.dumps(result))
    else:
        print("VALID" if valid else "INVALID")
        print(f"matched_signature={matched}")
        print(f"within_tolerance={within_tolerance}")
        print(f"age_seconds={age}")
        print(f"candidate_count={len(candidates)}")
        if not valid:
            print("expected_hex=" + expected_hex)

    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
