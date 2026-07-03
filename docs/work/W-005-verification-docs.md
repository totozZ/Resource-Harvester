# W-005 — Finish regression coverage and documentation

- Work ID: W-005
- Type: maintenance
- Priority: P1
- Owner: Codex
- Updated: 2026-07-03

## Outcome

Document installation, legal boundaries, login safety, FFmpeg setup, usage,
architecture, and verified behavior while preserving legacy command coverage.

## Non-goals

- Do not claim live capabilities that were not verified.

## Dependencies

- W-004.

## Design and interfaces

README and quick-start material describe both legacy and Bilibili workflows.
CI runs deterministic tests without requiring network or FFmpeg.

## Acceptance

- [x] Dependencies, Python requirement, FFmpeg prerequisite, and commands are documented.
- [x] Security and content-access boundaries are explicit.
- [x] Automated tests, legacy CLI smoke checks, and plan guard pass.
- [x] Any unavailable live or FFmpeg verification is recorded truthfully.

## Implementation notes

- Declared Python 3.11+, runtime dependencies, test dependencies, package data, and a console entry point.
- Updated Chinese, English, and quick-start documentation plus an architecture note.
- Added deterministic CI tests alongside the Project Plan Orchestrator guard.
- Extended Git ignores for isolated auth state and test caches.

## Verification

- [TR-20260703-005](../TEST_LOG.md#tr-20260703-005) — Passed.

## Known issues

- The machine has no FFmpeg executable, so a real media merge remains a manual environment check.
- The current upstream FastAPI/Starlette test client emits one deprecation warning; production endpoints and all tests pass.

## Next action

Install FFmpeg on PATH and perform an optional end-to-end download from the dashboard.
