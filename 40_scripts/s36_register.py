#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s36_register.py — 把梦辰溪登记进信源库：creators_scored.json + 视频索引页。

注意：B 站对其视频返回「幽灵字幕」（无 CC、无 AI 字幕，旧接口给的是与视频无关的
错配内容：iPhone 评测 / 蔡徐坤 / LCK 解说），18/18 均无法提炼。故只做「信源登记 +
真实视频索引 + 候选链接」，不编造任何卡片内容。详见信源名单第十一节。
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "10_sources" / "creators_cache"
SCORED = ROOT / "10_sources" / "creators_scored.json"
MANIFEST = CACHE / "mengchenxi_all.json"
MID = 1078678010
NAME = "梦辰溪_专注王者教学"
D_OUT = ROOT / "20_kb" / "D_对局内"

sys.path.insert(0, str(ROOT / "40_scripts"))
import bili_api as B  # noqa: E402

data = json.loads(MANIFEST.read_text(encoding="utf-8"))

# ── 1) creators_scored.json ───────────────────────────────────────
try:
    card = B.cards(MID)
except Exception:
    card = {}
scored = json.loads(SCORED.read_text(encoding="utf-8"))
vids = [{"bvid": d["bvid"], "title": d["title"], "play": d.get("play", 0),
         "dur": d.get("dur", 0), "author": NAME, "mid": MID,
         "hero_tag": d.get("hero", "general")}
        for d in data]
avg_min = round(sum(d.get("dur", 0) for d in data) / len(data) / 60, 1) if data else 0
entry = {
    "author": NAME, "mid": MID, "n": len(data), "n_s45": None,
    "avg_min": avg_min, "series_ratio": None, "series_name": None,
    "teach_r": None, "fans": card.get("fans"), "official": card.get("official"),
    "sign": card.get("sign"), "src": "focus 2026-11-13 全量消化（字幕不可用）",
    "note": "18/18 视频无可用字幕（B站幽灵字幕）：CC/AI 均无，旧接口返回错配内容。"
            "无法提炼，仅登记信源与真实视频索引。",
    "vids": vids,
}
# 去重（按 mid）
scored = [x for x in scored if x.get("mid") != MID]
scored.append(entry)
SCORED.write_text(json.dumps(scored, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"creators_scored.json 已追加 {NAME}（{len(data)} 视频）")

# ── 2) 视频索引页 ─────────────────────────────────────────────────
D_OUT.mkdir(parents=True, exist_ok=True)
hero_vids = [d for d in data if d.get("hero") not in ("general", "MULTI")]
multi_vids = [d for d in data if d.get("hero") == "MULTI"]
general_vids = [d for d in data if d.get("hero") == "general"]


def fmt(d: dict) -> str:
    m = d.get("dur", 0) // 60
    s = d.get("dur", 0) % 60
    return (f"- [{d['title']}](https://www.bilibili.com/video/{d['bvid']}) "
            f"· {m}:{s:02d} · 播放 {d.get('play',0):,}")


lines = ["# 梦辰溪_专注王者教学 · 视频索引（未转写）\n",
         "> mid 1078678010 ｜ 全部 18 条投稿，按主题归类。\n",
         "> **重要**：B 站对本 UP 的视频**不返回任何可用字幕**（无 CC、无 AI，旧接口给的是"
         "与视频错配的幽灵内容）。因此本页仅作**真实视频索引**，正文内容暂未提炼进卡片。\n",
         "> 需要真正消化内容 → 须对视频做音频转写（whisper 等），详见信源名单第十一节。\n"]

lines.append("\n## 一、英雄专项（标题即主题，可作候选素材）\n")
for d in sorted(hero_vids, key=lambda x: x["title"]):
    tags = " / ".join(d.get("multi") or [d["hero"]])
    lines.append(fmt(d) + f"  —— 命中：{tags}")
for d in multi_vids:
    tags = " / ".join(d.get("multi") or [])
    lines.append(fmt(d) + f"  —— 多英雄：{tags}")

lines.append("\n## 二、BP / 克制 / 阵容理论（他的核心内容方向）\n")
for d in general_vids:
    lines.append(fmt(d))

(D_OUT / "梦辰溪视频索引.md").write_text("\n".join(lines), encoding="utf-8")
print(f"索引页已写：{D_OUT / '梦辰溪视频索引.md'}（{len(data)} 条）")
