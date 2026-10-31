#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s9_pack.py — 把字幕切成「主题 × 时间戳」的证据包，供人写条目时引用

每主题每视频最多 2 段，每段 5 个 cue，避免堆砌。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
H = ROOT / "10_sources/heroes"
SUBS = ROOT / "10_sources/creators_cache/subs"

TOPICS = {
    "铭文": ["铭文", "符文", "红色带", "蓝色带", "绿色带"],
    "出装": ["出装", "装备", "第一件", "核心装", "出装顺序", "鞋子"],
    "连招": ["连招", "接技", "接一", "接二", "一套", "穿插"],
    "技能机制": ["被动", "一技能", "二技能", "三技能", "大招", "机制", "前摇", "后摇"],
    "开局": ["开局", "一级", "出门", "抢线", "抢二"],
    "对线": ["对线", "换血", "压线", "塔下"],
    "团战": ["团战", "开团", "切入", "先手", "后排"],
    "节奏运营": ["节奏", "运营", "兵线", "转线", "支援", "游走"],
}
MAX_WIN, WIN_LEN = 4, 7


def mmss(sec: float) -> str:
    s = int(sec or 0)
    return f"{s // 60:02d}:{s % 60:02d}"


def cues_of(bv: str) -> list[dict]:
    f = SUBS / f"{bv}.json"
    if not f.exists():
        return []
    return (json.loads(f.read_text(encoding="utf-8")).get("body") or [])


def pack(hero: str) -> str:
    vids = json.loads((H / hero / "videos.json").read_text(encoding="utf-8"))
    out = [f"# {hero} · 证据包\n"]
    used = 0
    bad = (f"对位{hero}", f"打{hero}", f"克制{hero}", f"怎么打{hero}")
    for v in vids:
        if any(b in v["title"] for b in bad):      # 别人讲「怎么打他」，不是他的教学
            continue
        cues = cues_of(v["bvid"])
        if len(cues) < 40:
            continue
        used += 1
        out.append(f"\n## [{v['up']}] {v['title']}\n"
                   f"`{v['bvid']}` · {v['dur']//60} 分钟 · "
                   f"{__import__('time').strftime('%Y-%m-%d', __import__('time').localtime(v['pub']))}\n")
        for topic, kws in TOPICS.items():
            hits, last = [], -99
            for i, c in enumerate(cues):
                txt = c.get("content") or ""
                if any(k in txt for k in kws) and i - last > 8:
                    seg = "".join((x.get("content") or "") for x in cues[i:i + WIN_LEN])
                    if len(seg) < 25:
                        continue
                    hits.append(f"- `{mmss(c.get('from'))}` {seg}")
                    last = i
                    if len(hits) >= MAX_WIN:
                        break
            if hits:
                out.append(f"**{topic}**\n" + "\n".join(hits))
        if used >= 9:
            break
    return "\n".join(out)


def main() -> int:
    for d in sorted(H.iterdir()):
        if not (d / "videos.json").exists():
            continue
        txt = pack(d.name)
        (d / "pack.md").write_text(txt, encoding="utf-8")
        print(f"{d.name}: {len(txt)} 字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
