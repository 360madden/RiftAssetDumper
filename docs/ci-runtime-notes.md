# CI runtime notes

Status date: 2026-05-25

## Current CI status

Latest observed `main` CI runs are passing.

## Observed non-failing runner warnings

GitHub Actions emitted two non-failing runtime notices during the 2026-05-25 CI runs:

1. JavaScript actions currently running on Node.js 20 are deprecated. The warning named `actions/checkout@v4` and `actions/setup-python@v5`.
2. `windows-latest` requests are being redirected to a newer Windows image.

## Current workflow file

Tracked workflow: `.github/workflows/ci.yml`

Current high-level jobs:

- `.NET Build & Test` on `windows-latest`
- `Python Lint & Test` on `windows-latest`
- `Summary` on `ubuntu-latest`

## Practical policy

- Treat these as CI hygiene warnings, not product blockers, while CI remains green.
- Do not change action major versions from memory. Before updating `actions/checkout`, `actions/setup-python`, or runner labels, verify the current official GitHub Actions release/docs and make a small isolated CI-only commit.
- Keep the existing validation commands stable until the migration is deliberately tested.

## Next safe remediation

1. Verify current official `actions/checkout` and `actions/setup-python` releases.
2. If newer Node-24-compatible majors are available, update `.github/workflows/ci.yml` in one CI-only patch.
3. If `windows-latest` migration causes failures, pin an explicit supported Windows runner image in one CI-only patch.
4. Keep `.NET`, Python syntax, ruff, mypy, Python tests, and summary jobs unchanged unless a failure proves a specific need.
