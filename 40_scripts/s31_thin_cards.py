#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s31_thin_cards.py — 给素材不足的英雄生成薄卡（防 404，防硬编）

薄卡只含三种内容，全是可核实的：
  1. 官方口径：分路 / 定位 / 强势期标签（roster.json）
  2. 官方克制方向（B 卡里的官方口径段，≤4 条）
  3. 大字声明「素材不足，待补」+ 该英雄在字幕库里被提到的位置（有就给 BV）

status: draft —— 站点上按草稿样式渲染，防止被当成品。

用法：python s31_thin_cards.py            # 只处理缺卡且素材不足的
      python s31_thin_cards.py --all      # 强制重建所有薄卡
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
A_DIR = ROOT / "20_kb" / "A_英雄教学"
B_DIR = ROOT / "20_kb" / "B_克制关系"
ROSTER = ROOT / "30_index" / "roster.json"
HEROES_DIR = ROOT / "10_sources" / "heroes"
SUBS = ROOT / "10_sources" / "creators_cache" / "subs"

LANE_CN = {"solo": "对抗路", "jungle": "打野", "mid": "中路",
           "adc": "发育路", "roam": "游走"}
TYPE_CN = {"1": "战士", "2": "法师", "3": "坦克", "4": "刺客",
           "5": "射手", "6": "辅助"}
FULL_SET = {  # 已验收干净的正式卡（子代理产出、零串源引用），别动
    "元流之子", "大司命", "姬小满", "影", "曹操", "李信", "梦奇",
    "海诺", "花木兰", "貂蝉", "镜",
}


def official_duel(hero: str) -> list[str]:
    """B 卡官方口径段里的压制/被压制方向，抽成一句话列表。"""
    p = B_DIR / f"{hero}.md"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    out = []
    m = re.search(r"<!-- AUTO:official:start -->(.*?)<!-- AUTO:official:end -->",
                  text, re.S)
    seg = m.group(1) if m else text
    for ln in seg.splitlines():
        ln = ln.strip().lstrip("-*| ").strip()
        if not ln or ln.startswith(("压制英雄", "被压制英雄", "最佳搭档", "官方口径", "---")):
            continue
        if len(ln) < 4 or len(ln) > 90:
            continue
        out.append(ln)
    return out[:4]


def subtitle_hits(hero: str) -> list[str]:
    """字幕库里提到这个英雄的视频（最多 3 个），给个线索而不是空手。"""
    vp = HEROES_DIR / hero / "videos.json"
    hits = []
    if vp.exists():
        for r in json.loads(vp.read_text(encoding="utf-8"))[:3]:
            hits.append(f"[{r['title'][:44]}](https://www.bilibili.com/video/{r['bvid']})（{r['up']}）")
    return hits


def build(hero: str, h: dict) -> str:
    lanes = [LANE_CN[x] for x in h.get("lanes") or []]
    main = LANE_CN.get(h.get("main_lane") or "", "未知")
    typ = TYPE_CN.get(str(h.get("hero_type") or ""), "未知")
    duel = official_duel(hero)
    hits = subtitle_hits(hero)
    lines = [
        "---",
        f"id: {hero}",
        "cat: A",
        f"title: {hero}（{main}）",
        "tempo: unknown",
        "job: open",
        f"motto: 素材不足，定位待采",
        "version: S45",
        "status: draft",
        "updated: 2026-11-03",
        "sources: []",
        "---",
        "",
        f"# {hero}：薄卡（素材不足，待补）",
        "",
        f"> ⚠️ **这张卡是薄卡**：B 站现有素材里没能挖到足量（≥3 份）有效教学字幕，",
        f"> 只有官方口径，没有实战打法。**不要把这张卡当成品用**。",
        f"> status=draft，站点上以草稿样式区分。",
        "",
        "## 官方口径",
        "",
        "| 项 | 值 |",
        "|---|---|",
        f"| 官方定位 | {typ} |",
        f"| 可走分路 | {'、'.join(lanes) or '未知'}（官方标注） |",
        f"| 主分路 | {main} |",
        "",
    ]
    if duel:
        lines += ["## 官方克制方向（只给方向，无条件下，可信度低）", ""]
        lines += [f"- {d}" for d in duel]
        lines.append("")
    if hits:
        lines += ["## 字幕库里被提到（还没拆出干货，待细采）", ""]
        lines += [f"- {x}" for x in hits]
        lines.append("")
    lines += [
        "## 待补清单",
        "",
        "- 专项搜索该英雄教学视频（`{英雄} 教学` / `{英雄} 出装 铭文`）并取字幕",
        "- 挖到 ≥3 份有效字幕后升级成正式卡（参照 A 类模板），status 改 active",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))["heroes"]
    # roster 可能是 dict{name: {...}} 或 list
    if isinstance(roster, list):
        roster = {h["name"]: h for h in roster}
    n = 0
    for hero, h in roster.items():
        if hero in FULL_SET:
            continue
        p = A_DIR / f"{hero}.md"
        if not args.all and p.exists():
            continue                      # 已有卡（正式或之前生成的薄卡）不动
        p.write_text(build(hero, h), encoding="utf-8")
        n += 1
        print(f"  thin -> {p.name}")
    print(f"共 {n} 张薄卡")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
