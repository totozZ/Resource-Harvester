from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class StreamVariant:
    quality_id: int
    quality_label: str
    url: str
    backup_urls: tuple[str, ...] = ()
    codec: str = ""
    bandwidth: int = 0
    width: int = 0
    height: int = 0
    mime_type: str = ""

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("url", None)
        data.pop("backup_urls", None)
        return data


@dataclass(frozen=True, slots=True)
class SubtitleTrack:
    subtitle_id: str
    language: str
    label: str
    url: str

    def public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("url", None)
        return data


@dataclass(frozen=True, slots=True)
class MediaPart:
    index: int
    cid: int
    title: str
    duration: int
    video_streams: tuple[StreamVariant, ...] = ()
    audio_streams: tuple[StreamVariant, ...] = ()
    subtitles: tuple[SubtitleTrack, ...] = ()
    danmaku_url: str = ""

    @property
    def qualities(self) -> tuple[dict[str, Any], ...]:
        result: list[dict[str, Any]] = []
        seen: set[int] = set()
        for stream in sorted(
            self.video_streams,
            key=lambda item: (item.quality_id, item.bandwidth),
            reverse=True,
        ):
            if stream.quality_id in seen:
                continue
            seen.add(stream.quality_id)
            result.append(
                {
                    "id": stream.quality_id,
                    "label": stream.quality_label,
                    "width": stream.width,
                    "height": stream.height,
                }
            )
        return tuple(result)

    def public_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "cid": self.cid,
            "title": self.title,
            "duration": self.duration,
            "qualities": list(self.qualities),
            "subtitles": [item.public_dict() for item in self.subtitles],
        }


@dataclass(frozen=True, slots=True)
class MediaResource:
    site: str
    source_url: str
    media_id: str
    title: str
    owner: str
    description: str
    cover_url: str
    duration: int
    parts: tuple[MediaPart, ...]
    selected_part: int | None = None
    authenticated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "site": self.site,
            "source_url": self.source_url,
            "media_id": self.media_id,
            "title": self.title,
            "owner": self.owner,
            "description": self.description,
            "cover_url": self.cover_url,
            "duration": self.duration,
            "selected_part": self.selected_part,
            "authenticated": self.authenticated,
            "parts": [part.public_dict() for part in self.parts],
            "extra": self.extra,
        }


@dataclass(frozen=True, slots=True)
class DownloadOptions:
    part_cids: tuple[int, ...]
    quality_id: int | None = None
    download_cover: bool = True
    download_metadata: bool = True
    download_subtitles: bool = True
    download_danmaku_xml: bool = True
    download_danmaku_ass: bool = True
