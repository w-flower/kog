#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s17_write_b.py — 按官方关系数据批量生成/刷新 B 类克制卡（全英雄池覆盖）

为什么要脚本：129 个英雄，人工建卡不可能全覆盖。但"覆盖"不等于"编"。
本脚本只做三件事：
  1. 把官方口径（L0）的四个方向边落成表，带来源与文案摘录 —— **可溯源**
  2. 保留人工写的 K 条目（在 <!-- AUTO --> 标记块之外）
  3. 明确标出"待实测"的格子，让缺口可见，而不是用推测填满

纪律：
  · 官方文案摘录 ≤40 字，加引号，视为合理引用；正文解释一律用自己的话。
  · 官方边**永不**写成"实测结论"，一律挂 `L0` 标记。
  · 已有 B 卡（手写）不覆盖正文，只替换标记块内的自动段落。

用法：
  python s17_write_b.py --dry            # 只看会写几个文件
  python s17_write_b.py                  # 全量写
  python s17_write_b.py --only 公孙离,铠   # 只刷这几个
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
IDX = ROOT / "30_index"
OFF = ROOT / "10_sources" / "official"
KB = ROOT / "20_kb" / "B_克制关系"
KB_MAKE = ROOT / "20_kb"
LANE_CN = {"solo": "对抗路", "jungle": "打野", "mid": "中路", "adc": "发育路", "roam": "游走"}
LANE_ORDER = ["solo", "jungle", "mid", "adc", "roam"]

AUTO_S = "<!-- AUTO:official:start 由 40_scripts/s17_write_b.py 生成，手改会被覆盖 -->"
AUTO_E = "<!-- AUTO:official:end -->"
AUTO_RE = re.compile(re.escape(AUTO_S) + r".*?" + re.escape(AUTO_E), re.S)

VER = "S45"
TODAY = "2026-11-01"


def clip(s: str, n: int = 44) -> str:
    s = re.sub(r"\s+", "", s or "").strip()
    return s[:n] + ("…" if len(s) > n else "")


def load() -> tuple[dict, list[dict], dict]:
    roster = json.loads((IDX / "roster.json").read_text(encoding="utf-8"))["heroes"]
    rel = json.loads((IDX / "relations.json").read_text(encoding="utf-8"))
    by_name = {h["name"]: h for h in roster}
    return by_name, roster, rel


def official_rows(me: str, by_name: dict, rel: dict) -> dict:
    """把全局边表拆成我这一侧的四个方向。"""
    out, inc = [], []          # out=我压的，inc=压我的
    for e in rel["edges"]:
        w, l = e["win"], e["lose"]
        if w == me and l != me:
            out.append({"opp": l, "desc": e.get("desc", ""), "src": e.get("src", [])})
        elif l == me and w != me:
            inc.append({"opp": w, "desc": e.get("desc", ""), "src": e.get("src", [])})
    return {"out": out, "in": inc}


def ev_cell(it: dict) -> str:
    """证据标记：官方直说 / 只有反向列 / 双向对上。"""
    src = it.get("src") or []
    if len(src) >= 2:
        return "L0 官方·双向"
    if any(s.endswith(":out") for s in src):
        return "L0 官方·直说"
    return "L0 官方·反列"


def cache_of(ename: int) -> dict:
    p = OFF / f"{ename}.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def lane_cn(name: str, by_name: dict) -> str:
    h = by_name.get(name)
    if not h:
        return "?"
    return "／".join(LANE_CN.get(x, x) for x in h["lanes"][:2])


def block_official(h: dict, by_name: dict, rel: dict) -> str:
    """生成 AUTO 标记块内的整段官方口径。"""
    me = h["name"]
    rows = official_rows(me, by_name, rel)
    c = cache_of(h["ename"][0]) if h["ename"] else {}
    mate = [x for x in c.get("mate", []) if x != me]

    L: list[str] = []
    L.append(AUTO_S)
    L.append("")
    L.append("## 官方口径（L0 · 未经实测）")
    L.append("")
    if not h["ename"]:
        L.append("> 本英雄在官方名录里没有独立 ename，无详情页，这一块留空。")
    elif not c or "err" in c:
        L.append(f"> 官方详情页不存在或抓取失败（`herodetail/{h['ename'][0]}.shtml`），这一块留空。")
        L.append("> 新英雄上线后官方常不补关系页，只能靠实测补。")
    else:
        L.append(f"> 来源：官方英雄详情页 `herodetail/{h['ename'][0]}.shtml`，{TODAY} 抓取。")
        L.append("> **这一层只是线索，不是结论。** 官方每个方向固定只列 2 个例子，"
                 "实测 117 个页面里双向能对上的只有 5 条（2%），说明它不是全量配对。")
        L.append("> 表格里「怎么打」一栏是空的就代表**本库还没有实测素材**，"
                 "空白比编造有用。")
        L.append("")

        def table(title: str, items: list[dict]) -> None:
            L.append(f"**{title}（{len(items)}）**")
            L.append("")
            if not items:
                L.append("_官方这一栏是空的。_")
                L.append("")
                return
            L.append("| 对手 | 对手分路 | 官方给的说法（摘录） | 我该怎么打 | 证据 |")
            L.append("|---|---|---|---|---|")
            for it in items:
                nm = it["opp"]
                d = clip(it.get("desc") or "（官方无文案）")
                L.append(f"| **{nm}** | {lane_cn(nm, by_name)} | “{d}” | _待补_ | {ev_cell(it)} |")
            L.append("")

        table("我压制的", rows["out"])
        table("压制我的", rows["in"])
        L.append(f"**和谁好搭（参考资料，不是克制）**：{'、'.join(mate) if mate else '—'}")
        L.append("")

    L.append(AUTO_E)
    return "\n".join(L)


def set_fm(text: str, key: str, val: str) -> str:
    """在 front matter 里设置一行（有则替换，无则插在结尾 `---` 之前）。"""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return text
    head = m.group(1)
    if re.search(rf"^{key}:.*$", head, re.M):
        head = re.sub(rf"^{key}:.*$", f"{key}: {val}", head, count=1, flags=re.M)
    else:
        head += f"\n{key}: {val}"
    return text[:m.start()] + f"---\n{head}\n---\n" + text[m.end():]


def fm_list(names: list[str]) -> str:
    return "[" + ", ".join(names) + "]" if names else "[]"


def skeleton(h: dict, by_name: dict, rel: dict, has_a: bool) -> str:
    me = h["name"]
    lanes = "／".join(LANE_CN.get(x, x) for x in h["lanes"])
    rows = official_rows(me, by_name, rel)
    fm = [
        "---",
        f"id: {me}",
        "cat: B",
        f"title: {me}的克制关系",
        f"version: {VER}",
        "status: active",
        f"updated: {TODAY}",
        "sources: [official]",
        # 机器可读：站点靠这两行做反向索引 + 克制矩阵
        f"beats: {fm_list([x['opp'] for x in rows['out']])}",
        f"loses: {fm_list([x['opp'] for x in rows['in']])}",
        "---",
        "",
        f"# {me}：克谁、怕谁",
        "",
        f"> 定位 {h['type'] or '—'}，分路 {lanes}。"
        + (f"英雄本身怎么玩见 `A_英雄教学/{me}.md`。" if has_a else "**本库还没有 A 卡。**"),
        "> 分层读法：**官方口径 L0**（谁克谁，没条件）→ **实测条目 K-Bxx**（有对局条件、有 BV 秒数）。",
        "",
    ]
    body = block_official(h, by_name, rel)
    n = sum(len(v) for v in official_rows(me, by_name, rel).values())
    tail = [
        "",
        "## 实测条目",
        "",
        "_还没有。要补的是：这套克制在什么分段、什么出装下成立，以及**具体怎么打**。_",
        "",
        "## 待补",
        "",
        f"- 上面官方边（{n} 条）的「我该怎么打」全是空的 —— 这是本卡最大的缺口"
        if n else "- 官方没有关系页，四条方向边全缺，只能靠实测从零建",
        f"- 找「打{me}」「{me}怎么打」类视频做实测（B 类专用采集，见 `s16_pick.py`）",
        "",
    ]
    return "\n".join(fm) + body + "\n" + "\n".join(tail)


def merge_into(old: str, h: dict, by_name: dict, rel: dict) -> str:
    """老卡：只替换 AUTO 块，没有就插在第一个 `## ` 之前。"""
    new_block = block_official(h, by_name, rel)
    if AUTO_RE.search(old):
        return AUTO_RE.sub(lambda _: new_block, old, count=1)
    m = re.search(r"^## ", old, re.M)
    if m:
        return old[:m.start()] + new_block + "\n\n" + old[m.start():]
    return old.rstrip() + "\n\n" + new_block + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--only", default="")
    args = ap.parse_args()

    by_name, roster, rel = load()
    a_cards = {p.stem for p in (KB_MAKE / "A_英雄教学").glob("*.md") if not p.name.startswith("_")}
    only = {x.strip() for x in args.only.split(",") if x.strip()}

    KB.mkdir(parents=True, exist_ok=True)
    made, merged, skipped = [], [], []
    for h in roster:
        me = h["name"]
        if only and me not in only:
            continue
        p = KB / f"{me}.md"
        rows = official_rows(me, by_name, rel)
        b_line = fm_list([x["opp"] for x in rows["out"]])
        l_line = fm_list([x["opp"] for x in rows["in"]])
        if p.exists():
            old = p.read_text(encoding="utf-8")
            new = merge_into(old, h, by_name, rel)
            new = set_fm(new, "beats", b_line)
            new = set_fm(new, "loses", l_line)
            if new != old:
                merged.append(me)
                if not args.dry:
                    p.write_text(new, encoding="utf-8")
            else:
                skipped.append(me)
        else:
            made.append(me)
            if not args.dry:
                p.write_text(skeleton(h, by_name, rel, me in a_cards), encoding="utf-8")

    print(f"新建 {len(made)}  合并 {len(merged)}  跳过 {len(skipped)}  总 {len(roster)}")
    if made[:12]:
        print("  新建样例：" + "、".join(made[:12]))
    if merged[:12]:
        print("  合并样例：" + "、".join(merged[:12]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
