#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s6_ask.py — 检索：给一句局面描述，返回该读哪几行

四类内容（A 英雄 / B 克制 / C BP / D 对局内）打分规则不同：
  · 提到英雄名 => 过滤条件，不是加分项（否则同一英雄的所有条目同分）
  · 提到「两个英雄」=> 对位问题，B 类优先，A 类降权
  · 提到「这波/该不该」=> D 类优先
  · 提到「怎么玩/连招」=> A 类优先

用法：
  python s6_ask.py "苏烈打孙策怎么打"
  python s6_ask.py "中路被压塔下怎么办" --json
  python s6_ask.py "K-D02" --show        # 打印条目全文
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parent.parent
IDX = ROOT / "30_index" / "index.jsonl"
LEX = ROOT / "30_index" / "lexicon.yaml"
KB = ROOT / "20_kb"

PHASE_HINT = {
    "选人": "01", "开局": "02", "一级": "02", "前四": "03", "对线": "04",
    "转线": "05", "游走": "05", "支援": "05", "资源": "06", "暴君": "06",
    "主宰": "06", "团战": "07", "开团": "07", "推进": "08", "顺风": "08",
    "逆风": "09", "翻盘": "09", "终结": "10", "推塔": "10",
}

# 分路词 → 分路名（L 类条目按文件名里的分路归属）
LANE_WORDS = {
    "中路": ["中路", "中单", "法师", "中线"],
    "游走": ["游走", "辅助", "软辅", "硬辅", "保人"],
    "发育路": ["发育路", "射手", "下路", "adc", "ADC"],
    "对抗路": ["对抗路", "边路", "上路", "上单", "坦边"],
    "打野": ["打野", "野区", "刷野", "反野"],
}

# 提问里的"这是哪一类问题"信号
CAT_HINT = {
    "A": ["怎么玩", "连招", "机制", "技能", "怎么用", "上手", "玩法", "怎么出"],
    "B": ["克制", "怕谁", "打不过", "被克", "怎么打他", "对线谁", "怎么打"],
    "C": ["选谁", "ban", "BP", "bp", "阵容", "先手", "后手", "拿什么"],
    "D": ["这波", "该不该", "什么时候", "几分钟", "现在", "要不要", "压塔"],
    "L": ["分路", "位置", "大局观", "该按什么", "第一步去哪", "我这个位置"],
}


def load_lexicon() -> tuple[list[str], list[str]]:
    if not LEX.exists() or yaml is None:
        return [], []
    d = yaml.safe_load(LEX.read_text(encoding="utf-8")) or {}
    return list(d.get("heroes") or []), list(d.get("terms") or [])


def tokenize(q: str, words: list[str]) -> list[str]:
    q = re.sub(r"\s+", "", q)
    toks = [w for w in words if w and w in q]
    for i in range(len(q) - 1):
        toks.append(q[i:i + 2])
    seen, out = set(), []
    for t in toks:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def score(e: dict, toks: list[str], q: str, q_heroes: set[str], hero_set: set[str]) -> float:
    s = 0.0
    e_heroes = set(e.get("heroes") or [])
    cat = e.get("cat", "")

    # ── 英雄门控：命中才保留，未命中降权（不是加分）
    if q_heroes:
        if e_heroes & q_heroes:
            s += 2.0
        else:
            s -= 3.0
        # B 类：题里点名的对手，正好是这条记录的对手
        opp = e.get("opponent") or ""
        if cat == "B" and opp:
            s += 5.0 if opp in q_heroes else -2.5
        # A 类明确不管对手是谁
        if cat == "A" and len(q_heroes) >= 2:
            s -= 2.5

    # 触发词（剔掉英雄名，避免重复计分）
    trig = [t for t in (e.get("triggers") or []) if t not in hero_set]
    s += 3.0 * sum(1 for t in trig if t in q)

    # 标题字重叠（排除英雄名：英雄已由门控计过，重复算会盖过真正的内容词）
    title = e.get("title", "")
    s += 1.5 * sum(1 for t in toks
                   if len(t) == 2 and t in title and t not in hero_set)

    # L 类：题里说的是哪个位置，就只该出哪个分路的条目
    if cat == "L":
        lane = (e.get("phase") or "").split("_")[-1]
        hit, miss = False, False
        for name, words in LANE_WORDS.items():
            if not any(w in q for w in words):
                continue
            if name == lane:
                hit = True
            else:
                miss = True
        if hit:
            s += 6.0
        elif miss:
            s -= 3.0

    for kw, ph in PHASE_HINT.items():
        if kw in q and e.get("phase", "").startswith(ph):
            s += 2.5
    for c, kws in CAT_HINT.items():
        if any(k in q for k in kws) and cat == c:
            s += 2.5

    st = e.get("status", "active")
    s += 0.5 if st == "active" else (-1.0 if st == "stale" else 0.0)
    return s


def locate(eid: str):
    if not IDX.exists():
        return None
    for ln in IDX.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        e = json.loads(ln)
        if e["id"] == eid:
            return KB / e.get("path", e["file"]), e["line"], e["end_line"]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--cat", default="", help="只搜某一类：A/B/C/D/L，逗号分隔")
    ap.add_argument("--show", action="store_true", help="打印条目全文，query 传 K-id")
    args = ap.parse_args()

    if args.show:
        loc = locate(args.query.strip())
        if not loc:
            print(f"没有 {args.query}", file=sys.stderr)
            return 1
        path, a, b = loc
        print("\n".join(path.read_text(encoding="utf-8").splitlines()[a - 1:b]))
        return 0

    if not IDX.exists():
        print("索引不存在，先跑 s5_index.py", file=sys.stderr)
        return 1

    heroes, terms = load_lexicon()
    hero_set = set(heroes)
    q_heroes = {h for h in heroes if h in args.query}
    toks = tokenize(args.query, terms + heroes)

    cats = {c.strip().upper() for c in args.cat.split(",") if c.strip()}
    entries = [json.loads(ln) for ln in IDX.read_text(encoding="utf-8").splitlines() if ln.strip()]
    if cats:
        entries = [e for e in entries if e.get("cat") in cats]

    if not entries:
        print("该类别下没有任何条目。看 `20_kb/<类>/_说明.md` 了解缺口。", file=sys.stderr)
        return 4

    hits = []
    for e in entries:
        sc = score(e, toks, args.query, q_heroes, hero_set)
        if sc > 0:
            hits.append({**e, "score": round(sc, 1)})
    hits.sort(key=lambda h: -h["score"])
    hits = hits[: args.top]

    if not hits:
        print("未命中。各类条目数：", file=sys.stderr)
        for d in sorted(KB.iterdir()):
            if d.is_dir() and len(d.name) > 1:
                n = sum(1 for x in entries if x.get("cat") == d.name[0])
                print(f"  {d.name}  ({n} 条)", file=sys.stderr)
        return 3

    if args.json:
        keys = ("id", "cat", "phase", "file", "path", "line", "end_line",
                "title", "score", "status", "bvid")
        print(json.dumps([{k: h.get(k) for k in keys} for h in hits],
                         ensure_ascii=False, indent=1))
        return 0

    labels = {"A": "英雄", "B": "克制", "C": "BP", "D": "对局内", "L": "分路"}
    for h in hits:
        print(f"[{h['score']:>4}] {h['id']} {h['title']}")
        print(f"        {labels.get(h.get('cat'), '?')}类 / {h.get('path', h['file'])}"
              f":{h['line']}-{h['end_line']}  ({h['status']}, {h.get('confidence','')})")
    if hits[0]["score"] < 4:
        print("\n⚠️ 命中偏弱，大概率该整节读而不是只看这一条", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
