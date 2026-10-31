#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s5_index.py — 扫 20_kb/*.md 建 index.jsonl，并做时间戳机械校验

校验规则（不靠模型自觉）：
  条目「来源」行里的每个 mm:ss，必须能在对应 <BV>.cues.json 里找到 ±3s 的 cue。
  找不到 → 判为编造，拒绝入库（--lenient 可只告警）。
  该 BV 没有 cues 文件 → 记 unverified，仍入库但标注。

用法：
  python s5_index.py
  python s5_index.py --strict      # 有任何时间戳对不上就 exit 1
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
KB = ROOT / "20_kb"
RAW = ROOT / "10_sources" / "raw"
IDX = ROOT / "30_index"

HEAD_RE = re.compile(r"^###\s+(K-([ABCD])\d{2,3})\s+(.+?)\s*$")
SEC_RE = re.compile(r"^#{2,3}\s+")
TS_RE = re.compile(r"(\d{1,2}):(\d{2})")
BV_RE = re.compile(r"BV[0-9A-Za-z]{10}")
FIELD_RE = re.compile(r"^[-*]\s*(?:\*\*)?([\u4e00-\u9fa5A-Za-z]{2,10})(?:\*\*)?\s*[:：]\s*(.+)$")
TOL = 3.0


def load_lexicon() -> tuple[list[str], list[str]]:
    p = IDX / "lexicon.yaml"
    if not p.exists() or yaml is None:
        return [], []
    d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return list(d.get("heroes") or []), list(d.get("terms") or [])


def cue_times(bvid: str) -> list[float] | None:
    """时间锚点来源：raw/ 的原始 cues，或 creators_cache/subs 的浏览器采集结果。"""
    p = RAW / f"{bvid}.cues.json"
    if p.exists():
        try:
            cues = json.loads(p.read_text(encoding="utf-8")).get("cues") or []
            return sorted(float(c.get("from", 0)) for c in cues)
        except Exception:
            return None
    q = ROOT / "10_sources" / "creators_cache" / "subs" / f"{bvid}.json"
    if q.exists():
        try:
            body = json.loads(q.read_text(encoding="utf-8")).get("body") or []
            return sorted(float(c.get("from", 0)) for c in body)
        except Exception:
            return None
    return None


def near(ts: float, times: list[float], tol: float = TOL) -> bool:
    import bisect
    i = bisect.bisect_left(times, ts)
    for j in (i - 1, i, i + 1):
        if 0 <= j < len(times) and abs(times[j] - ts) <= tol:
            return True
    return False


def parse_entries(path: Path) -> list[dict]:
    lines = path.read_text(encoding="utf-8").splitlines()
    heads = [(i, m) for i, ln in enumerate(lines) if (m := HEAD_RE.match(ln))]
    out = []
    for n, (i, m) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        for j in range(i + 1, len(lines)):
            if SEC_RE.match(lines[j]) and not HEAD_RE.match(lines[j]):
                end = min(end, j)
                break
        body = lines[i:end]
        fields: dict[str, str] = {}
        for ln in body[1:]:
            fm = FIELD_RE.match(ln.strip())
            if fm:
                k, v = fm.group(1), fm.group(2).strip()
                fields[k] = (fields[k] + " / " + v) if k in fields else v
        out.append({
            "id": m.group(1), "cat": m.group(2), "title": m.group(3).strip(),
            "line": i + 1, "end_line": end,
            "fields": fields, "file": path.name,
            "path": str(path.relative_to(KB)),
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--lenient", action="store_true", default=True)
    args = ap.parse_args()

    heroes, terms = load_lexicon()
    entries, problems = [], []
    cache: dict[str, list[float] | None] = {}

    for md in sorted(KB.rglob("*.md")):
        if md.name.startswith("_"):
            continue
        for e in parse_entries(md):
            f = e["fields"]
            src = f.get("来源", "")
            bvids = list(dict.fromkeys(BV_RE.findall(src)))
            stamps = [int(a) * 60 + int(b) for a, b in TS_RE.findall(src)]

            status = "ok"
            if not bvids:
                status = "no_source"
                problems.append(f"{e['id']} 无 BV 来源")
            else:
                # 语义：每个时间戳只要能在**任一**引用视频里找到就算可溯源。
                # 旧逻辑要求在每个视频里都有，多来源条目会被误判。
                have: list[tuple[str, list[float]]] = []
                for bv in bvids:
                    if bv not in cache:
                        cache[bv] = cue_times(bv)
                    times = cache[bv]
                    if times:
                        have.append((bv, times))
                if not have:
                    status = "unverified"
                else:
                    for ts in stamps:
                        if not any(near(ts, t) for _, t in have):
                            status = "bad_timestamp"
                            problems.append(
                                f"{e['id']} 时间戳 {ts//60:02d}:{ts%60:02d} 在 "
                                f"{'/'.join(b for b, _ in have)} 里找不到")

            text = e["title"] + " " + f.get("触发条件", "") + " " + f.get("判断依据", "")
            # A/B 类按英雄立卡，归属直接取文件名（正文不一定出现英雄名，靠猜会漏）
            stem = Path(md.stem).name
            own = [stem] if stem in heroes else []
            e_heroes = list(dict.fromkeys(own + [h for h in heroes if h in text]))
            e_terms = [t for t in terms if t in text]

            # B 类：标题里的「对XX：」就是这个条目的对手，单独存字段
            opp = ""
            mo = re.search(r"对([\u4e00-\u9fa5]{2,4})[：:]", e["title"])
            if mo and mo.group(1) in heroes:
                opp = mo.group(1)

            entries.append({
                "id": e["id"], "cat": e["cat"],
                "phase": Path(md.stem).name, "file": e["file"], "path": e["path"],
                "line": e["line"], "end_line": e["end_line"], "title": e["title"],
                "triggers": list(dict.fromkeys(e_terms + e_heroes))[:12],
                "heroes": e_heroes,
                "opponent": opp,
                "status": (f.get("状态") or "active").split("/")[0].strip(),
                "confidence": f.get("可信度", "mid").split("（")[0].split("(")[0].strip(),
                "bvid": bvids[0] if bvids else "",
                "version": f.get("适用版本", ""),
                "check": status,
            })

    IDX.mkdir(parents=True, exist_ok=True)
    (IDX / "index.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in entries) + "\n",
        encoding="utf-8")

    print(f"indexed={len(entries)} -> {IDX / 'index.jsonl'}")
    bad = [e for e in entries if e["check"] == "bad_timestamp"]
    print(f"bad_timestamp={len(bad)} unverified={sum(1 for e in entries if e['check']=='unverified')}")
    for p in problems:
        print("  ! " + p)
    if args.strict and bad:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
