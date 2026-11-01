#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s13_dump.py — 把字幕 cues 转成「带时间戳的可读文本」，便于人工/AI 阅读取证

用法：
  python s13_dump.py BV1xxx BV1yyy       # 输出到 50_logs/txt/<bvid>.txt
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SUBS = Path(r"C:/Users/Lenovo/WorkBuddy/kog/10_sources/creators_cache/subs")
OUT = Path(r"C:/Users/Lenovo/WorkBuddy/kog/50_logs/txt")
OUT.mkdir(parents=True, exist_ok=True)


def mmss(t: float) -> str:
    t = int(t)
    return f"{t // 60:02d}:{t % 60:02d}"


def main() -> int:
    for bv in sys.argv[1:]:
        p = SUBS / f"{bv}.json"
        if not p.exists():
            print(f"[skip] {bv} 无字幕")
            continue
        body = json.loads(p.read_text(encoding="utf-8")).get("body") or []
        lines, buf, start = [], "", 0.0
        for c in body:
            if not buf:
                start = c.get("from") or 0
            buf += (c.get("content") or "")
            # 每 ~80 字或遇到句号切一段
            if len(buf) >= 80 or buf.endswith(("。", "？", "！")):
                lines.append(f"[{mmss(start)}] {buf}")
                buf = ""
        if buf:
            lines.append(f"[{mmss(start)}] {buf}")
        (OUT / f"{bv}.txt").write_text("\n".join(lines), encoding="utf-8")
        print(f"{bv} -> {len(lines)} 段 {len(''.join(lines))} 字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
