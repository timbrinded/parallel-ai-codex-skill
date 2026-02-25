#!/usr/bin/env python3
"""Offline validation/linting for Parallel Search API payloads."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, List
from urllib.parse import urlparse

ALLOWED_MODES = {"one-shot", "agentic", "fast"}
MAX_RESULTS_DOCS = 20
MAX_QUERIES_DOCS = 5
MAX_OBJECTIVE_CHARS_DOCS = 5000
MAX_QUERY_CHARS_DOCS = 200
MAX_DOMAIN_LIST_ITEMS_DOCS = 10


def load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text())


def add_error(errors: List[str], path: str, msg: str) -> None:
    errors.append(f"{path}: {msg}")


def add_warning(warnings: List[str], path: str, msg: str) -> None:
    warnings.append(f"{path}: {msg}")


def is_domain_selector(value: str) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "/" in value:
        return False
    if "://" in value:
        return False
    if value.startswith("."):
        return len(value) > 1 and " " not in value
    # Simple domain-ish check; allow subdomains and hyphens.
    if " " in value or "." not in value:
        return False
    parsed = urlparse("//" + value)
    return bool(parsed.hostname) and parsed.hostname == value.lower()


def validate(payload: Any) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict):
        add_error(errors, "$", "payload must be a JSON object")
        return errors, warnings

    if "processor" in payload:
        add_warning(warnings, "$.processor", "deprecated in Search API; prefer $.mode")
    if "max_chars_per_result" in payload:
        add_warning(
            warnings,
            "$.max_chars_per_result",
            "deprecated; prefer $.excerpts.max_chars_per_result",
        )

    objective = payload.get("objective")
    search_queries = payload.get("search_queries")
    if objective is None and search_queries is None:
        add_error(errors, "$", "at least one of 'objective' or 'search_queries' is required")

    if objective is not None:
        if not isinstance(objective, str):
            add_error(errors, "$.objective", "must be a string")
        elif not objective.strip():
            add_error(errors, "$.objective", "must not be empty")
        elif len(objective) > MAX_OBJECTIVE_CHARS_DOCS:
            add_warning(
                warnings,
                "$.objective",
                f"length {len(objective)} exceeds docs guidance ({MAX_OBJECTIVE_CHARS_DOCS} chars)",
            )

    if search_queries is not None:
        if not isinstance(search_queries, list):
            add_error(errors, "$.search_queries", "must be an array of strings")
        else:
            if len(search_queries) == 0:
                add_warning(warnings, "$.search_queries", "empty array is usually not useful")
            if len(search_queries) > MAX_QUERIES_DOCS:
                add_warning(
                    warnings,
                    "$.search_queries",
                    f"{len(search_queries)} queries exceeds docs guidance ({MAX_QUERIES_DOCS})",
                )
            for i, q in enumerate(search_queries):
                path = f"$.search_queries[{i}]"
                if not isinstance(q, str):
                    add_error(errors, path, "must be a string")
                    continue
                if not q.strip():
                    add_error(errors, path, "must not be empty")
                if len(q) > MAX_QUERY_CHARS_DOCS:
                    add_warning(
                        warnings,
                        path,
                        f"length {len(q)} exceeds docs guidance ({MAX_QUERY_CHARS_DOCS} chars)",
                    )

    mode = payload.get("mode")
    if mode is not None:
        if not isinstance(mode, str):
            add_error(errors, "$.mode", "must be a string")
        elif mode not in ALLOWED_MODES:
            add_error(errors, "$.mode", f"must be one of {sorted(ALLOWED_MODES)}")

    max_results = payload.get("max_results")
    if max_results is not None:
        if not isinstance(max_results, int):
            add_error(errors, "$.max_results", "must be an integer")
        elif max_results <= 0:
            add_error(errors, "$.max_results", "must be > 0")
        elif max_results > MAX_RESULTS_DOCS:
            add_warning(
                warnings,
                "$.max_results",
                f"{max_results} exceeds current docs guidance max ({MAX_RESULTS_DOCS})",
            )

    excerpts = payload.get("excerpts")
    if excerpts is not None:
        if not isinstance(excerpts, dict):
            add_error(errors, "$.excerpts", "must be an object")
        else:
            for key in ("max_chars_per_result", "max_chars_total"):
                val = excerpts.get(key)
                if val is None:
                    continue
                if not isinstance(val, int):
                    add_error(errors, f"$.excerpts.{key}", "must be an integer")
                elif val <= 0:
                    add_error(errors, f"$.excerpts.{key}", "must be > 0")
                elif val < 1000:
                    add_warning(
                        warnings,
                        f"$.excerpts.{key}",
                        "values below 1000 are auto-clamped by the API",
                    )

    source_policy = payload.get("source_policy")
    if source_policy is not None:
        if not isinstance(source_policy, dict):
            add_error(errors, "$.source_policy", "must be an object")
        else:
            for key in ("include_domains", "exclude_domains"):
                arr = source_policy.get(key)
                if arr is None:
                    continue
                if not isinstance(arr, list):
                    add_error(errors, f"$.source_policy.{key}", "must be an array of domain selectors")
                    continue
                if len(arr) > MAX_DOMAIN_LIST_ITEMS_DOCS:
                    add_warning(
                        warnings,
                        f"$.source_policy.{key}",
                        f"{len(arr)} entries exceeds docs guidance ({MAX_DOMAIN_LIST_ITEMS_DOCS})",
                    )
                for i, item in enumerate(arr):
                    path = f"$.source_policy.{key}[{i}]"
                    if not isinstance(item, str):
                        add_error(errors, path, "must be a string")
                    elif not is_domain_selector(item):
                        add_error(
                            errors,
                            path,
                            "must be a plain domain, subdomain, or bare extension like '.gov' (no scheme/path)",
                        )

            after_date = source_policy.get("after_date")
            if after_date is not None:
                if not isinstance(after_date, str):
                    add_error(errors, "$.source_policy.after_date", "must be YYYY-MM-DD string")
                else:
                    try:
                        date.fromisoformat(after_date)
                    except ValueError:
                        add_error(errors, "$.source_policy.after_date", "must be valid YYYY-MM-DD")

    fetch_policy = payload.get("fetch_policy")
    if fetch_policy is not None:
        if not isinstance(fetch_policy, dict):
            add_error(errors, "$.fetch_policy", "must be an object")
        else:
            mas = fetch_policy.get("max_age_seconds")
            if mas is not None:
                if not isinstance(mas, int):
                    add_error(errors, "$.fetch_policy.max_age_seconds", "must be an integer")
                elif mas < 600:
                    add_warning(
                        warnings,
                        "$.fetch_policy.max_age_seconds",
                        "docs/OpenAPI describe minimum 600 seconds (10 minutes)",
                    )
            tos = fetch_policy.get("timeout_seconds")
            if tos is not None:
                if not isinstance(tos, (int, float)):
                    add_error(errors, "$.fetch_policy.timeout_seconds", "must be a number")
                elif tos <= 0:
                    add_error(errors, "$.fetch_policy.timeout_seconds", "must be > 0")
            dcf = fetch_policy.get("disable_cache_fallback")
            if dcf is not None and not isinstance(dcf, bool):
                add_error(errors, "$.fetch_policy.disable_cache_fallback", "must be a boolean")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Parallel Search API request payload")
    parser.add_argument("json_file", nargs="?", default="-", help="JSON file path or '-' for stdin")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()

    try:
        payload = load_json(args.json_file)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to read JSON: {exc}", file=sys.stderr)
        return 2

    errors, warnings = validate(payload)

    print("Parallel Search payload validation")
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
