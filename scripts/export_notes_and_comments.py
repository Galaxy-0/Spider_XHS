#!/usr/bin/env python
"""
Search notes by keyword, fetch full note details and all comments, and export to Excel.

Outputs:
- datas/excel_datas/<keyword>_notes.xlsx
- datas/excel_datas/<keyword>_comments.xlsx

Optionally downloads media to datas/media_datas/ via --media.
"""
import argparse
import os
from typing import List, Dict

from xhs_utils.common_util import init
from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.data_util import handle_note_info, handle_comment_info, save_to_xlsx, download_note


def build_note_url(note: Dict) -> str:
    return f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export notes + comments by keyword")
    parser.add_argument("--keyword", required=True, help="search keyword")
    parser.add_argument("--limit", type=int, default=50, help="max notes to fetch")
    parser.add_argument("--sort", type=int, default=2, help="0 综合, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏")
    parser.add_argument(
        "--media",
        default="none",
        choices=["none", "all", "media", "media-image", "media-video"],
        help="download media to datas/media_datas",
    )
    args = parser.parse_args()

    cookies, base_path = init()
    api = XHS_Apis()

    print(f"[1/4] search '{args.keyword}' limit={args.limit} sort={args.sort}")
    ok, msg, items = api.search_some_note(
        args.keyword, args.limit, cookies, sort_type_choice=args.sort
    )
    if not ok:
        print("[!] search failed:", msg)
        return 1

    notes = [i for i in items if i.get("model_type") == "note"]
    note_urls = [build_note_url(n) for n in notes]
    print(f"[+] notes: {len(note_urls)}")

    print("[2/4] fetch note details")
    note_rows: List[Dict] = []
    for url in note_urls:
        ok, msg, res = api.get_note_info(url, cookies)
        if not ok or not res:
            print("  - skip (detail fail):", url, msg)
            continue
        try:
            raw = res["data"]["items"][0]
            raw["url"] = url
            info = handle_note_info(raw)
            note_rows.append(info)
        except Exception as e:
            print("  - skip (parse fail):", url, e)

    if not note_rows:
        print("[!] no note details parsed; aborting comments step")
        return 2

    print("[3/4] fetch all comments per note")
    comment_rows: List[Dict] = []
    for url in note_urls:
        ok, msg, comments = api.get_note_all_comment(url, cookies)
        if not ok:
            print("  - skip (comments fail):", url, msg)
            continue
        for c in comments:
            # ensure note_url for downstream formatter
            c["note_url"] = url
            try:
                comment_rows.append(handle_comment_info(c))
            except Exception:
                # ignore malformed comment
                pass

    print("[4/4] export")
    excel_base = base_path["excel"]
    notes_xlsx = os.path.join(excel_base, f"{args.keyword}_notes.xlsx")
    comments_xlsx = os.path.join(excel_base, f"{args.keyword}_comments.xlsx")
    save_to_xlsx(note_rows, notes_xlsx, type="note")
    if comment_rows:
        save_to_xlsx(comment_rows, comments_xlsx, type="comment")
    else:
        print("[i] no comments parsed; skip comments.xlsx")

    if args.media != "none":
        print("[i] downloading media ->", base_path["media"])
        for n in note_rows:
            try:
                download_note(n, base_path["media"], args.media)
            except Exception:
                pass

    print("== done ==")
    print("notes:", notes_xlsx)
    if comment_rows:
        print("comments:", comments_xlsx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

