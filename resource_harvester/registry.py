from __future__ import annotations

from resource_harvester.adapters.base import SiteAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: list[SiteAdapter] = []

    def register(self, adapter: SiteAdapter) -> None:
        self._adapters.append(adapter)

    def adapter_for(self, url: str) -> SiteAdapter:
        for adapter in self._adapters:
            if adapter.can_handle(url):
                return adapter
        raise ValueError(f"没有可处理此地址的站点适配器：{url}")

    def resolve(self, url: str):
        return self.adapter_for(url).resolve(url)
