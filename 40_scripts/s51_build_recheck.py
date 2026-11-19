# -*- coding: utf-8 -*-
"""s51_build_recheck.py — 重采素材装配英雄卡批次。

读 recheck_ok.json，剔除"主体错位 / 万象棋 / 太浅"的噪声，按分路分 3 批。
输出 batch_R1~R3.md（复用 s42 的 SPEC 与样例卡）。
"""
import json
import re
from pathlib import Path

BASE = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
SUB = BASE / "10_sources/creators_cache/subs"
UP = BASE / "50_logs/upload"

# 预检 OK 但内容不对口的，人工剔除
EXCLUDE = {
    "BV1haCyBHEea",  # 王者万象棋（棋类玩法）
    "BV1aT436HEGp",  # 王者万象棋/吃鸡
    "BV1KG4y1K7Gq",  # 主体是程咬金
    "BV1yiPezhEBd",  # 主体是元歌
    "BV1FPWg69EL7",  # 主体是李信
    "BV1BL1dYgESX",  # 主体是花木兰
    "BV15X1NBHEsD",  # 主体是花木兰
    "BV1VDW76vEab",  # "坠机教学"，疑似搞笑集锦
    "BV1ykht6KE9E",  # 新手向全英雄基础介绍，太浅
}

BATCHES = {
    "R1": ["亚瑟", "李信", "猪八戒"],
    "R2": ["孙膑", "桑启", "武则天", "甄姬"],
    "R3": ["芈月", "元歌", "司马懿"],
}

# 复用 s42 的 SPEC / EXAMPLE_NOTE
src = (BASE / "40_scripts/s42_build_upload.py").read_text(encoding="utf-8")
i = src.index('SPEC = """'); j = src.index('"""', i + 10) + 3
k = src.index('EXAMPLE_NOTE = """'); l = src.index('"""', k + 20) + 3
ns = {}
exec(src[i:j], ns); exec(src[k:l], ns)
SPEC, EX = ns["SPEC"].replace("2026-11-18", "2026-11-19"), ns["EXAMPLE_NOTE"]


def mmss(s):
    try:
        s = int(float(s))
    except Exception:
        return "00:00"
    return f"{s // 60:02d}:{s % 60:02d}"


def dump(bv):
    p = SUB / f"{bv}.json"
    if not p.exists():
        return ""
    d = json.loads(p.read_text(encoding="utf-8"))
    body = d.get("body") or []
    return "\n".join(f"[{mmss(c.get('from', 0))}] {c.get('content', '')}" for c in body)


ok = json.loads((UP / "recheck_ok.json").read_text(encoding="utf-8"))
example = (BASE / "20_kb/A_英雄教学/老夫子.md").read_text(encoding="utf-8")

for tag, heroes in BATCHES.items():
    parts = [SPEC.format(tag=tag)]
    used = 0
    for h in heroes:
        items = [x for x in ok.get(h, []) if x["bvid"] not in EXCLUDE]
        if not items:
            print(f"  [WARN] {h} 无有效素材，跳过")
            continue
        for x in items:
            txt = dump(x["bvid"])
            if not txt:
                continue
            parts.append(f"\n### 素材：{h}（{x['bvid']}）— {x['up']}《{x['title'][:40]}》\n\n```text\n{txt}\n```\n")
            used += 1
    parts.append(EX.format(example=example))
    out = UP / f"batch_{tag}.md"
    out.write_text("".join(parts), encoding="utf-8")
    print(f"batch_{tag}.md  {out.stat().st_size} B  heroes={heroes}  素材条数={used}")
