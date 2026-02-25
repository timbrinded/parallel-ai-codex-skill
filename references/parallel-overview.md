# Parallel.ai Overview (Search + Task API)

## Purpose

Use this file for shared integration facts: auth, SDK packages, endpoint families, beta headers, and operational constraints.

## Authentication and base URL

- Base API host: `https://api.parallel.ai`
- Auth header: `x-api-key: <PARALLEL_API_KEY>`
- Most examples in docs and OpenAPI use JSON over HTTPS.

## Official SDKs (current docs navigation)

- Python package: `parallel-web`
- TypeScript package: `parallel-web`

Prefer SDKs for app integrations, but use raw HTTP/cURL when debugging exact headers or payloads.

## Endpoint families covered by this skill

- Search API (beta): `POST /v1beta/search`
- Task API v1 runs:
  - `POST /v1/tasks/runs`
  - `GET /v1/tasks/runs/{run_id}`
  - `GET /v1/tasks/runs/{run_id}/input`
  - `GET /v1/tasks/runs/{run_id}/result`
- Task API beta groups/events:
  - `POST /v1beta/tasks/groups`
  - `GET /v1beta/tasks/groups/{taskgroup_id}`
  - `POST /v1beta/tasks/groups/{taskgroup_id}/runs`
  - `GET /v1beta/tasks/groups/{taskgroup_id}/runs`
  - `GET /v1beta/tasks/groups/{taskgroup_id}/events`
  - `GET /v1beta/tasks/runs/{run_id}/events`

## Versioning and beta headers

Parallel uses both versioned paths (`/v1`, `/v1beta`) and beta feature flags in the `parallel-beta` header.

Examples visible in docs/OpenAPI include:

- `search-extract-2025-10-10` (Search/Extract beta features)
- `events-sse-2025-07-24` (Task run SSE events / `enable_events`)
- `mcp-server-2025-07-17` (Task MCP servers)
- `webhook-2025-08-12` (Task webhooks)
- `field-basis-2025-11-25` (field-level basis; docs/OpenAPI enum)

Guideline:

- Add beta headers only when using beta-gated fields/features.
- Keep beta values explicit and configurable in code.
- Re-verify beta values before shipping because values are date-stamped and may change.

## Rate limits (docs summary, verify before production rollout)

Docs list endpoint- and processor-specific quotas. Examples from the current rate-limit page include:

- Search API: request and result-rate quotas (for example 300 RPM and 2000 results/min)
- Task API v1 create/retrieve endpoints: separate quotas by endpoint
- Task API processor quotas differ by processor family (higher-end processors usually lower RPM)

Implementation guidance:

- Treat `429` as retryable with backoff and jitter.
- Split high-volume workloads into Task Groups and batch responsibly.
- Add monitoring around create vs retrieve endpoints separately.

## Common errors

Common errors across docs and OpenAPI examples:

- `401` unauthorized (missing/invalid API key)
- `402` payment required (insufficient credit)
- `403` forbidden (invalid processor/feature)
- `404` not found (run/taskgroup missing)
- `408` timeout on blocking result retrieval
- `422` validation errors
- `429` quota exceeded

## Research snapshot

- Last curated for this skill: `2026-02-25`
- Refresh source of truth: `https://docs.parallel.ai/public-openapi.json` and linked docs pages

## Sources

- Parallel Docs: https://docs.parallel.ai/
- Public OpenAPI Spec: https://docs.parallel.ai/public-openapi.json
- Rate Limits: https://docs.parallel.ai/getting-started/rate-limits
- Warnings and Errors: https://docs.parallel.ai/resources/warnings-and-errors
