# Search API (Beta)

Use this file to implement or debug Parallel Search API calls (`POST /v1beta/search`).

## Endpoint and auth

- Endpoint: `POST https://api.parallel.ai/v1beta/search`
- Headers:
  - `x-api-key: <PARALLEL_API_KEY>`
  - `Content-Type: application/json`
  - `parallel-beta: search-extract-2025-10-10` (required for current Search beta usage shown in docs/examples)

## Core request shape (`SearchRequest`)

Key fields from the OpenAPI schema:

- `mode`: `one-shot` | `agentic` | `fast` (default `one-shot`)
- `objective`: natural-language search objective
- `search_queries`: optional keyword queries (traditional search strings/operators)
- `max_results`: upper bound on results (docs best-practices mention current max 20)
- `excerpts`: excerpt controls (`max_chars_per_result`, `max_chars_total`)
- `source_policy`: domain/date filtering
- `fetch_policy`: cache-vs-live fetch behavior

Requirement:

- Provide at least one of `objective` or `search_queries`.

## Mode selection (practical)

- `one-shot`: richer results and longer excerpts for answering a question from one request.
- `agentic`: concise, token-efficient results for iterative agent loops.
- `fast`: lower latency tradeoff; works best with a sharp objective and strong keyword queries.

Rule of thumb:

- Use `one-shot` for human-facing answer assembly.
- Use `agentic` when another agent/model will do follow-up searching.
- Use `fast` for latency-sensitive ranking/filtering pipelines.

## Source policy (`SourcePolicy`)

Fields:

- `include_domains`: allowlist domains/extensions
- `exclude_domains`: blocklist domains/extensions
- `after_date`: RFC 3339 date (`YYYY-MM-DD`) for publish-date filtering

Accepted domain inputs (docs examples + schema):

- Plain domains: `wikipedia.org`, `usa.gov`
- Subdomains: `subdomain.example.gov`
- Bare domain extensions: `.gov`, `.edu`, `.co.uk`

Current docs guidance highlights:

- Max 10 `include_domains`
- Max 10 `exclude_domains`
- Prefer apex domains over deep subdomains when you want broad coverage
- Do not include scheme/path (for example use `nytimes.com`, not `https://nytimes.com/foo`)

## Fetch policy (`FetchPolicy`)

Use to control cache freshness vs latency:

- `max_age_seconds`: trigger live fetch if cache older than threshold (minimum 600s)
- `timeout_seconds`: timeout for live fetch attempts
- `disable_cache_fallback`: if `true`, error instead of falling back to stale cache

Use `fetch_policy` only when freshness requirements matter enough to justify latency/reliability tradeoffs.

## Response shape (`SearchResponse`)

Primary fields:

- `search_id`
- `results[]` (ordered by relevance)
  - `url`
  - `title`
  - `publish_date`
  - `excerpts[]` (markdown text)
- `warnings[]` (if any)
- `usage[]` (SKU usage counts)

Implementation guidance:

- Always log/store `search_id` for support/debugging.
- Preserve `warnings` because they often explain degraded behavior or fallback.
- Treat `publish_date` as optional.

## Example payloads

### cURL (domain/date constrained research)

```bash
curl --request POST \
  --url https://api.parallel.ai/v1beta/search \
  --header 'Content-Type: application/json' \
  --header "x-api-key: $PARALLEL_API_KEY" \
  --header 'parallel-beta: search-extract-2025-10-10' \
  --data '{
    "mode": "one-shot",
    "objective": "Find recent U.S. federal guidance on AI procurement",
    "max_results": 8,
    "source_policy": {
      "include_domains": [".gov"],
      "after_date": "2024-01-01"
    },
    "excerpts": {
      "max_chars_per_result": 2500,
      "max_chars_total": 10000
    }
  }'
```

### Python SDK (`parallel-web`)

```python
from parallel import Parallel

client = Parallel(api_key="API Key")

resp = client.beta.search(
    objective="Latest SEC cybersecurity disclosure guidance",
    mode="agentic",
    search_queries=["site:sec.gov cybersecurity disclosure guidance"],
    source_policy={"include_domains": ["sec.gov"]},
)

for r in resp.results:
    print(r.url, r.publish_date)
```

### TypeScript SDK (`parallel-web`)

```ts
import Parallel from "parallel-web";

const client = new Parallel({ apiKey: process.env.PARALLEL_API_KEY! });

const resp = await client.beta.search({
  mode: "fast",
  objective: "Find earnings release for Company X Q4 2025",
  search_queries: ["Company X Q4 2025 earnings release"],
  max_results: 5,
});

for (const item of resp.results) {
  console.log(item.url, item.title);
}
```

## Common Search API mistakes

- Missing `parallel-beta` header for Search beta.
- Sending neither `objective` nor `search_queries`.
- Passing full URLs in `include_domains` / `exclude_domains`.
- Treating `publish_date` as always present.
- Ignoring `warnings` and blaming ranking quality.
- Using `fast` mode for complex research questions with weak query inputs.

## Debugging checklist

- `422`: validate payload shape and field names; run `scripts/validate_search_payload.py`.
- `429`: lower `max_results`, reduce concurrency, add retries/backoff.
- Low-quality results: improve `objective`, add `search_queries`, constrain `source_policy`, or switch modes.
- Stale content concern: add `fetch_policy` with `max_age_seconds` and timeout tuning.

## Sources

- Search Quickstart: https://docs.parallel.ai/search/search-quickstart
- Search Best Practices: https://docs.parallel.ai/search/best-practices
- Search Modes: https://docs.parallel.ai/search/modes
- Search Source Policy: https://docs.parallel.ai/search/source-policy
- Search API Reference: https://docs.parallel.ai/api-reference/search-beta/search
- Public OpenAPI Spec: https://docs.parallel.ai/public-openapi.json
