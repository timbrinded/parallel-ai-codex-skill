# Task API Runs (v1)

Use this file for Task run creation, polling/blocking result retrieval, processor selection, and `TaskSpec` structured outputs.

## Endpoint lifecycle (v1)

1. Create run: `POST /v1/tasks/runs`
2. Check status: `GET /v1/tasks/runs/{run_id}`
3. Retrieve submitted input (optional): `GET /v1/tasks/runs/{run_id}/input`
4. Retrieve output (blocking): `GET /v1/tasks/runs/{run_id}/result?timeout=<seconds>`

Notes from OpenAPI:

- Create returns immediately with a `TaskRun` in status `queued` (`202 Accepted`).
- `/result` blocks until completion or timeout; returns `408` if still active.
- `/result` can return beta output shape when beta headers are used.

## Core create payload (`BetaTaskRunInput` superset)

Required:

- `processor` (string)
- `input` (string or JSON object)

Common optional fields:

- `metadata` (small user tags)
- `source_policy` (domain allow/deny rules for web research)
- `task_spec` (`TaskSpec` with input/output schema)
- `previous_interaction_id` (context reuse)

Beta-gated fields on Task runs (v1 endpoint still):

- `enable_events` -> requires `parallel-beta: events-sse-2025-07-24`
- `mcp_servers` -> requires `parallel-beta: mcp-server-2025-07-17`
- `webhook` -> requires `parallel-beta: webhook-2025-08-12`

## Processor selection (docs guidance snapshot)

Parallel docs list a processor lineup optimized for latency/quality/cost tradeoffs. Current docs guidance (re-check before shipping) references processors such as:

- `lite`
- `base`
- `core`
- `core2x`
- `pro`
- `ultra`
- `ultra2x`
- `ultra4x`
- `ultra8x`
- fast variants like `base-fast`, `core-fast`, `pro-fast`
- vision variants like `vision`, `vision_pro`
- deep research variants like `deep`, `deepv2`

Selection heuristics:

- Start with `base`/`core` for general structured extraction.
- Use `pro`/`ultra` tiers when answer quality or reasoning depth dominates cost.
- Use `*-fast` variants for latency-sensitive paths.
- Use `vision*` when input includes images or image-heavy pages.
- Use `deep`/`deepv2` for deep-research style workflows.

Always verify current names/availability in `task-api/guides/choose-a-processor` before hard-coding.

## `TaskSpec` and structured outputs

`TaskSpec` fields:

- `output_schema` (required)
- `input_schema` (optional)

Accepted schema forms (OpenAPI/docs):

- JSON schema object (`{"type":"json","json_schema": ...}` style via SDKs / API docs wrappers)
- Text schema/description
- Bare string (treated as text schema description)
- Auto output schema (`{"type":"auto"}`) or omit `task_spec`

Practical patterns:

- Use JSON schema for machine-parseable responses.
- Add field descriptions to improve output quality.
- Keep schema narrow (`additionalProperties: false`) to stabilize results.
- Use `input_schema` when callers send JSON inputs and you want validation feedback.

### TaskSpec docs limits and constraints (important)

Current docs mention constraints such as:

- `task_spec` size limits (and combined `task_spec` + `input` size limits)
- Max property count and nesting depth for JSON schemas
- Unsupported JSON Schema keywords for `input_schema` (for example `anyOf`, `oneOf`, `allOf`, `not`, `if`, `then`, `else`, `dependentSchemas`, `dependentRequired`, `patternProperties`)

Use `scripts/validate_task_payload.py` to catch common violations before calling the API.

## Source policy in Task runs

Task API supports `source_policy` for web research constraints:

- `include_domains`
- `exclude_domains`

Docs note `after_date` filtering is a Search API capability and is not currently supported in Task source policy.

## Polling vs blocking result retrieval

### Polling pattern

Use when you need custom timeouts/retries or UI progress loops:

1. Create run
2. Poll `GET /v1/tasks/runs/{run_id}` until status terminal
3. If `completed`, call `/result`
4. If `failed`, inspect `run.error` and `warnings`

### Blocking `/result` pattern

Use when synchronous flow is acceptable:

- Call `/result` directly with `timeout` (default in OpenAPI examples is `600`)
- Handle `408` as non-terminal and retry later

## Examples

### cURL (structured JSON output)

```bash
curl --request POST \
  --url https://api.parallel.ai/v1/tasks/runs \
  --header 'Content-Type: application/json' \
  --header "x-api-key: $PARALLEL_API_KEY" \
  --data '{
    "processor": "base",
    "input": "What was France GDP in 2023? Return a compact answer.",
    "task_spec": {
      "output_schema": {
        "type": "json",
        "json_schema": {
          "type": "object",
          "properties": {
            "gdp": {"type": "string", "description": "GDP with units and year"},
            "currency": {"type": "string"}
          },
          "required": ["gdp", "currency"],
          "additionalProperties": false
        }
      }
    }
  }'
```

### Python SDK (create + blocking result)

```python
from parallel import Parallel

client = Parallel(api_key="API Key")

run = client.task_run.create(
    input="Summarize the latest guidance on SBOMs for U.S. federal procurement.",
    processor="core",
)

result = client.task_run.result(run_id=run.run_id)
print(result.output)
```

### TypeScript SDK (polling)

```ts
import Parallel from "parallel-web";

const client = new Parallel({ apiKey: process.env.PARALLEL_API_KEY! });

const run = await client.taskRun.create({
  processor: "base",
  input: { company: "ExampleCo", quarter: "Q4 2025" },
  task_spec: {
    output_schema: {
      type: "json",
      json_schema: {
        type: "object",
        properties: {
          revenue: { type: "string" },
          citations: { type: "array", items: { type: "string" } },
        },
        required: ["revenue", "citations"],
        additionalProperties: false,
      },
    },
  },
});

while (true) {
  const status = await client.taskRun.retrieve(run.run_id);
  if (!status.is_active) break;
  await new Promise((r) => setTimeout(r, 2000));
}

const result = await client.taskRun.result(run.run_id);
console.log(result.output);
```

## Common Task run mistakes

- Invalid/unsupported processor name (`403`).
- Malformed `TaskSpec` or oversized schemas (`422`).
- Forgetting beta header when using `enable_events`, `mcp_servers`, or `webhook`.
- Assuming `/result` returns immediately; not handling `408`.
- Using Search-only `after_date` in Task `source_policy`.
- Ignoring `warnings` on `TaskRun` or `TaskRunResult`.

## Sources

- Task Quickstart: https://docs.parallel.ai/task-api/task-quickstart
- Task Deep Research Quickstart: https://docs.parallel.ai/task-api/task-deep-research
- Specify a Task: https://docs.parallel.ai/task-api/guides/specify-a-task
- Choose a Processor: https://docs.parallel.ai/task-api/guides/choose-a-processor
- Access Research Basis: https://docs.parallel.ai/task-api/guides/access-research-basis
- Task Source Policy: https://docs.parallel.ai/task-api/source-policy
- Tasks v1 API Reference: https://docs.parallel.ai/api-reference/tasks-v1/create-task-run
- Public OpenAPI Spec: https://docs.parallel.ai/public-openapi.json
