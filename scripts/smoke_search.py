#!/usr/bin/env python3
"""Optional live smoke test for Parallel Search API (beta)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable

DEFAULT_API_BASE = os.environ.get("PARALLEL_API_BASE_URL", "https://api.parallel.ai")
DEFAULT_SEARCH_BETA = "search-extract-2025-10-10"


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
    parser = argparse.ArgumentParser(description="Run a minimal Parallel Search API smoke test")
    parser.add_argument("--api-key", default=os.environ.get("PARALLEL_API_KEY"), help="Parallel API key (defaults to PARALLEL_API_KEY)")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"API base URL (default: {DEFAULT_API_BASE})")
    parser.add_argument("--objective", default="What was the GDP of France in 2023?", help="Search objective")
    parser.add_argument("--mode", default="one-shot", choices=["one-shot", "agentic", "fast"], help="Search mode")
    parser.add_argument("--max-results", type=int, default=3, help="max_results")
    parser.add_argument("--include-domain", action="append", default=[], help="source_policy.include_domains (repeatable)")
    parser.add_argument("--exclude-domain", action="append", default=[], help="source_policy.exclude_domains (repeatable)")
    parser.add_argument("--after-date", help="source_policy.after_date (YYYY-MM-DD)")
    parser.add_argument("--beta", action="append", default=[], help="parallel-beta value (repeatable). Default adds search-extract beta if none provided")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout seconds")
    parser.add_argument("--raw", action="store_true", help="Print raw JSON response")
    args = parser.parse_args()

    if not args.api_key:
        print("SKIPPED: PARALLEL_API_KEY is not set (or pass --api-key)")
        return 0

    betas = list(args.beta) if args.beta else [DEFAULT_SEARCH_BETA]
    payload: dict[str, Any] = {
        "mode": args.mode,
        "objective": args.objective,
        "max_results": args.max_results,
    }
    source_policy: dict[str, Any] = {}
    if args.include_domain:
        source_policy["include_domains"] = args.include_domain
    if args.exclude_domain:
        source_policy["exclude_domains"] = args.exclude_domain
    if args.after_date:
        source_policy["after_date"] = args.after_date
    if source_policy:
        payload["source_policy"] = source_policy

    url = args.api_base.rstrip("/") + "/v1beta/search"
    status, resp = post_json(url, args.api_key, payload, betas, args.timeout)

    print(f"status={status}")
    print(f"betas={','.join(betas)}")

    if args.raw:
        print(json.dumps(resp, indent=2))

    if status != 200:
        print("Search smoke test failed")
        if not args.raw:
            print(json.dumps(resp, indent=2))
        return 1

    results = resp.get("results") or []
    print(f"search_id={resp.get('search_id')}")
    print(f"result_count={len(results)}")
    for i, item in enumerate(results[: min(5, len(results))], start=1):
        print(f"{i}. {item.get('url')} | {item.get('publish_date')} | {item.get('title')}")

    warnings = resp.get("warnings") or []
    usage = resp.get("usage") or []
    print(f"warnings_count={len(warnings)} usage_items={len(usage)}")
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
