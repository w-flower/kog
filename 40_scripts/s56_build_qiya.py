# -*- coding: utf-8 -*-
"""s56_build_qiya.py — 把「欺压ya」已取到中文字幕的教学视频，按主题装配成 D 类系统卡任务包。

每个主题产出**一个自包含附件**（写作规范 + 全部素材 + 具体任务），规避多附件上传失败。
素材来自 10_sources/creators_cache/subs/<BV>.json（ego 取到的 ai-zh 字幕，带 from/to）。
用法: python 40_scripts/s56_build_qiya.py [--only 13]
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

BASE = Path(r"D:/Projects/kog")
SUB = BASE / "10_sources/creators_cache/subs"
HAVE = BASE / "50_logs/_qiya_have.json"
SKILL = (BASE / "50_logs/upload/skill_王者系统卡写作规范.md").read_text(encoding="utf-8").strip()
UP = BASE / "50_logs/upload"

THEMES = {
    "13": {
        "title": "13 辅助：开局与对线设计",
        "bvs": ["BV1ZYEx6nEKq", "BV1uLsv6jErz", "BV1vvdbB7EQQ", "BV1YtEb6HEhD", "BV19AQbBeEmX"],
        "depends": "[12]", "k": ("K-D136", "K-D160"),
        "focus": "高分辅助的开局设计、对线换血、粉丝复盘里暴露的中低分段错误。",
    },
    "14": {
        "title": "14 辅助：中期节奏与游走",
        "bvs": ["BV1dxam6kE3y", "BV135Hj6WExf", "BV15B766nE5a", "BV17M9fBhEhQ", "BV1ai5Q66EQW", "BV1B1hy6uEfw"],
        "depends": "[13]", "k": ("K-D161", "K-D185"),
        "focus": "前期到中期的过渡逻辑、关键节奏点、游走路线选择。",
    },
    "15": {
        "title": "15 辅助：团战、视野与开团",
        "bvs": ["BV1uMEx6BEvz", "BV1YCtb6CErq", "BV1jHoQBJEff", "BV19Ch462ELH", "BV1814C61EQw",
                "BV1cL7V6HE8b", "BV1bcuX6REUG", "BV1RChB6LE5i", "BV18B7s6NESY"],
        "depends": "[12,14]", "k": ("K-D186", "K-D210"),
        "focus": "视野博弈的本质、团战站位与阵型、开团时机（含逐帧教学系列）。",
    },
}

def mmss(s):
    try:
        s = float(s)
    except Exception:
        return "00:00"
    return f"{int(s)//60:02d}:{int(s)%60:02d}"

def dump(bv):
    p = SUB / f"{bv}.json"
    if not p.exists():
        return ""
    d = json.loads(p.read_text(encoding="utf-8"))
    return "\n".join(f"[{mmss(c.get('from',0))}] {c.get('content','')}" for c in (d.get("body") or []))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    have = {v["bvid"]: v for v in json.loads(HAVE.read_text(encoding="utf-8"))}
    for tid, cfg in THEMES.items():
        if args.only and tid != args.only:
            continue
        used = [bv for bv in cfg["bvs"] if bv in have and dump(bv).strip()]
        if not used:
            print(f"[{tid}] 无可用素材，跳过"); continue
        srcs = []
        parts = []
        for bv in used:
            v = have[bv]
            srcs.append(bv)
            parts.append(f"\n### 素材：{v['title']}（{bv}，{v['length']}）\n\n```text\n{dump(bv)}\n```\n")
        head = f"""# 任务：写一张 D 类系统卡《{cfg['title']}》

本文件三部分，请**从头读到尾**再动笔：
- 第一部分：写作规范（硬要求，违反即返工）
- 第二部分：素材包（唯一信源，均为 B 站 UP「欺压ya」的教学视频中文 AI 字幕，带 [mm:ss]）
- 第三部分：本次具体任务

产出一张卡，写到 `/workspace/系统卡_{tid}.md`（只写这一个文件）。

> 素材说明：本卡综合 {len(used)} 个视频。字幕为 AI 自动转写（非人工 CC），
> **时间戳整体可信（±2 秒），但有同音错别字**；涉及英雄名/专有名词拿不准时按「不指名」或写「（听音疑似，待核）」，不许当成事实硬编。

---

# 第一部分：写作规范

{SKILL}

---

# 第二部分：素材包

{"".join(parts)}

---

# 第三部分：本次具体任务

卡的身份（front matter 逐字照抄字段名）：
- id: {tid}
- cat: D
- title: `{cfg['title']}`
- depends_on: {cfg['depends']}
- unlocks: []
- role: [roam]
- version: S45
- status: draft
- updated: 2026-11-21
- sources: [{", ".join(srcs)}]

K 条目编号区段：**{cfg['k'][0]} ~ {cfg['k'][1]}**（不许越界/重复；少于上限完全允许，宁少勿凑）。

内容要求：
1. 开头写「## 判断顺序」：把「{cfg['focus']}」整理成可执行的 第 1 步→第 N 步，每步指向具体 K 条目。
2. 条目**不按视频顺序罗列**，按「辅助做决策的顺序」重组；同一主题多视频观点冲突时，单独用「反例/冲突」写清条件差异。
3. 每条必须带 `（@ mm:ss）`，时间戳以素材全文为准（±2 秒）。
4. 素材没讲到的（具体铭文、出装顺序、段位差异等）一律进「## 待补」，不许补常识。
5. 文末附「## 自检」：卡片覆盖了哪些视频/主题、哪些没覆盖、几条时间戳是抽样核对过的。
"""
        out = UP / f"qiya_task_{tid}.md"
        out.write_text(head, encoding="utf-8")
        prompt = f"附件是本任务的全部内容（写作规范+素材+任务）。请完整读附件，按第三部分要求，把一张 D 类系统卡写到 `/workspace/系统卡_{tid}.md`。只写这一个文件，不要输出 PDF。"
        (UP / f"qiya_prompt_{tid}.md").write_text(prompt, encoding="utf-8")
        print(f"[{tid}] {out.name} {out.stat().st_size}B  素材{len(used)}个 {used}")

if __name__ == "__main__":
    main()
