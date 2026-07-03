import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Resource Harvester")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("login", help="手动登录并保存 auth.json")
    subparsers.add_parser("list", help="列出页面链接和按钮")
    subparsers.add_parser("download", help="扫描并下载普通链接")
    subparsers.add_parser("click-download", help="尝试点击按钮触发下载")
    subparsers.add_parser("smartedu", help="按小源逻辑下载智慧教育平台四类资源")
    subparsers.add_parser("smartedu-grade", help="按教材目录整册下载智慧教育平台四类资源")

    bilibili = subparsers.add_parser(
        "bilibili",
        help="打开本地页面下载 Bilibili 单视频或多P视频",
    )
    bilibili.add_argument("url", help="BV号、Bilibili 视频地址或 b23.tv 短链接")
    bilibili.add_argument(
        "--port",
        type=int,
        default=8765,
        help="首选本地端口，默认 8765",
    )
    bilibili.add_argument(
        "--no-open",
        action="store_true",
        help="不自动打开默认浏览器",
    )
    subparsers.add_parser(
        "bilibili-login",
        help="手动登录 Bilibili 并保存独立登录态",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "login":
        from save_login import save_login

        save_login()
    elif args.command == "list":
        from list_links import list_links

        list_links()
    elif args.command == "download":
        from download_page import download_page

        download_page()
    elif args.command == "click-download":
        from click_download_buttons import click_download_buttons

        click_download_buttons()
    elif args.command == "smartedu":
        from smartedu_xiaoyuan_download import main as smartedu_download

        smartedu_download()
    elif args.command == "smartedu-grade":
        from smartedu_grade_download import main as smartedu_grade_download

        smartedu_grade_download()
    elif args.command == "bilibili":
        from utils import setup_logging
        from resource_harvester.web.launcher import launch_bilibili_dashboard

        setup_logging()
        launch_bilibili_dashboard(
            args.url,
            preferred_port=args.port,
            open_browser=not args.no_open,
        )
    elif args.command == "bilibili-login":
        from utils import setup_logging
        from resource_harvester.web.launcher import save_bilibili_login

        setup_logging()
        save_bilibili_login()


if __name__ == "__main__":
    main()
