# Task API Webhooks

Use this file to implement Task completion webhooks and verify signatures safely.

## What webhooks do (Task API)

Parallel Task runs can send an HTTP `POST` callback when a run completes.

OpenAPI (`Webhook` schema) and docs indicate:

- `webhook.url` is required
- `webhook.event_types` currently supports `task_run.status`
- Webhook support is beta-gated on Task runs

## Enabling webhooks

When creating a task run on `POST /v1/tasks/runs`, include:

- `webhook`: `{ "url": "https://your-app.example.com/parallel/webhook" }`
- `parallel-beta: webhook-2025-08-12`

Docs note this feature is API-request based and not available in the Python SDK path described in the OpenAPI schema notes. Prefer raw HTTP or verify SDK support before assuming parity.

## Signature verification (required)

Docs describe webhook signing headers including:

- `parallel-webhook-id`
- `parallel-webhook-timestamp`
- `parallel-webhook-signature`

Docs also describe an HMAC-SHA256 signature verification pattern using the raw request body. Current webhook setup docs describe a signed payload format equivalent to:

- `"<webhook_id>.<webhook_timestamp>.<raw_request_body>"`

Verification guidance from docs:

- Use the raw request body bytes (before JSON parsing/reformatting)
- Compare against the signature(s) in `parallel-webhook-signature`
- Reject if timestamp is outside an allowed tolerance window (docs examples use ~5 minutes)

Use `scripts/verify_webhook_signature.py` for local verification and debugging.

## Server implementation checklist

- Read raw body bytes first.
- Read signature headers.
- Verify HMAC before parsing JSON.
- Enforce replay window (timestamp tolerance).
- Return `2xx` quickly after verification and queue heavy processing asynchronously.
- Make processing idempotent by webhook ID and/or run ID.
- Log `run_id`, webhook ID, timestamp, and verification result (never log secrets).

## Example task run create payload (raw HTTP)

```json
{
  "processor": "base",
  "input": "Summarize this topic and return a short answer.",
  "webhook": {
    "url": "https://example.com/api/parallel/task-webhook",
    "event_types": ["task_run.status"]
  }
}
```

Required headers:

```http
x-api-key: <PARALLEL_API_KEY>
parallel-beta: webhook-2025-08-12
Content-Type: application/json
```

## Python verification sketch

```python
# See scripts/verify_webhook_signature.py for a reusable CLI implementation.
import hmac
import hashlib

signed = f"{webhook_id}.{timestamp}.".encode("utf-8") + raw_body
expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
valid = hmac.compare_digest(expected, provided_hex)
```

## TypeScript/Node verification sketch

```ts
import crypto from "node:crypto";

const signed = Buffer.concat([
  Buffer.from(`${webhookId}.${timestamp}.`, "utf8"),
  rawBody,
]);
const expected = crypto.createHmac("sha256", secret).update(signed).digest("hex");
const valid = crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(signatureHex));
```

## Local testing workflow

1. Expose local server via tunnel (for example ngrok/Cloudflare Tunnel).
2. Configure webhook URL in task run payload.
3. Capture raw headers/body from incoming request.
4. Run `scripts/verify_webhook_signature.py` to confirm your verifier logic.
5. Add automated unit tests in your application for valid/invalid/replay cases.

## Common mistakes

- Parsing JSON before signature verification (body bytes change).
- Using parsed JSON stringification instead of raw bytes.
- Ignoring timestamp replay protection.
- Forgetting webhook beta header.
- Assuming webhook payload schema without logging/capturing a real sample in staging.

## Sources

- Task Webhooks: https://docs.parallel.ai/task-api/webhooks
- Webhook Setup (signing details): https://docs.parallel.ai/resources/webhook-setup
- Tasks v1 Create Task Run API Reference: https://docs.parallel.ai/api-reference/tasks-v1/create-task-run
- Public OpenAPI Spec: https://docs.parallel.ai/public-openapi.json
