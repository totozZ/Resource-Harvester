from main import build_parser


def test_bilibili_command_arguments() -> None:
    args = build_parser().parse_args(
        ["bilibili", "BV1RVTz6HEc3", "--port", "9000", "--no-open"]
    )
    assert args.command == "bilibili"
    assert args.url == "BV1RVTz6HEc3"
    assert args.port == 9000
    assert args.no_open is True


def test_legacy_commands_still_parse() -> None:
    parser = build_parser()
    for command in (
        "login",
        "list",
        "download",
        "click-download",
        "smartedu",
        "smartedu-grade",
        "bilibili-login",
    ):
        assert parser.parse_args([command]).command == command
