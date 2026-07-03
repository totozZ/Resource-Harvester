from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
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
        return resource.public_dict()

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
