#!/usr/bin/env bash
# Shared by .github/workflows/scheduled-pipeline.yml's steps - each `run:`
# block in a workflow is a fresh shell, so a function defined in one step
# isn't visible in the next; this gets sourced fresh by each step instead.
#
# Retries a POST call on 502/503/504 (gateway-level errors) and on curl
# itself failing outright (timeout, connection reset, DNS failure - no HTTP
# response at all), not on the endpoint's own 4xx/5xx application errors -
# those still reach the caller's normal status check and fail the step
# immediately. Gateway errors happen because Render's free tier puts the
# app to sleep after ~15 minutes idle, and it's always asleep by the time
# this workflow's cron fires: Render's own edge gateway returns 502 while
# the origin is waking up, before the app (and curl's own --max-time) ever
# gets involved. A bare curl failure showed up for real too: /ingest/run
# hit curl's --max-time with zero bytes received (13 outlets fetched
# sequentially, each up to a 20s worst-case timeout, occasionally adding up
# to more than the caller's max_time) - curl's own %{http_code} write-out
# is empty in that case, which the original version of this check didn't
# account for, so it silently treated a total client-side timeout as if it
# were a normal successful response instead of retrying or failing loudly.
# All three pipeline endpoints are safe to retry: /ingest/run dedupes by
# content hash, and /process/run and /queue/assign only ever advance
# already-committed-per-item state, so a retried call (meaning the
# previous attempt's handler most likely never ran, or its result was
# simply never seen) can't cause duplicate processing.
post_with_retry() {
  local url="$1"
  local max_time="$2"
  local attempt=1
  local max_attempts=6
  local delay=10

  while [ "$attempt" -le "$max_attempts" ]; do
    resp=$(curl -sS --max-time "$max_time" -w '\n%{http_code}' -X POST "$url")
    curl_exit=$?
    if [ "$curl_exit" -ne 0 ]; then
      # curl itself failed - no HTTP response was ever received, so
      # %{http_code} above is empty/missing. Synthesize "599" (a common
      # non-standard "no real HTTP response" code) so this is treated the
      # same as a 502/503/504 below, and so that if every retry exhausts
      # this way, the caller's own `code -ge 400` check still catches it
      # as a real failure instead of silently seeing an empty/malformed
      # response and treating it as success.
      code="599"
      resp=$(printf '\n%s' "$code")
    else
      code=$(echo "$resp" | tail -n1)
    fi

    if [ "$code" != "502" ] && [ "$code" != "503" ] && [ "$code" != "504" ] && [ "$code" != "599" ]; then
      echo "$resp"
      return 0
    fi
    echo "::warning::POST $url got HTTP $code (attempt $attempt/$max_attempts, likely a Render free-tier cold start or a curl-level network timeout) - retrying in ${delay}s" >&2
    sleep "$delay"
    delay=$((delay * 2))
    attempt=$((attempt + 1))
  done

  # Exhausted retries - return the last response as-is and let the caller's
  # own status check report it as a real failure.
  echo "$resp"
  return 0
}
