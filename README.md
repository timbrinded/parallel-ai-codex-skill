# Parallel.ai Codex Skill (Search + Extract + Task API)

This repository is a Codex skill focused on building and debugging integrations with the Parallel.ai Search API, Extract API, and Task API.

It includes:

- A production-ready `SKILL.md` for Codex skill triggering and workflow guidance
- Curated references for Search, Extract, Task runs, SSE/task groups, and webhooks
- Utility scripts for payload validation, webhook signature verification, OpenAPI refresh, and optional live smoke tests
- Tests for the bundled CLI scripts

## Why This Exists

Parallel.ai has a fast-moving API surface (beta headers, SSE features, evolving processors, schema details). This skill exists to give Codex a compact but high-signal workflow for:

- Choosing the right Parallel endpoint and mode/processor
- Building valid payloads (`SearchRequest`, `ExtractRequest`, `TaskSpec`, `SourcePolicy`, etc.)
- Debugging common failures (`422`, `408`, beta header mismatches)
- Handling SSE streams and Task Groups correctly
- Verifying Task webhook signatures safely using raw request bodies

## What’s In The Repo

- `SKILL.md`: Main Codex skill instructions (lean orchestration + pointers)
- `agents/openai.yaml`: UI metadata for skill listing/chips
- `references/`: Detailed docs and examples (Search, Extract, Task)
- `scripts/`: CLI helpers and optional smoke checks
- `tests/`: CLI-level tests for the scripts

## Requirements

- Python 3.10+ (tested with local `python3`)
- Bash (for `scripts/refresh_openapi_snapshot.sh`)
- `curl` and `jq` (for OpenAPI refresh script)
- Optional: `PARALLEL_API_KEY` for live smoke tests

## Using This As a Codex Skill

This repository itself is the skill folder (`parallel-ai-codex-skill`).

Typical installation options:

1. Copy or symlink this repo into your Codex skills directory (`$CODEX_HOME/skills/parallel-ai-codex-skill`).
2. Ensure the folder contains `SKILL.md` at the top level.
3. Trigger it in Codex by asking for Parallel Search/Task API integration help.

Example trigger contexts:

- “Implement Parallel Search API with source policy filters”
- “Use Parallel Extract API to get focused excerpts/full content from URLs”
- “Debug Parallel Task API `TaskSpec` 422 error”
- “Stream Parallel task group events with SSE”
- “Verify Parallel webhook signature in FastAPI/Node”

## Validation and Development

### Structural validation (skill format)

```bash
python3 "${CODEX_HOME:-$HOME/.codex}"/skills/.system/skill-creator/scripts/quick_validate.py .
```

### Run tests

```bash
python3 -m unittest discover -s tests -v
```

### Script help (quick sanity)

```bash
scripts/validate_search_payload.py --help
scripts/validate_extract_payload.py --help
scripts/validate_task_payload.py --help
scripts/verify_webhook_signature.py --help
scripts/smoke_search.py --help
scripts/smoke_extract.py --help
scripts/smoke_task_run.py --help
scripts/refresh_openapi_snapshot.sh --help
```

## Optional Live Smoke Tests

Set your API key:

```bash
export PARALLEL_API_KEY=...
```

Run Search smoke test:

```bash
scripts/smoke_search.py --objective "What was the GDP of France in 2023?"
```

Run Extract smoke test:

```bash
scripts/smoke_extract.py --url https://www.example.com --full-content
```

Run Task run smoke test:

```bash
scripts/smoke_task_run.py --structured-output --poll
```

## OpenAPI Refresh Workflow

Dry run (print summary only):

```bash
scripts/refresh_openapi_snapshot.sh
```

Write snapshot + summary:

```bash
scripts/refresh_openapi_snapshot.sh --write
```

Generated files (gitignored):

- `references/generated/public-openapi.json`
- `references/generated/openapi-summary.txt`

## Links

- Parallel Docs: https://docs.parallel.ai/
- Parallel Public OpenAPI Spec: https://docs.parallel.ai/public-openapi.json
- Search Quickstart: https://docs.parallel.ai/search/search-quickstart
- Search Modes: https://docs.parallel.ai/search/modes
- Extract Quickstart: https://docs.parallel.ai/extract/extract-quickstart
- Extract Best Practices: https://docs.parallel.ai/extract/best-practices
- Task Quickstart: https://docs.parallel.ai/task-api/task-quickstart
- Task Processor Selection: https://docs.parallel.ai/task-api/guides/choose-a-processor
- Task SSE: https://docs.parallel.ai/task-api/task-sse
- Task Webhooks: https://docs.parallel.ai/task-api/webhooks
- Webhook Setup / Signing: https://docs.parallel.ai/resources/webhook-setup
- Search API Reference: https://docs.parallel.ai/api-reference/search-beta/search
- Extract API Reference: https://docs.parallel.ai/api-reference/extract-beta/extract
- Tasks v1 API Reference: https://docs.parallel.ai/api-reference/tasks-v1/create-task-run
- Tasks Beta API Reference: https://docs.parallel.ai/api-reference/tasks-beta/create-task-group

## Notes

- This repo intentionally includes a `README.md` and `tests/` for maintainability, even though a minimal skill only requires `SKILL.md`.
- API/beta-header details are time-sensitive. Re-verify against the OpenAPI spec and docs before shipping production changes.
