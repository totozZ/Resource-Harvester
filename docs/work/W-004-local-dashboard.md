# W-004 — Add the local dashboard and CLI

- Work ID: W-004
- Type: feature
- Priority: P0
- Owner: Codex
- Updated: 2026-07-03

## Outcome

Launch a loopback-only dashboard from the Bilibili CLI, preview media, select
parts and artifacts, and monitor one background job.

## Non-goals

- Do not add a frontend build system, database, multi-user access, or persistent jobs.

## Dependencies

- W-003.

## Design and interfaces

FastAPI serves Jinja2/vanilla-JavaScript assets. The public API is
`GET /api/media`, `POST /api/jobs`, and `GET /api/jobs/{job_id}`.

## Acceptance

- [x] `python main.py bilibili <URL>` starts on an available loopback port and opens a browser.
- [x] The page previews metadata, parts, qualities, options, progress, errors, and artifacts.
- [x] A second active job is rejected.
- [x] `python main.py bilibili-login` saves isolated Bilibili storage state.
- [x] API and CLI tests pass.

## Implementation notes

- Added a loopback FastAPI application with the three planned JSON endpoints.
- Added a Jinja2/vanilla-JavaScript dashboard with escaped external text, options, polling progress, messages, and artifacts.
- Added one-worker job management, FFmpeg preflight, port fallback, browser launch, isolated manual login, and CLI integration.

## Verification

- [TR-20260703-004](../TEST_LOG.md#tr-20260703-004) — Passed.

## Known issues

- None recorded.

## Next action

Implement W-005, dependency declarations, user documentation, and full regression.
