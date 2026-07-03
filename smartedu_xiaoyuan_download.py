import json
import logging
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import sync_playwright

from utils import AUTH_FILE, ensure_auth_file, ensure_download_dir, safe_filename, setup_logging, unique_path


DETAILS_URL = (
    "https://s-file-2.ykt.cbern.com.cn/zxx/ndrv2/"
    "national_lesson/resources/details/{resource_id}.json"
)

TARGETS = [
    ("课件", ["课件"]),
    ("教学设计", ["教学设计"]),
    ("学习任务单", ["学习任务单"]),
    ("课后练习", ["课后练习", "作业练习"]),
]


def parse_resource_id(page_url: str) -> str:
    query = parse_qs(urlparse(page_url).query)
    resource_id = (query.get("activityId") or query.get("resourceId") or [""])[0]
    if not resource_id:
        raise ValueError("URL 中没有找到 activityId/resourceId。请使用课程详情页 URL。")
    return resource_id


def parse_res_ref(ref: str) -> list[int]:
    if "[" not in ref or "]" not in ref:
        return []
    inside = ref.split("[", 1)[1].split("]", 1)[0]
    return [int(x.strip()) for x in inside.split(",") if x.strip().isdigit()]


def get_zh_title(value) -> str:
    if isinstance(value, dict):
        return value.get("zh-CN") or next(iter(value.values()), "")
    return value or ""


def get_access_token_from_auth(auth_path: str = AUTH_FILE) -> str:
    if not Path(auth_path).exists():
        return ""

    data = json.loads(Path(auth_path).read_text(encoding="utf-8"))
    for origin in data.get("origins", []):
        for item in origin.get("localStorage", []):
            name = item.get("name", "")
            value = item.get("value", "")
            if name.startswith("ND_UC_AUTH") and value:
                try:
                    outer = json.loads(value)
                    inner = json.loads(outer.get("value", "{}"))
                    token = inner.get("access_token")
                    if token:
                        return token
                except Exception:
                    continue
    return ""


def target_matches(resource: dict, names: list[str]) -> bool:
    custom = resource.get("custom_properties") or {}
    candidates = [
        resource.get("title"),
        get_zh_title(resource.get("global_title")),
        resource.get("resource_type_code_name"),
        custom.get("alias_name"),
        custom.get("original_title"),
    ]
    return any(candidate in names for candidate in candidates if candidate)


def find_target_resource(scope, names: list[str]) -> dict | None:
    if isinstance(scope, list):
        for item in scope:
            found = find_target_resource(item, names)
            if found:
                return found
        return None

    if not isinstance(scope, dict):
        return None

    if target_matches(scope, names):
        return scope

    for value in scope.values():
        if isinstance(value, (dict, list)):
            found = find_target_resource(value, names)
            if found:
                return found

    return None


def extract_pdf_url(resource: dict, token: str) -> str | None:
    for item in resource.get("ti_items") or []:
        storages = item.get("ti_storages") or []
        pdf_url = next(
            (
                url
                for url in storages
                if isinstance(url, str) and url.lower().split("?", 1)[0].endswith(".pdf")
            ),
            None,
        )
        if not pdf_url and item.get("ti_file_flag") == "pdf" and storages:
            pdf_url = storages[0]
        if pdf_url:
            if token and "accessToken=" not in pdf_url:
                sep = "&" if "?" in pdf_url else "?"
                pdf_url = f"{pdf_url}{sep}accessToken={token}"
            return pdf_url
    return None


def scoped_lesson_resources(data: dict, lesson_index: int) -> tuple[str, list[dict]]:
    all_resources = (data.get("relations") or {}).get("national_course_resource") or []
    lessons = ((data.get("resource_structure") or {}).get("relations")) or []

    if not lessons:
        return "第一课时", all_resources

    safe_index = max(0, min(lesson_index, len(lessons) - 1))
    lesson = lessons[safe_index]
    lesson_title = lesson.get("title") or f"第{safe_index + 1}课时"

    indices: list[int] = []
    for ref in lesson.get("res_ref") or []:
        indices.extend(parse_res_ref(ref))

    if not indices:
        return lesson_title, all_resources

    return lesson_title, [all_resources[i] for i in indices if 0 <= i < len(all_resources)]


def discover_resources(data: dict, token: str) -> list[dict]:
    title = get_zh_title(data.get("global_title")) or data.get("title") or "智慧教育资源"
    teacher_list = data.get("teacher_list") or []
    teacher = teacher_list[0].get("name") if teacher_list else ""
    lessons = ((data.get("resource_structure") or {}).get("relations")) or [None]
    total = max(1, len(lessons))

    results: list[dict] = []
    seen: set[str] = set()

    for lesson_index in range(total):
        lesson_title, scope = scoped_lesson_resources(data, lesson_index)
        for target_name, names in TARGETS:
            resource = find_target_resource(scope, names)
            if not resource:
                logging.warning("未找到：%s - %s", lesson_title, target_name)
                continue

            url = extract_pdf_url(resource, token)
            if not url:
                logging.warning("未找到 PDF 下载地址：%s - %s", lesson_title, target_name)
                continue

            key = f"{lesson_index}:{target_name}:{url}"
            if key in seen:
                continue
            seen.add(key)

            file_parts = [title]
            if total > 1:
                file_parts.append(lesson_title)
            if teacher:
                file_parts.append(teacher)
            file_parts.append(target_name)

            results.append(
                {
                    "lesson": lesson_title,
                    "type": target_name,
                    "title": title,
                    "filename": safe_filename("-".join(file_parts) + ".pdf"),
                    "url": url,
                }
            )

    return results


def download_resources(resources: list[dict], request_context) -> None:
    base_dir = ensure_download_dir() / "smartedu"
    base_dir.mkdir(parents=True, exist_ok=True)

    for index, item in enumerate(resources, start=1):
        lesson_dir = base_dir / safe_filename(item["lesson"])
        lesson_dir.mkdir(parents=True, exist_ok=True)
        path = unique_path(lesson_dir, item["filename"])

        try:
            logging.info("下载 [%s/%s] %s - %s", index, len(resources), item["lesson"], item["type"])
            response = request_context.get(item["url"], timeout=120000)
            if not response.ok:
                logging.error("下载失败：HTTP %s - %s", response.status, item["filename"])
                continue
            content_type = (response.headers.get("content-type") or "").lower()
            if "text/html" in content_type:
                logging.warning("可能下载到的是网页而不是文件：%s", item["filename"])
            path.write_bytes(response.body())
            logging.info("已保存：%s", path)
        except Exception as exc:
            logging.exception("下载失败：%s，原因：%s", item["filename"], exc)


def main() -> None:
    setup_logging()
    try:
        ensure_auth_file()
    except FileNotFoundError as exc:
        logging.error(str(exc))
        return

    page_url = input("请输入智慧教育课程页面 URL：").strip()
    if not page_url:
        logging.error("URL 不能为空。")
        return

    try:
        resource_id = parse_resource_id(page_url)
    except ValueError as exc:
        logging.error(str(exc))
        return

    token = get_access_token_from_auth()
    if not token:
        logging.warning("没有从 auth.json 中解析到 accessToken，仍会尝试使用 cookie 下载。")

    with sync_playwright() as p:
        request_context = p.request.new_context(storage_state=AUTH_FILE)
        details_url = DETAILS_URL.format(resource_id=resource_id)
        logging.info("读取资源详情：%s", details_url)
        response = request_context.get(details_url, timeout=60000)
        if not response.ok:
            logging.error("资源详情读取失败：HTTP %s", response.status)
            request_context.dispose()
            return

        resources = discover_resources(response.json(), token)
        if not resources:
            logging.error("没有发现可下载的四类资源。")
            request_context.dispose()
            return

        print("\n=== 将下载以下资源 ===")
        for i, item in enumerate(resources, start=1):
            print(f"[{i}] {item['lesson']} / {item['type']} -> {item['filename']}")

        confirm = input("\n确认全部下载？输入 y 继续：").strip().lower()
        if confirm != "y":
            logging.info("已取消。")
            request_context.dispose()
            return

        download_resources(resources, request_context)
        request_context.dispose()


if __name__ == "__main__":
    main()
