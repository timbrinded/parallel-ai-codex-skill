#!/usr/bin/env python3
"""Offline validation/linting for Parallel Extract API payloads."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, List, Set
from urllib.parse import urlparse

REQUIRED_BETA = "search-extract-2025-10-10"


def load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text())


def add_error(errors: List[str], path: str, msg: str) -> None:
    errors.append(f"{path}: {msg}")


def add_warning(warnings: List[str], path: str, msg: str) -> None:
    warnings.append(f"{path}: {msg}")


def is_http_url(value: str) -> bool:
    try:
        parsed = urlparse(value)
    except Exception:  # noqa: BLE001
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_fetch_policy(value: Any, errors: List[str], warnings: List[str], path: str) -> None:
    if not isinstance(value, dict):
        add_error(errors, path, "must be an object")
        return
    mas = value.get("max_age_seconds")
    if mas is not None:
        if not isinstance(mas, int):
            add_error(errors, f"{path}.max_age_seconds", "must be an integer")
        elif mas < 600:
            add_warning(warnings, f"{path}.max_age_seconds", "docs/OpenAPI describe minimum 600 seconds")
    tos = value.get("timeout_seconds")
    if tos is not None:
        if not isinstance(tos, (int, float)):
            add_error(errors, f"{path}.timeout_seconds", "must be a number")
        elif tos <= 0:
            add_error(errors, f"{path}.timeout_seconds", "must be > 0")
    dcf = value.get("disable_cache_fallback")
    if dcf is not None and not isinstance(dcf, bool):
        add_error(errors, f"{path}.disable_cache_fallback", "must be a boolean")


def validate_excerpt_settings(value: Any, errors: List[str], warnings: List[str], path: str) -> None:
    if not isinstance(value, dict):
        add_error(errors, path, "must be a boolean or object")
        return
    for key in ("max_chars_per_result", "max_chars_total"):
        v = value.get(key)
        if v is None:
            continue
        if not isinstance(v, int):
            add_error(errors, f"{path}.{key}", "must be an integer")
        elif v <= 0:
            add_error(errors, f"{path}.{key}", "must be > 0")
        elif v < 1000:
            add_warning(warnings, f"{path}.{key}", "values below 1000 are auto-clamped by the API")


def validate_full_content_settings(value: Any, errors: List[str], warnings: List[str], path: str) -> None:
    if not isinstance(value, dict):
        add_error(errors, path, "must be a boolean or object")
        return
    m = value.get("max_chars_per_result")
    if m is not None:
        if not isinstance(m, int):
            add_error(errors, f"{path}.max_chars_per_result", "must be an integer")
        elif m <= 0:
            add_error(errors, f"{path}.max_chars_per_result", "must be > 0")


def validate(payload: Any, betas: Set[str]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict):
        add_error(errors, "$", "payload must be a JSON object")
        return errors, warnings

    urls = payload.get("urls")
    if urls is None:
        add_error(errors, "$.urls", "is required")
    elif not isinstance(urls, list):
        add_error(errors, "$.urls", "must be an array of URLs")
    else:
        if len(urls) == 0:
            add_error(errors, "$.urls", "must not be empty")
        seen = set()
        for i, url in enumerate(urls):
            path = f"$.urls[{i}]"
            if not isinstance(url, str):
                add_error(errors, path, "must be a string")
                continue
            if not is_http_url(url):
                add_error(errors, path, "must be an absolute http/https URL")
                continue
            if url in seen:
                add_warning(warnings, path, "duplicate URL")
            seen.add(url)

    objective = payload.get("objective")
    if objective is not None:
        if not isinstance(objective, str):
            add_error(errors, "$.objective", "must be a string")
        elif not objective.strip():
            add_error(errors, "$.objective", "must not be empty")

    queries = payload.get("search_queries")
    if queries is not None:
        if not isinstance(queries, list):
            add_error(errors, "$.search_queries", "must be an array of strings")
        else:
            if not queries:
                add_warning(warnings, "$.search_queries", "empty array is usually not useful")
            for i, q in enumerate(queries):
                if not isinstance(q, str):
                    add_error(errors, f"$.search_queries[{i}]", "must be a string")
                elif not q.strip():
                    add_error(errors, f"$.search_queries[{i}]", "must not be empty")

    if "fetch_policy" in payload and payload.get("fetch_policy") is not None:
        validate_fetch_policy(payload.get("fetch_policy"), errors, warnings, "$.fetch_policy")

    excerpts_val = payload.get("excerpts", True)
    full_content_val = payload.get("full_content", False)

    if "excerpts" in payload and excerpts_val is not None:
        if isinstance(excerpts_val, bool):
            pass
        else:
            validate_excerpt_settings(excerpts_val, errors, warnings, "$.excerpts")

    if "full_content" in payload and full_content_val is not None:
        if isinstance(full_content_val, bool):
            pass
        else:
            validate_full_content_settings(full_content_val, errors, warnings, "$.full_content")

    excerpts_enabled = excerpts_val is True or isinstance(excerpts_val, dict)
    full_content_enabled = full_content_val is True or isinstance(full_content_val, dict)

    if not excerpts_enabled and not full_content_enabled:
        add_warning(warnings, "$", "both excerpts and full_content are disabled; response may contain no useful content")

    if excerpts_enabled and payload.get("objective") is None and payload.get("search_queries") is None:
        add_warning(
            warnings,
            "$.excerpts",
            "without objective/search_queries, excerpts may be redundant with full content",
        )

    if REQUIRED_BETA not in betas:
        add_warning(
            warnings,
            "$",
            f"Extract API is beta; include parallel-beta '{REQUIRED_BETA}' (current docs/OpenAPI)",
        )

    known = {"urls", "objective", "search_queries", "fetch_policy", "excerpts", "full_content"}
    for key in payload.keys():
        if key not in known:
            add_warning(warnings, f"$.{key}", "unknown field for current ExtractRequest snapshot")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Parallel Extract API request payload")
    parser.add_argument("json_file", nargs="?", default="-", help="JSON file path or '-' for stdin")
    parser.add_argument(
        "--beta",
        action="append",
        default=[],
        help="parallel-beta value(s) used with the request (repeatable or comma-separated)",
    )
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    betas: Set[str] = set()
    for item in args.beta:
        for part in item.split(","):
            part = part.strip()
            if part:
                betas.add(part)

    try:
        payload = load_json(args.json_file)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to read JSON: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate(payload, betas)

    print("Parallel Extract payload validation")
    if betas:
        print("betas=" + ",".join(sorted(betas)))
    print(f"errors={len(errors)} warnings={len(warnings)}")
    for msg in errors:
        print(f"ERROR  {msg}")
    for msg in warnings:
        print(f"WARN   {msg}")

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
