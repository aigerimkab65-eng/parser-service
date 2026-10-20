#!/usr/bin/env bash
# Пример: один URL → JSON (нужен API-ключ).
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:?Задайте API_KEY}"
URL="${1:-https://example.com/}"

curl -sS -X POST "${BASE_URL}/v1/parse" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${API_KEY}" \
  -d "$(printf '{"url":"%s","render":"never"}' "$URL")" | python3 -m json.tool
