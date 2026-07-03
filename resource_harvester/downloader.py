from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from pathlib import Path

import httpx


ProgressCallback = Callable[[int, int | None], None]


class DownloadError(RuntimeError):
    pass


class ResumableDownloader:
    def __init__(
        self,
        client: httpx.Client,
        *,
        chunk_size: int = 256 * 1024,
        attempts: int = 3,
    ) -> None:
        self.client = client
        self.chunk_size = chunk_size
        self.attempts = attempts

    def download(
        self,
        urls: Iterable[str],
        path: Path,
        *,
        progress: ProgressCallback | None = None,
    ) -> Path:
        candidates = [url for url in urls if url]
        if not candidates:
            raise DownloadError("没有可用的下载地址。")
        path.parent.mkdir(parents=True, exist_ok=True)

        last_error: Exception | None = None
        for attempt in range(self.attempts):
            for url in candidates:
                try:
                    return self._download_one(url, path, progress=progress)
                except (httpx.HTTPError, OSError, DownloadError) as exc:
                    last_error = exc
            if attempt < self.attempts - 1:
                time.sleep(2**attempt)
        raise DownloadError(f"所有下载地址均失败：{path.name}") from last_error

    def _download_one(
        self,
        url: str,
        path: Path,
        *,
        progress: ProgressCallback | None,
    ) -> Path:
        existing = path.stat().st_size if path.exists() else 0
        headers = {"Range": f"bytes={existing}-"} if existing else {}

        with self.client.stream("GET", url, headers=headers) as response:
            if response.status_code == 416 and existing:
                total_text = response.headers.get("content-range", "").rsplit("/", 1)[-1]
                if total_text.isdigit() and int(total_text) == existing:
                    if progress:
                        progress(existing, existing)
                    return path
            response.raise_for_status()

            is_partial = response.status_code == 206 and existing > 0
            mode = "ab" if is_partial else "wb"
            completed = existing if is_partial else 0
            length_text = response.headers.get("content-length")
            response_length = int(length_text) if length_text and length_text.isdigit() else None
            total = completed + response_length if response_length is not None else None

            with path.open(mode) as output:
                for chunk in response.iter_bytes(self.chunk_size):
                    if not chunk:
                        continue
                    output.write(chunk)
                    completed += len(chunk)
                    if progress:
                        progress(completed, total)
        return path
