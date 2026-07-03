from __future__ import annotations

import logging
import socket
import threading
import webbrowser
from pathlib import Path

import uvicorn
from playwright.sync_api import sync_playwright

from resource_harvester.adapters.bilibili import (
    DEFAULT_AUTH_PATH,
    BilibiliAdapter,
    BilibiliError,
)
from resource_harvester.bilibili_pipeline import BilibiliPipeline
from resource_harvester.web.app import create_app


def find_available_port(start: int = 8765, end: int = 8785) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"本地端口 {start}-{end} 均被占用。")


def launch_bilibili_dashboard(
    url: str,
    *,
    preferred_port: int = 8765,
    open_browser: bool = True,
) -> None:
    adapter = BilibiliAdapter()
    try:
        logging.info("正在解析 Bilibili 视频：%s", url)
        resource = adapter.resolve(url)
        pipeline = BilibiliPipeline(adapter.client)
        app = create_app(resource, pipeline)
        port = find_available_port(preferred_port, max(preferred_port, 8785))
        local_url = f"http://127.0.0.1:{port}/"
        logging.info("本地下载页面：%s", local_url)
        if open_browser:
            threading.Timer(0.8, webbrowser.open, args=(local_url,)).start()
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except BilibiliError as exc:
        logging.error("%s", exc)
    finally:
        adapter.close()


def save_bilibili_login(auth_path: Path = DEFAULT_AUTH_PATH) -> None:
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(
            "https://passport.bilibili.com/login",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        input("请在浏览器中完成 B站登录，成功后回到终端按回车保存登录态...")
        context.storage_state(path=str(auth_path))
        cookies = context.cookies()
        browser.close()

    cookie_names = {cookie.get("name") for cookie in cookies}
    if "SESSDATA" in cookie_names:
        logging.info("B站登录态已保存到 %s", auth_path)
    else:
        logging.warning(
            "已保存浏览器状态，但没有检测到 SESSDATA；可能尚未完成登录。"
        )
    logging.warning("%s 包含敏感 Cookie，不要上传或分享。", auth_path)
