from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from resource_harvester.bilibili_pipeline import (
    BilibiliPipeline,
    PipelineError,
    choose_video_stream,
    find_ffmpeg,
    merge_dash,
)
from resource_harvester.converters import danmaku_xml_to_ass, subtitle_json_to_srt
from resource_harvester.downloader import ResumableDownloader
from resource_harvester.jobs import DownloadJob
from resource_harvester.models import (
    DownloadOptions,
    MediaPart,
    MediaResource,
    StreamVariant,
)


def stream(quality: int, bandwidth: int, codec: str = "avc1") -> StreamVariant:
    return StreamVariant(
        quality_id=quality,
        quality_label=str(quality),
        url="https://example.test/video",
        bandwidth=bandwidth,
        codec=codec,
    )


def test_quality_falls_back_downward_and_prefers_avc() -> None:
    streams = (
        stream(80, 2000, "hev1"),
        stream(80, 1500, "avc1"),
        stream(64, 1000),
        stream(32, 500),
    )
    assert choose_video_stream(streams, 70).quality_id == 64
    selected = choose_video_stream(streams, 80)
    assert selected.codec == "avc1"
    assert choose_video_stream(streams, None).quality_id == 80
    with pytest.raises(PipelineError):
        choose_video_stream(streams, 16)


def test_subtitle_json_to_srt() -> None:
    result = subtitle_json_to_srt(
        {"body": [{"from": 1.25, "to": 2.5, "content": "你好\n世界"}]}
    )
    assert "00:00:01,250 --> 00:00:02,500" in result
    assert "你好\n世界" in result


def test_danmaku_xml_to_ass_supports_basic_modes() -> None:
    xml = (
        '<i><d p="1,1,25,16777215,0,0,0,0">滚动</d>'
        '<d p="2,5,25,16711680,0,0,0,0">顶部</d>'
        '<d p="3,4,25,65280,0,0,0,0">底部</d>'
        '<d p="4,7,25,255,0,0,0,0">高级</d></i>'
    )
    result, ignored = danmaku_xml_to_ass(xml, width=1280, height=720)
    assert "\\move(" in result
    assert "\\an8" in result
    assert "\\an2" in result
    assert ignored == 1


class RangeHandler(BaseHTTPRequestHandler):
    data = b"abcdefghijklmnopqrstuvwxyz"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/fail":
            self.send_response(500)
            self.end_headers()
            return
        start = 0
        range_header = self.headers.get("Range")
        if range_header:
            start = int(range_header.removeprefix("bytes=").removesuffix("-"))
            self.send_response(206)
            self.send_header(
                "Content-Range",
                f"bytes {start}-{len(self.data) - 1}/{len(self.data)}",
            )
        else:
            self.send_response(200)
        body = self.data[start:]
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


def test_resumable_download_and_backup_url(tmp_path: Path) -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), RangeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        target = tmp_path / "media.part"
        target.write_bytes(RangeHandler.data[:8])
        progress: list[tuple[int, int | None]] = []
        base = f"http://127.0.0.1:{server.server_port}"
        with httpx.Client(trust_env=False) as client:
            downloader = ResumableDownloader(client, attempts=1)
            downloader.download(
                [f"{base}/fail", f"{base}/media"],
                target,
                progress=lambda completed, total: progress.append((completed, total)),
            )
        assert target.read_bytes() == RangeHandler.data
        assert progress[-1] == (len(RangeHandler.data), len(RangeHandler.data))
    finally:
        server.shutdown()
        server.server_close()


def test_ffmpeg_error_is_actionable_when_missing(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(PipelineError, match="FFmpeg"):
        find_ffmpeg()


def test_merge_uses_stream_copy_and_replaces_output(
    tmp_path: Path,
    monkeypatch,
) -> None:
    video = tmp_path / "video.m4s.part"
    audio = tmp_path / "audio.m4s.part"
    output = tmp_path / "result.mp4"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")

    def fake_run(command, **kwargs):
        assert "-c" in command
        assert command[command.index("-c") + 1] == "copy"
        Path(command[-1]).write_bytes(b"merged")
        return SimpleNamespace(returncode=0, stderr="", stdout="")

    monkeypatch.setattr("subprocess.run", fake_run)
    merge_dash("ffmpeg", video, audio, output)

    assert output.read_bytes() == b"merged"
    assert video.exists()
    assert audio.exists()


def test_merge_failure_keeps_input_streams(tmp_path: Path, monkeypatch) -> None:
    video = tmp_path / "video.m4s.part"
    audio = tmp_path / "audio.m4s.part"
    output = tmp_path / "result.mp4"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")

    monkeypatch.setattr(
        "subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stderr="bad media",
            stdout="",
        ),
    )
    with pytest.raises(PipelineError, match="bad media"):
        merge_dash("ffmpeg", video, audio, output)

    assert video.exists()
    assert audio.exists()
    assert not output.exists()


def test_auxiliary_failure_marks_successful_video_as_partial(
    tmp_path: Path,
    monkeypatch,
) -> None:
    with httpx.Client() as http_client:
        pipeline = BilibiliPipeline(
            SimpleNamespace(client=http_client),
            output_root=tmp_path,
        )
        part = MediaPart(index=1, cid=100, title="P1", duration=10)
        resource = MediaResource(
            site="bilibili",
            source_url="https://www.bilibili.com/video/BV1RVTz6HEc3/",
            media_id="BV1RVTz6HEc3",
            title="测试",
            owner="UP",
            description="",
            cover_url="",
            duration=10,
            parts=(part,),
        )
        options = DownloadOptions(
            part_cids=(100,),
            download_cover=False,
            download_metadata=False,
        )
        job = DownloadJob()

        monkeypatch.setattr(
            "resource_harvester.bilibili_pipeline.find_ffmpeg",
            lambda: "ffmpeg",
        )

        def video_succeeds_but_subtitle_fails(*args):
            args[-1].add_artifact("video.mp4")
            args[-1].add_error("字幕保存失败")

        monkeypatch.setattr(pipeline, "_download_part", video_succeeds_but_subtitle_fails)
        pipeline.run(resource, options, job)

    assert job.status == "partial"
    assert job.artifacts == ["video.mp4"]
