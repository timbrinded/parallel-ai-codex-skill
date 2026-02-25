# Task API Streams and Task Groups (Beta)

Use this file for Task SSE event streaming and Task Group batch orchestration.

## Task run SSE events (`/v1beta/tasks/runs/{run_id}/events`)

Endpoint:

- `GET /v1beta/tasks/runs/{run_id}/events`

OpenAPI notes:

- Returns `text/event-stream`
- Streams progress updates and state changes
- Event frequency is reduced if the run was created without `enable_events=true`

### Enabling richer run events

Docs indicate `enable_events` is beta-gated.

To record progress events during run creation, set:

- `enable_events: true`
- `parallel-beta: events-sse-2025-07-24`

### Event types (current OpenAPI discriminator mappings)

Progress stats:

- `task_run.progress_stats`

Progress messages:

- `task_run.progress_msg.plan`
- `task_run.progress_msg.search`
- `task_run.progress_msg.result`
- `task_run.progress_msg.tool_call`
- `task_run.progress_msg.exec_status`

Run state / terminal updates:

- `task_run.state`

Errors:

- `error`

Implementation guidance:

- Parse by `type` field.
- Treat `task_run.state` terminal statuses as completion/cancel/failure events.
- Keep a timeout/reconnect strategy for long-running streams.

## Task Groups (beta)

Task Groups help batch and track many Task runs.

### Core flow

1. Create group: `POST /v1beta/tasks/groups`
2. Add runs: `POST /v1beta/tasks/groups/{taskgroup_id}/runs`
3. Observe group status: `GET /v1beta/tasks/groups/{taskgroup_id}`
4. Stream group events or runs:
   - `GET /v1beta/tasks/groups/{taskgroup_id}/events`
   - `GET /v1beta/tasks/groups/{taskgroup_id}/runs`

### Add-runs request (`TaskGroupRunRequest`)

Fields:

- `inputs[]` (required): list of task run payloads (`BetaTaskRunInput`)
- `default_task_spec` (optional): shared `TaskSpec` default for runs

OpenAPI docs note:

- Up to 1,000 runs per add-runs request
- Split larger workloads across multiple requests

### Group status (`TaskGroupStatus`)

Fields include:

- `num_task_runs`
- `task_run_status_counts`
- `is_active`
- `status_message`
- `modified_at`

Use this for progress bars and batch monitoring.

## Group event streaming (`/events`)

Endpoint:

- `GET /v1beta/tasks/groups/{taskgroup_id}/events`

OpenAPI behavior:

- `text/event-stream`
- Streams TaskGroup status updates and run completions
- Connection may stay open up to ~1 hour while at least one run remains active
- Supports resume via `last_event_id`

Event types:

- `task_group_status`
- `task_run.state`
- `error`

## Group runs streaming (`/runs`)

Endpoint:

- `GET /v1beta/tasks/groups/{taskgroup_id}/runs`

Important query params:

- `last_event_id` (resume cursor)
- `status` (filter by terminal/non-terminal statuses)
- `include_input` (include run input in stream events)
- `include_output` (include output in stream events when completed)

Use this endpoint when you want the stream of run state transitions and optionally inputs/outputs.

## Python and TypeScript patterns

### Python (run events)

```python
from parallel import Parallel

client = Parallel(api_key="API Key")

for event in client.beta.task_run.events(run_id="trun_..."):
    print(event)
```

### TypeScript (group events)

```ts
import Parallel from "parallel-web";

const client = new Parallel({ apiKey: process.env.PARALLEL_API_KEY! });

const stream = await client.beta.taskGroup.events("taskgroup_...");
for await (const event of stream) {
  console.log(event.type, event);
}
```

## Operational guidance

- Persist `last_event_id` for resumable consumers.
- Process events idempotently; reconnects may replay near-boundary events.
- Use `task_group_status` for aggregate progress and `task_run.state` for per-run completion records.
- For very large groups, prefer streamed consumption over repeated polling of individual runs.
- Expect mixed event payloads; use robust runtime type guards.

## Common mistakes

- Forgetting `enable_events` and beta header, then expecting rich run progress events.
- Parsing SSE as plain JSON lines without SSE framing support.
- Dropping `last_event_id` and losing resumability.
- Using `include_output=true` on huge groups without considering memory/backpressure.

## Sources

- Task SSE: https://docs.parallel.ai/task-api/task-sse
- Group API: https://docs.parallel.ai/task-api/group-api
- Tasks v1 Stream Task Run Events: https://docs.parallel.ai/api-reference/tasks-v1/stream-task-run-events
- Tasks Beta Create Group: https://docs.parallel.ai/api-reference/tasks-beta/create-task-group
- Tasks Beta Add Runs to Group: https://docs.parallel.ai/api-reference/tasks-beta/add-runs-to-task-group
- Tasks Beta Fetch Task Group Runs: https://docs.parallel.ai/api-reference/tasks-beta/fetch-task-group-runs
- Tasks Beta Stream Task Group Events: https://docs.parallel.ai/api-reference/tasks-beta/stream-task-group-events
- Public OpenAPI Spec: https://docs.parallel.ai/public-openapi.json
