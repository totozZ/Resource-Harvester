# Resource Harvester

A local Python + Playwright toolkit for harvesting downloadable resources from web pages.

中文文档：[README.cn.md](./README.cn.md)

## Security Notice

`auth.json` is a local-only session file. It may contain cookies, access tokens, or other browser storage data that can act like login credentials.

- Never commit `auth.json`.
- Never upload `auth.json` to a public repository.
- Never share `auth.json` with other people.
- If it is ever exposed, delete it, log out of the related website, rotate/revoke the session if possible, and rewrite Git history before pushing again.

This repository ignores `auth.json` in `.gitignore`.

Resource Harvester is designed for pages where downloads are hidden behind login, JavaScript-rendered links, buttons, export actions, or site-specific resource APIs. You log in manually once, the tool saves your browser session locally, and then it can reopen authenticated pages, inspect links/buttons, detect likely downloadable files, and save them into a local `downloads/` folder.

It also includes a built-in adapter for China’s SmartEdu platform as an example of how site-specific download logic can be added on top of the generic crawler/downloader.

This project does not store usernames or passwords. Login is completed manually in your browser.

## What It Can Do

- Resolve and archive public Bilibili single-part and multi-part videos
- Select DASH quality, resume partial streams, and merge with FFmpeg
- Save Bilibili covers, metadata, SRT subtitles, and XML/ASS danmaku
- Show a loopback-only local dashboard with live job progress
- Reuse your manually logged-in browser session
- Open authenticated pages with Chromium
- Scan all page links and button-like elements
- Detect likely download links by text, URL keywords, and file extensions
- Download normal `a` tag resources with authenticated cookies
- Try clicking download/export buttons and capture browser download events
- Preserve readable Chinese filenames when possible
- Save files into `downloads/`
- Provide a clean Python structure for adding more site adapters
- Include a SmartEdu adapter for course and full-book teaching resources

## Good Use Cases

- Logged-in education platforms
- Internal document portals
- Attachment pages
- Report/export pages
- Courseware download pages
- Pages where files are loaded through JavaScript
- Sites where you want to inspect links before downloading

## Limits

Resource Harvester uses your own logged-in session. It does not bypass paywalls, captchas, DRM, account permissions, or website access controls. If your browser account cannot access a file, the tool usually cannot access it either.

## Install

Python 3.11 or newer is required. Bilibili audio/video merging also requires
[FFmpeg](https://ffmpeg.org/download.html) on `PATH`.

```powershell
git clone https://github.com/totozZ/Resource-Harvester-.git
cd Resource-Harvester-
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

For tests:

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

## Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for the shortest path.

General flow:

```powershell
python main.py login
python main.py list
python main.py download
python main.py click-download
```

For SmartEdu full-book downloads:

```powershell
python main.py login
python main.py smartedu-grade
```

For Bilibili, provide a BV ID, video URL, `?p=` URL, or `b23.tv` short URL:

```powershell
python main.py bilibili "https://www.bilibili.com/video/BV..."
```

The command starts a server bound only to `127.0.0.1`, opens the dashboard,
and lets you select parts, quality, cover, metadata, subtitles, and danmaku.
Public videos work as a guest. For optional access already granted to your
account, run `python main.py bilibili-login` first.

Dashboard examples:

![Bilibili local archive download setup](./pics/download1.png)

![Bilibili local archive completed download](./pics/download2.png)

This stores sensitive cookies in `auth/bilibili.json`. Never commit, upload,
or share that file. The project does not bypass membership, payment, region,
account-permission, or DRM restrictions.

## Commands

### Save Login Session

```powershell
python main.py login
```

Enter a login page URL. Chromium opens in visible mode. Log in manually, then return to the terminal and press Enter. The session is saved to `auth.json`.

### Inspect A Page

```powershell
python main.py list
```

Enter any authenticated page URL. The tool lists:

- `a` tag text and `href`
- `button` elements
- `[role="button"]` elements
- elements with `onclick`

Use this first when you do not know how the page exposes its downloads.

### Download Normal Links

```powershell
python main.py download
```

The tool scans the page for likely downloadable links, prints candidates, asks for confirmation, then downloads them through Playwright’s authenticated request context.

Detection includes text or URL keywords:

```text
下载, download, 附件, file, export, 导出, 资料, downloadFile
```

And file extensions:

```text
.zip, .rar, .7z, .pdf, .doc, .docx, .xls, .xlsx,
.ppt, .pptx, .csv, .txt, .exe, .msi
```

### Click Download Buttons

```powershell
python main.py click-download
```

The tool searches for download/export-like buttons and tries to click them one by one. It uses `page.expect_download()` to capture browser download events. A failed button does not stop the whole run.

### SmartEdu Single Page Adapter

```powershell
python main.py smartedu
```

Use this for a SmartEdu course activity page, for example:

```text
https://basic.smartedu.cn/syncClassroom/classActivity?activityId=...
```

It downloads SmartEdu teaching resources such as courseware, teaching design, learning task sheets, and after-class exercises.

### SmartEdu Full-Book Adapter

```powershell
python main.py smartedu-grade
```

Use this for a SmartEdu full-book navigation page, for example:

```text
https://basic.smartedu.cn/syncClassroom/prepare?defaultTag=...
```

It automatically:

- Detects the textbook from `defaultTag`
- Loads the textbook chapter tree
- Creates nested folders by chapter
- Resolves each lesson package
- Downloads the available teaching PDFs

Example output:

```text
downloads/
  smartedu/
    小学数学人教版四年级下册/
      1 四则运算/
      2 观察物体（二）/
      3 运算律/
      ...
```

## Project Layout

```text
.
├─ main.py                         # CLI entrypoint
├─ save_login.py                   # Save browser login session
├─ list_links.py                   # Inspect links and buttons
├─ download_page.py                # Download regular links
├─ click_download_buttons.py       # Capture button-triggered downloads
├─ smartedu_xiaoyuan_download.py   # SmartEdu single-page adapter
├─ smartedu_grade_download.py      # SmartEdu full-book adapter
├─ utils.py                        # Shared helpers
├─ requirements.txt
├─ README.md
└─ QUICKSTART.md
```

## Extending To More Sites

The generic commands work best when files are exposed as normal links or browser downloads. If a site hides files behind JSON APIs, add a dedicated adapter similar to:

- `smartedu_xiaoyuan_download.py`
- `smartedu_grade_download.py`

Recommended adapter pattern:

1. Parse the target page URL.
2. Fetch the site’s resource JSON/API with `context.request`.
3. Extract real file URLs.
4. Build readable filenames.
5. Save into a site-specific folder under `downloads/`.

## Git Ignore

The project ignores local secrets and generated files:

```text
auth.json
downloads/
.venv/
__pycache__/
*.pyc
xiaoyuandownload-resource/
```

Do not commit `auth.json` or downloaded resources.

## FAQ

### Does this work on any website?

It can inspect and attempt downloads from any page your logged-in browser can access. Generic mode handles common links and browser downloads. Sites with custom APIs may need a small adapter.

### What if auth.json expires?

Run:

```powershell
python main.py login
```

Then log in again and save a fresh session.

### What if the downloaded file is HTML?

That usually means the URL returned an error page, login expired, access is missing, or the real file is generated by another API. Re-login, run `list`, or write a site adapter.

### What if no links are found?

Try:

```powershell
python main.py click-download
```

If the site uses background APIs, inspect browser network requests and add an adapter.

### Why is auth.json sensitive?

It stores cookies and localStorage tokens. Someone with that file may be able to reuse your logged-in session.

## Credits

The SmartEdu adapter is inspired by the public implementation approach of 小源教材下载助手: resolve SmartEdu resource JSON, locate file entries, and download them with the active login session.

- 小源页面：https://www.yuanstudy.com/pages/7/
- Public repo：https://github.com/MaxXiaoChen/xiaoyuandownload-resource
