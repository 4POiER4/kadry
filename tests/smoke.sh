#!/usr/bin/env bash
# Быстрая проверка запущенного контейнера: bash tests/smoke.sh [BASE_URL]
set -euo pipefail
BASE="${1:-http://localhost:8080}"
USER="${HR_USERNAME:-kadry}"
PASS="${HR_PASSWORD:-kadry}"
JAR="$(mktemp)"
trap 'rm -f "$JAR" /tmp/smoke_sample.xlsx' EXIT

echo "1) login page"
curl -sf -o /dev/null -c "$JAR" "$BASE/login"

echo "2) login"
code=$(curl -s -o /dev/null -w '%{http_code}' -b "$JAR" -c "$JAR" \
  --data-urlencode "username=$USER" --data-urlencode "password=$PASS" "$BASE/login")
[ "$code" = "200" ] || [ "$code" = "302" ] || { echo "login failed: $code"; exit 1; }

echo "3) make sample xlsx (in container-independent way)"
python3 tests/make_sample.py /tmp/smoke_sample.xlsx

echo "4) process"
curl -sf -b "$JAR" -F "file=@/tmp/smoke_sample.xlsx" -F "day_type=auto" \
  "$BASE/api/process" | python3 -m json.tool | head -40

echo "5) unauthenticated api -> 401"
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/config")
[ "$code" = "401" ] || { echo "expected 401, got $code"; exit 1; }

echo "OK"
