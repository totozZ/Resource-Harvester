import logging
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from playwright.sync_api import sync_playwright

from smartedu_xiaoyuan_download import (
    DETAILS_URL,
    discover_resources,
    get_access_token_from_auth,
    get_zh_title,
)
from utils import AUTH_FILE, ensure_download_dir, safe_filename, setup_logging, unique_path


TEACHING_MATERIAL_PARTS_URL = (
    "https://s-file-2.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/teachingmaterials/parts.json"
)
TREE_URL = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/trees/{material_id}.json"
RESOURCE_PARTS_URL = (
    "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/"
    "teachingmaterials/{material_id}/resources/parts.json"
)


def default_tag_ids(page_url: str) -> set[str]:
    query = parse_qs(urlparse(page_url).query)
    default_tag = unquote((query.get("defaultTag") or [""])[0])
    ids = {part for part in default_tag.split("/") if part}
    if not ids:
        raise ValueError("URL 中没有 defaultTag，无法自动定位教材。")
    return ids


def fetch_json(request_context, url: str):
    response = request_context.get(url, timeout=60000)
    if not response.ok:
        raise RuntimeError(f"读取失败 HTTP {response.status}: {url}")
    return response.json()


def find_material(request_context, tag_ids: set[str]) -> dict:
    part_urls = fetch_json(request_context, TEACHING_MATERIAL_PARTS_URL)
    for part_url in part_urls:
        for material in fetch_json(request_context, part_url):
            material_tag_ids = {tag.get("tag_id") for tag in material.get("tag_list") or []}
            if tag_ids.issubset(material_tag_ids):
                return material
    raise RuntimeError("没有找到匹配 defaultTag 的教材。")


def walk_tree(nodes: list[dict], parents: list[str] | None = None):
    parents = parents or []
    for node in nodes:
        title = node.get("title") or node.get("rich_title") or node.get("id")
        path_titles = parents + [title]
        yield node, path_titles
        children = node.get("child_nodes") or []
        yield from walk_tree(children, path_titles)


def build_path_map(tree: list[dict]) -> dict[str, list[str]]:
    path_map: dict[str, list[str]] = {}
    for node, path_titles in walk_tree(tree):
        if node.get("node_path"):
            path_map[node["node_path"]] = path_titles
        if node.get("id"):
            path_map[node["id"]] = path_titles
    return path_map


def create_tree_dirs(root: Path, tree: list[dict]) -> None:
    for _, path_titles in walk_tree(tree):
        folder = root
        for title in path_titles:
            folder = folder / safe_filename(title)
        folder.mkdir(parents=True, exist_ok=True)


def resource_folder(root: Path, path_map: dict[str, list[str]], resource: dict) -> Path:
    chapter_path = ((resource.get("chapter_paths") or resource.get("chapter_ids") or [""])[0])
    titles = path_map.get(chapter_path)

    if not titles and "/" in chapter_path:
        titles = path_map.get(chapter_path.rsplit("/", 1)[0])
    if not titles:
        titles = ["未归类"]

    folder = root
    for title in titles:
        folder = folder / safe_filename(title)

    resource_title = resource.get("title") or get_zh_title(resource.get("global_title")) or resource.get("id")
    if resource_title and (not titles or resource_title != titles[-1]):
        folder = folder / safe_filename(resource_title)

    folder.mkdir(parents=True, exist_ok=True)
    return folder


def load_national_lessons(request_context, material_id: str) -> list[dict]:
    part_urls = fetch_json(request_context, RESOURCE_PARTS_URL.format(material_id=material_id))
    lessons: list[dict] = []
    for part_url in part_urls:
        for item in fetch_json(request_context, part_url):
            if item.get("resource_type_code") == "national_lesson":
                lessons.append(item)
    return lessons


def download_one(response_context, url: str, path: Path) -> bool:
    response = response_context.get(url, timeout=120000)
    if not response.ok:
        logging.error("下载失败 HTTP %s: %s", response.status, path.name)
        return False

    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" in content_type:
        logging.warning("可能下载到的是网页而不是文件：%s", path.name)

    path.write_bytes(response.body())
    return True


def download_grade(page_url: str) -> None:
    setup_logging()

    tag_ids = default_tag_ids(page_url)
    token = get_access_token_from_auth()
    if not token:
        logging.warning("没有从 auth.json 中解析到 accessToken，仍会尝试使用 cookie 下载。")

    with sync_playwright() as p:
        auth_path = Path(AUTH_FILE)
        request_context = p.request.new_context(storage_state=AUTH_FILE) if auth_path.exists() else p.request.new_context()

        material = find_material(request_context, tag_ids)
        material_id = material["id"]
        material_title = material.get("title") or "智慧教育整册资源"
        root = ensure_download_dir() / "smartedu" / safe_filename(material_title)
        root.mkdir(parents=True, exist_ok=True)

        logging.info("教材：%s (%s)", material_title, material_id)

        tree = fetch_json(request_context, TREE_URL.format(material_id=material_id))
        path_map = build_path_map(tree)
        create_tree_dirs(root, tree)

        lessons = load_national_lessons(request_context, material_id)
        logging.info("发现课程包：%s 个", len(lessons))

        total_files = 0
        ok_files = 0
        missing_packages: list[str] = []

        for package_index, lesson in enumerate(lessons, start=1):
            package_title = lesson.get("title") or get_zh_title(lesson.get("global_title")) or lesson["id"]
            logging.info("[%s/%s] 解析课程包：%s", package_index, len(lessons), package_title)

            details_url = DETAILS_URL.format(resource_id=lesson["id"])
            try:
                details = fetch_json(request_context, details_url)
                resources = discover_resources(details, token)
            except Exception as exc:
                logging.exception("课程包解析失败：%s，原因：%s", package_title, exc)
                missing_packages.append(package_title)
                continue

            if not resources:
                logging.warning("没有发现四类 PDF：%s", package_title)
                missing_packages.append(package_title)
                continue

            package_folder = resource_folder(root, path_map, lesson)

            for item in resources:
                lesson_folder = package_folder / safe_filename(item["lesson"])
                lesson_folder.mkdir(parents=True, exist_ok=True)
                target_path = unique_path(lesson_folder, item["filename"])

                total_files += 1
                logging.info("下载 %s / %s / %s", package_title, item["lesson"], item["type"])
                try:
                    if download_one(request_context, item["url"], target_path):
                        ok_files += 1
                        logging.info("已保存：%s", target_path)
                except Exception as exc:
                    logging.exception("下载失败：%s，原因：%s", target_path.name, exc)

        request_context.dispose()

    logging.info("完成：成功 %s/%s 个文件。目录：%s", ok_files, total_files, root)
    if missing_packages:
        logging.warning("以下课程包未下载到四类 PDF：%s", "；".join(missing_packages))


def main() -> None:
    setup_logging()

    page_url = input("请输入智慧教育整册导航页 URL：").strip()
    if not page_url:
        logging.error("URL 不能为空。")
        return

    try:
        download_grade(page_url)
    except Exception as exc:
        logging.exception("整册下载失败：%s", exc)


if __name__ == "__main__":
    main()
