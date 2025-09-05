#!/usr/bin/env python
import argparse
import json
import platform
import shutil
import subprocess
import sys

from xhs_utils.common_util import init, load_env
from xhs_utils.cookie_util import trans_cookies


def shell_out(cmd):
    try:
        res = subprocess.run(cmd, check=False, capture_output=True, text=True)
        out = (res.stdout or res.stderr).strip()
        return res.returncode, out
    except Exception as e:
        return 1, str(e)


def print_kv(k, v):
    print(f"[+] {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Spider_XHS environment check and quick run")
    parser.add_argument("--keyword", default="榴莲", help="search keyword")
    parser.add_argument("--limit", type=int, default=20, help="number of notes to fetch")
    parser.add_argument("--sort", type=int, default=2, help="0 综合, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏")
    parser.add_argument(
        "--export",
        default="excel",
        choices=["none", "excel", "media", "all", "media-image", "media-video"],
        help="export mode",
    )
    args = parser.parse_args()

    print("== Spider_XHS env check ==")
    print_kv("Python", sys.version.split()[0])
    print_kv("Platform", platform.platform())

    # Node & npm
    code, node_v = shell_out([shutil.which("node") or "node", "-v"])
    print_kv("Node", node_v if code == 0 else f"not found ({node_v})")
    code, npm_v = shell_out([shutil.which("npm") or "npm", "-v"])
    print_kv("npm", npm_v if code == 0 else f"not found ({npm_v})")

    # ExecJS runtime
    try:
        import execjs

        print_kv("ExecJS runtime", execjs.get().name)
    except Exception as e:
        print_kv("ExecJS runtime", f"error: {e}")

    # Cookies
    cookies_str = load_env() or ""
    ck = trans_cookies(cookies_str) if cookies_str else {}
    print_kv("COOKIES set", bool(cookies_str))
    print_kv("has a1", "a1" in ck)

    if not cookies_str or "a1" not in ck:
        print("[!] Missing or invalid COOKIES in .env (must include a1). Aborting search step.")
        return 1

    # Optional: quick search + export
    from main import Data_Spider

    cookies, base_path = init()
    ds = Data_Spider()
    export_mode = args.export
    if export_mode == "none":
        export_mode = "media"  # avoid excel name requirement; we won't save anyway

    excel_name = args.keyword if args.export in ("excel", "all") else ""
    try:
        notes, ok, msg = ds.spider_some_search_note(
            args.keyword,
            args.limit,
            cookies,
            base_path,
            export_mode,
            args.sort,
        )
        print_kv("search ok", ok)
        if not ok:
            print_kv("search msg", msg)
        print_kv("notes found", len(notes))
        for i, url in enumerate(notes[: min(5, len(notes))], 1):
            print(f"  {i}. {url}")
        if args.export in ("excel", "all"):
            print_kv("excel dir", base_path["excel"])
        if args.export in ("media", "all", "media-image", "media-video"):
            print_kv("media dir", base_path["media"])
    except Exception as e:
        print_kv("search error", e)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

