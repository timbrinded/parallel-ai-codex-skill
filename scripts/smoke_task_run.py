#!/usr/bin/env python3
"""Optional live smoke test for Parallel Task API v1 runs."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable

DEFAULT_API_BASE = os.environ.get("PARALLEL_API_BASE_URL", "https://api.parallel.ai")
EVENTS_BETA = "events-sse-2025-07-24"


def http_json(
    method: str,
    url: str,
    api_key: str,
    *,
    payload: dict[str, Any] | None = None,
    betas: list[str] | None = None,
    timeout: float = 60.0,
) -> tuple[int, Any]:
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
    }
    if betas:
        headers["parallel-beta"] = ",".join(betas)
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            parsed = json.loads(body) if body else None
            return resp.getcode(), parsed
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return e.code, parsed


def terminal_status(status: str | None) -> bool:
    return status in {"completed", "failed", "cancelled"}


def build_task_spec() -> dict[str, Any]:
    return {
        "output_schema": {
            "type": "json",
            "json_schema": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string", "description": "Short direct answer"},
                    "confidence": {"type": "string", "description": "low/medium/high"},
                },
                "required": ["answer", "confidence"],
                "additionalProperties": False,
            },
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal Parallel Task API create/retrieve/result smoke test")
    parser.add_argument("--api-key", default=os.environ.get("PARALLEL_API_KEY"), help="Parallel API key (defaults to PARALLEL_API_KEY)")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--processor", default="base", help="Task processor")
    parser.add_argument("--input", dest="task_input", default="What was the GDP of France in 2023?", help="Task input text")
    parser.add_argument("--beta", action="append", default=[], help="parallel-beta value (repeatable)")
    parser.add_argument("--enable-events", action="store_true", help="Set enable_events=true and add events beta header if needed")
    parser.add_argument("--structured-output", action="store_true", help="Include a small TaskSpec JSON output schema")
    parser.add_argument("--poll", action="store_true", help="Poll status endpoint before fetching result")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Polling interval seconds")
    parser.add_argument("--max-poll-seconds", type=float, default=120.0, help="Max total polling time")
    parser.add_argument("--result-timeout", type=int, default=120, help="/result timeout query param seconds")
    parser.add_argument("--http-timeout", type=float, default=60.0, help="Per-request network timeout seconds")
    parser.add_argument("--raw", action="store_true", help="Print raw API responses")
    args = parser.parse_args()

    if not args.api_key:
        print("SKIPPED: PARALLEL_API_KEY is not set (or pass --api-key)")
        return 0

    betas = list(args.beta)
    payload: dict[str, Any] = {
        "processor": args.processor,
        "input": args.task_input,
    }
    if args.enable_events:
        payload["enable_events"] = True
        if EVENTS_BETA not in betas:
            betas.append(EVENTS_BETA)
    if args.structured_output:
        payload["task_spec"] = build_task_spec()

    base = args.api_base.rstrip("/")
    create_url = f"{base}/v1/tasks/runs"
    status_code, create_resp = http_json("POST", create_url, args.api_key, payload=payload, betas=betas, timeout=args.http_timeout)
    print(f"create_status={status_code}")
    print(f"betas={','.join(betas) if betas else '(none)'}")
    if args.raw:
        print(json.dumps(create_resp, indent=2))
    if status_code != 202:
        print("Task create smoke test failed")
        if not args.raw:
            print(json.dumps(create_resp, indent=2))
        return 1

    run_id = create_resp.get("run_id")
    if not run_id:
        print("Task create response missing run_id")
        return 1
    print(f"run_id={run_id}")

    if args.poll:
        retrieve_url = f"{base}/v1/tasks/runs/{urllib.parse.quote(run_id)}"
        start = time.time()
        while True:
            code, status_resp = http_json("GET", retrieve_url, args.api_key, betas=betas, timeout=args.http_timeout)
            if code != 200:
                print(f"retrieve_status={code}")
                print(json.dumps(status_resp, indent=2))
                return 1
            status = status_resp.get("status")
            print(f"run_status={status} is_active={status_resp.get('is_active')}")
            if terminal_status(status):
                break
            if time.time() - start > args.max_poll_seconds:
                print("Polling timed out before terminal status")
                return 1
            time.sleep(args.poll_interval)

    result_url = f"{base}/v1/tasks/runs/{urllib.parse.quote(run_id)}/result?timeout={args.result_timeout}"
    code, result_resp = http_json("GET", result_url, args.api_key, betas=betas, timeout=max(args.http_timeout, args.result_timeout + 5))
    print(f"result_status={code}")
    if args.raw:
        print(json.dumps(result_resp, indent=2))
    if code != 200:
        print("Task result smoke test failed")
        if not args.raw:
            print(json.dumps(result_resp, indent=2))
        return 1

    run = (result_resp or {}).get("run") or {}
    output = (result_resp or {}).get("output") or {}
    print(f"final_run_status={run.get('status')}")
    print(f"output_type={output.get('type')}")
    content = output.get("content")
    if isinstance(content, (dict, list)):
        print("output_content=" + json.dumps(content, ensure_ascii=False))
    else:
        print(f"output_content={content}")
    basis = output.get("basis") or []
    print(f"basis_count={len(basis)}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
