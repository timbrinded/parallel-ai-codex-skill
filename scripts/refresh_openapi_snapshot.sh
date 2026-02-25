#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
OUT_DIR="$ROOT_DIR/references/generated"
SPEC_URL="https://docs.parallel.ai/public-openapi.json"
WRITE=0

usage() {
  cat <<'USAGE'
Usage: scripts/refresh_openapi_snapshot.sh [--write] [--spec-url URL]

Fetch the Parallel public OpenAPI spec and print a compact summary.

Options:
  --write         Save files to references/generated/ (spec + summary)
  --spec-url URL  Override OpenAPI URL (default: https://docs.parallel.ai/public-openapi.json)
  -h, --help      Show help

Examples:
  scripts/refresh_openapi_snapshot.sh
  scripts/refresh_openapi_snapshot.sh --write
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --write)
      WRITE=1
      shift
      ;;
    --spec-url)
      [[ $# -ge 2 ]] || { echo "missing value for --spec-url" >&2; exit 2; }
      SPEC_URL="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

command -v curl >/dev/null 2>&1 || { echo "curl is required" >&2; exit 127; }
command -v jq >/dev/null 2>&1 || { echo "jq is required" >&2; exit 127; }

TMP_SPEC="$(mktemp)"
TMP_SUMMARY="$(mktemp)"
cleanup() {
  rm -f "$TMP_SPEC" "$TMP_SUMMARY"
}
trap cleanup EXIT

curl -fsSL "$SPEC_URL" -o "$TMP_SPEC"

GENERATED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
{
  echo "Parallel Public OpenAPI Summary"
  echo "Generated at (UTC): $GENERATED_AT"
  echo "Spec URL: $SPEC_URL"
  echo
  echo "Scoped paths (search + extract + tasks):"
  jq -r '.paths | keys[] | select(test("^/v1beta/(search|extract)$|^/v1(beta)?/tasks"))' "$TMP_SPEC" | sort
  echo
  echo "ParallelBeta enum (if present):"
  jq -r '
    .components.schemas.ParallelBeta.anyOf[]? | select(.enum) | .enum[]
  ' "$TMP_SPEC" 2>/dev/null || true
  echo
  echo "Key schemas present:"
  jq -r '
    ["SearchRequest","SearchResponse","SourcePolicy","BetaTaskRunInput","TaskSpec","TaskRun","TaskRunResult","TaskRunEvent","TaskGroupRunRequest","TaskGroupStatus","Webhook"]
    | .[] as $k
    | if (. | type) == "array" then $k else empty end
  ' /dev/null >/dev/null 2>&1 || true
  for name in SearchRequest SearchResponse ExtractRequest ExtractResponse ExtractResult ExtractError SourcePolicy ExcerptSettings FullContentSettings FetchPolicy BetaTaskRunInput TaskSpec TaskRun TaskRunResult TaskRunEvent TaskGroupRunRequest TaskGroupStatus Webhook; do
    if jq -e --arg name "$name" '.components.schemas[$name] != null' "$TMP_SPEC" >/dev/null; then
      echo "- $name"
    else
      echo "- $name (missing)"
    fi
  done
  echo
  echo "Task run statuses:"
  jq -r '.components.schemas.TaskRun.properties.status.enum[]?' "$TMP_SPEC" 2>/dev/null || true
} > "$TMP_SUMMARY"

cat "$TMP_SUMMARY"

if [[ $WRITE -eq 1 ]]; then
  mkdir -p "$OUT_DIR"
  cp "$TMP_SPEC" "$OUT_DIR/public-openapi.json"
  cp "$TMP_SUMMARY" "$OUT_DIR/openapi-summary.txt"
  echo
  echo "[OK] Wrote $OUT_DIR/public-openapi.json"
  echo "[OK] Wrote $OUT_DIR/openapi-summary.txt"
else
  echo
  echo "[INFO] Dry run only. Re-run with --write to save files under references/generated/."
fi
