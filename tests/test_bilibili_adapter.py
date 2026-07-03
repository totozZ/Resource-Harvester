from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from resource_harvester.adapters.bilibili import (
    PLAY_URL,
    PLAYER_URL,
    VIEW_URL,
    BilibiliAdapter,
    BilibiliError,
    load_bilibili_cookies,
)
from resource_harvester.registry import AdapterRegistry


class FakeClient:
    authenticated = False

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def resolve_redirect(self, url: str) -> str:
        assert url == "https://b23.tv/demo"
        return "https://www.bilibili.com/video/BV1RVTz6HEc3?p=2"

    def get_json(self, url: str, *, params: dict):
        self.calls.append((url, params))
        if url == VIEW_URL:
            return {
                "aid": 123,
                "title": "测试视频",
                "desc": "description",
                "pic": "//i.example/cover.jpg",
                "duration": 30,
                "pubdate": 1234567890,
                "owner": {"name": "测试UP"},
                "pages": [
                    {"page": 1, "cid": 101, "part": "第一部分", "duration": 10},
                    {"page": 2, "cid": 102, "part": "第二部分", "duration": 20},
                ],
            }
        if url == PLAY_URL:
            return {
                "accept_quality": [80, 64],
                "accept_description": ["1080P", "720P"],
                "dash": {
                    "video": [
                        {
                            "id": 80,
                            "baseUrl": "//cdn.example/video-80.m4s",
                            "backupUrl": ["https://backup.example/video-80.m4s"],
                            "codecs": "avc1",
                            "bandwidth": 1000,
                            "width": 1920,
                            "height": 1080,
                            "mimeType": "video/mp4",
                        },
                        {
                            "id": 64,
                            "baseUrl": "https://cdn.example/video-64.m4s",
                            "codecs": "avc1",
                            "bandwidth": 700,
                            "width": 1280,
                            "height": 720,
                            "mimeType": "video/mp4",
                        },
                    ],
                    "audio": [
                        {
                            "id": 30280,
                            "baseUrl": "https://cdn.example/audio.m4s",
                            "codecs": "mp4a",
                            "bandwidth": 192000,
                            "mimeType": "audio/mp4",
                        }
                    ],
                },
            }
        if url == PLAYER_URL:
            return {
                "subtitle": {
                    "subtitles": [
                        {
                            "id": 1,
                            "lan": "zh-CN",
                            "lan_doc": "中文",
                            "subtitle_url": "//i.example/subtitle.json",
                        }
                    ]
                }
            }
        raise AssertionError(url)


def test_resolve_multi_part_resource_and_hide_stream_urls() -> None:
    adapter = BilibiliAdapter(FakeClient())
    resource = adapter.resolve("https://www.bilibili.com/video/BV1RVTz6HEc3?p=2")

    assert resource.media_id == "BV1RVTz6HEc3"
    assert resource.selected_part == 2
    assert len(resource.parts) == 2
    assert resource.parts[0].qualities[0]["label"] == "1080P"
    assert resource.parts[0].video_streams[0].url.startswith("https://")
    public = resource.public_dict()
    serialized = json.dumps(public)
    assert "video-80.m4s" not in serialized
    assert "audio.m4s" not in serialized
    assert "subtitle.json" not in serialized
    assert public["parts"][0]["subtitles"][0]["label"] == "中文"


def test_short_url_and_registry() -> None:
    adapter = BilibiliAdapter(FakeClient())
    registry = AdapterRegistry()
    registry.register(adapter)

    resource = registry.resolve("https://b23.tv/demo")

    assert resource.selected_part == 2
    assert registry.adapter_for("BV1RVTz6HEc3") is adapter


def test_rejects_untrusted_host() -> None:
    adapter = BilibiliAdapter(FakeClient())
    with pytest.raises(BilibiliError):
        adapter.normalize_url("https://example.com/video/BV1RVTz6HEc3")
    with pytest.raises(BilibiliError, match="超出范围"):
        adapter.resolve("https://www.bilibili.com/video/BV1RVTz6HEc3?p=3")


def test_loads_only_bilibili_cookies(tmp_path: Path) -> None:
    auth = tmp_path / "bilibili.json"
    auth.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "SESSDATA",
                        "value": "secret",
                        "domain": ".bilibili.com",
                        "path": "/",
                    },
                    {
                        "name": "other",
                        "value": "ignore",
                        "domain": ".example.com",
                        "path": "/",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    cookies = load_bilibili_cookies(auth)
    request = httpx.Request("GET", "https://api.bilibili.com/")
    cookies.set_cookie_header(request)

    assert request.headers["cookie"] == "SESSDATA=secret"
