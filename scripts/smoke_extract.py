#!/usr/bin/env python3
"""Optional live smoke test for Parallel Extract API (beta)."""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_API_BASE = os.environ.get("PARALLEL_API_BASE_URL", "https://api.parallel.ai")
DEFAULT_EXTRACT_BETA = "search-extract-2025-10-10"


def post_json(url: str, api_key: str, payload: dict[str, Any], betas: list[str], timeout: float) -> tuple[int, Any]:
    headers = {
        "content-type": "application/json",
        "x-api-key": api_key,
    }
    if betas:
        headers["parallel-beta"] = ",".join(betas)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.getcode(), json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return e.code, parsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a minimal Parallel Extract API smoke test")
    parser.add_argument("--api-key", default=os.environ.get("PARALLEL_API_KEY"), help="Parallel API key (defaults to PARALLEL_API_KEY)")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--url", dest="urls", action="append", default=[], help="URL to extract (repeatable). Defaults to https://www.example.com")
    parser.add_argument("--objective", help="Optional objective to focus excerpts")
    parser.add_argument("--search-query", action="append", default=[], help="Optional search query for focused excerpts (repeatable)")
    parser.add_argument("--excerpts", dest="excerpts", action="store_true", help="Request excerpts (default true)")
    parser.add_argument("--no-excerpts", dest="excerpts", action="store_false", help="Disable excerpts")
    parser.set_defaults(excerpts=True)
    parser.add_argument("--full-content", action="store_true", help="Request full_content=true")
    parser.add_argument("--full-content-max-chars", type=int, help="Request full_content object with max_chars_per_result")
    parser.add_argument("--beta", action="append", default=[], help="parallel-beta value (repeatable). Default adds search-extract beta if none provided")
    parser.add_argument("--timeout", type=float, default=90.0, help="HTTP timeout seconds")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    args = parser.parse_args()

    if not args.api_key:
        print("SKIPPED: PARALLEL_API_KEY is not set (or pass --api-key)")
        return 0

    urls = args.urls or ["https://www.example.com"]
    betas = list(args.beta) if args.beta else [DEFAULT_EXTRACT_BETA]

    payload: dict[str, Any] = {"urls": urls, "excerpts": args.excerpts}
    if args.objective:
        payload["objective"] = args.objective
    if args.search_query:
        payload["search_queries"] = args.search_query
    if args.full_content_max_chars is not None:
        payload["full_content"] = {"max_chars_per_result": args.full_content_max_chars}
    elif args.full_content:
        payload["full_content"] = True

    url = args.api_base.rstrip("/") + "/v1beta/extract"
    status, resp = post_json(url, args.api_key, payload, betas, args.timeout)

    print(f"status={status}")
    print(f"betas={','.join(betas)}")

    if args.raw:
        print(json.dumps(resp, indent=2))

    if status != 200:
        print("Extract smoke test failed")
        if not args.raw:
            print(json.dumps(resp, indent=2))
        return 1

    results = resp.get("results") or []
    errors = resp.get("errors") or []
    warnings = resp.get("warnings") or []
    usage = resp.get("usage") or []
    print(f"extract_id={resp.get('extract_id')}")
    print(f"results_count={len(results)} errors_count={len(errors)} warnings_count={len(warnings)} usage_items={len(usage)}")
    for i, item in enumerate(results[: min(5, len(results))], start=1):
        excerpts = item.get("excerpts") or []
        full_content = item.get("full_content") or ""
        print(
            f"{i}. {item.get('url')} | excerpts={len(excerpts)} | full_content_chars={len(full_content)} | title={item.get('title')}"
        )
    for i, err in enumerate(errors[: min(5, len(errors))], start=1):
        print(f"ERR{i}. {err.get('url')} | {err.get('error_type')} | {err.get('http_status_code')}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
