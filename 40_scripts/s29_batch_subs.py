#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s29_batch_subs.py — 为 10_sources/heroes/{hero}/videos.json 挑视频并生成取字幕清单

挑选规则：score 降序 → 时长降序；每英雄最多 4 条；同一 UP 最多 2 条（防一家之声）。
输出 creators_cache/hero_batch.json（subs_browser --from-json 格式），只挑还没有字幕缓存的。

用法：
  python s29_batch_subs.py                 # 全部英雄
  python s29_batch_subs.py --hero 镜 马超   # 指定英雄
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
HEROES_DIR = ROOT / "10_sources" / "heroes"
SUBS = ROOT / "10_sources" / "creators_cache" / "subs"
OUT = ROOT / "10_sources" / "creators_cache" / "hero_batch.json"

PER_HERO = 4
PER_UP = 2


def pick(hero: str) -> list[dict]:
    vp = HEROES_DIR / hero / "videos.json"
    if not vp.exists():
        return []
    rows = json.loads(vp.read_text(encoding="utf-8"))
    cap: Counter = Counter()
    picked = []
    for r in sorted(rows, key=lambda r: (-r["score"], -r["dur"])):
        if cap[r["up"]] >= PER_UP:
            continue
        cap[r["up"]] += 1
        picked.append(r)
        if len(picked) >= PER_HERO:
            break
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", nargs="*", default=None)
    args = ap.parse_args()
    heroes = args.hero or sorted(p.name for p in HEROES_DIR.iterdir()
                                 if p.is_dir())
    out = []
    n_have = 0
    for h in heroes:
        for r in pick(h):
            if (SUBS / f"{r['bvid']}.json").exists():
                n_have += 1
                continue
            out.append({"bvid": r["bvid"], "hero": h,
                        "title": r["title"], "up": r["up"]})
    seen = set()
    out = [x for x in out if not (x["bvid"] in seen or seen.add(x["bvid"]))]
    # subs_browser 读取格式：[{vids:[{bvid}]}]
    payload = [{"vids": [{"bvid": x["bvid"]} for x in out]}]
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"{len(heroes)} 个英雄 · 待取 {len(out)} 条 · 已有缓存 {n_have} 条 -> {OUT}")
    # 同时留一份 BV->英雄 的映射，写字卡时知道每份字幕属于谁
    m = ROOT / "10_sources" / "creators_cache" / "hero_batch_map.json"
    m.write_text(json.dumps({x["bvid"]: x["hero"] for x in out},
                            ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
