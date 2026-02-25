#!/usr/bin/env python3
"""Offline validation/linting for Parallel Task run payloads (v1 create endpoint)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Iterable, List, Set

KNOWN_PROCESSORS = {
    # Current docs families (2026-02 snapshot) plus a few older names for compatibility warnings.
    "lite",
    "base",
    "core",
    "core2x",
    "pro",
    "ultra",
    "ultra2x",
    "ultra4x",
    "ultra8x",
    "base-fast",
    "core-fast",
    "pro-fast",
    "vision",
    "vision_pro",
    "deep",
    "deepv2",
    # Legacy/older names seen in examples or prior docs
    "fast",
    "nano",
}

BETA_REQUIREMENTS = {
    "enable_events": "events-sse-2025-07-24",
    "mcp_servers": "mcp-server-2025-07-17",
    "webhook": "webhook-2025-08-12",
}

TASK_STATUSES = {
    "queued",
    "action_required",
    "running",
    "completed",
    "failed",
    "cancelling",
    "cancelled",
}

UNSUPPORTED_JSON_SCHEMA_KEYWORDS = {
    "anyOf",
    "oneOf",
    "allOf",
    "not",
    "if",
    "then",
    "else",
    "dependentSchemas",
    "dependentRequired",
    "patternProperties",
}

TASK_SPEC_SIZE_LIMIT = 15000
COMBINED_TASK_SPEC_INPUT_LIMIT = 18000
JSON_SCHEMA_PROPERTY_LIMIT = 100
JSON_SCHEMA_DEPTH_LIMIT = 5


class Collector:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def error(self, path: str, msg: str) -> None:
        self.errors.append(f"{path}: {msg}")

    def warn(self, path: str, msg: str) -> None:
        self.warnings.append(f"{path}: {msg}")


class SchemaStats:
    def __init__(self) -> None:
        self.property_count = 0
        self.max_depth = 0


def load_json(path: str) -> Any:
    if path == "-":
        return json.load(sys.stdin)
    return json.loads(Path(path).read_text())


def json_size(value: Any) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=True))


def validate_source_policy(sp: Any, c: Collector, path: str, allow_after_date: bool) -> None:
    if not isinstance(sp, dict):
        c.error(path, "must be an object")
        return
    for key in ("include_domains", "exclude_domains"):
        arr = sp.get(key)
        if arr is None:
            continue
        if not isinstance(arr, list):
            c.error(f"{path}.{key}", "must be an array of strings")
            continue
        if len(arr) > 10:
            c.warn(f"{path}.{key}", "docs guidance is max 10 entries")
        for i, item in enumerate(arr):
            if not isinstance(item, str):
                c.error(f"{path}.{key}[{i}]", "must be a string")
            elif "://" in item or "/" in item or " " in item or "." not in item and not item.startswith("."):
                c.error(
                    f"{path}.{key}[{i}]",
                    "must be a plain domain, subdomain, or bare extension like '.gov'",
                )
    if "after_date" in sp:
        if not allow_after_date:
            c.warn(f"{path}.after_date", "Task source policy does not currently support after_date")
        val = sp.get("after_date")
        if val is not None:
            if not isinstance(val, str):
                c.error(f"{path}.after_date", "must be YYYY-MM-DD string")
            else:
                try:
                    date.fromisoformat(val)
                except ValueError:
                    c.error(f"{path}.after_date", "must be valid YYYY-MM-DD")


def validate_metadata(meta: Any, c: Collector, path: str) -> None:
    if meta is None:
        return
    if not isinstance(meta, dict):
        c.error(path, "must be an object")
        return
    for k, v in meta.items():
        if not isinstance(k, str):
            c.error(path, "all metadata keys must be strings")
            continue
        if len(k) > 16:
            c.warn(f"{path}.{k}", "key length exceeds 16 (OpenAPI docs note a short-key limit)")
        if not isinstance(v, (str, int, float, bool)):
            c.error(f"{path}.{k}", "value must be string/number/integer/boolean")
            continue
        if len(str(v)) > 512:
            c.warn(f"{path}.{k}", "value length exceeds 512 characters when stringified")


def validate_mcp_servers(value: Any, c: Collector, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, list):
        c.error(path, "must be an array")
        return
    for i, item in enumerate(value):
        p = f"{path}[{i}]"
        if not isinstance(item, dict):
            c.error(p, "must be an object")
            continue
        if "url" not in item or not isinstance(item.get("url"), str) or not item["url"]:
            c.error(f"{p}.url", "is required and must be a non-empty string")
        if "name" not in item or not isinstance(item.get("name"), str) or not item["name"]:
            c.error(f"{p}.name", "is required and must be a non-empty string")
        t = item.get("type")
        if t is not None and t != "url":
            c.warn(f"{p}.type", "OpenAPI currently documents MCP server type as constant 'url'")
        headers = item.get("headers")
        if headers is not None and not isinstance(headers, dict):
            c.error(f"{p}.headers", "must be an object mapping header names to strings")
        elif isinstance(headers, dict):
            for hk, hv in headers.items():
                if not isinstance(hk, str) or not isinstance(hv, str):
                    c.error(f"{p}.headers", "header keys and values must be strings")
                    break
        allowed_tools = item.get("allowed_tools")
        if allowed_tools is not None:
            if not isinstance(allowed_tools, list) or not all(isinstance(x, str) for x in allowed_tools):
                c.error(f"{p}.allowed_tools", "must be an array of strings")


def validate_webhook(value: Any, c: Collector, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        c.error(path, "must be an object")
        return
    if "url" not in value or not isinstance(value.get("url"), str) or not value["url"]:
        c.error(f"{path}.url", "is required and must be a non-empty string")
    event_types = value.get("event_types")
    if event_types is not None:
        if not isinstance(event_types, list) or not all(isinstance(x, str) for x in event_types):
            c.error(f"{path}.event_types", "must be an array of strings")
        else:
            for i, item in enumerate(event_types):
                if item != "task_run.status":
                    c.warn(f"{path}.event_types[{i}]", "OpenAPI currently documents only 'task_run.status'")


def validate_json_schema_node(
    node: Any,
    c: Collector,
    path: str,
    stats: SchemaStats,
    depth: int,
    warn_on_unsupported_keywords: bool,
    strict_additional_properties_hint: bool,
) -> None:
    if depth > stats.max_depth:
        stats.max_depth = depth
    if depth > JSON_SCHEMA_DEPTH_LIMIT:
        c.error(path, f"nesting depth exceeds docs guidance ({JSON_SCHEMA_DEPTH_LIMIT})")

    if not isinstance(node, dict):
        return

    for key in node.keys():
        if key in UNSUPPORTED_JSON_SCHEMA_KEYWORDS:
            msg = f"contains unsupported JSON Schema keyword '{key}' per Task docs guidance"
            if warn_on_unsupported_keywords:
                c.warn(path, msg)
            else:
                c.error(path, msg)

    node_type = node.get("type")
    if node_type == "object":
        props = node.get("properties")
        if props is not None:
            if not isinstance(props, dict):
                c.error(f"{path}.properties", "must be an object")
            else:
                stats.property_count += len(props)
                if stats.property_count > JSON_SCHEMA_PROPERTY_LIMIT:
                    c.error(
                        path,
                        f"total JSON schema properties exceed docs guidance ({JSON_SCHEMA_PROPERTY_LIMIT})",
                    )
                for name, sub in props.items():
                    if not isinstance(name, str):
                        c.error(f"{path}.properties", "property names must be strings")
                        continue
                    validate_json_schema_node(
                        sub,
                        c,
                        f"{path}.properties.{name}",
                        stats,
                        depth + 1,
                        warn_on_unsupported_keywords,
                        strict_additional_properties_hint,
                    )
        if strict_additional_properties_hint and node.get("additionalProperties") is not False:
            c.warn(path, "set additionalProperties=false for more stable Task outputs")

        req = node.get("required")
        if req is not None and (not isinstance(req, list) or not all(isinstance(x, str) for x in req)):
            c.error(f"{path}.required", "must be an array of strings")

    if isinstance(node.get("items"), dict):
        validate_json_schema_node(
            node["items"],
            c,
            f"{path}.items",
            stats,
            depth + 1,
            warn_on_unsupported_keywords,
            strict_additional_properties_hint,
        )

    if isinstance(node.get("additionalProperties"), dict):
        validate_json_schema_node(
            node["additionalProperties"],
            c,
            f"{path}.additionalProperties",
            stats,
            depth + 1,
            warn_on_unsupported_keywords,
            strict_additional_properties_hint,
        )


def extract_json_schema_descriptor(value: Any, c: Collector, path: str, is_output_schema: bool) -> None:
    if value is None:
        c.error(path, "must not be null")
        return
    if isinstance(value, str):
        # Bare string is allowed (text schema shorthand).
        return
    if not isinstance(value, dict):
        c.error(path, "must be a string or object")
        return

    # Allow wrapper forms used by SDK/API docs.
    schema_obj = None
    schema_type = value.get("type")
    if schema_type == "auto":
        return
    if "json_schema" in value:
        if value.get("type") not in (None, "json"):
            c.warn(path, "json_schema is present but type is not 'json'")
        if not isinstance(value["json_schema"], dict):
            c.error(f"{path}.json_schema", "must be an object")
            return
        schema_obj = value["json_schema"]
    elif schema_type == "json":
        c.error(path, "type='json' requires a nested 'json_schema' object")
        return
    elif schema_type in ("text", None):
        # Could be a text schema wrapper or a plain JSON Schema object.
        # Heuristically treat objects with JSON Schema keys as plain JSON Schema.
        if any(k in value for k in ("properties", "items", "required", "additionalProperties")):
            schema_obj = value
        else:
            # Accept text-schema-like wrapper without deep validation.
            return
    else:
        # Unknown wrapper type: still allow but warn.
        c.warn(path, f"unrecognized schema wrapper type '{schema_type}'")
        if any(k in value for k in ("properties", "items", "required", "additionalProperties")):
            schema_obj = value

    if schema_obj is not None:
        stats = SchemaStats()
        validate_json_schema_node(
            schema_obj,
            c,
            path + (".json_schema" if schema_obj is not value else ""),
            stats,
            depth=1,
            warn_on_unsupported_keywords=not is_output_schema,
            strict_additional_properties_hint=is_output_schema,
        )


def validate_task_spec(task_spec: Any, payload: dict[str, Any], c: Collector, path: str) -> None:
    if task_spec is None:
        return
    if isinstance(task_spec, str):
        return
    if not isinstance(task_spec, dict):
        c.error(path, "must be a string or object")
        return
    if "output_schema" not in task_spec:
        c.error(path, "must contain output_schema")
        return

    extract_json_schema_descriptor(task_spec.get("output_schema"), c, f"{path}.output_schema", is_output_schema=True)

    if "input_schema" in task_spec and task_spec.get("input_schema") is not None:
        extract_json_schema_descriptor(task_spec.get("input_schema"), c, f"{path}.input_schema", is_output_schema=False)

    try:
        ts_size = json_size(task_spec)
    except TypeError as exc:
        c.error(path, f"must be JSON serializable: {exc}")
        return
    if ts_size > TASK_SPEC_SIZE_LIMIT:
        c.error(path, f"serialized size {ts_size} exceeds docs guidance limit {TASK_SPEC_SIZE_LIMIT}")

    if "input" in payload:
        try:
            combined = ts_size + json_size(payload["input"])
        except TypeError:
            combined = None
        if combined is not None and combined > COMBINED_TASK_SPEC_INPUT_LIMIT:
            c.error(
                path,
                f"combined serialized size of task_spec + input ({combined}) exceeds docs guidance limit {COMBINED_TASK_SPEC_INPUT_LIMIT}",
            )


def validate(payload: Any, betas: Set[str]) -> Collector:
    c = Collector()
    if not isinstance(payload, dict):
        c.error("$", "payload must be a JSON object")
        return c

    processor = payload.get("processor")
    if processor is None:
        c.error("$.processor", "is required")
    elif not isinstance(processor, str) or not processor.strip():
        c.error("$.processor", "must be a non-empty string")
    elif processor not in KNOWN_PROCESSORS:
        c.warn(
            "$.processor",
            "processor not in known snapshot set; verify against docs before shipping",
        )

    if "input" not in payload:
        c.error("$.input", "is required")
    else:
        inp = payload["input"]
        if not isinstance(inp, (str, dict)):
            c.error("$.input", "must be a string or JSON object")

    if "metadata" in payload:
        validate_metadata(payload.get("metadata"), c, "$.metadata")

    if "source_policy" in payload and payload.get("source_policy") is not None:
        validate_source_policy(payload.get("source_policy"), c, "$.source_policy", allow_after_date=False)

    if "previous_interaction_id" in payload:
        val = payload.get("previous_interaction_id")
        if val is not None and not isinstance(val, str):
            c.error("$.previous_interaction_id", "must be a string")

    if "task_spec" in payload:
        validate_task_spec(payload.get("task_spec"), payload, c, "$.task_spec")

    if "enable_events" in payload:
        val = payload.get("enable_events")
        if val is not None and not isinstance(val, bool):
            c.error("$.enable_events", "must be a boolean")
        if val and BETA_REQUIREMENTS["enable_events"] not in betas:
            c.warn(
                "$.enable_events",
                f"enable_events is beta-gated; include parallel-beta '{BETA_REQUIREMENTS['enable_events']}'",
            )

    if "mcp_servers" in payload:
        validate_mcp_servers(payload.get("mcp_servers"), c, "$.mcp_servers")
        if payload.get("mcp_servers") and BETA_REQUIREMENTS["mcp_servers"] not in betas:
            c.warn(
                "$.mcp_servers",
                f"mcp_servers is beta-gated; include parallel-beta '{BETA_REQUIREMENTS['mcp_servers']}'",
            )

    if "webhook" in payload:
        validate_webhook(payload.get("webhook"), c, "$.webhook")
        if payload.get("webhook") and BETA_REQUIREMENTS["webhook"] not in betas:
            c.warn(
                "$.webhook",
                f"webhook is beta-gated; include parallel-beta '{BETA_REQUIREMENTS['webhook']}'",
            )

    # Unknown-key hinting (warn only; API may add new fields)
    known_keys = {
        "processor",
        "metadata",
        "source_policy",
        "task_spec",
        "input",
        "previous_interaction_id",
        "mcp_servers",
        "enable_events",
        "webhook",
    }
    for key in payload.keys():
        if key not in known_keys:
            c.warn(f"$.{key}", "unknown field for current BetaTaskRunInput snapshot; verify docs/OpenAPI")

    return c


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a Parallel Task run create payload")
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

    c = validate(payload, betas)

    print("Parallel Task payload validation")
    if betas:
        print("betas=" + ",".join(sorted(betas)))
    print(f"errors={len(c.errors)} warnings={len(c.warnings)}")
    for msg in c.errors:
        print(f"ERROR  {msg}")
    for msg in c.warnings:
        print(f"WARN   {msg}")

    if c.errors:
        return 1
    if args.strict and c.warnings:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
