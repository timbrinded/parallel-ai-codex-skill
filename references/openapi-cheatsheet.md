# OpenAPI Cheatsheet (Search + Task APIs)

Use this file when you need exact endpoint paths, schema names, enums, or to diff Parallel API changes.

## Primary source

- `https://docs.parallel.ai/public-openapi.json`

## High-value endpoint paths (this skill scope)

### Search

- `POST /v1beta/search`

### Task runs (v1)

- `POST /v1/tasks/runs`
- `GET /v1/tasks/runs/{run_id}`
- `GET /v1/tasks/runs/{run_id}/input`
- `GET /v1/tasks/runs/{run_id}/result`

### Task events and groups (beta)

- `GET /v1beta/tasks/runs/{run_id}/events`
- `POST /v1beta/tasks/groups`
- `GET /v1beta/tasks/groups/{taskgroup_id}`
- `GET /v1beta/tasks/groups/{taskgroup_id}/events`
- `POST /v1beta/tasks/groups/{taskgroup_id}/runs`
- `GET /v1beta/tasks/groups/{taskgroup_id}/runs`
- `GET /v1beta/tasks/groups/{taskgroup_id}/runs/{run_id}`

## High-value schemas

### Search

- `SearchRequest`
- `SearchResponse`
- `WebSearchResult`
- `SourcePolicy`
- `ExcerptSettings`
- `FetchPolicy`
- `Warning`
- `UsageItem`

### Task runs / outputs

- `BetaTaskRunInput`
- `TaskRun`
- `TaskRunInput`
- `TaskSpec`
- `TaskRunResult`
- `BetaTaskRunResult`
- `TaskRunTextOutput`
- `TaskRunJsonOutput`

### Task events / groups

- `TaskRunEvent`
- `TaskRunProgressMessageEvent`
- `TaskRunProgressStatsEvent`
- `TaskGroupResponse`
- `TaskGroupStatus`
- `TaskGroupRunRequest`
- `TaskGroupRunResponse`
- `TaskGroupStatusEvent`
- `Webhook`

## Useful enums / values (from current spec)

### `ParallelBeta` enum (spec may expand)

Current spec enum includes:

- `mcp-server-2025-07-17`
- `events-sse-2025-07-24`
- `webhook-2025-08-12`
- `findall-2025-09-15`
- `search-extract-2025-10-10`
- `field-basis-2025-11-25`

### Task run statuses

- `queued`
- `action_required`
- `running`
- `completed`
- `failed`
- `cancelling`
- `cancelled`

## `jq` commands for local inspection

List scoped paths:

```bash
curl -s https://docs.parallel.ai/public-openapi.json \
  | jq -r '.paths | keys[]' \
  | rg 'search|tasks'
```

Inspect Search request/response schemas:

```bash
curl -s https://docs.parallel.ai/public-openapi.json \
  | jq '.components.schemas.SearchRequest, .components.schemas.SearchResponse'
```

Inspect Task beta fields and webhook schema:

```bash
curl -s https://docs.parallel.ai/public-openapi.json \
  | jq '.components.schemas.BetaTaskRunInput, .components.schemas.Webhook'
```

Inspect beta header enum:

```bash
curl -s https://docs.parallel.ai/public-openapi.json \
  | jq '.components.schemas.ParallelBeta'
```

## Refresh workflow

- Dry run (summary only): `scripts/refresh_openapi_snapshot.sh`
- Write snapshot + summary: `scripts/refresh_openapi_snapshot.sh --write`
- Output files (when written):
  - `references/generated/public-openapi.json`
  - `references/generated/openapi-summary.txt`

## Maintenance checklist

- Compare endpoint paths for additions/removals.
- Check `ParallelBeta` enum changes.
- Check `SearchRequest` and `BetaTaskRunInput` field changes.
- Check event schema discriminator mappings for SSE changes.
- Update examples and validators if schema semantics moved.

## Sources

- Public OpenAPI Spec: https://docs.parallel.ai/public-openapi.json
- API Reference (Search Beta): https://docs.parallel.ai/api-reference/search-beta/search
- API Reference (Tasks v1): https://docs.parallel.ai/api-reference/tasks-v1/create-task-run
- API Reference (Tasks Beta): https://docs.parallel.ai/api-reference/tasks-beta/create-task-group
