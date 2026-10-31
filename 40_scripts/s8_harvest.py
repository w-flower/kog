#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s8_harvest.py — 按英雄采教学视频（小 UP 也收，只按时长和分区过滤）

每个英雄多关键词 × 多排序，合并去重；同一 UP 最多取 3 条，保证信源分散。

用法：
  python s8_harvest.py --hero 不知火舞 --hero 小乔
  python s8_harvest.py --all
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

import bili_api as B

OUT = Path(r"C:/Users/Lenovo/WorkBuddy/kog/10_sources/heroes")

HEROES = ["不知火舞", "小乔", "大乔", "夏洛特", "盾山", "鲁班大师", "苏烈", "女娲"]

QS = ["{h} 教学", "{h} 出装 铭文", "{h} 连招 技巧", "{h} 全局 思路"]
MIN_DUR, MAX_DUR = 240, 4200          # 4–70 分钟
EXCLUDE = ["自走棋", "模拟战", "英雄联盟", "LOL", "端游", "云顶", "皮肤",
           "抽奖", "开箱", "高光", "集锦", "搞笑", "赛事", "KPL", "主播怎么"]
TEACH = ["教学", "思路", "技巧", "连招", "出装", "铭文", "全局", "讲解",
         "解析", "意识", "细节", "打法", "公式"]


def ds(s: str) -> int:
    p = [int(x) for x in re.findall(r"\d+", s or "")]
    if len(p) == 2:
        return p[0] * 60 + p[1]
    if len(p) == 3:
        return p[0] * 3600 + p[1] * 60 + p[2]
    return 0


def harvest(hero: str) -> list[dict]:
    seen: dict[str, dict] = {}
    for q in QS:
        kw = q.format(h=hero)
        for order in ("", "click"):
            for pg in (1, 2):
                try:
                    res = B.search(kw, pg, order)
                except Exception as e:
                    print(f"  [WARN] {kw}/{order or 'rel'} p{pg}: {e}")
                    continue
                for x in res:
                    bv = x.get("bvid") or ""
                    if not bv or bv in seen:
                        continue
                    t = re.sub(r"<[^>]+>", "", x.get("title") or "")
                    tag = x.get("tag") or ""
                    if "王者荣耀" not in tag and "王者荣耀" not in t:
                        continue
                    if hero not in t:                      # 标题必须点名这个英雄
                        continue
                    if any(w in t for w in EXCLUDE):
                        continue
                    d = ds(x.get("duration"))
                    if not (MIN_DUR <= d <= MAX_DUR):
                        continue
                    seen[bv] = {
                        "bvid": bv, "title": t, "up": x.get("author") or "",
                        "mid": int(x.get("mid") or 0), "dur": d,
                        "play": int(x.get("play") or 0),
                        "pub": int(x.get("pubdate") or 0),
                        "score": sum(1 for w in TEACH if w in t) * 10,
                    }
                time.sleep(0.9)

    rows = list(seen.values())
    # 同一个 UP 最多 3 条，避免一家之声
    cap: Counter = Counter()
    picked = []
    for r in sorted(rows, key=lambda r: (-r["score"], -r["dur"])):
        if cap[r["up"]] >= 3:
            continue
        cap[r["up"]] += 1
        picked.append(r)
    picked.sort(key=lambda r: (-r["score"], -r["dur"]))
    return picked[:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    hs = HEROES if args.all else (args.hero or HEROES)

    for h in hs:
        print(f"\n=== {h} ===")
        rows = harvest(h)
        d = OUT / h
        d.mkdir(parents=True, exist_ok=True)
        (d / "videos.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        ups = len({r["up"] for r in rows})
        print(f"  {len(rows)} 条 / {ups} 个 UP")
        for r in rows:
            print(f"   {r['dur']//60:>2}m {time.strftime('%Y-%m', time.localtime(r['pub']))} "
                  f"{r['bvid']} {r['up'][:12]:<14} {r['title'][:40]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
