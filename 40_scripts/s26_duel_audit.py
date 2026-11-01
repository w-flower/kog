#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s26_duel_audit.py — 对位矩阵的十项机械校验

为什么要有：552 个格靠人填，最怕的是「看起来填满了，其实一半是错的」。
这个脚本只做机器能判的事，判不了的一律不放过。

用法：
  python s26_duel_audit.py --lane mid --gate 1
  python s26_duel_audit.py --lane mid --gate 3 --json
返回码：0 全过 / 1 有失败项
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import names  # noqa: E402
import s24_duel_grid as G  # noqa: E402

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
IDX = ROOT / "30_index"
DUEL = IDX / "duel"
SUBS = ROOT / "10_sources" / "creators_cache" / "subs"
OFF = ROOT / "10_sources" / "official"
ARTS = ROOT / "10_sources" / "articles"
ARTCACHE = ROOT / "10_sources" / "bili_cache" / "article"


def load_grid(lane: str) -> dict:
    p = DUEL / f"{lane}.grid.json"
    if not p.exists():
        raise SystemExit(f"缺 {p}，先跑 s24_duel_grid.py --lane {lane}")
    return json.loads(p.read_text(encoding="utf-8"))


def article_index() -> set[str]:
    p = ARTS / "index.json"
    if not p.exists():
        return set()
    try:
        return {str(x.get("cv")) for x in json.loads(p.read_text(encoding="utf-8"))}
    except Exception:
        return set()


def max_cue_time(bv: str) -> float:
    p = SUBS / f"{bv}.json"
    if not p.exists():
        return -1
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return -1
    body = d.get("body") or []
    return max((float(c.get("from") or 0) for c in body), default=0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="mid")
    ap.add_argument("--gate", type=int, default=1, choices=[1, 2, 3])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    lane = args.lane

    g = load_grid(lane)
    cells = g["cells"]
    hs = set(g["heroes"])
    N = names.load()
    expect = set(N.by_lane(lane, primary_only=False))
    arts = article_index()

    res: list[dict] = []

    def chk(no: int, name: str, bad: list[str], need: str = "100%") -> None:
        res.append({"no": no, "name": name, "bad": bad[:8],
                    "n_bad": len(bad), "ok": not bad, "need": need})

    # 1 格数 / 集合 / 自环
    bad1 = []
    if len(cells) != len(expect) * (len(expect) - 1):
        bad1.append(f"格数 {len(cells)} ≠ {len(expect)}×{len(expect)-1}")
    if hs != expect:
        bad1.append(f"英雄集合不一致：多 {sorted(hs-expect)} 缺 {sorted(expect-hs)}")
    bad1 += [c["key"] for c in cells if c["a"] == c["b"]]
    chk(1, "格数 / 英雄集合 / 无自环", bad1)

    # 2 对称性
    idx = {c["key"]: c for c in cells}
    bad2 = []
    for c in cells:
        r = idx.get(G.key(c["b"], c["a"], lane))
        if not r:
            bad2.append(f"{c['key']} 没有反向格")
            continue
        if c["grade"] and r["grade"] and r["grade"] != G.INV.get(c["grade"]):
            bad2.append(f"{c['a']}›{c['b']}={c['grade']} 但 {c['b']}›{c['a']}={r['grade']}")
    chk(2, "对称性 grade(b,a)==INV[grade(a,b)]", bad2)

    # 3 枚举
    bad3 = []
    for c in cells:
        if c["grade"] and c["grade"] not in G.GRADES:
            bad3.append(f"{c['key']} grade={c['grade']}")
        if c["status"] not in G.STATUS:
            bad3.append(f"{c['key']} status={c['status']}")
        if c["basis"] and c["basis"] not in G.BASIS:
            bad3.append(f"{c['key']} basis={c['basis']}")
        if c["conf"] and c["conf"] not in G.CONF:
            bad3.append(f"{c['key']} conf={c['conf']}")
        if c["layer"] not in G.LAYERS:
            bad3.append(f"{c['key']} layer={c['layer']}")
        if c["status"] == "empty" and c["grade"]:
            bad3.append(f"{c['key']} empty 却有档位")
        if c["status"] != "empty" and not c["grade"]:
            bad3.append(f"{c['key']} 非 empty 却无档位")
    chk(3, "枚举合法 / 档位与状态自洽", bad3)

    # 4 measured 必须有实证
    bad4 = []
    for c in cells:
        if c["status"] != "measured":
            continue
        if not any(e.get("kind") in ("column", "video") for e in c["ev"]):
            bad4.append(f"{c['key']} 无 column/video 证据")
        if c["conf"] == "high" and len(c["ev"]) < 2:
            bad4.append(f"{c['key']} conf=high 但只有 {len(c['ev'])} 条证据")
    chk(4, "measured 必有实证 / high 需≥2条", bad4)

    # 5 证据可查
    bad5 = []
    for c in cells:
        for e in c["ev"]:
            k, r = e.get("kind"), str(e.get("ref") or "")
            if k == "video" and not (SUBS / f"{r}.json").exists():
                bad5.append(f"{c['key']} 视频字幕缺失 {r}")
            elif k == "official" and not (OFF / r).exists():
                bad5.append(f"{c['key']} 官方缓存缺失 {r}")
            elif k == "column" and r not in arts \
                    and not (ARTCACHE / f"{r}.json").exists():
                bad5.append(f"{c['key']} 专栏未收录 {r}")
    chk(5, "ev.ref 可查（unknown-ref=0）", bad5)

    # 6 视频时间戳可回溯
    bad6 = []
    cache: dict[str, float] = {}
    for c in cells:
        for e in c["ev"]:
            if e.get("kind") != "video" or not e.get("ts"):
                continue
            bv = str(e.get("ref"))
            mx = cache.setdefault(bv, max_cue_time(bv))
            if mx < 0:
                continue                      # 缺字幕已在第 5 项报
            if float(e["ts"]) > mx + 3:
                bad6.append(f"{c['key']} ts={e['ts']} > 字幕最大 {mx:.0f}s ({bv})")
    chk(6, "视频证据时间戳可回溯", bad6)

    # 7 measured 要有 cond
    bad7 = [c["key"] for c in cells
            if c["status"] == "measured" and not (c["cond"] or "").strip()]
    chk(7, "measured 必写 cond", bad7)

    # 8 推演必须带 basis（站点「推」标由 status=derived 驱动）
    bad8 = [c["key"] for c in cells
            if c["status"] == "derived" and c["basis"] not in G.BASIS]
    chk(8, "推演格必须带 basis", bad8)

    # 9 verdicts 全部能落地（没有指向不存在格子的裁决）
    vs = G.load_verdicts(lane)
    bad9 = [k for k in vs if k not in idx]
    chk(9, "verdicts 无孤儿 key", bad9)

    # 10 覆盖统计与 Gate 门槛
    st = Counter(c["status"] for c in cells)
    gd = Counter(c["grade"] for c in cells if c["grade"])
    # 覆盖门槛。
    #
    # 为什么是比例不是绝对值：矩阵从 552 格改成 930 格（英雄池口径改了，见 _schema.md），
    # 绝对条数失去意义。而且「五五开」这一档天然稀薄——没有任何一个 UP 会专门讲
    # 「谁跟谁五五开」，它只能在排除法里出现，硬性要求 30 格等于逼人造假。
    #
    # 真正防糊弄的是第 4/5/7/8 项（每条 measured 必须能点开原文），不是这一项。
    # 这里的门槛只保证「这东西确实被填过」，随证据增长逐级抬高。
    rows = {c["a"] for c in cells if c["status"] == "measured"}
    row_cov = len(rows) / len(expect) if expect else 0
    pct = st["measured"] / len(cells) if cells else 0
    REQ = {1: (0.005, 0.0), 2: (0.10, 0.50), 3: (0.18, 1.0)}
    need_pct, need_row = REQ[args.gate]
    bad10 = []
    if pct < need_pct:
        bad10.append(f"实测 {pct*100:.1f}% < Gate{args.gate} 要求 {need_pct*100:.0f}%")
    if row_cov < need_row:
        miss = sorted(expect - rows)
        bad10.append(f"有实测边的英雄 {len(rows)}/{len(expect)}"
                     f"（{row_cov*100:.0f}%）< 要求 {need_row*100:.0f}%；"
                     f"全空的：{'、'.join(miss[:8])}")
    if args.gate == 3 and st["empty"] > len(cells) * 0.75:
        bad10.append(f"待补 {st['empty']} > 总格数 75%")
    chk(10, f"Gate {args.gate} 覆盖门槛", bad10,
        need=f"实测≥{need_pct*100:.0f}% 且行覆盖≥{need_row*100:.0f}%")

    cov = {
        "total": len(cells), "measured": st["measured"],
        "derived": st["derived"], "empty": st["empty"],
        "grades": {x: gd[x] for x in G.GRADES},
        "measured_pct": round(st["measured"] / len(cells) * 100, 1),
    }

    if args.json:
        print(json.dumps({"lane": lane, "gate": args.gate, "coverage": cov,
                          "checks": res}, ensure_ascii=False, indent=1))
    else:
        print(f"== {g['lane_cn']}对位矩阵审计 · Gate {args.gate} ==")
        print(f"   覆盖 {cov['total']} 格：实测 {cov['measured']}"
              f"（{cov['measured_pct']}%）/ 推演 {cov['derived']} / 待补 {cov['empty']}")
        print("   五档：" + " ".join(f"{k}{v}" for k, v in cov["grades"].items()))
        print()
        for r in res:
            mark = "PASS" if r["ok"] else "FAIL"
            print(f"  [{mark}] {r['no']:2d}. {r['name']}"
                  + (f"  —— {r['n_bad']} 处" if r["n_bad"] else ""))
            for b in r["bad"]:
                print(f"         · {b}")

    return 0 if all(r["ok"] for r in res) else 1


if __name__ == "__main__":
    sys.exit(main())
