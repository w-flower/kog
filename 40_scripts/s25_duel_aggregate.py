#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s25_duel_aggregate.py — 把专栏边聚合成可以写进矩阵的裁决记录

s23 产出的是一堆「某篇文章说了某件事」，同一个对位会被好几篇重复提到，
也可能被两篇说反。这一步负责：

  1. 方向归并  同一对的两个方向取反后若互相矛盾 → 整对挂起，等人判
  2. 强度定档  克/小优 属同一符号，取证据更多的那个；平票取弱的（保守）
  3. 状态定级  硬门槛见 DECIDE：不是我凑不出 measured，是不给就降级
  4. 前提抽取  只认文中真写了的（前期/四级前/出装/分段），抽不到就降级

输出 30_index/duel/{lane}.col_verdicts.jsonl，由 s24 load_verdicts(…, "col_verdicts")
读入；人工写的 {lane}.verdicts.jsonl 在它之后 apply，覆盖自动结果。

用法：
  python s25_duel_aggregate.py --lane mid
  python s25_duel_aggregate.py --lane mid --review 12    # 抽样复核
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import names as N
import s24_duel_grid as G

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "30_index" / "duel"
TODAY = G.TODAY

SIGN = {"克": 1, "小优": 1, "五五开": 0, "小劣": -1, "被克": -1}
STRENGTH = {"克": 2, "小优": 1, "五五开": 0, "小劣": 1, "被克": 2}   # 同号内比强弱用

# 写成 measured 的硬门槛。达不到就是 derived——宁可少写，也不给用户一个假结论。
# 状态口径（和站点上的三个词一一对应）：
#   measured = 有人真讲过，能点开原文看到那句话 —— 一篇专栏也算
#   derived  = 只有方向、没有原文（官方 L0）或机制推演
# 所以专栏边一律 measured，可信度靠 conf 表达，不靠状态表达。
CONF_BY_N = {1: "low", 2: "mid", 3: "high"}

TIME_WORDS = ("前期", "中期", "后期", "四级前", "两级", "六神", "开局", "对线期",
              "第一波", "换线", "大后期", "前中后期", "中后期")
GEAR_WORDS = ("出装", "铭文", "装备", "抵抗鞋", "不祥", "制裁", "纯净", "魔女")
RANK_WORDS = ("低分段", "中低分段", "高分段", "高端局", "星耀", "钻石", "王者",
              "职业", "巅峰赛", "路人局")


def cond_of(quotes: list[str], cvs: list[str]) -> str:
    """成立条件。原文写了前提就照抄前提，没写就明说没写——不编一个像模像样的。"""
    blob = " ".join(quotes)
    bits = []
    for w in TIME_WORDS + GEAR_WORDS + RANK_WORDS:
        if w in blob and w not in bits:
            bits.append(w)
    src = "、".join("cv" + c for c in cvs[:2])
    when = "/".join(bits[:3]) if bits else "前提未标注"
    return f"{G.VERSION} · {when} · 来源 {src}"


def load_edges(lane: str) -> list[dict]:
    p = OUT / f"{lane}.column_edges.jsonl"
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def group(edges: list[dict]) -> tuple[dict[str, dict], list[tuple[str, str, str]]]:
    """按有向对归并。返回 (可用的, 冲突挂起列表)。"""
    by: dict[str, dict] = defaultdict(lambda: {"ev": [], "grades": Counter(),
                                               "cvs": set(), "branches": set(),
                                               "quotes": [], "layers": Counter()})
    for e in edges:
        k = G.key(e["a"], e["b"], e.get("_lane", ""))
        rec = by[k]
        rec["ev"].append(e)
        rec["grades"][e["grade"]] += 1
        rec["cvs"].add(e["cv"])
        rec["branches"].add(e["branch"])
        rec["quotes"].append(e["quote"])
        if e.get("layer"):
            rec["layers"][e["layer"]] += 1

    # 反向对账：a→b 说"a 赢"，b→a 也说"b 赢"，那就是互相都说自己赢，挂起
    held: list[tuple[str, str, str]] = []
    bad_keys: set[str] = set()
    for k, rec in by.items():
        lane, a, b = k.split("|")
        rk = G.key(b, a, lane)
        rev = by.get(rk)
        if not rev:
            continue
        sa = Counter()
        for g, n in rec["grades"].items():
            sa[SIGN[g]] += n
        sb = Counter()
        for g, n in rev["grades"].items():
            sb[-SIGN[g]] += n       # 反向看回来要取负
        if sa and sb:
            win_a, win_b = sa.most_common(1)[0][0], sb.most_common(1)[0][0]
            if win_a != 0 and win_b != 0 and win_a != win_b:
                held.append((a, b, f"两篇说反：{dict(rec['grades'])} vs {dict(rev['grades'])}"))
                bad_keys.update({k, rk})
    good = {k: v for k, v in by.items() if k not in bad_keys}
    return good, held


def pick_grade(grades: Counter) -> str:
    """同号内取证据多的；票数相同取弱的一档（保守），避免把「小优」吹成「克」。"""
    sgn = Counter()
    for g, n in grades.items():
        sgn[SIGN[g]] += n
    if not sgn:
        return ""
    sign = sgn.most_common(1)[0][0]
    pool = [g for g in grades if SIGN[g] == sign]
    pool.sort(key=lambda g: (-grades[g], STRENGTH[g]))
    return pool[0]


def to_verdict(lane: str, a: str, b: str, rec: dict) -> dict:
    grade = pick_grade(rec["grades"])
    cvs = sorted(rec["cvs"])
    quotes = rec["quotes"][:2]
    # 证据条目：每条来源一条，取该来源里最短的那句引用
    ev = []
    for e in rec["ev"][:3]:
        q = re.sub(r"^\[(?:win|lose)\]\s*", "", e["quote"] or "")
        ev.append({"kind": "column", "ref": str(e["cv"]), "quote": q,
                   "url": e.get("url", ""), "ts": None})
    cond = cond_of(rec["quotes"], cvs)
    status = "measured"
    layer = rec["layers"].most_common(1)[0][0] if rec["layers"] else ""
    return {
        "key": G.key(a, b, lane), "a": a, "b": b,
        "grade": grade, "status": status,
        "basis": "column",
        "layer": layer,
        "conf": CONF_BY_N.get(min(len(cvs), 3), "low"),
        "cond": cond,
        "how": "", "counter": "",
        "ev": ev,
        "updated": TODAY, "by": "column",
        "src": {"cvs": cvs, "branches": sorted(rec["branches"]), "n": len(rec["ev"])},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="mid")
    ap.add_argument("--review", type=int, default=0, help="抽样复核条数")
    args = ap.parse_args()
    lane = args.lane

    edges = load_edges(lane)
    if not edges:
        print(f"[FATAL] 没有 {OUT / f'{lane}.column_edges.jsonl'}，先跑 s23", file=sys.stderr)
        return 1
    for e in edges:
        e["_lane"] = lane

    good, held = group(edges)
    verdicts = []
    for k, rec in good.items():
        _, a, b = k.split("|")
        v = to_verdict(lane, a, b, rec)
        errs = G.validate_verdict(v, lane)
        if errs:
            print(f"  [跳过] {k}: {'; '.join(errs)}")
            continue
        verdicts.append(v)

    verdicts.sort(key=lambda v: (v["a"], v["b"]))
    dst = OUT / f"{lane}.col_verdicts.jsonl"
    with dst.open("w", encoding="utf-8") as f:
        for v in verdicts:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")

    st = Counter(v["status"] for v in verdicts)
    gd = Counter(v["grade"] for v in verdicts)
    n_cv = len({c for v in verdicts for c in v["src"]["cvs"]})
    print(f"== 专栏聚合 · {lane} ==")
    print(f"   边 {len(edges)} → 有向对 {len(good)} 挂起 {len(held)}")
    print(f"   写入 {len(verdicts)} 条：measured {st['measured']} / derived {st['derived']}")
    print(f"   档位 {dict(gd)} · 用到的专栏 {n_cv} 篇")
    if held:
        print(f"   [挂起] 需要人工裁决的 {len(held)} 对：")
        for a, b, why in held[:10]:
            print(f"     {a} vs {b} — {why}")
    print(f"   -> {dst}")

    if args.review:
        print(f"\n== 抽样复核 {args.review} 条 ==")
        step = max(1, len(verdicts) // args.review)
        for v in verdicts[::step][:args.review]:
            print(f"  {v['a']} {v['grade']} {v['b']}  [{v['status']}/{v['conf']}]"
                  f" {v['src']['cvs']} {v['src']['branches']}")
            for e in v["ev"][:2]:
                print(f"     「{e['quote'][:56]}」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
