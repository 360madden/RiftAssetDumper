#!/bin/bash
# poll_ci_v1.sh — Poll latest GitHub Actions CI run for RiftAssetDumper
# Usage: ./poll_ci_v1.sh [--wait]

set -euo pipefail

REPO="360madden/RiftAssetDumper"
WAIT=false
[[ "${1:-}" == "--wait" ]] && WAIT=true

poll() {
    gh run list --repo "$REPO" --limit 1 --json status,conclusion,headSha,displayTitle,createdAt \
        | python -c "
import json, sys
data = json.load(sys.stdin)[0]
status   = data['status']
concl    = data.get('conclusion', 'N/A')
sha      = data['headSha'][:7]
title    = data['displayTitle']
created  = data['createdAt']

emoji = '🟡' if status == 'in_progress' else ('🟢' if concl == 'success' else '🔴')
print(f'{emoji} CI {status:12s} | {concl:12s} | {sha} | {created} | {title[:60]}')
sys.exit(0 if concl == 'success' else 1 if concl == 'failure' else 0)
"
}

if $WAIT; then
    echo "Waiting for CI to complete..."
    while true; do
        poll
        sleep 30
    done
else
    poll
fi
