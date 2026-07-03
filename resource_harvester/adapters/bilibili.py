from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx

from resource_harvester.models import (
    MediaPart,
    MediaResource,
    StreamVariant,
    SubtitleTrack,
)


BVID_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}")
VIEW_URL = "https://api.bilibili.com/x/web-interface/view"
PLAY_URL = "https://api.bilibili.com/x/player/playurl"
PLAYER_URL = "https://api.bilibili.com/x/player/v2"
DANMAKU_URL = "https://comment.bilibili.com/{cid}.xml"
DEFAULT_AUTH_PATH = Path("auth") / "bilibili.json"


class BilibiliError(RuntimeError):
    """A safe, user-facing Bilibili resolution error."""


def _https_url(value: str | None) -> str:
    if not value:
        return ""
    if value.startswith("//"):
        return f"https:{value}"
    return value


def load_bilibili_cookies(auth_path: Path = DEFAULT_AUTH_PATH) -> httpx.Cookies:
    cookies = httpx.Cookies()
    if not auth_path.exists():
        return cookies

    try:
        state = json.loads(auth_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BilibiliError(f"B站登录态文件无法读取：{auth_path}") from exc

    for item in state.get("cookies", []):
        domain = str(item.get("domain") or "")
        if not (domain == "bilibili.com" or domain.endswith(".bilibili.com")):
            continue
        name = item.get("name")
        value = item.get("value")
        if not name or value is None:
            continue
        cookies.set(
            str(name),
            str(value),
            domain=domain,
            path=str(item.get("path") or "/"),
        )
    return cookies


class BilibiliHttpClient:
    def __init__(
        self,
        auth_path: Path = DEFAULT_AUTH_PATH,
        *,
        timeout: float = 30.0,
        min_interval: float = 0.25,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.auth_path = auth_path
        cookies = load_bilibili_cookies(auth_path)
        self.authenticated = any(
            cookie.name == "SESSDATA" for cookie in cookies.jar
        )
        self.min_interval = min_interval
        self._last_request = 0.0
        self._rate_lock = threading.Lock()
        self.client = httpx.Client(
            cookies=cookies,
            follow_redirects=True,
            timeout=timeout,
            transport=transport,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.bilibili.com/",
            },
        )

    def close(self) -> None:
        self.client.close()

    def _wait_for_slot(self) -> None:
        with self._rate_lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self._last_request = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            self._wait_for_slot()
            try:
                response = self.client.request(method, url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response
            except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        raise BilibiliError("B站请求失败，请稍后重试。") from last_error

    def get_json(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
        response = self.request("GET", url, params=params)
        try:
            payload = response.json()
        except ValueError as exc:
            raise BilibiliError("B站返回了无法解析的数据。") from exc
        if payload.get("code") != 0:
            message = payload.get("message") or payload.get("msg") or "未知错误"
            raise BilibiliError(f"B站接口拒绝请求：{message}")
        return payload.get("data") or {}

    def resolve_redirect(self, url: str) -> str:
        return str(self.request("GET", url).url)


class BilibiliAdapter:
    name = "bilibili"

    def __init__(
        self,
        client: BilibiliHttpClient | Any | None = None,
        *,
        auth_path: Path = DEFAULT_AUTH_PATH,
    ) -> None:
        self.client = client or BilibiliHttpClient(auth_path)
        self.auth_path = auth_path

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close:
            close()

    def can_handle(self, value: str) -> bool:
        value = value.strip()
        if BVID_PATTERN.fullmatch(value):
            return True
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        return (
            host in {"b23.tv", "www.b23.tv"}
            or host == "bilibili.com"
            or host.endswith(".bilibili.com")
        )

    def normalize_url(self, value: str) -> tuple[str, str, int | None]:
        value = value.strip()
        if BVID_PATTERN.fullmatch(value):
            bvid = value[:2].upper() + value[2:]
            return f"https://www.bilibili.com/video/{bvid}/", bvid, None

        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        if host in {"b23.tv", "www.b23.tv"}:
            value = self.client.resolve_redirect(value)
            parsed = urlparse(value)
            host = (parsed.hostname or "").lower()

        if not (host == "bilibili.com" or host.endswith(".bilibili.com")):
            raise BilibiliError("仅支持 bilibili.com 或 b23.tv 地址。")

        match = BVID_PATTERN.search(value)
        if not match:
            raise BilibiliError("地址中没有找到有效的 BV 号。")
        bvid = match.group(0)[:2].upper() + match.group(0)[2:]

        page_value = (parse_qs(parsed.query).get("p") or [None])[0]
        try:
            selected_part = int(page_value) if page_value else None
        except (TypeError, ValueError):
            selected_part = None
        normalized = f"https://www.bilibili.com/video/{bvid}/"
        if selected_part:
            normalized = f"{normalized}?p={selected_part}"
        return normalized, bvid, selected_part

    def resolve(self, value: str) -> MediaResource:
        source_url, bvid, selected_part = self.normalize_url(value)
        view = self.client.get_json(VIEW_URL, params={"bvid": bvid})
        pages = view.get("pages") or []
        if not pages:
            raise BilibiliError("该视频没有可下载的分P信息。")
        if selected_part is not None and not 1 <= selected_part <= len(pages):
            raise BilibiliError(
                f"分P编号 {selected_part} 超出范围，该视频共有 {len(pages)} P。"
            )

        parts = tuple(
            self._resolve_part(
                bvid=bvid,
                page_number=int(page.get("page") or index),
                cid=int(page["cid"]),
                title=str(page.get("part") or f"P{index}"),
                duration=int(page.get("duration") or 0),
            )
            for index, page in enumerate(pages, start=1)
        )
        owner = view.get("owner") or {}
        authenticated = bool(getattr(self.client, "authenticated", False))
        return MediaResource(
            site=self.name,
            source_url=source_url,
            media_id=bvid,
            title=str(view.get("title") or bvid),
            owner=str(owner.get("name") or ""),
            description=str(view.get("desc") or ""),
            cover_url=_https_url(view.get("pic")),
            duration=int(view.get("duration") or sum(item.duration for item in parts)),
            parts=parts,
            selected_part=selected_part,
            authenticated=authenticated,
            extra={
                "aid": view.get("aid"),
                "published_at": view.get("pubdate"),
                "part_count": len(parts),
            },
        )

    def _resolve_part(
        self,
        *,
        bvid: str,
        page_number: int,
        cid: int,
        title: str,
        duration: int,
    ) -> MediaPart:
        play = self.client.get_json(
            PLAY_URL,
            params={
                "bvid": bvid,
                "cid": cid,
                "qn": 127,
                "fnval": 4048,
                "fourk": 1,
            },
        )
        dash = play.get("dash") or {}
        labels = {
            int(quality): str(label)
            for quality, label in zip(
                play.get("accept_quality") or [],
                play.get("accept_description") or [],
            )
        }

        video_streams = tuple(
            self._stream_from_payload(item, labels)
            for item in dash.get("video") or []
            if item.get("baseUrl") or item.get("base_url")
        )
        audio_payloads = list(dash.get("audio") or [])
        dolby = dash.get("dolby") or {}
        if dolby.get("audio"):
            audio_payloads.extend(dolby["audio"])
        flac = dash.get("flac") or {}
        if flac.get("audio"):
            audio_payloads.append(flac["audio"])
        audio_streams = tuple(
            self._stream_from_payload(item, {})
            for item in audio_payloads
            if item.get("baseUrl") or item.get("base_url")
        )

        player = self.client.get_json(
            PLAYER_URL,
            params={"bvid": bvid, "cid": cid},
        )
        subtitle_items = ((player.get("subtitle") or {}).get("subtitles") or [])
        subtitles = tuple(
            SubtitleTrack(
                subtitle_id=str(item.get("id") or item.get("id_str") or ""),
                language=str(item.get("lan") or ""),
                label=str(item.get("lan_doc") or item.get("lan") or "subtitle"),
                url=_https_url(item.get("subtitle_url")),
            )
            for item in subtitle_items
            if item.get("subtitle_url")
        )

        return MediaPart(
            index=page_number,
            cid=cid,
            title=title,
            duration=duration,
            video_streams=video_streams,
            audio_streams=audio_streams,
            subtitles=subtitles,
            danmaku_url=DANMAKU_URL.format(cid=cid),
        )

    @staticmethod
    def _stream_from_payload(
        item: dict[str, Any],
        labels: dict[int, str],
    ) -> StreamVariant:
        quality_id = int(item.get("id") or 0)
        codecs = str(item.get("codecs") or "")
        return StreamVariant(
            quality_id=quality_id,
            quality_label=labels.get(quality_id, f"音质 {quality_id}" if quality_id else "音频"),
            url=_https_url(item.get("baseUrl") or item.get("base_url")),
            backup_urls=tuple(
                _https_url(url)
                for url in (item.get("backupUrl") or item.get("backup_url") or [])
            ),
            codec=codecs,
            bandwidth=int(item.get("bandwidth") or 0),
            width=int(item.get("width") or 0),
            height=int(item.get("height") or 0),
            mime_type=str(item.get("mimeType") or item.get("mime_type") or ""),
        )
