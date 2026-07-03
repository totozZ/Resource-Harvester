from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any


TERMINAL_STATES = {"completed", "partial", "failed"}


@dataclass(slots=True)
class DownloadJob:
    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "ready"
    stage: str = "等待开始"
    current_file: str = ""
    downloaded_bytes: int = 0
    total_bytes: int | None = None
    actual_quality: str = ""
    artifacts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def update(self, **changes: Any) -> None:
        with self._lock:
            for key, value in changes.items():
                setattr(self, key, value)

    def add_artifact(self, path: str) -> None:
        with self._lock:
            if path not in self.artifacts:
                self.artifacts.append(path)

    def add_warning(self, message: str) -> None:
        with self._lock:
            self.warnings.append(message)

    def add_error(self, message: str) -> None:
        with self._lock:
            self.errors.append(message)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "job_id": self.job_id,
                "status": self.status,
                "stage": self.stage,
                "current_file": self.current_file,
                "downloaded_bytes": self.downloaded_bytes,
                "total_bytes": self.total_bytes,
                "actual_quality": self.actual_quality,
                "artifacts": list(self.artifacts),
                "warnings": list(self.warnings),
                "errors": list(self.errors),
            }
