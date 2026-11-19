# -*- coding: utf-8 -*-
"""s47_precheck_subs.py — 派活前预检字幕是否串源（幽灵字幕闸门）。

背景：subs 缓存里混着大量「标题是王者教学、字幕其实是装机/探店/试驾/政策解读」的串源文件。
直接喂给码道会浪费额度，还可能生成基于假素材的卡。

判据（OR）：字幕正文里 英雄名/关键词出现 >= 2 次，或王者术语密度 >= 阈值/千字。
两样都不满足 = 疑似串源，标记为不要派。

用法:
  python 40_scripts/s47_precheck_subs.py BV1xxx BVyyy ...
  python 40_scripts/s47_precheck_subs.py --file 50_logs/upload/batch_X.md   # 从任务包里抽 BV + 英雄名
"""
import json, re, sys
from pathlib import Path

BASE = Path("C:/Users/Lenovo/WorkBuddy/kog")
SD = BASE / "10_sources/creators_cache/subs"
KOG = set("技能 兵线 野区 打野 大招 一技能 二技能 三技能 装备 经济 团战 射手 法师 辅助 对抗路 发育路 中路 升级 冷却 血条 防御塔 峡谷 英雄 王者荣耀 buff 铭文 出门装 回城 闪现 主宰 暴君 高地".split())


def check(bv, expect=""):
    p = SD / f"{bv}.json"
    if not p.exists():
        return (bv, expect, 0, 0, 0, "MISSING")
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return (bv, expect, 0, 0, 0, "BAD_JSON")
    txt = "".join(c.get("content", "") for c in d.get("body", []))
    if len(txt) < 200:
        return (bv, expect, len(txt), 0, 0, "EMPTY_BODY")
    dens = sum(txt.count(k) for k in KOG) / len(txt) * 1000
    hc = txt.count(expect) if expect else 0
    ok = hc >= 2 or dens >= 12
    return (bv, expect, len(txt), round(dens, 1), hc, "OK" if ok else "SUSPECT")


def main():
    args = sys.argv[1:]
    if not args:
        print("用法: s47_precheck_subs.py BVxxx BVyyy  或  --file <任务包.md>")
        return
    items = []
    if args[0] == "--file":
        text = Path(args[1]).read_text(encoding="utf-8")
        # 从 "### 素材：<英雄>（BVxxx）" 或 "### 素材 BVxxx" 抽
        for m in re.finditer(r"###\s*素材[：: ]*\s*(\S+)[（(]?(BV[0-9A-Za-z]{8,12})?", text):
            items.append((m.group(2) or "", m.group(1)))
        if not items:
            bvs = re.findall(r"BV[0-9A-Za-z]{8,12}", text)
            items = [(b, "") for b in dict.fromkeys(bvs)]
    else:
        items = [(a, "") for a in args]

    print(f"{'BV':14} {'期望':10} {'字数':>7} {'术语/千':>8} {'关键词':>6}  判定")
    bad = 0
    for bv, exp in items:
        r = check(bv, exp)
        if r[5] not in ("OK",):
            bad += 1
        print(f"{r[0]:14} {r[1][:10]:10} {r[2]:7d} {r[3]:8.1f} {r[4]:6d}  {r[5]}")
    print(f"\n合计 {len(items)} 条，疑似串源/空 {bad} 条。只派 OK 的。")


if __name__ == "__main__":
    main()
