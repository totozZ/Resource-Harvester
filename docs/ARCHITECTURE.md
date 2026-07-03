# Architecture

Resource Harvester keeps the existing generic and SmartEdu commands intact
while introducing a typed adapter path for new sites.

```text
CLI
 └─ Bilibili adapter
     ├─ URL/authenticated API resolution
     └─ MediaResource / MediaPart / StreamVariant
          └─ Bilibili pipeline
              ├─ resumable HTTP downloader
              ├─ subtitle and danmaku converters
              ├─ FFmpeg stream-copy merge
              └─ thread-safe DownloadJob
                   └─ FastAPI + Jinja2 dashboard
```

## Boundaries

- `resource_harvester.adapters` recognizes a site and resolves protected
  download details into typed in-process models.
- Public API serialization intentionally removes stream, subtitle, and
  danmaku URLs.
- `BilibiliPipeline` owns deterministic files, resume, selection, conversion,
  and merge behavior.
- The web layer owns one in-memory job and binds only to loopback.
- Existing top-level scripts remain compatibility entry points until a later
  migration work item is accepted.

## Security

General site state remains in `auth.json`; Bilibili state is isolated at
`auth/bilibili.json`. Both paths are ignored by Git and must be treated as
login credentials. No cookie values are logged or sent to the dashboard.
