# -*- coding: utf-8 -*-
"""s63_annotate_patches.py — 把更新公告的「英雄数值改动」回填到技能官方卡 md 的末尾。

读: 10_sources/official/patches/by_hero.json
写: 10_sources/official/md/<英雄>.md 末尾追加/替换「## 近期更新公告数值（自动汇总）」小节
（可重复运行，幂等：先删旧小节再写）
"""
import json
from pathlib import Path

BASE = Path(r"D:/Projects/kog")
OFF = BASE / "10_sources/official"
by = json.load(open(OFF / "patches/by_hero.json", encoding="utf-8"))
MD = OFF / "md"
MARK = "## 近期更新公告数值（自动汇总）"

n = 0
missing = []
for hero, recs in by.items():
    p = MD / f"{hero}.md"
    if not p.exists():
        missing.append(hero); continue
    t = p.read_text(encoding="utf-8")
    i = t.find(MARK)
    if i >= 0:
        t = t[:i].rstrip() + "\n"
    lines = ["", MARK, "",
             "> 以下数值来自官网「版本更新/平衡性调整」公告（脚本 s63 自动汇总）。",
             "> 这些改动**未必同步写进了上面的技能描述文案**——正是「可能未标注」的重点核对对象。", ""]
    for r in recs:
        lines.append(f"- **{r['date'] or r['tid']}** {r['title']}")
        for c in r["changes"]:
            lines.append(f"  - {c}")
    lines.append("")
    p.write_text(t.rstrip() + "\n" + "\n".join(lines), encoding="utf-8")
    n += 1

print("annotated", n, "heroes; missing md:", missing)
