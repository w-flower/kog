#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s32_scrub_subs.py — 字幕缓存串源清洗

现象（2026-11-03 实锤）：视频没有 CC 字幕时，player/v2 仍会返回一个
subtitle_url，内容是乱配的（德州靶场解说 / 歌词 / 短剧旁白 / iPhone 评测）。
三个写作代理因此被污染，12/23 张卡只能出 draft。

判据：这批字幕是为某个英雄采的（hero_batch_map.json），正文里连该英雄
的名字都不出现，就认定串源——正文改标 err='offtopic'，body 清空。
不是为英雄采的（老博主字幕）不动，只统计不删。

用法：python s32_scrub_subs.py --dry    # 先看要清哪些
      python s32_scrub_subs.py          # 实际清洗
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
SUBS = ROOT / "10_sources" / "creators_cache" / "subs"
sys.path.insert(0, str(ROOT / "40_scripts"))
import names as N  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()
    nm = N.load()
    # ASR 同音词：字幕转写里英雄名会被写成同音字（元流之子 -> 源流之子），
    # 不加这条会把真素材误清掉。踩过才加的。
    HOMOPHONE = {"元流之子": ["源流之子"], "芈月": ["米月"], "镜": ["近镜"],
                 "暃": ["非哥", "飞哥"]}
    mapping = {}
    mp = ROOT / "10_sources" / "creators_cache" / "hero_batch_map.json"
    if mp.exists():
        mapping.update(json.loads(mp.read_text(encoding="utf-8")))
    # creators_cache/ups.json（老博主清单）按 author 分组，正文命中任一英雄即留
    bad, ok = [], []
    for bv, hero in mapping.items():
        p = SUBS / f"{bv}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        body = d.get("body") or []
        if not body:
            continue
        text = " ".join(c.get("content", "") for c in body)
        # 该英雄名（含别名）不出现 → 串源。宽一点：全文 4000 字内找
        aka = [k for k, v in nm.alias.items() if v == hero]
        aka += HOMOPHONE.get(hero, [])
        if hero in text or any(a in text for a in aka):
            ok.append(bv)
        else:
            bad.append((bv, hero, text[:50]))
    print(f"英雄相关字幕 {len(ok)} 条；疑似串源 {len(bad)} 条")
    for bv, hero, head in bad:
        print(f"  {bv} 应为[{hero}] 实际: {head}")
    if not args.dry:
        for bv, hero, _ in bad:
            p = SUBS / f"{bv}.json"
            d = json.loads(p.read_text(encoding="utf-8"))
            d["err"] = "offtopic"
            d["body"] = []
            p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        print(f"已清洗 {len(bad)} 条（body 清空，标 err=offtopic）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
