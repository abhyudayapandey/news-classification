#!/usr/bin/env bash
# Shared by .github/workflows/scheduled-pipeline.yml's steps - each `run:`
# block in a workflow is a fresh shell, so a function defined in one step
# isn't visible in the next; this gets sourced fresh by each step instead.
#
# Retries a POST call specifically on 502/503/504 (gateway-level errors),
# not on the endpoint's own 4xx/5xx application errors - those still reach
# the caller's normal status check and fail the step immediately. This
# exists because Render's free tier puts the app to sleep after ~15
# minutes idle, and it's always asleep by the time this workflow's 4-hour
# cron fires: Render's own edge gateway returns 502 while the origin is
# waking up, before the app (and curl's own --max-time) ever gets
# involved. All three pipeline endpoints are safe to retry: /ingest/run
# dedupes by content hash, and /process/run and /queue/assign only ever
# advance already-committed-per-item state, so a 502 (meaning the app's
# handler most likely never ran at all) can't cause duplicate processing.
post_with_retry() {
  local url="$1"
  local max_time="$2"
  local attempt=1
  local max_attempts=6
  local delay=10

  while [ "$attempt" -le "$max_attempts" ]; do
    resp=$(curl -sS --max-time "$max_time" -w '\n%{http_code}' -X POST "$url")
    code=$(echo "$resp" | tail -n1)
    if [ "$code" != "502" ] && [ "$code" != "503" ] && [ "$code" != "504" ]; then
      echo "$resp"
      return 0
    fi
    echo "::warning::POST $url got HTTP $code (attempt $attempt/$max_attempts, likely a Render free-tier cold start) - retrying in ${delay}s" >&2
    sleep "$delay"
    delay=$((delay * 2))
    attempt=$((attempt + 1))
  done

  # Exhausted retries - return the last response as-is and let the caller's
  # own status check report it as a real failure.
  echo "$resp"
  return 0
}
