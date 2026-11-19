# -*- coding: utf-8 -*-
"""汇总重采英雄的候选 BV（去重），供 subs_browser 批量取字幕。"""
import json
from pathlib import Path

BASE = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
HEROES = ["李信", "猪八戒", "武则天", "桑启", "孙膑", "元歌", "甄姬", "司马懿", "芈月", "亚瑟"]
bvs = []
for h in HEROES:
    p = BASE / f"10_sources/heroes/{h}/videos.json"
    if not p.exists():
        print("MISSING", h)
        continue
    for r in json.loads(p.read_text(encoding="utf-8")):
        if r.get("bvid"):
            bvs.append(r["bvid"])
seen = []
for b in bvs:
    if b not in seen:
        seen.append(b)
out = BASE / "50_logs/upload/bv_recheck.txt"
out.write_text("\n".join(seen), encoding="utf-8")
print("heroes", len(HEROES), "bvs", len(seen), "->", out)
