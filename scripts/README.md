# scripts 使用说明

本目录提供一键脚本，帮助你在 uv 隔离的 Python 环境下，使用全局 Node 执行搜索、导出笔记详情与评论等任务。

## 前置条件
- 已安装 uv 与 Node/npm（Node ≥ 18，推荐 20+）。
- 项目根目录 `.env` 写入登录 Cookie：
  - `COOKIES="a1=...; web_session=...; webId=...; ..."`（必须包含 `a1`）。
- 首次安装依赖：
  - `uv sync`
  - `npm ci`

## 脚本列表

### 1) scripts/setup_uv.sh
- 作用：一键执行 `uv sync` → `npm ci` → 关键词搜索与导出（调用 `check_env.py`）。
- 用法：
  ```bash
  bash scripts/setup_uv.sh "关键词" [limit] [export]
  # 例如：
  bash scripts/setup_uv.sh "植青俱乐部" 100 excel
  ```
- 参数：
  - `limit`：最大笔记数（默认 50）
  - `export`：导出方式（`none|excel|media|all|media-image|media-video`，默认 `excel`）
- 输出：
  - Excel 在 `datas/excel_datas/`；媒体在 `datas/media_datas/`。

### 2) scripts/check_env.py
- 作用：环境自检（Python/Node/ExecJS/Cookies）+ 按关键词搜索，按需导出。
- 用法：
  ```bash
  uv run python scripts/check_env.py --keyword "植青俱乐部" --limit 100 --sort 2 --export excel
  ```
- 参数：
  - `--keyword`（必填）：搜索关键词
  - `--limit`：最大笔记数（默认 20）
  - `--sort`：0 综合，1 最新，2 最多点赞，3 最多评论，4 最多收藏（默认 2）
  - `--export`：同上（默认 excel）
- 说明：控制台会打印 `notes found` 与输出目录。

### 3) scripts/export_notes_and_comments.py
- 作用：按关键词拉取笔记，获取每条的“详情”和“全部评论”，导出两份表。
- 用法：
  ```bash
  uv run python scripts/export_notes_and_comments.py --keyword "植青俱乐部" --limit 100 --sort 2
  # 下媒体：
  uv run python scripts/export_notes_and_comments.py --keyword "植青俱乐部" --limit 100 --sort 2 --media all
  ```
- 参数：
  - `--keyword`（必填）：搜索关键词
  - `--limit`：最大笔记数（默认 50）
  - `--sort`：排序同上
  - `--media`：`none|media|media-image|media-video|all`（默认 none）
- 输出：
  - `datas/excel_datas/<keyword>_notes.xlsx`（标题/描述/标签/点赞/评论/收藏/分享/直链/时间/IP 等）
  - `datas/excel_datas/<keyword>_comments.xlsx`（评论内容/点赞/时间/用户信息/图片等）
  - 媒体（可选）在 `datas/media_datas/`。

## 常见问题
- ExecJS 报错找不到 Node：确保 `node -v` 可用；若使用 nvm，确认当前 shell 已初始化 nvm。
- 登录态失效：`.env` 里的 `COOKIES` 需要更新（必须含 `a1`）。
- 数量不足：接口可能返回不足或 `has_more=false` 提前结束；提高 `--limit` 或调整 `--sort` 尝试。

