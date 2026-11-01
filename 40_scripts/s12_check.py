#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s12_check.py — 分路素材字幕有效性体检

为什么要有这一步：B 站的字幕轨经常是**别的视频**的（iPhone 评测、职场访谈、LoL 局）。
不体检直接写卡，就是拿别人的稿子当王者素材用。

判定：
  · 噪音密度 > 8%           → reject（游戏音效/无关英文）
  · 分路术语密度 < 3 /千字   → reject（跑题）
  · 术语密度 ≥ 8 /千字       → ok

用法：
  python s12_check.py --lane adc
  python s12_check.py --lane adc,jungle --top 8
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
SUBS = ROOT / "10_sources" / "creators_cache" / "subs"
LANES = ROOT / "10_sources" / "lanes"

NOISE = re.compile(
    r"技能正在冷却|请求集合|发起进攻|开始撤退|大招还未升级|敌军还有|"
    r"First Blood|Double Kill|Triple Kill|Enemy|Ally|slain|destroyed|"
    r"IPHONE|iPhone|相机|像素|续航|屏幕|拍摄")

TERMS = {
    "adc": ["射手", "发育路", "补刀", "兵线", "站位", "输出", "防御塔", "辅助",
            "打野", "经济", "对线", "团战", "下路"],
    "jungle": ["野区", "刷野", "反野", "节奏", "抓人", "兵线", "龙", "视野",
               "打野", "经济", "中线", "四级"],
    "mid": ["中线", "兵线", "线权", "转线", "支援", "法强", "中路", "对线", "团战"],
    "roam": ["辅助", "视野", "开团", "射手", "打野", "中线", "保护", "游走", "节奏"],
    "solo": ["对抗路", "兵线", "线权", "边路", "单带", "传送", "对线", "经济"],
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="adc")
    ap.add_argument("--top", type=int, default=8)
    args = ap.parse_args()

    for lane in args.lane.split(","):
        lane = lane.strip()
        src = LANES / f"{lane}.json"
        if not src.exists():
            print(f"缺 {src}")
            continue
        items = json.loads(src.read_text(encoding="utf-8"))[: args.top]
        terms = TERMS[lane]
        print(f"\n=== {lane} ===")
        for it in items:
            p = SUBS / f"{it['bvid']}.json"
            if not p.exists():
                print(f"  {it['bvid']}  （无字幕文件）")
                continue
            body = (json.loads(p.read_text(encoding="utf-8")).get("body") or [])
            txt = "".join(c.get("content", "") for c in body)
            n = len(txt)
            if n < 1200:
                print(f"  {it['bvid']}  reject  太短 {n} 字")
                continue
            noise = len(NOISE.findall(txt)) * 3 / n
            hit = sum(txt.count(t) for t in terms)
            dens = hit * 1000 / n
            if noise > 0.08:
                verdict = f"reject  噪音{noise:.0%}"
            elif dens < 3:
                verdict = f"reject  跑题(术语{dens:.1f}/k)"
            elif dens >= 8:
                verdict = f"OK      术语{dens:.1f}/k"
            else:
                verdict = f"maybe   术语{dens:.1f}/k"
            print(f"  {it['bvid']}  {verdict:<24} {n//1000}k字  {it['up'][:10]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
