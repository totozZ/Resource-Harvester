# W-003 — Build the media download and conversion pipeline

- Work ID: W-003
- Type: feature
- Priority: P0
- Owner: Codex
- Updated: 2026-07-03

## Outcome

Download selected Bilibili parts with progress, resume partial transfers,
merge DASH streams, and export metadata, cover, subtitles, and danmaku.

## Non-goals

- Do not auto-install FFmpeg.
- Do not copy GPL-licensed danmaku conversion code.

## Dependencies

- W-002.

## Design and interfaces

The pipeline writes deterministic paths beneath `downloads/bilibili`, uses
HTTP Range for `.part` files, and reports a thread-safe job snapshot.

## Acceptance

- [x] Quality selection falls back only to a lower available quality.
- [x] Stream downloads support backup URLs, retries, resume, and byte progress.
- [x] FFmpeg merges audio/video without transcoding and retains temp files on failure.
- [x] Metadata, cover, SRT, XML, and independently generated basic ASS are supported.
- [x] Automated pipeline and conversion tests pass.

## Implementation notes

- Added thread-safe job snapshots and resumable streaming downloads.
- Added deterministic output naming, stream selection, FFmpeg stream-copy merge, and artifact orchestration.
- Added an original basic Bilibili XML-to-ASS converter and JSON-to-SRT converter.
- Missing FFmpeg fails before any artifact download with an actionable message.

## Verification

- [TR-20260703-003](../TEST_LOG.md#tr-20260703-003) — Passed.
- Real FFmpeg merge was not run because the executable is absent; missing-executable behavior is covered automatically.

## Known issues

- The local machine currently has no FFmpeg executable on PATH.

## Next action

Implement W-004, the local dashboard, background job API, and CLI.
