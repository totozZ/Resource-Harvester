from __future__ import annotations

import threading
import time

from fastapi.testclient import TestClient

from resource_harvester.jobs import DownloadJob
from resource_harvester.models import MediaPart, MediaResource, StreamVariant
from resource_harvester.web.app import create_app
from resource_harvester.web.launcher import find_available_port


def sample_resource() -> MediaResource:
    video = StreamVariant(
        quality_id=80,
        quality_label="1080P",
        url="https://secret.example/video.m4s",
        width=1920,
        height=1080,
    )
    audio = StreamVariant(
        quality_id=30280,
        quality_label="音频",
        url="https://secret.example/audio.m4s",
    )
    return MediaResource(
        site="bilibili",
        source_url="https://www.bilibili.com/video/BV1RVTz6HEc3/",
        media_id="BV1RVTz6HEc3",
        title="测试视频",
        owner="UP",
        description="简介",
        cover_url="https://example.test/cover.jpg",
        duration=10,
        parts=(
            MediaPart(
                index=1,
                cid=100,
                title="P1",
                duration=10,
                video_streams=(video,),
                audio_streams=(audio,),
            ),
        ),
    )


class BlockingPipeline:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, resource, options, job: DownloadJob) -> None:
        job.update(status="running", stage="测试下载")
        self.started.set()
        self.release.wait(timeout=3)
        job.add_artifact("downloads/test.mp4")
        job.update(status="completed", stage="全部完成")


def payload() -> dict:
    return {
        "part_cids": [100],
        "quality_id": 80,
        "download_cover": True,
        "download_metadata": True,
        "download_subtitles": True,
        "download_danmaku_xml": True,
        "download_danmaku_ass": True,
    }


def test_media_api_hides_stream_urls() -> None:
    pipeline = BlockingPipeline()
    app = create_app(sample_resource(), pipeline)
    with TestClient(app) as client:
        response = client.get("/api/media")
    assert response.status_code == 200
    assert "secret.example" not in response.text


def test_job_lifecycle_and_rejects_second_active_job(monkeypatch) -> None:
    monkeypatch.setattr(
        "resource_harvester.web.app.find_ffmpeg",
        lambda: "ffmpeg",
    )
    pipeline = BlockingPipeline()
    app = create_app(sample_resource(), pipeline)
    with TestClient(app) as client:
        created = client.post("/api/jobs", json=payload())
        assert created.status_code == 202
        assert pipeline.started.wait(timeout=1)

        conflict = client.post("/api/jobs", json=payload())
        assert conflict.status_code == 409

        job_id = created.json()["job_id"]
        running = client.get(f"/api/jobs/{job_id}")
        assert running.json()["status"] == "running"

        pipeline.release.set()
        for _ in range(20):
            snapshot = client.get(f"/api/jobs/{job_id}").json()
            if snapshot["status"] == "completed":
                break
            time.sleep(0.02)
        assert snapshot["artifacts"] == ["downloads/test.mp4"]


def test_job_is_blocked_when_ffmpeg_is_missing(monkeypatch) -> None:
    from resource_harvester.bilibili_pipeline import PipelineError

    def missing():
        raise PipelineError("未找到 FFmpeg")

    monkeypatch.setattr("resource_harvester.web.app.find_ffmpeg", missing)
    app = create_app(sample_resource(), BlockingPipeline())
    with TestClient(app) as client:
        response = client.post("/api/jobs", json=payload())
    assert response.status_code == 503
    assert "FFmpeg" in response.json()["detail"]


def test_port_fallback(monkeypatch) -> None:
    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def bind(self, address):
            if address[1] == 8765:
                raise OSError("occupied")

    monkeypatch.setattr(
        "resource_harvester.web.launcher.socket.socket",
        lambda *args, **kwargs: FakeSocket(),
    )
    assert find_available_port(8765, 8766) == 8766
