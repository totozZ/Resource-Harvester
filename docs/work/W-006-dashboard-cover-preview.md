# W-006 — Fix dashboard cover preview

- Work ID: W-006
- Type: bug
- Priority: P1
- Owner: Codex
- Updated: 2026-07-05

## Outcome

Make the local Bilibili dashboard show the video cover preview reliably instead
of leaving the broken image alt text visible.

## Non-goals

- Do not change media download selection or artifact layout.
- Do not expose protected stream URLs through the public API.

## Dependencies

- W-005.

## Design and interfaces

The dashboard should use a local backend cover endpoint for the preview so the
browser does not depend on direct remote image loading behavior.

## Acceptance

- [x] The media API gives the page a local cover preview URL when a cover is available.
- [x] The local preview endpoint returns cover bytes with an image content type.
- [x] Stream URLs remain hidden from public dashboard responses.
- [x] Regression tests and the plan guard pass.
- [ ] Manual dashboard reload shows the cover image in the preview panel.

## Implementation notes

- Added `/api/cover` to fetch the cover through the backend with browser-like image
  headers and return image bytes to the local page.
- Added `cover_preview_url` to the media API and updated the dashboard script to
  prefer it over the direct remote cover URL.
- Added an image-load failure handler so a failed preview does not leave the alt
  text printed in the cover panel.
- Added web regression coverage for the local cover preview endpoint and public
  media payload.
- Manual validation later showed the attempted proxy fix did not change the
  visible dashboard behavior.

## Verification

- [TR-20260705-001](../TEST_LOG.md#tr-20260705-001) — Passed.
- [TR-20260705-002](../TEST_LOG.md#tr-20260705-002) — Failed manual check.

## Known issues

- The upstream FastAPI/Starlette test client deprecation warning remains
  unrelated to this fix.
- The dashboard cover preview still does not appear after the W-006 change.

## Next action

Diagnose the live dashboard path: verify whether the browser is loading the
updated `/static/app.js`, whether `/api/media` includes `cover_preview_url`,
whether `/api/cover` returns an image response, and whether the browser console
shows a load or CSP/CORS/cache error.
