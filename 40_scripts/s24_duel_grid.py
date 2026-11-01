#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s24_duel_grid.py — 同路对位矩阵：建骨架 / 出队列 / 收裁决 / 重建

是什么：把「不知火舞打得过谁」这件事变成 24×23 = 552 个格，每格一个五档判断。
        档位相对**本方**（`grade` 说的是 a 对 b）。

五档：克 / 小优 / 五五开 / 小劣 / 被克
三态：measured（有人真的讲过）/ derived（有档位但没实测）/ empty（待补）
      推演必须带 `basis`，站点上会画斜纹 +「推」角标，和实测分开。

一条关键简化：档位满足反对称（克↔被克、小优↔小劣、五五开↔五五开），
所以真正要人判的是 276 个无序对，另一侧由本脚本镜像。

文件：
  30_index/duel/{lane}.grid.json        552 格，唯一权威（本脚本生成，不手改）
  30_index/duel/{lane}.verdicts.jsonl   裁决记录，append-only，按 key 去重（唯一手改）
  30_index/duel/candidates.{lane}.jsonl 机器候选池（s23 专栏 / s19 字幕产出）
  30_index/duel/{lane}.queue.json       待判队列，按优先级分批

用法：
  python s24_duel_grid.py --lane mid                 # 重建 grid
  python s24_duel_grid.py --lane mid --dry           # 只看统计
  python s24_duel_grid.py --lane mid --queue         # 出队列
  python s24_duel_grid.py --lane mid --queue --hero 不知火舞,小乔
  python s24_duel_grid.py --lane mid --ingest 50_logs/duel_verdict_batch_1.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import names  # noqa: E402

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
IDX = ROOT / "30_index"
DUEL = IDX / "duel"
KB = ROOT / "20_kb" / "B_克制关系"
LOGS = ROOT / "50_logs"
VERSION = "S45"
TODAY = "2026-11-01"

LANE_CN = {"solo": "对抗路", "jungle": "打野", "mid": "中路", "adc": "发育路", "roam": "游走"}
GRADES = ["克", "小优", "五五开", "小劣", "被克"]
INV = {"克": "被克", "小优": "小劣", "五五开": "五五开", "小劣": "小优", "被克": "克"}
STATUS = ["empty", "derived", "measured"]
BASIS = ["column", "video", "official", "mechanism"]
CONF = ["high", "mid", "low"]
LAYERS = ["机制", "数值", "节奏", ""]

# 官方只给方向不给强度。落到五档里取最保守的可撤销默认，且 status=derived 永不显示成实测。
OFFICIAL_GRADE = "小优"


def key(a: str, b: str, lane: str) -> str:
    return f"{lane}|{a}|{b}"


# ────────────────────────── 建格子 ──────────────────────────
def lane_heroes(lane: str) -> list[str]:
    """矩阵英雄池 = 官方 lanes 里含该路的全部英雄（不是只看 main_lane）。

    只看主位会漏掉诸葛亮、貂蝉、司马懿这些「主位写的是打野/边路、
    实际天天在中路」的英雄，而这几个恰恰是对位问题里最常出现的名字。
    """
    N = names.load()
    return sorted(N.by_lane(lane, primary_only=False))


def skeleton(lane: str) -> dict[str, dict]:
    hs = lane_heroes(lane)
    cells: dict[str, dict] = {}
    for a in hs:
        for b in hs:
            if a == b:
                continue
            cells[key(a, b, lane)] = {
                "key": key(a, b, lane), "a": a, "b": b,
                "grade": None, "status": "empty", "basis": None,
                "layer": "", "conf": None, "cond": "",
                "how": "", "counter": "", "ev": [],
                "mirror_of": "", "updated": "", "by": "",
            }
    return cells


def seed_official(cells: dict[str, dict], lane: str) -> int:
    """官方同路边 → derived。官方只给方向，强度一律按 OFFICIAL_GRADE。"""
    p = IDX / "relations.json"
    if not p.exists():
        return 0
    rel = json.loads(p.read_text(encoding="utf-8"))
    N = names.load()
    ename_of = {h["name"]: (h["ename"][0] if h["ename"] else 0) for h in N.roster}
    n = 0
    for e in rel["edges"]:
        w, l = e["win"], e["lose"]
        if N.lane_of(w) != lane or N.lane_of(l) != lane:
            continue
        k = key(w, l, lane)
        if k not in cells:
            continue
        c = cells[k]
        if c["status"] == "measured":
            continue
        c["grade"] = OFFICIAL_GRADE
        c["status"] = "derived"
        c["basis"] = "official"
        c["layer"] = "机制"
        c["conf"] = "low"
        c["ev"] = [{"kind": "official",
                    "ref": f"{ename_of.get(w, 0)}.json",
                    "wt": 1,
                    "quote": (e.get("desc") or "")[:44],
                    "url": f"https://pvp.qq.com/web201605/herodetail/{ename_of.get(w, 0)}.shtml"}]
        c["updated"], c["by"] = TODAY, "seed"
        n += 1
    return n


GRADE_FROM_LAYER = [
    (r"机制克|数值克|节奏克|完克|天克", "克"),
    (r"被压制|被克|打不过", "被克"),
    (r"五五开|均势", "五五开"),
]

FIELD_RE = re.compile(r"^\s*-\s*\*\*(.+?)\*\*[：:]\s*(.+?)\s*$")


def _entry_fields(md: str, eid: str) -> dict:
    """从 B 卡里抠出某个 K-B 条目的 bullet 字段。"""
    m = re.search(rf"^###\s+{re.escape(eid)}\b.*?$", md, re.M)
    if not m:
        return {}
    rest = md[m.end():]
    nxt = re.search(r"^###\s|^##\s", rest, re.M)
    body = rest[:nxt.start()] if nxt else rest
    out = {}
    for ln in body.splitlines():
        f = FIELD_RE.match(ln)
        if f:
            out[f.group(1)] = f.group(2)
    return out


# ────────────────────────── 裁决 ──────────────────────────
def load_verdicts(lane: str, suffix: str = "verdicts") -> dict[str, dict]:
    """suffix=verdicts 是人写的；suffix=col_verdicts 是 s25 从专栏自动生成的。"""
    p = DUEL / f"{lane}.{suffix}.jsonl"
    if not p.exists():
        return {}
    out: dict[str, dict] = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        try:
            v = json.loads(ln)
        except Exception:
            continue
        if v.get("key"):
            out[v["key"]] = v          # 后到的覆盖先到的
    return out


def validate_verdict(v: dict, lane: str) -> list[str]:
    """返回错误列表，空 = 通过。s26 也 import 这个，保证两边规则一致。"""
    errs = []
    k = v.get("key", "")
    if not k.startswith(lane + "|"):
        errs.append(f"key 前缀不对：{k}")
    parts = k.split("|")
    if len(parts) != 3:
        errs.append(f"key 格式应为 lane|a|b：{k}")
        return errs
    _, a, b = parts
    if v.get("a") and v["a"] != a:
        errs.append(f"a 与 key 不一致：{v['a']} vs {a}")
    if v.get("b") and v["b"] != b:
        errs.append(f"b 与 key 不一致：{v['b']} vs {b}")
    if v.get("grade") not in GRADES:
        errs.append(f"grade 非法：{v.get('grade')}")
    if v.get("status") not in STATUS:
        errs.append(f"status 非法：{v.get('status')}")
    if v.get("status") == "derived" and v.get("basis") not in BASIS:
        errs.append("derived 必须带合法 basis")
    if v.get("status") == "measured":
        ev = [e for e in (v.get("ev") or []) if e.get("kind") in ("column", "video")]
        if not ev:
            errs.append("measured 必须有 column/video 证据")
        if not (v.get("cond") or "").strip():
            errs.append("measured 必须写 cond（版本·节点·前提），写不出就降级 derived")
        if v.get("conf") == "high" and len(v.get("ev") or []) < 2:
            errs.append("conf=high 必须 ≥2 条证据")
    if v.get("layer") not in LAYERS:
        errs.append(f"layer 非法：{v.get('layer')}")
    if v.get("conf") and v["conf"] not in CONF:
        errs.append(f"conf 非法：{v['conf']}")
    for e in (v.get("ev") or []):
        if e.get("kind") not in ("official", "column", "video", "mechanism"):
            errs.append(f"ev.kind 非法：{e.get('kind')}")
    return errs


def apply_verdicts(cells: dict[str, dict], verdicts: dict[str, dict], lane: str) -> int:
    n = 0
    for k, v in verdicts.items():
        if k not in cells:
            continue                      # 跨路的 key，忽略
        c = cells[k]
        c.update({kk: v[kk] for kk in
                  ("grade", "status", "basis", "layer", "conf", "cond",
                   "how", "counter", "ev", "updated", "by") if kk in v})
        n += 1
    return n


def mirror(cells: dict[str, dict], lane: str) -> int:
    """一侧有档位、另一侧空 → 按反对称补上。own 的 how/counter 不继承（视角不同）。"""
    n = 0
    for k, c in list(cells.items()):
        if c["status"] == "empty" or not c["grade"]:
            continue
        rk = key(c["b"], c["a"], lane)
        r = cells.get(rk)
        if not r or r["status"] != "empty":
            continue
        r.update({
            "grade": INV[c["grade"]],
            "status": "derived" if c["status"] == "derived" else "measured",
            "basis": c["basis"], "layer": c["layer"],
            "conf": "low" if c["status"] == "derived" else c["conf"],
            "cond": c["cond"], "how": "", "counter": "",
            "ev": c["ev"], "mirror_of": k, "updated": c["updated"], "by": "mirror",
        })
        n += 1
    return n


def stats(cells: dict[str, dict]) -> dict:
    st = defaultdict(int)
    gd = defaultdict(int)
    for c in cells.values():
        st[c["status"]] += 1
        if c["grade"]:
            gd[c["grade"]] += 1
    return {"total": len(cells),
            "measured": st["measured"], "derived": st["derived"], "empty": st["empty"],
            "grades": dict(gd)}


def build(lane: str) -> tuple[dict[str, dict], dict]:
    cells = skeleton(lane)
    n_off = seed_official(cells, lane)
    n_c = apply_verdicts(cells, load_verdicts(lane, "col_verdicts"), lane)
    # 人工裁决放最后，覆盖自动生成的那一层
    n_v = apply_verdicts(cells, load_verdicts(lane), lane)
    n_m = mirror(cells, lane)
    return cells, {"official": n_off, "columns": n_c, "verdicts": n_v,
                   "mirrored": n_m}


def save(cells: dict[str, dict], lane: str, meta: dict) -> None:
    DUEL.mkdir(parents=True, exist_ok=True)
    hs = lane_heroes(lane)
    order = {h: i for i, h in enumerate(hs)}
    rows = sorted(cells.values(), key=lambda c: (order.get(c["a"], 999), order.get(c["b"], 999)))
    for c in rows:
        c["ev"] = (c.get("ev") or [])[:2]        # 站点体积：每格最多 2 条证据
    payload = {
        "lane": lane, "lane_cn": LANE_CN.get(lane, lane), "version": VERSION,
        "updated": TODAY, "grades": GRADES, "inv": INV,
        "heroes": hs, "coverage": stats(cells), "seed": meta,
        "cells": rows,
    }
    (DUEL / f"{lane}.grid.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


# ────────────────────────── 队列 ──────────────────────────
def kb_candidates(lane: str) -> dict[str, list[dict]]:
    """已有 K-B 条目 → **候选**，不直接落档位。

    为什么不当种子：B 卡的「克制层级」字段方向语义不统一——
    「机制克」多数指"我克他"，但女娲 K-B04 明写「机制克（反向）——这条是女娲被克」。
    自动映射必然写反。所以这里只把它变成一条高可信候选，让人判。
    """
    p = IDX / "index.jsonl"
    if not p.exists():
        return {}
    N = names.load()
    lane_set = set(N.by_lane(lane))
    out: dict[str, list[dict]] = defaultdict(list)
    for ln in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("cat") != "B":
            continue
        a, b = r.get("phase", ""), r.get("opponent", "")
        if a not in lane_set or b not in lane_set or a == b:
            continue
        out[key(a, b, lane)].append({
            "kind": "video", "ref": r.get("bvid") or "",
            "quote": r.get("title", "")[:60], "grade_hint": None,
            "kb": r.get("id"), "conf": "high", "from_kb": True,
            "url": (f"https://www.bilibili.com/video/{r['bvid']}"
                    if r.get("bvid") else ""),
        })
    return dict(out)


def load_candidates(lane: str) -> dict[str, list[dict]]:
    p = DUEL / f"candidates.{lane}.jsonl"
    out: dict[str, list[dict]] = defaultdict(list)
    N = names.load()
    mid = set(N.by_lane(lane))
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            win, lose = r.get("win", ""), r.get("lose", "")
            if win in mid and lose in mid and win != lose:
                out[key(win, lose, lane)].append(r)
    for k, lst in kb_candidates(lane).items():
        out[k] = lst + out.get(k, [])
    return out


def build_queue(cells: dict[str, dict], lane: str, heroes: set[str] | None,
                per_batch: int = 20) -> dict:
    cands = load_candidates(lane)
    rows = []
    for k, c in cells.items():
        if heroes and c["a"] not in heroes:
            continue
        cs = cands.get(k, [])
        # 同一对两个方向都被抽到 = 冲突，最该先看
        rev = key(c["b"], c["a"], lane)
        conflict = bool(cs) and bool(cands.get(rev))
        if conflict:
            pri = 0
        elif len(cs) >= 2 or any(x.get("title_pair") for x in cs):
            pri = 1
        elif cs:
            pri = 2
        elif c["status"] == "derived":
            pri = 3
        else:
            pri = 4
        rows.append({
            "key": k, "a": c["a"], "b": c["b"], "pri": pri, "conflict": conflict,
            "cur": {"grade": c["grade"], "status": c["status"], "basis": c["basis"]},
            "cands": cs[:4],
        })
    rows.sort(key=lambda x: (x["pri"], x["a"], x["b"]))
    batches = [{"n": i // per_batch + 1, "cells": rows[i:i + per_batch]}
               for i in range(0, len(rows), per_batch)]
    return {"lane": lane, "generated": TODAY, "per_batch": per_batch,
            "stats": {p: sum(1 for r in rows if r["pri"] == p) for p in range(5)},
            "batches": batches}


# ────────────────────────── main ──────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="mid")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--queue", action="store_true")
    ap.add_argument("--hero", default="")
    ap.add_argument("--ingest", default="")
    args = ap.parse_args()
    lane = args.lane

    if args.ingest:
        p = Path(args.ingest)
        if not p.exists():
            print(f"找不到 {p}", file=sys.stderr)
            return 2
        good, bad = [], []
        for i, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            try:
                v = json.loads(ln)
            except Exception as e:
                bad.append((i, f"JSON 解析失败 {e}"))
                continue
            v.setdefault("updated", TODAY)
            v.setdefault("by", "human")
            e = validate_verdict(v, lane)
            (bad.append((i, "; ".join(e))) if e else good.append(v))
        if bad:
            print("整批拒收，问题行：", file=sys.stderr)
            for i, m in bad:
                print(f"  第 {i} 行：{m}", file=sys.stderr)
            return 1
        DUEL.mkdir(parents=True, exist_ok=True)
        vf = DUEL / f"{lane}.verdicts.jsonl"
        with vf.open("a", encoding="utf-8") as f:
            for v in good:
                f.write(json.dumps(v, ensure_ascii=False) + "\n")
        print(f"已收 {len(good)} 条 → {vf}")
        return 0

    cells, meta = build(lane)
    st = stats(cells)
    if args.dry:
        print(f"{lane}: {st}")
        print(f"seed {meta}")
        return 0

    if args.queue:
        heroes = {x.strip() for x in args.hero.split(",") if x.strip()} or None
        q = build_queue(cells, lane, heroes)
        DUEL.mkdir(parents=True, exist_ok=True)
        (DUEL / f"{lane}.queue.json").write_text(
            json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
        s = q["stats"]
        print(f"queue -> {DUEL / f'{lane}.queue.json'}  {len(q['batches'])} 批")
        print(f"  P0冲突 {s[0]} / P1证据足 {s[1]} / P2单条 {s[2]} / P3仅官方 {s[3]} / P4全空 {s[4]}")
        return 0

    save(cells, lane, meta)
    g = st["grades"]
    print(f"grid -> {DUEL / f'{lane}.grid.json'}")
    print(f"  共 {st['total']} 格：实测 {st['measured']} / 推演 {st['derived']} / 待补 {st['empty']}")
    print(f"  五档分布：" + " ".join(f"{x}{g.get(x, 0)}" for x in GRADES))
    print(f"  种子：官方 {meta['official']} · 裁决 {meta['verdicts']} · 镜像 {meta['mirrored']}")

    LOGS.mkdir(exist_ok=True)
    (LOGS / f"duel_coverage_{lane}.md").write_text(
        f"# {LANE_CN.get(lane, lane)}对位覆盖\n\n"
        f"- 总格数 {st['total']}\n- 实测 {st['measured']}\n"
        f"- 推演 {st['derived']}\n- 待补 {st['empty']}\n\n"
        f"## 五档分布\n\n" + "\n".join(f"- {x}：{g.get(x, 0)}" for x in GRADES) + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
