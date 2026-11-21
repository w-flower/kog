# -*- coding: utf-8 -*-
"""s62_patch_parse.py — 从抓到的更新公告正文里，抽出「英雄 → 数值改动」结构化数据。

输入: 10_sources/official/patches/<tid>.md （由 ego_patch_fetch.mjs 渲染抓取）
     10_sources/official/skills.json  （英雄名集合）
输出: 10_sources/official/patches/patches_structured.json
     10_sources/official/patches/英雄数值改动.md （汇总可读）
"""
import json, re
from pathlib import Path

BASE = Path(r"D:/Projects/kog")
PD = BASE / "10_sources/official/patches"
skills = json.load(open(BASE / "10_sources/official/skills.json", encoding="utf-8"))
HEROES = {h["cname"] for h in skills["heroes"]}

STOP = ("夺宝更新", "问题修复", "活动", "商城", "皮肤", "上架", "限时", "福利", "公告", "赛末", "英雄平衡", "其他")


def parse(md: str):
    t = md.split("---", 2)[-1]
    # 定位「英雄调整」段
    m = re.search(r"\n\s*英雄调整\s*\n", t)
    if not m:
        return {}
    seg = t[m.end():]
    lines = [l.strip() for l in seg.splitlines()]
    out, cur = {}, None
    stop_hit = False
    for ln in lines:
        if not ln:
            continue
        # 结束：遇到非英雄的章节标题
        if len(ln) <= 12 and any(ln.startswith(s) for s in STOP) and ln not in HEROES:
            stop_hit = True
        if stop_hit:
            break
        if ln in HEROES and len(ln) <= 6:
            cur = ln
            out.setdefault(cur, [])
        elif cur:
            out[cur].append(ln)
    return {h: v for h, v in out.items() if v}


def main():
    data = {}
    for p in sorted(PD.glob("*.md")):
        tid = p.stem
        if not tid.isdigit():
            continue
        d = parse(p.read_text(encoding="utf-8"))
        if d:
            data[tid] = d
    (PD / "patches_structured.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    # 汇总 md
    lines = ["# 更新公告 · 英雄数值改动汇总", ""]
    for tid, heroes in data.items():
        lines.append(f"## {tid}")
        for h, chs in heroes.items():
            lines.append(f"### {h}")
            for c in chs:
                if re.search(r"\d", c):
                    lines.append(f"- {c}")
        lines.append("")
    (PD / "英雄数值改动.md").write_text("\n".join(lines), encoding="utf-8")
    print("patches_with_hero_changes", len(data), "total_hero_entries", sum(len(v) for v in data.values()))
    for tid, heroes in data.items():
        print(tid, "heroes:", ",".join(heroes.keys()))


if __name__ == "__main__":
    main()
