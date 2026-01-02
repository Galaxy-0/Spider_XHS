#!/usr/bin/env python
"""
End-to-end XHS pipeline: search across keywords until target notes collected,
fetch note details (and optionally comments), export combined Excel, then run analysis.

Outputs:
- datas/excel_datas/xhs_pipeline_notes.xlsx
- datas/excel_datas/xhs_pipeline_comments.xlsx (if comments enabled)
- datas/excel_datas/xhs_notes_dedup.xlsx
- datas/excel_datas/xhs_summary.xlsx

Progress checkpoints are written periodically to avoid data loss on long runs.
"""
import argparse
import os
import sys
import time
import random
import re
from typing import Dict, List, Set, Tuple

from apis.xhs_pc_apis import XHS_Apis
from xhs_utils.common_util import init
from xhs_utils.data_util import handle_note_info, handle_comment_info, save_to_xlsx


DEFAULT_KEYWORDS = [
    # 核心词
    "慢性乙肝",
    "替诺福韦",
    "韦立得",
    "韦瑞德",
    "恩替卡韦",
    "博路定",
    "恒沐",
    "艾米替诺福韦",
    # 扩展词
    "乙肝治疗",
    "乙肝药物",
    "肝炎用药",
    "乙肝患者经验",
    "乙肝安全性对比",
    "乙肝医保",
    "乙肝停药",
]


def build_note_url(note: Dict) -> str:
    return f"https://www.xiaohongshu.com/explore/{note['id']}?xsec_token={note['xsec_token']}"


def log(msg: str):
    print(time.strftime("[%H:%M:%S]"), msg, flush=True)


NOTE_HEADERS_CN = [
    '笔记id', '笔记url', '笔记类型', '用户id', '用户主页url', '昵称', '头像url', '标题', '描述',
    '点赞数量', '收藏数量', '评论数量', '分享数量', '视频封面url', '视频地址url', '图片地址url列表', '标签', '上传时间', 'ip归属地'
]


def _extract_note_id(item: Dict) -> str:
    return str(item.get('note_id') or item.get('笔记id') or '')


def _normalize_to_cn(item: Dict) -> Dict:
    # Map english keys from handle_note_info to CN header order.
    if '笔记id' in item:
        # already CN-ordered
        return {k: item.get(k) for k in NOTE_HEADERS_CN}
    mapping = {
        '笔记id': 'note_id',
        '笔记url': 'note_url',
        '笔记类型': 'note_type',
        '用户id': 'user_id',
        '用户主页url': 'home_url',
        '昵称': 'nickname',
        '头像url': 'avatar',
        '标题': 'title',
        '描述': 'desc',
        '点赞数量': 'liked_count',
        '收藏数量': 'collected_count',
        '评论数量': 'comment_count',
        '分享数量': 'share_count',
        '视频封面url': 'video_cover',
        '视频地址url': 'video_addr',
        '图片地址url列表': 'image_list',
        '标签': 'tags',
        '上传时间': 'upload_time',
        'ip归属地': 'ip_location',
    }
    return {cn: item.get(en) for cn, en in mapping.items()}


def _read_existing_notes(excel_dir: str) -> Tuple[List[Dict], Set[str]]:
    """Read existing pipeline notes (CN-ordered dicts) and ids."""
    rows: List[Dict] = []
    ids: Set[str] = set()
    try:
        from openpyxl import load_workbook
        path = os.path.join(excel_dir, "xhs_pipeline_notes.xlsx")
        if not os.path.exists(path):
            return rows, ids
        wb = load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        header_cells = next(ws.iter_rows(min_row=1, max_row=1))
        headers = [c.value for c in header_cells]
        # Fallback if headers mismatch: use first row
        if not headers or headers[0] != '笔记id':
            headers = NOTE_HEADERS_CN
        for r in ws.iter_rows(min_row=2, values_only=True):
            if not r or not r[0]:
                continue
            d = {h: r[i] if i < len(r) else None for i, h in enumerate(headers)}
            nid = str(d.get('笔记id') or '')
            if nid:
                ids.add(nid)
                rows.append({k: d.get(k) for k in NOTE_HEADERS_CN})
    except Exception:
        pass
    return rows, ids


def _build_proxies_from_env() -> Dict[str, str]:
    """Build requests proxies dict from environment variables if present."""
    # Prefer XHS_HTTP_PROXY / XHS_HTTPS_PROXY, fallback to standard vars
    http = os.getenv("XHS_HTTP_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("http_proxy")
    https = os.getenv("XHS_HTTPS_PROXY") or os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")
    proxies: Dict[str, str] = {}
    if http:
        proxies["http"] = http
    if https:
        proxies["https"] = https
    return proxies


def run_pipeline(
    keywords: List[str],
    target: int,
    sort: int,
    per_kw_limit: int,
    sleep_sec: float,
    with_comments: bool,
) -> Tuple[List[Dict], List[Dict], Dict]:
    cookies, base_path = init()
    api = XHS_Apis()
    proxies = _build_proxies_from_env() or None

    seen_ids: Set[str] = set()
    note_urls: List[str] = []
    note_rows_cn: List[Dict] = []
    comment_rows: List[Dict] = []

    # Resume from existing checkpoint (rows + ids)
    resume_rows, resume_ids = _read_existing_notes(base_path["excel"])
    if resume_rows:
        seen_ids |= resume_ids
        note_rows_cn.extend(resume_rows)
        log(f"resume: preload {len(resume_ids)} existing ids from checkpoint")

    def checkpoint():
        out_notes = os.path.join(base_path["excel"], "xhs_pipeline_notes.xlsx")
        if not note_rows_cn:
            log("checkpoint skipped (no rows)")
        else:
            # dedup by 笔记id before save
            uniq = {}
            for r in note_rows_cn:
                uniq[_extract_note_id(r)] = r
            merged = list(uniq.values())
            save_to_xlsx(merged, out_notes, type="note")
        if with_comments and comment_rows:
            out_cmts = os.path.join(base_path["excel"], "xhs_pipeline_comments.xlsx")
            from openpyxl import Workbook
            # Reuse save_to_xlsx with comment type if available
            try:
                save_to_xlsx(comment_rows, out_cmts, type="comment")
            except Exception:
                # Fallback minimal writer
                wb = Workbook()
                ws = wb.active
                if comment_rows:
                    ws.append(list(comment_rows[0].keys()))
                    for r in comment_rows:
                        ws.append(list(r.values()))
                wb.save(out_cmts)
        log("checkpoint saved")

    for kw in keywords:
        if len(seen_ids) >= target:
            break
        log(f"[search] '{kw}' limit={per_kw_limit} sort={sort}")
        # basic backoff retries for search
        backoffs = [5, 15, 30, 60]
        for attempt, wait in enumerate([0] + backoffs):
            if wait:
                log(f"  backoff {wait}s before retry (attempt {attempt+1})")
                time.sleep(wait)
            ok, msg, items = api.search_some_note(
                kw, per_kw_limit, cookies, sort_type_choice=sort, proxies=proxies
            )
            if ok:
                break
            # Break early on auth issues to avoid hammering
            if any(s in str(msg) for s in ["登录", "无登录", "expired", "过期"]):
                log(f"  ! auth error: {msg}")
                break
            if any(s in str(msg) for s in ["限制", "频繁", "429", "too many", "frequency", "aborted"]):
                # continue the retry loop
                continue
            # other errors: stop retrying this keyword
            break
        if not ok:
            log(f"  ! search fail: {msg}")
            continue
        notes = [i for i in items if i.get("model_type") == "note"]
        urls = [build_note_url(n) for n in notes]
        log(f"  + found {len(urls)} candidates")

        for url in urls:
            if len(seen_ids) >= target:
                break
            # Detail
            ok, msg, res = api.get_note_info(url, cookies, proxies=proxies)
            if not ok or not res:
                continue
            try:
                raw = res["data"]["items"][0]
                raw["url"] = url
                info = handle_note_info(raw)
                nid = info.get("note_id")
                if not nid or nid in seen_ids:
                    continue
                seen_ids.add(nid)
                note_urls.append(url)
                note_rows_cn.append(_normalize_to_cn(info))
            except Exception:
                continue

            # Comments (optional)
            if with_comments:
                ok, msg, comments = api.get_note_all_comment(url, cookies, proxies=proxies)
                if ok and comments:
                    for c in comments:
                        try:
                            comment_rows.append(handle_comment_info(c))
                        except Exception:
                            pass

            # Periodic checkpoint
            if len(seen_ids) % 100 == 0:
                log(f"  progress: {len(seen_ids)} notes; writing checkpoint")
                checkpoint()

            if sleep_sec > 0:
                # add small jitter to reduce detectability
                jitter = min(0.3, sleep_sec)
                time.sleep(sleep_sec + random.uniform(0, jitter))

    # Final checkpoint
    checkpoint()
    return note_rows_cn, comment_rows, base_path


def main():
    parser = argparse.ArgumentParser(description="Run XHS end-to-end pipeline to target notes")
    parser.add_argument("--target", type=int, default=1000, help="target unique notes to collect")
    parser.add_argument("--sort", type=int, default=2, help="0 综合, 1 最新, 2 最多点赞, 3 最多评论, 4 最多收藏")
    parser.add_argument("--per-keyword-limit", type=int, default=300, help="max notes to fetch per keyword")
    parser.add_argument("--sleep", type=float, default=0.0, help="sleep seconds between note detail requests")
    parser.add_argument("--keywords", nargs="*", default=DEFAULT_KEYWORDS, help="keywords to iterate (space separated)")
    parser.add_argument("--comments", action="store_true", help="also fetch all comments per note (slower)")
    parser.add_argument("--no-analyze", action="store_true", help="skip running analyze_xhs after export")
    args = parser.parse_args()

    log(
        f"start pipeline: target={args.target}, sort={args.sort}, per_kw_limit={args.per_keyword_limit}, comments={args.comments}"
    )
    notes, comments, base_path = run_pipeline(
        args.keywords, args.target, args.sort, args.per_keyword_limit, args.sleep, args.comments
    )
    log(f"collected: notes={len(notes)}, comments={len(comments)}")

    # Analyze
    if not args.no_analyze:
        try:
            # Prefer importing the analyzer to avoid subprocess overhead
            analyze_path = os.path.join(os.path.dirname(__file__), "analyze_xhs.py")
            sys.path.insert(0, os.path.dirname(analyze_path))
            import analyze_xhs as analyzer  # type: ignore

            # Use default glob of *_notes.xlsx plus our combined file
            inputs_patterns = [
                os.path.join(base_path["excel"], "*_notes.xlsx"),
                os.path.join(base_path["excel"], "xhs_pipeline_notes.xlsx"),
            ]
            detail_path = os.path.join(base_path["excel"], "xhs_notes_dedup.xlsx")
            summary_path = os.path.join(base_path["excel"], "xhs_summary.xlsx")
            log("running analysis ...")

            # Reuse analyzer functions directly
            df = analyzer.load_note_files(inputs_patterns)  # type: ignore
            df = df.drop_duplicates().sort_values("上传时间").drop_duplicates(subset=["笔记id"], keep="last")
            df = analyzer.enrich(df)  # type: ignore
            # Light noise filter
            mask_short = (df["标题"].fillna("").str.len() < 3) & (df["描述"].fillna("").str.len() < 5) & (df["互动总数"] == 0)
            df_clean = df[~mask_short].copy()
            detail_cols = analyzer.NOTE_COLS + ["平台", "药品", "作者类型", "话题标签", "浏览量", "互动总数"]  # type: ignore
            df_clean.to_excel(detail_path, index=False, columns=[c for c in detail_cols if c in df_clean.columns])
            summary = analyzer.build_summary(df_clean)  # type: ignore
            import pandas as pd

            with pd.ExcelWriter(summary_path) as writer:
                for sheet, data in summary.items():
                    data.to_excel(writer, sheet_name=sheet, index=False)
            log("analysis done")
        except Exception as e:
            log(f"analysis skipped due to error: {e}")

    log("== pipeline finished ==")


if __name__ == "__main__":
    raise SystemExit(main())
