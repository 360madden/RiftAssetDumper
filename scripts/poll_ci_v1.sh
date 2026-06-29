#!/bin/bash
# scripts/poll_ci_v1.sh -- Poll latest GitHub Actions CI runs for the current repo.
# Mirrors the semantics of the root poll_ci_v1.sh: print emoji-coded CI status for
# the N most recent runs and exit non-zero if any of them failed.
#
# Usage:
#   bash scripts/poll_ci_v1.sh                      # print 1 most recent run
#   bash scripts/poll_ci_v1.sh --limit N            # print N most recent runs
#   bash scripts/poll_ci_v1.sh --wait               # poll continuously until conclusion != in_progress
#   bash scripts/poll_ci_v1.sh --wait --interval 60 # custom poll interval (seconds)
#   bash scripts/poll_ci_v1.sh --repo OWNER/NAME    # explicit repo override (skip auto-detect)
#
# Behavior:
#   * If `gh` CLI is installed AND `gh auth status` succeeds AND the current
#     directory is a git repo with an `origin` remote pointing at GitHub, this
#     script polls via `gh run list --repo $REPO`.
#   * If `gh` is unavailable or auth fails or origin is missing, the script falls
#     back to `git log -1` plus a pointer to install gh, so a developer on a
#     remote shell without `gh` still gets useful local information. Exit code
#     distinguishes the failure mode:
#       0 = at least one conclusion=success (or `--wait` resolved to OK)
#       1 = gh available but at least one conclusion=failure / API error
#       2 = invalid CLI args
#       3 = `--wait` mode but gh unavailable (would spin forever without gh)
#           OR no origin detected (fallback engaged)

set -euo pipefail

LIMIT=1
WAIT=false
INTERVAL=30
REPO_OVERRIDE=""

# Exit codes -- exported for downstream scripts to introspect.
EXIT_OK=0
EXIT_POLL_FAILED=1
EXIT_BAD_ARGS=2
EXIT_NO_GH=3

while [[ $# -gt 0 ]]; do
    case "$1" in
        --limit)     LIMIT="${2:?--limit requires an integer}"; shift 2 ;;
        --wait)      WAIT=true; shift ;;
        --interval)  INTERVAL="${2:?--interval requires integer seconds}"; shift 2 ;;
        --repo)      REPO_OVERRIDE="${2:?--repo requires owner/name}"; shift 2 ;;
        -h|--help)
            grep -E "^# " "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)  echo "Unrecognized argument: $1" >&2; exit "$EXIT_BAD_ARGS" ;;
    esac
done

# Light validation: ensure LIMIT/INTERVAL are positive integers so downstream
# commands don't get cryptic errors. Fail plainly with EXIT_BAD_ARGS (=2).
if ! [[ "$LIMIT" =~ ^[0-9]+$ ]] || [[ "$LIMIT" -eq 0 ]]; then
    echo "--limit value must be a positive integer (got '$LIMIT')" >&2
    exit "$EXIT_BAD_ARGS"
fi
if ! [[ "$INTERVAL" =~ ^[0-9]+$ ]] || [[ "$INTERVAL" -eq 0 ]]; then
    echo "--interval value must be a positive integer (got '$INTERVAL')" >&2
    exit "$EXIT_BAD_ARGS"
fi

# REPO detection: explicit override wins, otherwise derive from origin remote
# AND validate the result matches the canonical owner/name shape.
# Source: the actual GitHub-Cloud URL forms:
#   SSH:   git@github.com:owner/repo.git           -> owner/repo
#   HTTPS: https://github.com/owner/repo[.git]      -> owner/repo
REPO="$REPO_OVERRIDE"
if [[ -z "$REPO" ]] && command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
    REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
    if [[ -n "$REMOTE_URL" ]]; then
        # Single-pass sed: if the regex matches, sed outputs owner/repo; if not, it
        # outputs the original REMOTE_URL unchanged (no -n). We therefore detect a
        # successful substitution by comparing CANDIDATE against the unmodified input.
        CANDIDATE="$(printf '%s' "$REMOTE_URL" | sed -E 's#.*github\.com[:/]([^/]+/[^/]+)(\.git)?$#\1#')"
        if [[ "$CANDIDATE" != "$REMOTE_URL" && "$CANDIDATE" =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]]; then
            REPO="$CANDIDATE"
        else
            echo "Note: extracted '$CANDIDATE' from origin doesn't match owner/name shape; falling through to git log fallback. Re-run with --repo OWNER/NAME to override." >&2
        fi
    fi
fi

# Pretty-print one or more CI runs. Returns one of the EXIT_* codes above.
poll() {
    if ! command -v gh >/dev/null 2>&1; then
        echo "gh CLI not installed -- cannot poll GitHub Actions. Showing git log instead:" >&2
        git log --oneline -"$LIMIT" || true
        echo "" >&2
        echo "On a host with gh CLI installed (https://cli.github.com/manual/install) run:" >&2
        echo "  gh run list --repo <owner/repo> --limit $LIMIT \\" >&2
        echo "    --json status,conclusion,headSha,displayTitle,createdAt" >&2
        return "$EXIT_NO_GH"
    fi
    if [[ -z "$REPO" ]]; then
        echo "Could not determine REPO from git origin and no --repo override given." >&2
        echo "Either run inside a cloned repo with a GitHub origin, or pass --repo OWNER/NAME." >&2
        return "$EXIT_NO_GH"
    fi
    if ! gh auth status >/dev/null 2>&1; then
        echo "gh not authenticated. Run 'gh auth login' first, or use a machine with a pre-paid GITHUB_TOKEN." >&2
        return "$EXIT_NO_GH"
    fi

    gh run list --repo "$REPO" --limit "$LIMIT" --json status,conclusion,headSha,displayTitle,createdAt \
        | python -c "
import json, sys
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError as e:
    print(f'gh returned non-JSON (likely 404/auth failure): {e}', file=sys.stderr)
    sys.exit(1)
if not data:
    print('No CI runs found.')
    sys.exit(0)
nonzero = 0
for entry in data:
    status   = entry.get('status', '?')
    concl    = entry.get('conclusion') or 'in_progress'
    sha      = entry.get('headSha', 'unknown')[:7]
    title    = entry.get('displayTitle', '<no title>')
    created  = entry.get('createdAt', '<unknown>')
    if status == 'in_progress':
        emoji = '\U0001F7E1'  # yellow circle
    elif concl == 'success':
        emoji = '\U0001F7E2'  # green circle
    else:
        emoji = '\U0001F534'  # red circle
        if concl == 'failure':
            nonzero = 1
    print(f'{emoji} CI {status:12s} | {concl:12s} | {sha} | {created} | {title[:60]}')
sys.exit(nonzero)
"
}

if $WAIT; then
    echo "Waiting for CI to complete (interval=${INTERVAL}s, limit=${LIMIT}, repo=${REPO:-auto-detect-failed})..."
    while true; do
        set +e
        poll
        rc=$?
        set -e
        if [[ $rc -eq $EXIT_OK ]]; then
            exit "$EXIT_OK"
        fi
        if [[ $rc -eq $EXIT_NO_GH ]]; then
            echo "--wait mode requires gh CLI to be installed + authed. Exiting to avoid spinning forever." >&2
            exit "$EXIT_NO_GH"
        fi
        echo "Poll result: exit=$rc; sleeping ${INTERVAL}s before retry..." >&2
        sleep "$INTERVAL"
    done
else
    poll
fi
