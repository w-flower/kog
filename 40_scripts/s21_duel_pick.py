#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s21_duel_pick.py — 专采「对位」类视频（B 类专属素材链，和英雄教学分开）

为什么要单开一个：s8_harvest.py 当年**故意排除**标题含「打X」「克制X」的视频，
免得把"别人讲怎么打她"混进英雄教学。B 类要的正好是这些，所以反过来只采这些。

做法：
  1. 从 30_index/roster.json 取全部英雄名，按"度数"（官方边的多少）排序，
     先给边多的英雄搜——他们最可能有人做专项对位
  2. 每个英雄搜 2 个模板：「<英雄>怎么打」「打<英雄>」，各 1 页
  3. 标题必须命中「对位/怎么打/打X/克制/被克/克制关系」之一，且不含赛事/直播回放
  4. 输出 10_sources/pick_duel.json，可直接喂 subs_browser.py --from-json

用法：
  python s21_duel_pick.py --limit 40          # 前 40 个英雄
  python s21_duel_pick.py --limit 0           # 全量
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
sys.path.insert(0, str(ROOT / "40_scripts"))
import bili_api as B  # noqa: E402

IDX = ROOT / "30_index"
OUT = ROOT / "10_sources"
LOGS = ROOT / "50_logs"

# 标题必须像"讲对位"的（用词表而不是长正则，省得漏括号）
GOOD_WORDS = ["怎么打", "对位", "克制", "被克", "怕谁", "谁克", "撞车",
              "打法", "打不过", "好打", "难打", "counter"]
# 明显不是对位教学的
BAD_WORDS = ["万象棋", "建模", "羁绊", "棋盘", "体验服", "预测", "爆料", "上线",
             "公告", "赛事", "KPL", "决赛", "直播回放", "皮肤", "COS", "cos",
             "手办", "配音", "剧情", "动画", "剪辑", "高光", "集锦", "五杀",
             "搞笑", "片段", "搞笑", "解说"]


def is_duel_title(t: str) -> bool:
    if any(w in t for w in BAD_WORDS):
        return False
    return any(w in t for w in GOOD_WORDS)


def dur_sec(v) -> int:
    """B 站 duration 是 "12:34" 字符串，也可能是数字。统一成秒。"""
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v or "").strip()
    if not s:
        return 0
    parts = [int(x) for x in s.split(":") if x.isdigit()]
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return sec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--pages", type=int, default=1)
    args = ap.parse_args()

    roster = json.loads((IDX / "roster.json").read_text(encoding="utf-8"))["heroes"]
    rel_p = IDX / "relations.json"
    deg: dict[str, int] = {}
    if rel_p.exists():
        for e in json.loads(rel_p.read_text(encoding="utf-8"))["edges"]:
            deg[e["win"]] = deg.get(e["win"], 0) + 1
            deg[e["lose"]] = deg.get(e["lose"], 0) + 1
    names = [h["name"] for h in roster if deg.get(h["name"], 0) >= 4]
    names.sort(key=lambda n: -deg.get(n, 0))
    if args.limit:
        names = names[:args.limit]

    picked: dict[str, dict] = {}
    for i, name in enumerate(names, 1):
        for tpl in (f"{name}怎么打", f"打{name}"):
            for pg in range(1, args.pages + 1):
                try:
                    res = B.search(tpl, pg)
                except Exception as e:
                    print(f"  [{i}] {name} 搜索失败 {e}", file=sys.stderr)
                    time.sleep(1.2)
                    continue
                for v in res:
                    t = (v.get("title") or "")
                    bv = v.get("bvid") or ""
                    if not bv or bv in picked:
                        continue
                    if not is_duel_title(t):
                        continue
                    picked[bv] = {"bvid": bv, "title": t,
                                  "dur": dur_sec(v.get("duration")),
                                  "play": v.get("play") or 0,
                                  "up": (v.get("owner") or {}).get("name", ""),
                                  "mid": (v.get("owner") or {}).get("mid", 0),
                                  "kw": name, "tpl": tpl}
                time.sleep(0.5)
        if i % 10 == 0:
            print(f"  {i}/{len(names)} 已选 {len(picked)}", file=sys.stderr)

    lst = sorted(picked.values(), key=lambda x: -x["dur"])
    (OUT / "pick_duel.json").write_text(
        json.dumps(lst, ensure_ascii=False, indent=1), encoding="utf-8")

    L = ["# 对位视频候选（B 类专属采集）", "",
         f"搜了 {len(names)} 个英雄 × 2 个模板 → 命中 {len(lst)} 条。",
         "筛选：标题要像讲对位；排除赛事/直播/皮肤/高光。", ""]
    for x in lst[:120]:
        L.append(f"- `{x['bvid']}` {x['dur'] // 60}分 · {x['up']} — {x['title'][:56]}")
    (LOGS / "pick_duel.md").write_text("\n".join(L), encoding="utf-8")

    print(f"pick_duel -> {OUT/'pick_duel.json'}  {len(lst)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
