#!/usr/bin/env bash
set -u
cd "C:/RIFT MODDING/Assets" || exit 1

RUN_ID=27472855858
EXPECTED_SHA=9d1cefd61b3f3e8a3c2828ae8dd9f4cddd9d2e1a
MAX_POLLS=24        # 24 * 15s = 6 min
SLEEP_SECS=15

echo "===polling CI run $RUN_ID (expecting HEAD=$EXPECTED_SHA) every ${SLEEP_SECS}s for up to $((MAX_POLLS*SLEEP_SECS/60)) min==="

for i in $(seq 1 $MAX_POLLS); do
  STATUS=$(gh run view "$RUN_ID" --json status -q '.status' 2>/dev/null || echo "unknown")
  CONCLUSION=$(gh run view "$RUN_ID" --json conclusion -q '.conclusion' 2>/dev/null || echo "unknown")
  HEAD_SHA=$(gh run view "$RUN_ID" --json headSha -q '.headSha' 2>/dev/null || echo "unknown")
  echo "[poll $i/$MAX_POLLS] status=$STATUS conclusion=$CONCLUSION headSha=${HEAD_SHA:0:9}"

  if [ "$STATUS" = "completed" ]; then
    echo "===CI run completed==="
    echo "---per-job results---"
    gh run view "$RUN_ID" --json jobs | python -c "import sys, json; d = json.load(sys.stdin); [print(' ', j.get('name'), '->', j.get('conclusion')) for j in d.get('jobs', [])]"
    echo "---conclusion: $CONCLUSION---"

    if [ "$CONCLUSION" = "success" ] && [ "$HEAD_SHA" = "$EXPECTED_SHA" ]; then
      echo "PASS: CI is green on $HEAD_SHA"
      exit 0
    else
      echo "FAIL: CI conclusion=$CONCLUSION (expected success) on headSha=$HEAD_SHA (expected $EXPECTED_SHA)"
      exit 1
    fi
  fi

  sleep $SLEEP_SECS
done

echo "TIMEOUT: CI run $RUN_ID did not complete within $((MAX_POLLS*SLEEP_SECS/60)) min"
echo "---last known per-job results---"
gh run view "$RUN_ID" --json jobs 2>/dev/null | python -c "import sys, json; d = json.load(sys.stdin); [print(' ', j.get('name'), '->', j.get('conclusion')) for j in d.get('jobs', [])]" 2>/dev/null || true
exit 2
