#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s15_roster.py — 宽口径扫「教学 UP 主」，先求数量够

和 s0_creators.py 的分工：
  · s0 = 深评（要抓字幕、算质量分），一次只能覆盖 20 来个
  · s15 = 广扫（只看标题/标签/时长），目标是「有哪些人在做教学」，
          以及每个人主要讲哪个分路、哪几个英雄

用法：
  python s15_roster.py                # 扫 + 聚合 + 生成 md
  python s15_roster.py --min-vids 2   # 只保留至少 N 条命中视频的 UP
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import bili_api as B

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
OUT = ROOT / "10_sources"
OUT.mkdir(parents=True, exist_ok=True)

S45 = 1789056000  # 2026-09-23

# ── 搜索词：通用 + 分路 + 具体英雄 ─────────────────────────
KWS_COMMON = [
    "王者荣耀 教学", "王者荣耀 全局 思路", "王者荣耀 意识 教学",
    "王者荣耀 上分 教学", "王者荣耀 复盘 教学", "王者荣耀 运营 教学",
    "王者荣耀 对线 细节", "王者荣耀 bp 思路", "王者荣耀 出装 铭文",
    "王者荣耀 连招 教学", "王者荣耀 心态 上分", "王者荣耀 新手 教学",
]
KWS_LANE = [
    "王者荣耀 中路 教学", "王者荣耀 打野 教学", "王者荣耀 发育路 教学",
    "王者荣耀 对抗路 教学", "王者荣耀 游走 教学", "王者荣耀 射手 教学",
    "王者荣耀 辅助 教学", "王者荣耀 边路 教学",
]
KWS_HERO = [
    "公孙离 教学", "马可波罗 教学", "孙尚香 教学", "虞姬 教学",
    "狄仁杰 教学", "伽罗 教学", "鲁班七号 教学", "后羿 教学",
    "百里守约 教学", "蒙犽 教学", "戈娅 教学", "敖隐 教学",
]

EXCLUDE = ["自走棋", "模拟战", "棋手", "吃鸡", "皮肤", "抽奖", "开箱", "返场",
           "英雄联盟", "LOL", "端游", "云顶", "高光", "集锦", "搞笑", "沙雕",
           "直播回放", "录播", "赛事", "KPL", "主播怎么", "配音", "音乐",
           "cos", "COS", "手办", "壁纸", "剧情", "动画"]
TEACH = ["教学", "思路", "复盘", "整局", "意识", "细节", "对线", "运营",
         "上分", "节奏", "开局", "转线", "大局观", "讲解", "解析", "公式",
         "技巧", "打法", "出装", "铭文", "连招", "教程"]

LANE_PAT = [
    ("mid", re.compile(r"中路|中单|法师")),
    ("jungle", re.compile(r"打野|野区|反野|刷野")),
    ("adc", re.compile(r"射手|发育路|ADC|adc")),
    ("solo", re.compile(r"对抗路|边路|上单")),
    ("roam", re.compile(r"辅助|游走|硬辅|软辅")),
]
HEROES = ["公孙离", "马可波罗", "孙尚香", "虞姬", "狄仁杰", "伽罗", "鲁班七号",
          "后羿", "百里守约", "蒙犽", "戈娅", "敖隐", "黄忠", "李元芳", "成吉思汗",
          "艾琳", "埃罗", "女娲", "不知火舞", "小乔", "大乔", "夏洛特", "盾山",
          "鲁班大师", "苏烈", "韩信", "铠", "刘备", "雅典娜", "元歌", "王维",
          "张良", "钟馗", "庄周", "孙膑", "甄姬", "上官婉儿", "貂蝉", "干将莫邪",
          "武则天", "海月", "杨玉环", "张飞", "牛魔", "东皇太一", "蔡文姬",
          "明世隐", "瑶", "桑启", "鬼谷子", "太乙真人", "刘禅", "刘邦", "大禹",
          "空空儿", "少司缘", "朵莉亚", "安奈特", "墨子", "廉颇", "项羽",
          "白起", "达摩", "金蝉", "姜子牙", "王昭君", "孙策", "赵怀真", "夏侯惇"]


def ds(s: str) -> int:
    p = [int(x) for x in re.findall(r"\d+", s or "")]
    if len(p) == 2:
        return p[0] * 60 + p[1]
    if len(p) == 3:
        return p[0] * 3600 + p[1] * 60 + p[2]
    return 0


def clean(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t or "")


def sweep(pages: int = 2) -> list[dict]:
    f = OUT / "pool_wide.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    vids: list[dict] = []
    seen: set[str] = set()
    kws = KWS_COMMON + KWS_LANE + KWS_HERO
    for i, kw in enumerate(kws, 1):
        n0 = len(vids)
        for pg in range(1, pages + 1):
            try:
                res = B.search(kw, pg)
            except Exception as e:
                print(f"[WARN] {kw} p{pg}: {e}", file=sys.stderr)
                continue
            for x in res:
                bv = x.get("bvid") or ""
                if not bv or bv in seen:
                    continue
                seen.add(bv)
                title = clean(x.get("title"))
                tag = x.get("tag") or ""
                if "王者荣耀" not in tag and "王者荣耀" not in title:
                    continue
                if any(w in title for w in EXCLUDE):
                    continue
                d = ds(x.get("duration"))
                if d < 240 or d > 5400:
                    continue
                vids.append({"bvid": bv, "title": title,
                             "play": int(x.get("play") or 0),
                             "pubdate": int(x.get("pubdate") or 0),
                             "dur": d, "author": x.get("author", ""),
                             "mid": int(x.get("mid") or 0), "kw": kw})
            time.sleep(1.0)
        print(f"[sweep] {i}/{len(kws)} {kw} +{len(vids) - n0} (总 {len(vids)})",
              file=sys.stderr)
    f.write_text(json.dumps(vids, ensure_ascii=False), encoding="utf-8")
    return vids


def aggregate(vids: list[dict], min_vids: int = 1) -> list[dict]:
    by: dict[str, list[dict]] = defaultdict(list)
    for v in vids:
        if v["author"]:
            by[v["author"]].append(v)

    rows = []
    for author, vs in by.items():
        if len(vs) < min_vids:
            continue
        lane = Counter()
        heroes = Counter()
        teach = 0
        s45 = 0
        for v in vs:
            t = v["title"]
            if any(w in t for w in TEACH):
                teach += 1
            if v["pubdate"] >= S45:
                s45 += 1
            hit = False
            for k, p in LANE_PAT:
                if p.search(t):
                    lane[k] += 1
                    hit = True
            for h in HEROES:
                if h in t:
                    heroes[h] += 1
        rows.append({
            "author": author,
            "mid": vs[0]["mid"],
            "n": len(vs),
            "n_s45": s45,
            "teach_r": round(teach / len(vs), 2),
            "avg_min": round(sum(v["dur"] for v in vs) / len(vs) / 60, 1),
            "play_sum": sum(v["play"] for v in vs),
            "lanes": dict(lane.most_common()),
            "heroes": dict(heroes.most_common(8)),
            "top": sorted(vs, key=lambda v: (-v["dur"], -v["play"]))[:3],
        })
    rows.sort(key=lambda r: (-r["n"], -r["play_sum"]))
    return rows


LANE_CN = {"mid": "中路", "jungle": "打野", "adc": "发育路",
           "solo": "对抗路", "roam": "游走"}


def to_md(rows: list[dict], top: int = 60) -> str:
    out = ["# 教学 UP 主扩充池（自动扫，2026-11-01）", "",
           "> 这张表是**候选**，不是推荐。判据只有「近期有没有在稳定做教学」，",
           "> 质量分见 `95_信源名单.md` 的实测分档。",
           "",
           "| # | UP 主 | mid | 命中 | S45 | 教学占比 | 均长 | 主攻分路 | 常见英雄 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows[:top], 1):
        lanes = " / ".join(f"{LANE_CN.get(k, k)}{v}" for k, v in
                           list(r["lanes"].items())[:3]) or "—"
        hs = "、".join(list(r["heroes"])[:5]) or "—"
        out.append(f"| {i} | {r['author']} | {r['mid']} | {r['n']} | {r['n_s45']} | "
                   f"{r['teach_r']:.0%} | {r['avg_min']}m | {lanes} | {hs} |")
    out.append("")
    out.append(f"共 {len(rows)} 个 UP 主进池（至少 1 条命中视频）。")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-vids", type=int, default=1)
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--pages", type=int, default=2)
    args = ap.parse_args()

    vids = sweep(args.pages)
    print(f"[sweep] {len(vids)} 条视频", file=sys.stderr)
    rows = aggregate(vids, args.min_vids)
    (OUT / "roster_wide.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    md = to_md(rows, args.top)
    (ROOT / "50_logs" / "roster_wide.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
