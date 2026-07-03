from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from resource_harvester.adapters.bilibili import BilibiliHttpClient
from resource_harvester.converters import danmaku_xml_to_ass, subtitle_json_to_srt
from resource_harvester.downloader import ResumableDownloader
from resource_harvester.jobs import DownloadJob
from resource_harvester.models import (
    DownloadOptions,
    MediaPart,
    MediaResource,
    StreamVariant,
)
from utils import safe_filename


class PipelineError(RuntimeError):
    pass


def choose_video_stream(
    streams: tuple[StreamVariant, ...],
    quality_id: int | None,
) -> StreamVariant:
    if not streams:
        raise PipelineError("没有可用的视频流。")
    available_ids = sorted({item.quality_id for item in streams}, reverse=True)
    if quality_id is None:
        selected_id = available_ids[0]
    else:
        allowed = [item for item in available_ids if item <= quality_id]
        if not allowed:
            raise PipelineError(f"没有不高于目标 {quality_id} 的视频画质。")
        selected_id = allowed[0]
    candidates = [item for item in streams if item.quality_id == selected_id]
    return max(
        candidates,
        key=lambda item: (item.codec.lower().startswith("avc"), item.bandwidth),
    )


def choose_audio_stream(streams: tuple[StreamVariant, ...]) -> StreamVariant:
    if not streams:
        raise PipelineError("没有可用的音频流。")
    return max(streams, key=lambda item: item.bandwidth)


def find_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise PipelineError(
            "未找到 FFmpeg。请安装 FFmpeg、加入 PATH，然后重新启动下载。"
        )
    return executable


def merge_dash(
    ffmpeg: str,
    video_path: Path,
    audio_path: Path,
    output_path: Path,
) -> None:
    temporary_output = output_path.with_suffix(".tmp.mp4")
    temporary_output.unlink(missing_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        str(temporary_output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        temporary_output.unlink(missing_ok=True)
        detail = (result.stderr or result.stdout or "未知错误").strip()
        raise PipelineError(f"FFmpeg 合并失败：{detail[-500:]}")
    os.replace(temporary_output, output_path)


class BilibiliPipeline:
    def __init__(
        self,
        client: BilibiliHttpClient,
        *,
        output_root: Path = Path("downloads") / "bilibili",
    ) -> None:
        self.client = client
        self.output_root = output_root
        self.downloader = ResumableDownloader(client.client)

    def run(
        self,
        resource: MediaResource,
        options: DownloadOptions,
        job: DownloadJob,
    ) -> None:
        try:
            ffmpeg = find_ffmpeg()
        except PipelineError as exc:
            job.add_error(str(exc))
            job.update(status="failed", stage="环境检查失败")
            return

        selected = [part for part in resource.parts if part.cid in options.part_cids]
        if not selected:
            job.add_error("没有选择任何有效分P。")
            job.update(status="failed", stage="参数检查失败")
            return

        root = self.output_root / safe_filename(resource.title)
        root.mkdir(parents=True, exist_ok=True)
        job.update(status="running", stage="准备资源")

        try:
            if options.download_metadata:
                self._write_metadata(resource, options, root, job)
            if options.download_cover and resource.cover_url:
                self._download_cover(resource.cover_url, root, job)
        except Exception as exc:
            job.add_error(f"封面或元数据保存失败：{exc}")

        completed_parts = 0
        for part in selected:
            try:
                self._download_part(resource, part, options, root, ffmpeg, job)
                completed_parts += 1
            except Exception as exc:
                job.add_error(f"P{part.index} {part.title}：{exc}")

        if completed_parts == len(selected) and not job.errors:
            job.update(status="completed", stage="全部完成", current_file="")
        elif completed_parts:
            job.update(status="partial", stage="部分完成", current_file="")
        else:
            job.update(status="failed", stage="下载失败", current_file="")

    def _write_metadata(
        self,
        resource: MediaResource,
        options: DownloadOptions,
        root: Path,
        job: DownloadJob,
    ) -> None:
        path = root / "metadata.json"
        payload = resource.public_dict()
        payload["downloaded_at"] = datetime.now(UTC).isoformat()
        payload["selection"] = {
            "part_cids": list(options.part_cids),
            "quality_id": options.quality_id,
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        job.add_artifact(str(path))

    def _download_cover(self, url: str, root: Path, job: DownloadJob) -> None:
        path = root / "cover.jpg"
        if path.exists():
            job.add_artifact(str(path))
            return
        partial = path.with_suffix(".jpg.part")
        job.update(stage="下载封面", current_file=path.name)
        self.downloader.download(
            [url],
            partial,
            progress=self._progress_callback(job),
        )
        os.replace(partial, path)
        job.add_artifact(str(path))

    def _download_part(
        self,
        resource: MediaResource,
        part: MediaPart,
        options: DownloadOptions,
        root: Path,
        ffmpeg: str,
        job: DownloadJob,
    ) -> None:
        base = f"{part.index:02d}-{safe_filename(part.title)}"
        output = root / f"{base}.mp4"
        video = choose_video_stream(part.video_streams, options.quality_id)
        audio = choose_audio_stream(part.audio_streams)
        job.update(actual_quality=f"P{part.index} · {video.quality_label}")
        if options.quality_id is not None and video.quality_id != options.quality_id:
            job.add_warning(
                f"P{part.index} 目标画质 {options.quality_id} 不可用，"
                f"已降级为 {video.quality_label}。"
            )

        if output.exists():
            job.add_warning(f"已存在，跳过：{output.name}")
            job.add_artifact(str(output))
        else:
            temp_dir = root / ".temp"
            video_path = temp_dir / f"{base}.video.m4s.part"
            audio_path = temp_dir / f"{base}.audio.m4s.part"

            job.update(stage="下载视频流", current_file=video_path.name)
            self.downloader.download(
                [video.url, *video.backup_urls],
                video_path,
                progress=self._progress_callback(job),
            )
            job.update(stage="下载音频流", current_file=audio_path.name)
            self.downloader.download(
                [audio.url, *audio.backup_urls],
                audio_path,
                progress=self._progress_callback(job),
            )

            job.update(
                status="merging",
                stage="合并音视频",
                current_file=output.name,
                downloaded_bytes=0,
                total_bytes=None,
            )
            merge_dash(ffmpeg, video_path, audio_path, output)
            video_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)
            if temp_dir.exists() and not any(temp_dir.iterdir()):
                temp_dir.rmdir()
            job.add_artifact(str(output))
            job.update(status="running")

        if options.download_subtitles:
            try:
                self._download_subtitles(part, root, base, job)
            except Exception as exc:
                job.add_error(f"P{part.index} 字幕保存失败：{exc}")
        if options.download_danmaku_xml or options.download_danmaku_ass:
            try:
                self._download_danmaku(part, root, base, video, options, job)
            except Exception as exc:
                job.add_error(f"P{part.index} 弹幕保存失败：{exc}")

    def _download_subtitles(
        self,
        part: MediaPart,
        root: Path,
        base: str,
        job: DownloadJob,
    ) -> None:
        if not part.subtitles:
            job.add_warning(f"P{part.index} 未提供字幕。")
            return
        for track in part.subtitles:
            language = safe_filename(track.language or track.label or "subtitle")
            path = root / f"{base}.{language}.srt"
            if not path.exists():
                job.update(stage="下载字幕", current_file=path.name)
                payload = self.client.request("GET", track.url).json()
                path.write_text(subtitle_json_to_srt(payload), encoding="utf-8-sig")
            job.add_artifact(str(path))

    def _download_danmaku(
        self,
        part: MediaPart,
        root: Path,
        base: str,
        video: StreamVariant,
        options: DownloadOptions,
        job: DownloadJob,
    ) -> None:
        xml_path = root / f"{base}.danmaku.xml"
        if not xml_path.exists():
            job.update(stage="下载弹幕", current_file=xml_path.name)
            xml_content = self.client.request("GET", part.danmaku_url).content
            xml_path.write_bytes(xml_content)
        else:
            xml_content = xml_path.read_bytes()

        if options.download_danmaku_xml:
            job.add_artifact(str(xml_path))
        if options.download_danmaku_ass:
            ass_path = root / f"{base}.danmaku.ass"
            if not ass_path.exists():
                ass_text, ignored = danmaku_xml_to_ass(
                    xml_content,
                    width=video.width or 1920,
                    height=video.height or 1080,
                )
                ass_path.write_text(ass_text, encoding="utf-8-sig")
                if ignored:
                    job.add_warning(
                        f"P{part.index} 有 {ignored} 条高级或无效弹幕未写入 ASS。"
                    )
            job.add_artifact(str(ass_path))
        if not options.download_danmaku_xml:
            xml_path.unlink(missing_ok=True)

    @staticmethod
    def _progress_callback(job: DownloadJob):
        def update(completed: int, total: int | None) -> None:
            job.update(downloaded_bytes=completed, total_bytes=total)

        return update
