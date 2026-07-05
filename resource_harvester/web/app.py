from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from resource_harvester.bilibili_pipeline import (
    BilibiliPipeline,
    PipelineError,
    find_ffmpeg,
)
from resource_harvester.jobs import TERMINAL_STATES, DownloadJob
from resource_harvester.models import DownloadOptions, MediaResource


WEB_ROOT = Path(__file__).resolve().parent
COVER_PREVIEW_PATH = "/api/cover"
COVER_HEADERS = {
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    "Referer": "https://www.bilibili.com/",
}


class Pipeline(Protocol):
    def run(
        self,
        resource: MediaResource,
        options: DownloadOptions,
        job: DownloadJob,
    ) -> None: ...


class JobRequest(BaseModel):
    part_cids: list[int] = Field(min_length=1)
    quality_id: int | None = None
    download_cover: bool = True
    download_metadata: bool = True
    download_subtitles: bool = True
    download_danmaku_xml: bool = True
    download_danmaku_ass: bool = True


class JobManager:
    def __init__(
        self,
        resource: MediaResource,
        pipeline: Pipeline,
    ) -> None:
        self.resource = resource
        self.pipeline = pipeline
        self.jobs: dict[str, DownloadJob] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bilibili")

    def create(self, request: JobRequest) -> DownloadJob:
        valid_cids = {part.cid for part in self.resource.parts}
        if not set(request.part_cids).issubset(valid_cids):
            raise ValueError("包含无效的分P编号。")

        with self._lock:
            if any(
                job.status not in TERMINAL_STATES
                for job in self.jobs.values()
            ):
                raise RuntimeError("已有下载任务正在运行。")
            job = DownloadJob()
            self.jobs[job.job_id] = job

        options = DownloadOptions(
            part_cids=tuple(request.part_cids),
            quality_id=request.quality_id,
            download_cover=request.download_cover,
            download_metadata=request.download_metadata,
            download_subtitles=request.download_subtitles,
            download_danmaku_xml=request.download_danmaku_xml,
            download_danmaku_ass=request.download_danmaku_ass,
        )
        self._executor.submit(self.pipeline.run, self.resource, options, job)
        return job

    def get(self, job_id: str) -> DownloadJob | None:
        return self.jobs.get(job_id)

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=False)


def _media_payload(resource: MediaResource) -> dict:
    payload = resource.public_dict()
    payload["cover_preview_url"] = COVER_PREVIEW_PATH if resource.cover_url else ""
    return payload


def _fetch_cover(url: str, pipeline: BilibiliPipeline | Pipeline) -> httpx.Response:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("封面地址不是 HTTP(S) URL。")

    bilibili_client = getattr(pipeline, "client", None)
    request = getattr(bilibili_client, "request", None)
    if request:
        return request("GET", url, headers=COVER_HEADERS)

    with httpx.Client(
        follow_redirects=True,
        timeout=30.0,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            **COVER_HEADERS,
        },
    ) as client:
        response = client.get(url)
        response.raise_for_status()
        return response


def create_app(
    resource: MediaResource,
    pipeline: BilibiliPipeline | Pipeline,
) -> FastAPI:
    manager = JobManager(resource, pipeline)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        manager.close()

    app = FastAPI(
        title="Resource Harvester",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )
    templates = Jinja2Templates(directory=str(WEB_ROOT / "templates"))
    app.state.job_manager = manager

    app.mount(
        "/static",
        StaticFiles(directory=str(WEB_ROOT / "static")),
        name="static",
    )

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"source_url": resource.source_url},
        )

    @app.get("/api/media")
    def get_media():
        return _media_payload(resource)

    @app.get(COVER_PREVIEW_PATH)
    def get_cover():
        if not resource.cover_url:
            raise HTTPException(status_code=404, detail="该视频没有封面地址。")
        try:
            upstream = _fetch_cover(resource.cover_url, pipeline)
        except (httpx.HTTPError, RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=502,
                detail=f"封面预览加载失败：{exc}",
            ) from exc

        content_type = upstream.headers.get("content-type", "image/jpeg").split(";", 1)[0]
        if not content_type.lower().startswith("image/"):
            raise HTTPException(status_code=502, detail="封面响应不是图片。")
        return Response(
            content=upstream.content,
            media_type=content_type,
            headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.post("/api/jobs", status_code=202)
    def create_job(payload: JobRequest):
        try:
            find_ffmpeg()
        except PipelineError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        try:
            job = manager.create(payload)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "job_id": job.job_id,
            "status_url": f"/api/jobs/{job.job_id}",
        }

    @app.get("/api/jobs/{job_id}")
    def get_job(job_id: str):
        job = manager.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="下载任务不存在。")
        return job.snapshot()

    return app
