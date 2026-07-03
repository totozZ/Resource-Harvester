from __future__ import annotations

from typing import Protocol

from resource_harvester.models import MediaResource


class SiteAdapter(Protocol):
    name: str

    def can_handle(self, url: str) -> bool:
        """Return whether this adapter understands the supplied URL or ID."""

    def resolve(self, url: str) -> MediaResource:
        """Resolve a URL into a complete, download-ready media description."""
