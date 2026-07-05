# W-007 - Add README download page screenshots

- Work ID: W-007
- Type: maintenance
- Priority: P2
- Owner: Codex
- Updated: 2026-07-05

## Outcome

Show the newly added local Bilibili server download page screenshots in the
project README files so readers can preview the dashboard flow.

## Non-goals

- Do not change dashboard behavior, download logic, or media artifact layout.
- Do not resolve the existing dashboard cover preview bug.

## Dependencies

- W-005.

## Design and interfaces

The English and Chinese README files reference the checked-in screenshots with
relative Markdown image links under `pics/`.

## Acceptance

- [x] `README.md` shows the setup and completed job screenshots.
- [x] `README.cn.md` mirrors the same screenshot examples for Chinese readers.
- [x] The referenced image paths resolve locally.
- [x] The project plan guard passes.

## Implementation notes

- Added `pics/download1.png` as the local Bilibili archive setup screenshot in
  both README files.
- Added `pics/download2.png` as the completed live job screenshot in both
  README files.
- Kept W-006 and BUG-001 unchanged because the screenshot documentation does
  not fix the existing cover preview issue.

## Verification

- [TR-20260705-003](../TEST_LOG.md#tr-20260705-003) - Passed.

## Known issues

- BUG-001 remains open and unrelated to this documentation update.

## Next action

Return to W-006 live dashboard cover-path diagnosis.
