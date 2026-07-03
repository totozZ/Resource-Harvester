# Test Log

Append one record for every delivery work unit. Allowed results: `Passed`, `Failed`, `Blocked`, `NotRun`, `N/A`.

<!-- project-plan-orchestrator:tests:start -->
<!-- Append new test records above the end marker. -->
## TR-20260703-001

- Result: Passed
- Work: W-001
- Environment: Windows PowerShell, Python 3.14.5, dirty working tree preserved
- Command: `python .project-plan/planctl.py check --root .`
- Evidence: Adoption preview was clean, non-destructive apply completed, and the structural guard passed.

## TR-20260703-002

- Result: Passed
- Work: W-002
- Environment: Windows PowerShell, Python 3.14.5 virtual environment
- Command: `.venv\Scripts\python.exe -m pytest tests\test_bilibili_adapter.py -q`
- Evidence: 4 tests passed; a separate live guest probe resolved a public BV video, one part, and two available qualities without exposing protected URLs.

## TR-20260703-003

- Result: Passed
- Work: W-003
- Environment: Windows PowerShell, Python 3.14.5 virtual environment; FFmpeg absent
- Command: `.venv\Scripts\python.exe -m pytest tests\test_media_pipeline.py -q`
- Evidence: 5 tests passed for quality fallback, AVC preference, SRT conversion, basic ASS conversion, Range resume, backup URL use, progress, and actionable missing-FFmpeg failure.

## TR-20260703-004

- Result: Passed
- Work: W-004
- Environment: Windows PowerShell, Python 3.14.5 virtual environment
- Command: `.venv\Scripts\python.exe -m pytest tests\test_web_app.py tests\test_cli.py -q`
- Evidence: 6 tests passed for public media serialization, job lifecycle, active-job conflict, missing FFmpeg response, port fallback, new CLI arguments, and legacy command parsing; CLI help also ran successfully.

## TR-20260703-005

- Result: Passed
- Work: W-005
- Environment: Windows PowerShell, Python 3.14.5 virtual environment; guest Bilibili access; FFmpeg absent
- Command: `.venv\Scripts\python.exe -m pytest -q`
- Evidence: 18 tests passed. Compileall and legacy CLI help passed, a live public multi-P BV resolved two parts, an actual loopback CLI server returned `/api/media`, and the plan guard passed. A real FFmpeg merge was not run because FFmpeg is not installed; command construction, stream-copy success/failure handling, input retention, and missing-FFmpeg behavior are covered by tests.

<!-- project-plan-orchestrator:tests:end -->
