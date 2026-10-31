#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s2_cues.py — 取带时间戳的 B 站字幕

为什么不用 batch_extract.py：它输出纯文本，时间戳全丢，条目里就没法写 "@03:12"。
本脚本直接调 bilibili-video-summary 的 fetch_cues()，一次请求同时落：
  <out>/<BV>.cues.json   原始结构化（cues[].from/to/content）
  <out>/<BV>.txt         [mm:ss] 逐行（人读 + 抽取用）

用法：
  python s2_cues.py --bvid BV1xx BV1yy
  python s2_cues.py --manifest channels/548729992.json --limit 5
  python s2_cues.py --manifest xxx.json --sleep 4 --workers 1
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

BILI = Path(r"C:/Users/Lenovo/.workbuddy/skills/bilibili-video-summary/scripts")
if str(BILI) not in sys.path:
    sys.path.insert(0, str(BILI))

try:
    from fetch_cues import fetch_cues  # noqa: E402
except Exception as e:  # pragma: no cover
    print(f"[FATAL] 无法导入 fetch_cues: {e}", file=sys.stderr)
    raise


def mmss(t: float) -> str:
    t = int(round(t))
    return f"{t // 60:02d}:{t % 60:02d}"


def load_manifest(path: Path) -> list[dict]:
    """兼容 scrape_channel.py --json 的多种返回形状。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        return raw
    for key in ("videos", "list", "items", "data"):
        v = raw.get(key)
        if isinstance(v, list):
            return v
    return []


def norm_item(it: dict) -> dict:
    bvid = it.get("bvid") or it.get("bv") or ""
    if isinstance(bvid, str):
        m = re.search(r"BV[0-9A-Za-z]{8,}", bvid)
        if m:
            bvid = m.group(0)
    return {
        "bvid": bvid,
        "title": (it.get("title") or it.get("name") or "").strip(),
        "pubdate": it.get("pubdate") or it.get("date") or it.get("pub_time") or "",
        "play": it.get("play") or it.get("views") or "",
        "duration": it.get("duration") or "",
    }


def write_outputs(out_dir: Path, item: dict, res: dict) -> dict:
    bvid = item["bvid"]
    cues = res.get("cues") or []
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "bvid": bvid,
        "title": item.get("title", ""),
        "pubdate": item.get("pubdate", ""),
        "play": item.get("play", ""),
        "duration": res.get("duration") or item.get("duration") or 0,
        "cue_count": len(cues),
        "source": res.get("source", ""),
        "ok": res.get("ok", bool(cues)),
    }
    (out_dir / f"{bvid}.cues.json").write_text(
        json.dumps({"meta": meta, "cues": cues}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    lines = [f"[{mmss(c.get('from', 0))}] {c.get('content', '')}" for c in cues]
    (out_dir / f"{bvid}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bvid", nargs="*", default=[])
    ap.add_argument("--manifest", type=Path)
    ap.add_argument("--out-dir", type=Path, default=Path("../10_sources/raw"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=4.0, help="基础间隔秒数")
    ap.add_argument("--jitter", type=float, default=3.0, help="随机抖动上限")
    ap.add_argument("--skip-existing", action="store_true", default=True)
    args = ap.parse_args()

    items: list[dict] = []
    if args.manifest:
        items = [norm_item(x) for x in load_manifest(args.manifest)]
    for b in args.bvid:
        items.append({"bvid": b, "title": "", "pubdate": "", "play": "", "duration": ""})

    items = [i for i in items if i["bvid"]]
    if not items:
        print("[FATAL] 没有可处理的 BV 号", file=sys.stderr)
        return 2
    if args.limit:
        items = items[: args.limit]

    out_dir = args.out_dir.resolve()
    stats = {"ok": 0, "empty": 0, "fail": 0, "skip": 0}

    for idx, item in enumerate(items, 1):
        bvid = item["bvid"]
        target = out_dir / f"{bvid}.cues.json"
        if args.skip_existing and target.exists():
            stats["skip"] += 1
            print(f"[{idx}/{len(items)}] SKIP {bvid} (已存在)")
            continue

        try:
            res = fetch_cues(bvid)
        except Exception as e:
            stats["fail"] += 1
            print(f"[{idx}/{len(items)}] FAIL {bvid} :: {type(e).__name__}: {e}")
            continue

        cues = res.get("cues") or []
        if not cues:
            stats["empty"] += 1
            print(f"[{idx}/{len(items)}] NOSUB {bvid} :: source={res.get('source')}")
            continue

        meta = write_outputs(out_dir, item, res)
        stats["ok"] += 1
        print(f"[{idx}/{len(items)}] OK   {bvid} cues={meta['cue_count']} "
              f"dur={meta['duration']} via={meta['source']}")

        if idx < len(items):
            time.sleep(args.sleep + random.uniform(0, args.jitter))

    print(f"\nDONE ok={stats['ok']} nosub={stats['empty']} fail={stats['fail']} skip={stats['skip']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
