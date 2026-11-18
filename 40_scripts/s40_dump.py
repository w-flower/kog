# -*- coding: utf-8 -*-
"""s40_dump.py — 把已采集字幕（creators_cache/subs）按英雄/BV 抽成可读纯文本，供写卡时阅读。

用法：
  python s40_dump.py hero 影 甄姬 镜 ...      # 按英雄名抽（来自 hero_batch_map）
  python s40_dump.py bv   BV1X2jV6KEiP ...     # 按 BV 抽（topic/系列视频）
  python s40_dump.py zero                          # 抽 zero_heroes.txt 中已有素材的英雄

输出：50_logs/transcripts/<英雄或BV>.txt  （每条 cue 带 [MM:SS] 时间戳，便于 @MM:SS 引用）
空 body 的 BV 自动跳过（幽灵字幕）。
"""
import json
import sys
from pathlib import Path

ROOT = Path("C:/Users/Lenovo/WorkBuddy/kog")
MP = json.loads((ROOT / "10_sources/creators_cache/hero_batch_map.json").read_text(encoding="utf-8"))
SUB = ROOT / "10_sources/creators_cache/subs"
OUT = ROOT / "50_logs/transcripts"
OUT.mkdir(parents=True, exist_ok=True)


def mmss(s):
    try:
        s = int(float(s))
    except Exception:
        return "00:00"
    return f"{s // 60:02d}:{s % 60:02d}"


def dump_bv(bv: str):
    p = SUB / f"{bv}.json"
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    body = d.get("body", [])
    if not body:
        return None
    lines = [f"[{mmss(c.get('from', 0))}] {c.get('content', '')}" for c in body]
    return "\n".join(lines)


def dump_hero(hero: str):
    bvs = [b for b, h in MP.items() if h == hero]
    out = []
    for bv in bvs:
        t = dump_bv(bv)
        if t:
            out.append(f"===== BV {bv} =====\n{t}")
    if not out:
        return False
    (OUT / f"{hero}.txt").write_text("\n\n".join(out), encoding="utf-8")
    return True


def main():
    if not sys.argv[1:]:
        print("用法: python s40_dump.py hero 影 甄姬 | bv BVxxx | zero")
        return
    mode = sys.argv[1]
    if mode == "hero":
        for h in sys.argv[2:]:
            print(f"{h}: {'OK' if dump_hero(h) else 'NO SUBS'}")
    elif mode == "bv":
        for bv in sys.argv[2:]:
            t = dump_bv(bv)
            if t:
                (OUT / f"{bv}.txt").write_text(t, encoding="utf-8")
                print(f"{bv}: OK ({len(t)} chars)")
            else:
                print(f"{bv}: EMPTY/SKIP")
    elif mode == "zero":
        zh = set(Path("40_scripts/zero_heroes.txt").read_text(encoding="utf-8").split())
        done = 0
        for h in sorted(zh):
            if dump_hero(h):
                done += 1
                print(f"{h}: OK")
        print(f"\nzero-material heroes with subs: {done}")
    else:
        print("unknown mode")


if __name__ == "__main__":
    main()
