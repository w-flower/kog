#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s1_discover.py — 按关键词找可用的教学视频（匿名搜索接口，实测 code=0 可用）

筛选逻辑写死在这里，不靠人肉判断：
  · 时长 8–45 分钟（<8 是切片讲不完决策链；>45 多是直播回放）
  · 发布日期 >= 赛季首日（默认 2026-09-23，S45）
  · 播放 >= 20000
  · 标题命中排除词直接砍：自走棋/模拟战/棋手/夺冠率/皮肤/活动/赛事/直播…
  · 标题命中教学词加分

用法：
  python s1_discover.py --kw "王者荣耀 中路 教学" --kw "王者荣耀 辅助 教学"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0")
CK = Path(r"C:/Users/Lenovo/.workbuddy/data/bilibili-video-summary/bilibili_cookies.txt")

EXCLUDE = ["自走棋", "模拟战", "棋手", "夺冠率", "吃鸡", "皮肤", "活动", "赛事",
           "KPL", "直播", "录播", "高光", "集锦", "剪辑", "抽奖", "开箱",
           "版本前瞻", "爆料", "瓜", "主播怎么", "八卦", "解说",
           "英雄联盟", "LOL", "端游", "云顶"]
BOOST = ["教学", "思路", "复盘", "整局", "意识", "细节", "对线", "运营",
         "上分", "节奏", "开局", "转线", "大局观"]
# 旧赛季标记：S38 及以前的教程一律不当素材
OLD_SEASON = re.compile(r"S(3[0-9]|4[0-4])(?![0-9])")
REQUIRED_TAG = "王者荣耀"


def cookie_header() -> str:
    if not CK.exists():
        return ""
    p = []
    for ln in CK.read_text(encoding="utf-8").splitlines():
        if ln and not ln.startswith("#"):
            f = ln.split("\t")
            if len(f) >= 7:
                p.append(f"{f[5]}={f[6]}")
    return "; ".join(p)


def clean(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t or "")


def dur_s(s: str) -> int:
    if not s:
        return 0
    parts = [int(x) for x in re.findall(r"\d+", s)]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return 0


def search(kw: str, page: int = 1) -> list[dict]:
    q = urllib.parse.urlencode({"search_type": "video", "keyword": kw, "page": page})
    req = urllib.request.Request(
        f"https://api.bilibili.com/x/web-interface/search/type?{q}",
        headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/",
                 "Cookie": cookie_header()})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("code") != 0:
        raise RuntimeError(f"search code={d.get('code')} {d.get('message')}")
    return ((d.get("data") or {}).get("result") or [])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kw", action="append", required=True)
    ap.add_argument("--page", type=int, default=1)
    ap.add_argument("--since", default="2026-09-23")
    ap.add_argument("--min-play", type=int, default=20000)
    ap.add_argument("--min-dur", type=int, default=480)
    ap.add_argument("--max-dur", type=int, default=2700)
    ap.add_argument("--out", type=Path, default=Path("../10_sources/candidates.json"))
    ap.add_argument("--sleep", type=float, default=5.0)
    args = ap.parse_args()

    since_ts = int(time.mktime(time.strptime(args.since, "%Y-%m-%d")))
    seen: dict[str, dict] = {}
    rejected: list[tuple[str, str]] = []

    for i, kw in enumerate(args.kw):
        try:
            res = search(kw, args.page)
        except Exception as e:
            print(f"[WARN] {kw} 搜索失败: {e}", file=sys.stderr)
            continue
        for x in res:
            bv = x.get("bvid") or ""
            title = clean(x.get("title"))
            if not bv or bv in seen:
                continue
            d = dur_s(x.get("duration") or "")
            play = int(x.get("play") or 0)
            pub = int(x.get("pubdate") or 0)

            why = ""
            tag = x.get("tag") or ""
            if REQUIRED_TAG not in tag and REQUIRED_TAG not in title:
                why = "非王者分区"
            elif d < args.min_dur:
                why = f"太短{d}s"
            elif d > args.max_dur:
                why = f"太长{d}s"
            elif pub < since_ts:
                why = f"早于{args.since}"
            elif play < args.min_play:
                why = f"播放{play}"
            elif OLD_SEASON.search(title):
                why = "旧赛季:" + OLD_SEASON.search(title).group(0)
            else:
                hit = [w for w in EXCLUDE if w in title]
                if hit:
                    why = "排除词:" + hit[0]
            if why:
                rejected.append((f"{bv} {title[:28]}", why))
                continue

            score = sum(1 for w in BOOST if w in title) * 10 + min(play // 10000, 30)
            seen[bv] = {"bvid": bv, "title": title, "play": play, "pubdate": pub,
                        "duration_s": d, "up": x.get("author", ""),
                        "score": score, "kw": kw, "tag": tag[:60]}
        if i < len(args.kw) - 1:
            time.sleep(args.sleep)

    rows = sorted(seen.values(), key=lambda r: -r["score"])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    for r in rows:
        print(f"{r['score']:>3} {r['bvid']} {r['duration_s']//60:>2}min "
              f"{r['play']:>7} {r['title'][:46]}")
    print(f"\n通过 {len(rows)} 条 / 丢弃 {len(rejected)} 条 -> {args.out}")
    if not rows:
        for t, w in rejected[:12]:
            print(f"  x {t} :: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
