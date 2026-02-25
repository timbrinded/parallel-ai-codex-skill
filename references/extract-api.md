# Extract API (Beta)

Use this file to implement or debug Parallel Extract API calls (`POST /v1beta/extract`).

## Endpoint and auth

- Endpoint: `POST https://api.parallel.ai/v1beta/extract`
- Headers:
  - `x-api-key: <PARALLEL_API_KEY>`
  - `Content-Type: application/json`
  - `parallel-beta: search-extract-2025-10-10` (required per current API reference/OpenAPI description)

## What Extract does

Extract converts specific public URLs into clean markdown content for LLM use.

Unlike Search, you provide the target URLs directly. Extract can return:

- focused `excerpts` (relevance-filtered snippets)
- `full_content` (top-of-page markdown content, optionally truncated)

You can also provide `objective` and/or `search_queries` to focus excerpt selection.

## Request shape (`ExtractRequest`)

Required:

- `urls` (array of URL strings)

Optional:

- `objective` (string): focus extraction on a natural-language goal
- `search_queries` (array[string]): focus extraction on keyword queries
- `fetch_policy` (`FetchPolicy`): cache vs live-fetch behavior
- `excerpts` (bool or `ExcerptSettings`, default `true`)
- `full_content` (bool or `FullContentSettings`, default `false`)

### `excerpts` options

- `true` / `false`
- object form (`ExcerptSettings`):
  - `max_chars_per_result`
  - `max_chars_total`

### `full_content` options

- `true` / `false`
- object form (`FullContentSettings`):
  - `max_chars_per_result`

## Request design guidance

- Use `excerpts` when you need relevant passages, not whole pages.
- Use `full_content` when you need the page body for downstream parsing/classification.
- Use both when you want a fast “relevant snippet + fallback full page” response.
- Provide `objective` and/or `search_queries` whenever you request excerpts; otherwise excerpts may be redundant with full content.
- Use `fetch_policy` when freshness matters and you can tolerate higher latency.

## Response shape (`ExtractResponse`)

Fields:

- `extract_id`
- `results[]` (`ExtractResult`)
  - `url`
  - `title`
  - `publish_date`
  - `excerpts[]` (optional)
  - `full_content` (optional markdown)
- `errors[]` (`ExtractError`) for URLs that failed extraction
  - `url`
  - `error_type`
  - `http_status_code`
  - `content`
- `warnings[]`
- `usage[]`

Implementation guidance:

- Treat `results` and `errors` as complementary; do not assume all URLs succeed.
- Preserve `extract_id` for support/debugging.
- Log failed URLs with `error_type` and `http_status_code` to distinguish fetch vs parsing failures.

## Examples

### cURL (focused excerpts + full content)

```bash
curl --request POST \
  --url https://api.parallel.ai/v1beta/extract \
  --header 'Content-Type: application/json' \
  --header "x-api-key: $PARALLEL_API_KEY" \
  --header 'parallel-beta: search-extract-2025-10-10' \
  --data '{
    "urls": [
      "https://www.example.com"
    ],
    "objective": "Find statements about enterprise pricing",
    "excerpts": {"max_chars_per_result": 2000},
    "full_content": {"max_chars_per_result": 12000}
  }'
```

### Python SDK (`parallel-web`)

```python
from parallel import Parallel

client = Parallel(api_key="API Key")

resp = client.beta.extract(
    urls=["https://www.example.com"],
    objective="Find the support SLA and uptime commitments",
    excerpts=True,
    full_content=False,
)

print(resp.extract_id)
for r in resp.results:
    print(r.url, r.title)
for e in resp.errors:
    print("ERROR", e.url, e.error_type, e.http_status_code)
```

### TypeScript SDK (`parallel-web`)

```ts
import Parallel from "parallel-web";

const client = new Parallel({ apiKey: process.env.PARALLEL_API_KEY! });

const resp = await client.beta.extract({
  urls: ["https://www.example.com"],
  search_queries: ["pricing", "enterprise plan"],
  excerpts: { max_chars_per_result: 2000, max_chars_total: 4000 },
  full_content: false,
});

console.log(resp.extract_id, resp.results.length, resp.errors.length);
```

## Common mistakes

- Missing `parallel-beta: search-extract-2025-10-10`.
- Sending `urls` as a string instead of array.
- Requesting neither `excerpts` nor `full_content` (no useful content requested).
- Expecting all URLs to succeed and ignoring `errors[]`.
- Forgetting to provide `objective`/`search_queries` when relying on focused excerpts.
- Treating `publish_date` as always present.

## Debugging checklist

- `422`: validate request shape with `scripts/validate_extract_payload.py`.
- Empty/weak excerpts: provide a clearer `objective` and/or `search_queries`, or request `full_content`.
- Staleness concern: tune `fetch_policy.max_age_seconds` and `timeout_seconds`.
- Partial success: inspect `errors[]`, retry failed URLs selectively instead of retrying the full batch.

## Sources

- Extract Quickstart: https://docs.parallel.ai/extract/extract-quickstart
- Extract Best Practices: https://docs.parallel.ai/extract/best-practices
- Extract API Reference: https://docs.parallel.ai/api-reference/extract-beta/extract
- Public OpenAPI Spec: https://docs.parallel.ai/public-openapi.json
