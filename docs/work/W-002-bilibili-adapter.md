# W-002 — Build the adapter core and Bilibili resolver

- Work ID: W-002
- Type: feature
- Priority: P0
- Owner: Codex
- Updated: 2026-07-03

## Outcome

Introduce typed site-adapter contracts and resolve public Bilibili BV URLs,
short URLs, metadata, parts, qualities, streams, subtitles, and login state.

## Non-goals

- Do not migrate the existing generic or SmartEdu commands.
- Do not add search, favorites, creator-space, paid-content, or DRM support.

## Dependencies

- W-001.

## Design and interfaces

`SiteAdapter` exposes URL matching and media resolution. `BilibiliAdapter`
uses a retrying, rate-limited `httpx` client and optional Playwright storage
state at `auth/bilibili.json`. Public models contain no cookies.

## Acceptance

- [x] Direct BV URLs, bare BV IDs, `?p=` URLs, and `b23.tv` redirects resolve.
- [x] Single and multi-part resources expose typed metadata and quality choices.
- [x] Optional saved cookies are used without being logged or serialized.
- [x] Existing commands and user SmartEdu edits remain unchanged.
- [x] Automated resolver/model tests pass.

## Implementation notes

- Added typed media, part, stream, subtitle, and option models.
- Added a registry and Bilibili adapter with trusted-host validation.
- Added isolated cookie loading, rate limiting, retry, DASH parsing, subtitle discovery, and public serialization that omits protected resource URLs.

## Verification

- [TR-20260703-002](../TEST_LOG.md#tr-20260703-002) — Passed.

## Known issues

- Bilibili web endpoints are not a stable public API and may change.

## Next action

Implement W-003, the resumable media and artifact pipeline.
