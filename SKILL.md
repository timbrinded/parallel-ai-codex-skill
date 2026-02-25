---
name: parallel-ai-codex-skill
description: Comprehensive Parallel.ai Search API, Extract API, and Task API implementation and debugging guidance. Use when Codex needs to build, inspect, troubleshoot, or refactor integrations using parallel.ai / Parallel / parallel-web, Search API (/v1beta/search), Extract API (/v1beta/extract), Task API runs (/v1/tasks/runs), task groups/events (/v1beta/tasks/groups), SSE streams, webhooks, TaskSpec structured outputs, SourcePolicy filtering, processor selection, fetch policies, or Parallel beta headers.
---

# Parallel.ai Search + Extract + Task API Skill

Use this skill to implement or debug Parallel.ai Search, Extract, and Task API integrations.

## Start with the right reference

- Use `references/search-api.md` for Search API requests, modes, source policy, and response parsing.
- Use `references/extract-api.md` for Extract API URL content extraction, focused excerpts/full-content settings, and response/error parsing.
- Use `references/task-api-runs.md` for Task v1 run lifecycle, processors, and `TaskSpec` structured outputs.
- Use `references/task-api-streams-groups.md` for SSE events and beta task groups.
- Use `references/webhooks.md` for Task webhooks and signature verification.
- Use `references/openapi-cheatsheet.md` for endpoint/schema discovery and OpenAPI refresh workflow.
- Use `references/parallel-overview.md` for auth, SDK packages, rate limits, and versioning/beta-header conventions.

Load only the reference files needed for the user request.

## Triage workflow

1. Identify whether the user needs `search`, `extract`, `task run`, `task group`, `sse`, or `webhook` behavior.
2. Confirm SDK vs raw HTTP preference (Python, TypeScript, or cURL).
3. Choose processor/mode before writing payloads.
4. Draft payload and validate locally with `scripts/validate_search_payload.py`, `scripts/validate_extract_payload.py`, or `scripts/validate_task_payload.py`.
5. Run optional live smoke checks only if `PARALLEL_API_KEY` is available.
6. For failures, inspect status codes, beta headers, and schema shape before changing logic.

## Implementation rules

- Prefer official docs and `https://docs.parallel.ai/public-openapi.json` when answering schema questions.
- Treat `parallel-beta` header values as time-sensitive. Re-verify before relying on them.
- Mark beta-gated fields explicitly in examples (`enable_events`, `mcp_servers`, `webhook`, Search/Extract beta endpoints).
- Prefer explicit `TaskSpec` JSON schemas for stable downstream parsing.
- Use `SourcePolicy` domain filters and date filters instead of post-filtering when possible.
- Use Extract `objective` / `search_queries` to focus excerpts before post-processing text.
- For SSE, preserve event ordering and resume cursors (`last_event_id`) when available.
- For webhooks, verify signatures against the raw request body before parsing JSON.

## Useful scripts

- `scripts/validate_search_payload.py`: Offline search payload validation and linting.
- `scripts/validate_extract_payload.py`: Offline extract payload validation and linting.
- `scripts/validate_task_payload.py`: Offline task payload validation and beta-header linting.
- `scripts/smoke_search.py`: Optional live Search API smoke check (`PARALLEL_API_KEY`).
- `scripts/smoke_extract.py`: Optional live Extract API smoke check (`PARALLEL_API_KEY`).
- `scripts/smoke_task_run.py`: Optional live Task run smoke check (`PARALLEL_API_KEY`).
- `scripts/verify_webhook_signature.py`: Verify `parallel-webhook-signature` using raw body + secret.
- `scripts/refresh_openapi_snapshot.sh`: Fetch and inspect/save the latest Parallel public OpenAPI spec.

## Common debugging checklist

- `401`: Missing/invalid `x-api-key`.
- `402`: Account lacks credit.
- `403`: Invalid processor or forbidden feature.
- `404`: Wrong `run_id` / `taskgroup_id`, or fetching result for failed/missing run.
- `408`: `/result` timed out while run is still active.
- `422`: Payload/schema validation error (most common integration bug).
- `429`: Rate limit exceeded (check endpoint- and processor-specific quotas).

## Refresh workflow (when user asks for latest docs behavior)

1. Run `scripts/refresh_openapi_snapshot.sh` (dry run) to inspect endpoint/schema changes.
2. Run `scripts/refresh_openapi_snapshot.sh --write` to save `references/generated/public-openapi.json` and summary.
3. Update the specific `references/*.md` files affected by the diff.
4. Re-run script `--help` checks and optional smoke tests.

## Constraints and caveats

- Parallel docs are Mintlify pages and can change quickly; prefer links + paraphrase over stale copied text.
- Processor names and `parallel-beta` versions are not stable forever.
- Search and Extract APIs are currently beta endpoints (`/v1beta/search`, `/v1beta/extract`).
- Some Task features are beta-gated even on `/v1/tasks/runs` (for example SSE/webhooks/MCP fields).
