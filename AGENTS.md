# Repository Guidelines

## Project Structure & Module Organization
- `apis/`: HTTP clients for Xiaohongshu (e.g., `xhs_pc_apis.py`, `xhs_creator_apis.py`).
- `xhs_utils/`: helpers for cookies, signing, data IO (e.g., `common_util.py`, `data_util.py`). Creates `datas/media_datas` and `datas/excel_datas` on first run.
- `static/`: JS used by PyExecJS (`xhs_xs_xsc_56.js`, `xhs_xray.js`).
- `main.py`: entry point with example flows (notes, user notes, search).
- `.env`: local config; set `COOKIES`.
- `author/`: project images; `datas/` is generated at runtime.

## Build, Test, and Development Commands
- Install Python deps: `pip install -r requirements.txt`
- Install Node deps (ExecJS backend): `npm install`
- Run locally: `python main.py`
- Docker build: `docker build -t spider_xhs .`
- Docker run (example): `docker run --rm -e COOKIES='your_cookie' -v "$PWD/datas:/app/datas" spider_xhs`

## Coding Style & Naming Conventions
- Python 3.7+; 4‑space indent; follow PEP 8.
- Naming: snake_case (func/vars), PascalCase (classes), UPPER_SNAKE_CASE (constants).
- Module layout: APIs in `apis/`, utilities in `xhs_utils/`. Keep side effects under `if __name__ == "__main__":`.
- Logging: use `loguru`; avoid `print` in library modules.

## Testing Guidelines
- No formal test suite yet. Use smoke tests:
  - Set `COOKIES` in `.env`, run `python main.py`.
  - Validate outputs in `datas/media_datas` and `datas/excel_datas`.
- If adding tests, prefer `pytest`, name files `test_*.py`, and mock network I/O.

## Commit & Pull Request Guidelines
- Commits: prefer Conventional Commits (e.g., `feat: 增加创作者接口`, `fix: 修复视频编码问题`, `docs: 更新 README`).
- PRs: include what/why, reproduction/test steps, sample outputs/screenshots (e.g., saved Excel), and linked issues.
- Keep changes focused; update README when behavior or flags change.

## Security & Configuration Tips
- Never commit `.env` or cookies; `.gitignore` excludes them.
- Pass secrets via env: `-e COOKIES=...` or `--env-file .env`.
- Optional `proxies` args are supported by API methods; don’t hardcode secrets, tokens, or endpoints.

