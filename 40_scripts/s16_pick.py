#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s16_pick.py — 从 pool_wide.json 里挑出某一类候选，喂给 subs_browser.py

用法：
  python s16_pick.py --kind adc --max 45
  python s16_pick.py --kind jungle --max 30
  python s16_pick.py --kind mid --max 30
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
OUT = ROOT / "10_sources"

ADC = re.compile(r"射手|发育路|公孙离|马可波罗|孙尚香|虞姬|狄仁杰|伽罗|鲁班七号|"
                 r"后羿|百里守约|蒙犽|戈娅|敖隐|黄忠|李元芳|成吉思汗|艾琳|ADC")
JUNGLE = re.compile(r"打野|野区|反野|刷野|韩信|李白|澜|镜|曜|云缨|阿古朵|裴擒虎|"
                    r"盘古|兰陵王|橘右京")
MID = re.compile(r"中路|中单|法师|不知火舞|小乔|女娲|王昭君|甄姬|上官婉儿|貂蝉|"
                 r"干将|武则天|海月|杨玉环|王维|金蝉|姜子牙|墨子")
SOLO = re.compile(r"对抗路|边路|上单|夏洛特|吕布|马超|花木兰|老夫子|白起|达摩|曹操")
ROAM = re.compile(r"辅助|游走|硬辅|软辅|张飞|牛魔|东皇|蔡文姬|明世隐|瑶|桑启|"
                  r"鬼谷子|太乙|刘禅|刘邦|大禹|苏烈|庄周|孙膑|张良|钟馗|鲁班大师|盾山")

KIND = {"adc": ADC, "jungle": JUNGLE, "mid": MID, "solo": SOLO, "roam": ROAM}
TEACH = re.compile(r"教学|思路|复盘|整局|意识|细节|对线|运营|上分|节奏|开局|转线|"
                   r"大局观|讲解|解析|公式|技巧|打法|出装|铭文|连招|教程")
BAD = re.compile(r"集锦|高光|搞笑|录播|回放|赛事|KPL|皮肤|抽奖|开箱|英雄联盟|"
                 r"自走棋|模拟战|音乐|配音|cos|手办|万象棋|建模|羁绊|棋盘|"
                 r"体验服|预测|爆料|上线|公告")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True, choices=list(KIND))
    ap.add_argument("--max", type=int, default=40)
    ap.add_argument("--min-dur", type=int, default=600)
    ap.add_argument("--per-up", type=int, default=3)
    args = ap.parse_args()

    vids = json.loads((OUT / "pool_wide.json").read_text(encoding="utf-8"))
    pat = KIND[args.kind]
    cand = [v for v in vids
            if v["dur"] >= args.min_dur and pat.search(v["title"])
            and not BAD.search(v["title"])]
    # 同一 UP 最多 per-up 条，优先长视频
    cand.sort(key=lambda v: (-v["dur"], -v["play"]))
    cnt: dict[str, int] = defaultdict(int)
    picked = []
    for v in cand:
        if cnt[v["author"]] >= args.per_up:
            continue
        cnt[v["author"]] += 1
        picked.append(v)
        if len(picked) >= args.max:
            break

    payload = [{"author": p["author"], "mid": p["mid"],
                "vids": [{"bvid": p["bvid"], "title": p["title"]}]} for p in picked]
    f = OUT / f"pick_{args.kind}.json"
    f.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(picked)} 条 -> {f}")
    for p in picked[:60]:
        print(f"  {p['dur']//60:>2}m {p['author'][:16]:<18}{p['title'][:44]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
