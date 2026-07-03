# Resource Harvester

**网页资源采集器**：一个基于 Python + Playwright 的本地网页资源下载工具。

它适合处理那些需要登录后才能访问、下载入口藏在链接/按钮/导出操作/页面接口里的资源页面。你只需要手动登录一次，工具会把登录态保存在本地，然后复用这个登录态去扫描页面、识别下载项、点击下载按钮，或者通过站点适配器批量下载资源。

## 安全提醒

`auth.json` 是本地登录态文件，里面可能包含 cookie、access token 或 localStorage 数据，很多情况下等同于登录凭据。

- 不要提交 `auth.json`。
- 不要把 `auth.json` 上传到公开仓库。
- 不要把 `auth.json` 分享给别人。
- 如果不小心泄露，应删除该文件，退出相关网站登录，尽量撤销/刷新登录态，并在再次推送前清理 Git 历史。

本仓库已经在 `.gitignore` 中忽略 `auth.json`。

项目不会保存账号密码。登录由你在浏览器中手动完成。

## 适合什么场景

- 登录后才能下载附件的网站
- 教育资源平台
- 内部文档系统
- 报表导出页面
- 课程资料页面
- 有“下载 / 导出 / 附件”按钮的页面
- 文件链接由 JavaScript 动态生成的页面
- 需要先扫描、确认，再批量下载的页面

## 功能

- Bilibili 单视频、多 P 视频解析和本地可视化下载
- DASH 画质选择、断点续传及 FFmpeg 音视频合并
- Bilibili 封面、元数据、字幕 SRT、弹幕 XML/ASS 归档
- 游客访问及隔离保存的可选 Bilibili 登录态
- 手动登录一次并保存登录态
- 使用 Chromium 打开登录后的页面
- 扫描页面里的所有 `a` 链接
- 扫描按钮、`role=button`、`onclick` 元素
- 自动识别疑似下载链接
- 下载普通文件链接
- 尝试点击下载/导出按钮并捕获下载事件
- 尽量保留中文文件名
- 所有文件保存到 `downloads/`
- 结构清晰，方便后续扩展更多网站适配器
- 内置国家中小学智慧教育平台资源下载适配器

## 能不能扒任何网页？

它可以处理“你的账号本来就有权限访问”的网页资源。

它不会绕过验证码、付费墙、DRM、账号权限或网站访问控制。如果你自己的浏览器账号不能访问某个文件，工具通常也不能访问。

通用模式适合普通链接和浏览器下载事件。对于用复杂后台接口生成文件的网站，可以参考 SmartEdu 适配器写一个专门适配器。

## 安装

需要 Python 3.11 或更高版本。Bilibili 音视频合并还需要单独安装
[FFmpeg](https://ffmpeg.org/download.html)，并确保终端可以运行
`ffmpeg -version`。

克隆仓库并进入项目目录：

```powershell
git clone https://github.com/totozZ/Resource-Harvester-.git
cd Resource-Harvester-
```

创建并启用虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

安装依赖：

```powershell
pip install -r requirements.txt
```

安装 Playwright Chromium：

```powershell
playwright install chromium
```

运行测试：

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
```

## 快速开始

通用网页下载流程：

```powershell
python main.py login
python main.py list
python main.py download
python main.py click-download
```

智慧教育平台整册下载流程：

```powershell
python main.py login
python main.py smartedu-grade
```

Bilibili 本地可视化下载：

```powershell
python main.py bilibili "https://www.bilibili.com/video/BV..."
```

命令会启动仅监听 `127.0.0.1` 的服务并自动打开浏览器。游客模式可以处理
公开内容；如需使用账号本身有权访问的画质或字幕，先运行：

```powershell
python main.py bilibili-login
```

登录态保存在 `auth/bilibili.json`，属于敏感凭据，禁止提交、上传或分享。

更短的上手步骤见 [QUICKSTART.md](./QUICKSTART.md)。

## 命令说明

### Bilibili 视频归档

```powershell
python main.py bilibili <BV号或视频链接>
```

支持裸 BV 号、标准视频地址、带 `?p=` 的地址和 `b23.tv` 短链接；页面可以
选择分 P、画质、封面、元数据、字幕和弹幕，并查看下载及合并进度。

默认输出：

```text
downloads/bilibili/<视频标题>/
  metadata.json
  cover.jpg
  01-<分P标题>.mp4
  01-<分P标题>.<语言>.srt
  01-<分P标题>.danmaku.xml
  01-<分P标题>.danmaku.ass
```

本项目不绕过会员、付费、地区、账号权限或 DRM，仅处理公开内容或当前账号
本身有权访问的内容。高级定位弹幕不会写入基础 ASS，并会在页面显示跳过数量。

### 1. 保存登录态

```powershell
python main.py login
```

输入登录页 URL。浏览器会以可见模式打开。你手动完成登录后，回到命令行按回车，工具会保存 `auth.json`。

### 2. 扫描页面链接和按钮

```powershell
python main.py list
```

输入目标页面 URL。工具会输出：

- 链接文本和 `href`
- `button` 元素
- `[role="button"]` 元素
- 带 `onclick` 的元素

如果你不知道页面的下载入口在哪里，先运行这个命令。

### 3. 下载普通链接

```powershell
python main.py download
```

工具会扫描疑似下载链接，先列出候选项，输入 `y` 后才开始下载。

识别关键词包括：

```text
下载, download, 附件, file, export, 导出, 资料, downloadFile
```

识别文件后缀包括：

```text
.zip, .rar, .7z, .pdf, .doc, .docx, .xls, .xlsx,
.ppt, .pptx, .csv, .txt, .exe, .msi
```

### 4. 尝试按钮下载

```powershell
python main.py click-download
```

工具会查找“下载 / Download / 附件 / 导出 / Export / 资料”等按钮，逐个尝试点击，并用 Playwright 捕获下载事件。某个按钮失败不会中断整个流程。

### 5. 智慧教育平台单课下载

```powershell
python main.py smartedu
```

适合这种页面：

```text
https://basic.smartedu.cn/syncClassroom/classActivity?activityId=...
```

会下载当前课程里的：

- 课件
- 教学设计
- 学习任务单
- 课后练习

### 6. 智慧教育平台整册下载

```powershell
python main.py smartedu-grade
```

适合这种整册导航页：

```text
https://basic.smartedu.cn/syncClassroom/prepare?defaultTag=...
```

工具会自动：

- 根据 `defaultTag` 识别教材
- 拉取教材目录树
- 按章节创建文件夹
- 逐个解析课程包
- 下载可用的教学 PDF

示例目录：

```text
downloads/
  smartedu/
    小学数学人教版四年级下册/
      1 四则运算/
      2 观察物体（二）/
      3 运算律/
      ...
```

## 项目结构

```text
.
├─ main.py                         # 统一命令入口
├─ save_login.py                   # 手动登录并保存 auth.json
├─ list_links.py                   # 扫描页面链接和按钮
├─ download_page.py                # 下载普通链接
├─ click_download_buttons.py       # 尝试点击按钮下载
├─ smartedu_xiaoyuan_download.py   # 智慧教育平台单课适配器
├─ smartedu_grade_download.py      # 智慧教育平台整册适配器
├─ utils.py                        # 公共函数
├─ requirements.txt
├─ README.md
├─ README.cn.md
└─ QUICKSTART.md
```

## 如何扩展更多网站

通用命令适合普通链接和标准下载事件。如果某个网站把真实文件地址藏在接口里，可以新增一个站点适配器。

推荐流程：

1. 从用户输入的页面 URL 解析资源 ID 或参数。
2. 使用 Playwright 的 `context.request` 带登录态请求接口。
3. 从 JSON/API 响应中提取真实文件 URL。
4. 生成安全、可读的文件名。
5. 保存到 `downloads/站点名/`。

可以参考：

- `smartedu_xiaoyuan_download.py`
- `smartedu_grade_download.py`

## Git 忽略

项目已忽略本地敏感文件和下载产物：

```text
auth.json
downloads/
.venv/
__pycache__/
*.pyc
xiaoyuandownload-resource/
```

不要提交 `auth.json` 和 `downloads/`。

## 常见问题

### auth.json 失效怎么办？

重新登录：

```powershell
python main.py login
```

### 下载下来是 HTML 怎么办？

通常说明登录态失效、权限不足、真实文件地址不在当前链接里，或者网站返回了错误页。先重新登录，再用 `list` 观察页面，必要时写站点适配器。

### 页面找不到下载链接怎么办？

先运行：

```powershell
python main.py list
```

如果是按钮下载，再运行：

```powershell
python main.py click-download
```

如果页面通过后台接口生成文件，需要分析 Network 请求并写适配器。

### 为什么有些目录是空的？

整册下载会按教材目录完整建文件夹。如果平台资源索引里某章没有对应课程包，这个目录会存在，但没有 PDF。

### 为什么不能上传 auth.json？

`auth.json` 保存 cookie 和 localStorage token。别人拿到后可能复用你的登录状态。

## 致谢

SmartEdu 适配器参考了“小源教材下载助手”的公开实现思路：解析智慧教育平台资源 JSON，从资源条目中定位文件链接，并结合当前登录态下载。

- 小源页面：https://www.yuanstudy.com/pages/7/
- 公开仓库：https://github.com/MaxXiaoChen/xiaoyuandownload-resource
