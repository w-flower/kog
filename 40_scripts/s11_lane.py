#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s11_lane.py — 按【分路】采全局教学素材（不是按英雄）

用途：L 类（分路大局观）和 D 类（对局内环节）需要的是"这个位置整局怎么想"，
      英雄卡那套 s8_harvest 是按英雄名搜的，采不到这类。

用法：
  python s11_lane.py --lane adc --lane jungle
  python s11_lane.py --all

产出：10_sources/lanes/<lane>.json
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import defaultdict
from pathlib import Path

import bili_api as B

OUT = Path(r"C:/Users/Lenovo/WorkBuddy/kog/10_sources/lanes")

LANES = {
    "adc": ["射手 全局 思路", "发育路 教学 细节", "射手 发育 教学", "射手 站位 输出"],
    "jungle": ["打野 全局 思路", "打野 节奏 教学", "打野 教学 意识"],
    "mid": ["中单 全局 思路", "中路 教学 细节", "法师 全局 教学"],
    "roam": ["辅助 全局 思路", "游走 教学 思路", "辅助 节奏 教学"],
    "solo": ["对抗路 全局 思路", "边路 教学 思路", "对抗路 对线 细节"],
}

MIN_DUR, MAX_DUR = 480, 2400      # 8–40 分钟（全局教学才够，短视频是切片）
EXCLUDE = ["自走棋", "模拟战", "英雄联盟", "LOL", "端游", "云顶", "皮肤", "抽奖",
           "开箱", "高光", "集锦", "搞笑", "赛事", "KPL", "世冠", "解说", "直播回放",
           "皮肤", "cos", "Cos", "动画", "漫画", "同人", "壁纸"]
TEACH = ["教学", "思路", "全局", "意识", "细节", "打法", "教科书", "解析", "讲解", "攻略"]


def ds(s: str) -> int:
    p = [int(x) for x in re.findall(r"\d+", s or "")]
    if len(p) == 2:
        return p[0] * 60 + p[1]
    if len(p) == 3:
        return p[0] * 3600 + p[1] * 60 + p[2]
    return 0


def clean(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").replace("&quot;", '"')


def ok_title(t: str) -> bool:
    if any(x in t for x in EXCLUDE):
        return False
    return any(x in t for x in TEACH)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--per-up", type=int, default=2)
    args = ap.parse_args()

    lanes = list(LANES) if args.all else (args.lane or list(LANES))
    OUT.mkdir(parents=True, exist_ok=True)

    for lane in lanes:
        seen: dict[str, dict] = {}
        per_up: dict[int, int] = defaultdict(int)
        for kw in LANES[lane]:
            for order in ("", "click"):
                for page in (1, 2):
                    try:
                        rows = B.search(kw, page, order)
                    except Exception as e:
                        print(f"  [{kw} p{page}] ERR {e}")
                        continue
                    for r in rows:
                        bv = r.get("bvid")
                        if not bv or bv in seen:
                            continue
                        t = clean(r.get("title"))
                        if "王者荣耀" not in (r.get("tag") or "") + t:
                            continue
                        if not ok_title(t):
                            continue
                        dur = ds(r.get("duration"))
                        if not (MIN_DUR <= dur <= MAX_DUR):
                            continue
                        mid = r.get("mid")
                        if per_up[mid] >= args.per_up:
                            continue
                        per_up[mid] += 1
                        seen[bv] = {
                            "bvid": bv, "title": t, "up": r.get("author"),
                            "mid": mid, "dur": dur, "play": r.get("play"),
                            "pub": r.get("pubdate"), "kw": kw,
                        }
                    time.sleep(0.4)
        items = sorted(seen.values(), key=lambda x: -(x["play"] or 0))
        (OUT / f"{lane}.json").write_text(
            json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{lane}: {len(items)} 条")
        for it in items[:6]:
            print(f"   {it['bvid']}  {it['dur']//60:>2}分  {it['up'][:8]:<8} {it['title'][:38]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
