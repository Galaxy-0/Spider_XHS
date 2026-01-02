#!/usr/bin/env python
"""
Analyze exported Xiaohongshu note Excel files and produce deduped details + summary.

Inputs (by default):
- datas/excel_datas/*_notes.xlsx (from scripts/export_notes_and_comments.py)

Outputs:
- datas/excel_datas/xhs_notes_dedup.xlsx  (enriched detailed notes, deduped + filtered)
- datas/excel_datas/xhs_summary.xlsx      (overall/by_drug/by_author_type/by_topic/top_examples)

Steps:
- Load all *_notes.xlsx, concat, dedup by 笔记id
- Filter 上传时间 to [2023-01-01, 2025-09-05]
- Derive: 平台=小红书, 药品, 作者类型(HCP/KOP/其他), 话题标签, 浏览量=N/A, 互动总数
- Aggregate: counts + interaction rate per drug, author type share, topic share, top examples
"""
import argparse
import glob
import os
import re
from datetime import datetime
from typing import List

import pandas as pd


NOTE_COLS = [
    "笔记id",
    "笔记url",
    "笔记类型",
    "用户id",
    "用户主页url",
    "昵称",
    "头像url",
    "标题",
    "描述",
    "点赞数量",
    "收藏数量",
    "评论数量",
    "分享数量",
    "视频封面url",
    "视频地址url",
    "图片地址url列表",
    "标签",
    "上传时间",
    "ip归属地",
]


DEFAULT_START = datetime(2023, 1, 1)
DEFAULT_END = datetime(2025, 9, 5, 23, 59, 59)


def load_note_files(patterns: List[str]) -> pd.DataFrame:
    files: List[str] = []
    for p in patterns:
        files.extend(glob.glob(p))
    files = sorted(set(files))
    if not files:
        raise SystemExit(f"No input files matched: {patterns}")
    dfs = []
    for fp in files:
        try:
            df = pd.read_excel(fp)
            # basic sanity: has required columns
            if set(NOTE_COLS).issubset(df.columns):
                dfs.append(df[NOTE_COLS].copy())
        except Exception:
            continue
    if not dfs:
        raise SystemExit("No valid *_notes.xlsx files found with expected columns")
    return pd.concat(dfs, ignore_index=True)


def to_datetime_safe(s):
    try:
        return pd.to_datetime(s)
    except Exception:
        return pd.NaT


def classify_drug(text: str) -> str:
    t = text or ""
    # Normalize spaces
    t = str(t)
    # Brand override: 恒沐 / 艾米替诺福韦
    if re.search(r"恒沐|艾米替诺福韦", t):
        return "恒沐"
    # TAF
    if re.search(r"替诺福韦艾拉酚胺|TAF|韦立得", t, flags=re.IGNORECASE):
        return "TAF"
    # TDF
    if re.search(r"替诺福韦二吡呋酯|TDF|韦瑞德", t, flags=re.IGNORECASE):
        return "TDF"
    # ETV
    if re.search(r"恩替卡韦|博路定|ETV", t, flags=re.IGNORECASE):
        return "ETV"
    return "其他"


def classify_author(row: pd.Series) -> str:
    # Heuristics using nickname + title + desc + tags
    text = f"{row.get('昵称','')} {row.get('标题','')} {row.get('描述','')} {row.get('标签','')}"
    if re.search(r"医生|医师|主任|药师|医院|科普|指南|门诊|随访|临床|RCT|对照|证据", text):
        return "HCP"
    if re.search(r"日记|经验|复查|复阴|复阳|转氨酶|乙肝患者|治疗经历|用药体验", text):
        return "KOP"
    return "其他"


TOPIC_MAP = {
    "对比": r"对比|比较|优劣|选择|vs",
    "安全性": r"安全|风险|副作用|不良反应|伤肝|耐受",
    "价格": r"医保|集采|报销|价格|费|花费",
    "真实体验": r"日记|经验|复查|复阴|复阳|转氨酶|吃了|疗程",
    "指南": r"指南|共识|解读|推荐等级|循证",
}


def extract_topics(text: str) -> List[str]:
    t = str(text or "")
    tags = []
    for k, pat in TOPIC_MAP.items():
        if re.search(pat, t, flags=re.IGNORECASE):
            tags.append(k)
    return tags


def enrich(df: pd.DataFrame, start_date: datetime = DEFAULT_START, end_date: datetime = DEFAULT_END, do_date_filter: bool = True) -> pd.DataFrame:
    df = df.copy()
    # Ensure numeric interaction columns
    for c in ["点赞数量", "评论数量", "收藏数量", "分享数量"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)

    # Parse date range
    dt = df["上传时间"].apply(to_datetime_safe)
    if do_date_filter:
        df = df[dt.between(start_date, end_date, inclusive="both")].copy()

    # Derive fields
    df["平台"] = "小红书"
    cat_text = (
        df["标题"].fillna("")
        + "\n"
        + df["描述"].fillna("")
        + "\n"
        + df["标签"].astype(str).fillna("")
    )
    df["药品"] = cat_text.apply(classify_drug)
    df["作者类型"] = df.apply(classify_author, axis=1)
    df["话题标签"] = cat_text.apply(lambda s: ";".join(extract_topics(s)))
    df["浏览量"] = "N/A"
    df["互动总数"] = df[["点赞数量", "评论数量", "收藏数量", "分享数量"]].sum(axis=1)
    return df


def build_summary(df: pd.DataFrame, start_date: datetime, end_date: datetime) -> dict:
    res = {}
    total = len(df)
    total_interactions = int(df["互动总数"].sum()) if total else 0
    overall = pd.DataFrame(
        {
            "总样本数": [total],
            "总互动数": [total_interactions],
            "总体互动率(%)": [round((total_interactions / total * 100), 2) if total else 0.0],
            "时间范围": [f"{start_date.date()} ~ {end_date.date()}"],
        }
    )
    res["overall"] = overall

    # by drug
    by_drug = (
        df.groupby("药品")["互动总数"].agg(["count", "sum"]).reset_index().rename(columns={"count": "样本数", "sum": "互动数"})
    )
    by_drug["互动率(%)"] = by_drug.apply(
        lambda r: round((r["互动数"] / r["样本数"] * 100), 2) if r["样本数"] else 0.0, axis=1
    )
    res["by_drug"] = by_drug.sort_values(["互动率(%)", "样本数"], ascending=[False, False])

    # by author type
    by_author = df.groupby("作者类型")["笔记id"].count().reset_index().rename(columns={"笔记id": "样本数"})
    by_author["占比(%)"] = by_author["样本数"] / by_author["样本数"].sum() * 100
    by_author["占比(%)"] = by_author["占比(%)"].round(2)
    res["by_author_type"] = by_author.sort_values("样本数", ascending=False)

    # by topic
    # explode on topics
    tmp = df.copy()
    tmp["话题标签"] = tmp["话题标签"].fillna("")
    exploded = tmp.assign(**{"话题": tmp["话题标签"].str.split(";")}).explode("话题")
    exploded = exploded[exploded["话题"].str.len() > 0]
    by_topic = exploded.groupby("话题")["笔记id"].count().reset_index().rename(columns={"笔记id": "样本数"})
    by_topic = by_topic.sort_values("样本数", ascending=False)
    res["by_topic"] = by_topic

    # top examples
    cols = [
        "笔记id",
        "笔记url",
        "标题",
        "上传时间",
        "药品",
        "作者类型",
        "互动总数",
        "点赞数量",
        "评论数量",
        "收藏数量",
        "分享数量",
    ]
    top_examples = df.sort_values(["互动总数", "点赞数量"], ascending=False)[cols].head(50)
    res["top_examples"] = top_examples
    return res


def main():
    parser = argparse.ArgumentParser(description="Analyze XHS notes Excel into summary outputs")
    parser.add_argument(
        "--inputs",
        nargs="*",
        default=["datas/excel_datas/*_notes.xlsx"],
        help="glob patterns for input *_notes.xlsx files",
    )
    parser.add_argument(
        "--out-detail",
        default="datas/excel_datas/xhs_notes_dedup.xlsx",
        help="path to save deduped detailed notes",
    )
    parser.add_argument(
        "--out-summary",
        default="datas/excel_datas/xhs_summary.xlsx",
        help="path to save summary workbook",
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START.strftime("%Y-%m-%d"),
        help="start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="end date (YYYY-MM-DD); default to today",
    )
    parser.add_argument(
        "--no-date-filter",
        action="store_true",
        help="disable date range filtering",
    )
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.out_detail), exist_ok=True)

    # Load -> dedup -> enrich
    df = load_note_files(args.inputs)
    # Drop exact duplicates before id-dedup
    df = df.drop_duplicates()
    if "笔记id" not in df.columns:
        raise SystemExit("Missing column 笔记id in inputs")
    df = df.sort_values("上传时间").drop_duplicates(subset=["笔记id"], keep="last")
    # parse date args
    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d")
    except Exception:
        start_date = DEFAULT_START
    try:
        end_date = datetime.strptime(args.end, "%Y-%m-%d")
    except Exception:
        end_date = DEFAULT_END
    df = enrich(df, start_date=start_date, end_date=end_date, do_date_filter=not args.no_date_filter)

    # Basic lightweight noise filtering (optional & conservative)
    mask_short = (df["标题"].fillna("").str.len() < 3) & (df["描述"].fillna("").str.len() < 5) & (df["互动总数"] == 0)
    df_clean = df[~mask_short].copy()

    # Save detailed
    detail_cols = NOTE_COLS + ["平台", "药品", "作者类型", "话题标签", "浏览量", "互动总数"]
    df_clean.to_excel(args.out_detail, index=False, columns=[c for c in detail_cols if c in df_clean.columns])

    # Build and save summary
    summary = build_summary(df_clean, start_date=start_date, end_date=end_date)
    with pd.ExcelWriter(args.out_summary) as writer:
        for sheet, data in summary.items():
            data.to_excel(writer, sheet_name=sheet, index=False)

    print("== analysis done ==")
    print("detail:", args.out_detail)
    print("summary:", args.out_summary)


if __name__ == "__main__":
    raise SystemExit(main())
