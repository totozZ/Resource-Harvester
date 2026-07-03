# Quickstart

This is the fastest path for using **Resource Harvester** as a local web resource downloader.

## Security First

`auth.json` is a local session file and may contain sensitive cookies or tokens.

Do not commit it. Do not upload it. Do not share it.

## 1. Install

```powershell
git clone https://github.com/totozZ/Resource-Harvester-.git
cd Resource-Harvester-
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

## 2. Save A Login Session

```powershell
python main.py login
```

Paste the login page URL for the website you want to download from.

Examples:

```text
https://basic.smartedu.cn/
https://example.com/login
```

Chromium opens visibly. Log in manually. After the page shows you are logged in, return to the terminal and press Enter.

This creates:

```text
auth.json
```

Keep this file local only. It is already ignored by `.gitignore`.

## Bilibili Video Dashboard

Install FFmpeg separately and confirm it is available:

```powershell
ffmpeg -version
```

Then start with a BV ID or video URL:

```powershell
python main.py bilibili "BV1..."
```

The command opens a local page where you can preview the video, select parts
and quality, choose metadata/subtitle/danmaku outputs, and watch progress.

Public videos do not require login. For optional account-authorized access:

```powershell
python main.py bilibili-login
```

This creates `auth/bilibili.json`. Keep it private. The downloader does not
bypass paid content, membership, region restrictions, account permissions, or DRM.

## 3. Inspect The Target Page

```powershell
python main.py list
```

Paste the page URL that contains files, attachments, export buttons, or download actions.

The tool prints:

- Link text and URLs
- Buttons
- `role=button` elements
- `onclick` elements

Use this step to understand what the page exposes before downloading.

## 4. Download Normal File Links

```powershell
python main.py download
```

Paste the same target page URL. Resource Harvester will list likely files first. Type:

```text
y
```

to download them into:

```text
downloads/
```

## 5. Try Button-Based Downloads

If the page uses buttons like Download, Export, 附件, 下载, 导出:

```powershell
python main.py click-download
```

Paste the target page URL. The tool will try matching buttons and capture browser download events.

## 6. SmartEdu One-Page Download

For SmartEdu course activity pages:

```text
https://basic.smartedu.cn/syncClassroom/classActivity?activityId=...
```

Run:

```powershell
python main.py smartedu
```

It downloads available courseware, teaching design, learning task sheets, and after-class exercises.

## 7. SmartEdu Full-Book Download

For SmartEdu textbook navigation pages:

```text
https://basic.smartedu.cn/syncClassroom/prepare?defaultTag=...
```

Run:

```powershell
python main.py smartedu-grade
```

It creates chapter folders and downloads all available teaching PDFs.

Example:

```text
downloads/
  smartedu/
    小学数学人教版四年级下册/
      1 四则运算/
      2 观察物体（二）/
      3 运算律/
      ...
```

## Command Cheat Sheet

```powershell
python main.py login           # Save login session
python main.py list            # Inspect links/buttons
python main.py download        # Download likely file links
python main.py click-download  # Try download/export buttons
python main.py smartedu        # SmartEdu single course page
python main.py smartedu-grade  # SmartEdu full textbook page
python main.py bilibili URL    # Bilibili local download dashboard
python main.py bilibili-login  # Save optional Bilibili login state
```

## Where Are Files Saved?

Generic downloads:

```text
downloads/
```

SmartEdu downloads:

```text
downloads/smartedu/
```

Bilibili downloads:

```text
downloads/bilibili/<video title>/
```

## Troubleshooting

If downloads fail, try this order:

1. Re-login:

```powershell
python main.py login
```

2. Inspect the page:

```powershell
python main.py list
```

3. Try normal links:

```powershell
python main.py download
```

4. Try buttons:

```powershell
python main.py click-download
```

If the site uses custom background APIs, add a site adapter or inspect the browser Network panel to find the real file endpoint.
