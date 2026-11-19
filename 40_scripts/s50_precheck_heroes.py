# -*- coding: utf-8 -*-
"""s50_precheck_heroes.py — 重采英雄素材的严格预检（带英雄名）。

对每个英雄的 videos.json 里每个 BV，用 s47 的判据检查：
  英雄名命中 >= 2  或  王者术语密度 >= 12/千字
输出：50_logs/upload/recheck_ok.json（只含 OK 的），并打印每英雄统计。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from s47_precheck_subs import check

BASE = Path(__file__).resolve().parent.parent
HEROES = ["李信", "猪八戒", "武则天", "桑启", "孙膑", "元歌", "甄姬", "司马懿", "芈月", "亚瑟"]

ok_all = {}
for h in HEROES:
    p = BASE / f"10_sources/heroes/{h}/videos.json"
    if not p.exists():
        print(f"{h:6} MISSING videos.json")
        continue
    rows = json.loads(p.read_text(encoding="utf-8"))
    oks, stats = [], {"OK": 0, "SUSPECT": 0, "EMPTY_BODY": 0, "MISSING": 0, "BAD_JSON": 0}
    for r in rows:
        bv = r.get("bvid") or ""
        bv2, exp, chars, dens, hc, verdict = check(bv, h)
        stats[verdict] = stats.get(verdict, 0) + 1
        if verdict == "OK":
            oks.append({
                "bvid": bv, "title": r.get("title", ""), "up": r.get("up", ""),
                "dur": r.get("dur", 0), "pub": r.get("pub", 0),
                "chars": chars, "dens": dens, "hero_hits": hc,
            })
    ok_all[h] = oks
    print(f"{h:6} total={len(rows):2d}  OK={stats['OK']:2d}  "
          f"SUSPECT={stats['SUSPECT']:2d}  EMPTY={stats['EMPTY_BODY']:2d}  MISSING={stats.get('MISSING',0)}")

out = BASE / "50_logs/upload/recheck_ok.json"
out.write_text(json.dumps(ok_all, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nwritten", out)
for h, oks in ok_all.items():
    print(f"\n== {h} ==")
    for x in oks:
        print(f"  {x['bvid']}  {x['dens']:5.1f}/k  命中{x['hero_hits']:2d}  {x['up'][:10]:12} {x['title'][:36]}")
