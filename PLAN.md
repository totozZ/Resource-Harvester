# 1 Project Plan

- Updated: 2026-07-05
- Current objective: Dashboard cover preview bug remains open.
- Current work unit: W-006

## Priority queue

<!-- project-plan-orchestrator:work-items:start -->
| ID | Priority | Type | Delivery | Verification | Dependencies | Detail | Tests | Bugs |
|---|---|---|---|---|---|---|---|---|
| W-001 | P0 | maintenance | Done | Passed | — | [Adopt the project plan](docs/work/W-001-adopt-project-plan.md) | TR-20260703-001 | — |
| W-002 | P0 | feature | Done | Passed | W-001 | [Build the adapter core and Bilibili resolver](docs/work/W-002-bilibili-adapter.md) | TR-20260703-002 | — |
| W-003 | P0 | feature | Done | Passed | W-002 | [Build the media download and conversion pipeline](docs/work/W-003-media-pipeline.md) | TR-20260703-003 | — |
| W-004 | P0 | feature | Done | Passed | W-003 | [Add the local dashboard and CLI](docs/work/W-004-local-dashboard.md) | TR-20260703-004 | — |
| W-005 | P1 | maintenance | Done | Passed | W-004 | [Finish regression coverage and documentation](docs/work/W-005-verification-docs.md) | TR-20260703-005 | — |
| W-006 | P1 | bug | Implemented | Failed | W-005 | [Fix dashboard cover preview](docs/work/W-006-dashboard-cover-preview.md) | TR-20260705-001, TR-20260705-002 | BUG-001 |
<!-- project-plan-orchestrator:work-items:end -->

## Next action

Diagnose the live dashboard cover path: confirm refreshed JS, `/api/media`, `/api/cover`, and browser console/network behavior.

## Record index

- [Work items](docs/work/)
- [Bug registry](docs/BUGS.md)
- [Test log](docs/TEST_LOG.md)
