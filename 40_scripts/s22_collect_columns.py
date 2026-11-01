#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s22_collect_columns.py — 按英雄搜 B 站专栏 → 抓全文 → 落候选清单

为什么要有这一步：官方关系页每边只给 2 个例子、77% 跨路，同路对位靠它填不满。
专栏是唯一能一次给出几十条有方向关系的来源（一篇能覆盖整条分路的克制表）。

两段开销：
  搜索   每个英雄一条 query，8 秒节流 → 24 个英雄约 4 分钟
  取全文 只取通过筛选的前 N 篇，每篇 8 秒 → 60 篇约 8 分钟

抓到的正文落 10_sources/bili_cache/article/（该目录 gitignore，正文有版权不进仓库），
重跑直接命中缓存不重抓。可用 --force 强制刷新。

用法：
  python s22_collect_columns.py --lane mid
  python s22_collect_columns.py --lane mid --fetch 80 --force
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bili_api as B
import names as N

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "30_index" / "duel"

# 标题/摘要里必须出现的关系词——没有这些词的文章基本是「英雄攻略」，不是对位表
GOOD_WORDS = ("克制", "压制", "对位", "对线", "五五开", "均势", "打不过",
              "好打", "难打", "天敌", "counter")
# 分路限定词，用来给通用 query 的命中加权
LANE_WORDS = {"mid": ("中单", "中路", "法师", "法核"),
              "solo": ("对抗路", "边路", "上单"),
              "jungle": ("打野",),
              "adc": ("射手", "发育路"),
              "roam": ("辅助", "游走")}

# 通用 query：不针对单个英雄，专捞「整条分路的克制表」
GENERIC = {"mid": ["中路 克制关系", "法师 对位 克制", "中单 对线 打不过",
                   "中路 英雄 五五开", "法师 天敌 盘点"],
           "solo": ["对抗路 克制关系", "边路 对位 克制", "上单 天敌"],
           "jungle": ["打野 克制关系"],
           "adc": ["射手 对位 克制"],
           "roam": ["辅助 克制关系"]}


# 查询模板。「克星」这一组是后补的：这类文章标题常写成「XX 的三大克星」，
# 正文用「克星一：YYY」分节，正好是 B3 分支能吃下的形状，比泛搜精准得多。
QMODES = {
    "base": [("{h} 克制", True)],
    "more": [("{h} 克星", True), ("克制{h}的英雄", True)],
}


def queries(lane: str, heroes: list[str], mode: str = "base") -> list[tuple[str, str]]:
    out = []
    for tmpl, per_hero in QMODES.get(mode, QMODES["base"]):
        out += [("" if not per_hero else h, tmpl.format(h=h)) for h in heroes]
    if mode == "base":
        out += [("", q) for q in GENERIC.get(lane, [])]
    return out


def score(rec: dict, lane: str, hit: list[str]) -> int:
    """排序分：命中英雄数最重要，其次关系词与分路词，播放/点赞只作微调。

    为什么不按播放量排：几万播放的英雄攻略遍地都是，能给关系表的往往是
    几百播放的专项整理帖。播放量只能当加权项，不能当主序。
    """
    s = len(hit) * 10
    blob = rec["title"] + rec["desc"]
    if any(w in blob for w in GOOD_WORDS):
        s += 6
    if any(w in blob for w in LANE_WORDS.get(lane, ())):
        s += 4
    s += min(rec["like"] // 50, 5)
    s += min(rec["view"] // 5000, 5)
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="mid")
    ap.add_argument("--fetch", type=int, default=60, help="最多抓多少篇全文")
    ap.add_argument("--pages", type=int, default=1, help="每个 query 翻几页")
    ap.add_argument("--hero", action="append", help="只跑指定英雄（调试用）")
    ap.add_argument("--force", action="store_true", help="忽略缓存重抓")
    ap.add_argument("--mode", default="base", choices=sorted(QMODES),
                    help="base=每英雄搜「克制」；more=搜「克星」「克制X的英雄」")
    ap.add_argument("--no-merge", action="store_true",
                    help="不与已有 columns.json 合并（默认合并，避免上一轮结果被覆盖）")
    args = ap.parse_args()

    nm = N.load()
    heroes = args.hero or nm.by_lane(args.lane, primary_only=False)
    pool = queries(args.lane, heroes, args.mode)
    print(f"[1/3] 搜专栏：{args.lane} · {len(heroes)} 个英雄 · "
          f"{len(pool)} 条 query（mode={args.mode}）")

    seen: dict[str, dict] = {}
    fails = 0
    for i, (hero, q) in enumerate(pool, 1):
        for page in range(1, args.pages + 1):
            try:
                hits = B.search_articles(q, page=page)
            except RuntimeError as exc:
                fails += 1
                print(f"  [{i}/{len(pool)}] {q!r} 失败：{exc}")
                break
            new = 0
            for r in hits:
                hit = [h for h in nm.find_all(r["title"] + " " + r["desc"])
                       if nm.in_lane(h, args.lane)]
                if not hit:
                    continue
                if not any(w in r["title"] + r["desc"] for w in GOOD_WORDS):
                    continue
                rec = seen.get(r["cv"])
                if rec:
                    rec["hit"] = sorted(set(rec["hit"]) | set(hit))
                    continue
                r["hit"] = sorted(hit)
                r["q"] = q
                rec = r
                seen[r["cv"]] = rec
                new += 1
            print(f"  [{i}/{len(pool)}] {q!r} → {len(hits)} 条，收 {new}")
            if not hits:
                break

    if not seen:
        print("[FATAL] 一条候选都没有，检查网络或 query", file=sys.stderr)
        return 1

    ranked = sorted(seen.values(), key=lambda r: -score(r, args.lane, r["hit"]))
    for r in ranked:
        r["score"] = score(r, args.lane, r["hit"])
    print(f"\n[2/3] 候选 {len(ranked)} 篇（搜索失败 {fails} 次），"
          f"抓前 {min(args.fetch, len(ranked))} 篇全文")

    picked, got, skipped = [], 0, 0
    for i, r in enumerate(ranked[:args.fetch], 1):
        try:
            art = B.cached("article", r["cv"],
                           lambda cv=r["cv"]: B.article_view(cv), force=args.force)
        except RuntimeError as exc:
            skipped += 1
            print(f"  [{i}] cv{r['cv']} 取不到：{exc}")
            time.sleep(3)
            continue
        words = len(art.get("text") or "")
        if words < 400:                       # 太短的多半是图集或公告
            skipped += 1
            continue
        r["words"] = words
        r["art_title"] = art.get("title") or ""
        r["art_author"] = art.get("author") or ""
        picked.append(r)
        got += 1
        print(f"  [{i}] cv{r['cv']} {words} 字  {r['title'][:34]}")

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "columns.json"

    # 与已有结果合并：分模式跑的时候，后一轮不能把前一轮的文档冲掉。
    # 同一 cv 取有 words 的那条（说明真的抓到正文了）。
    merged: dict[str, dict] = {}
    if not args.no_merge and out.exists():
        try:
            for d in json.loads(out.read_text(encoding="utf-8")).get("docs", []):
                merged[d["cv"]] = d
        except Exception:
            pass
    for d in picked:
        old = merged.get(d["cv"])
        if old and old.get("words", 0) >= d.get("words", 0):
            continue
        merged[d["cv"]] = d
    docs = sorted(merged.values(), key=lambda x: -x.get("score", 0))

    out.write_text(json.dumps({
        "lane": args.lane,
        "queries": len(pool),
        "mode": args.mode,
        "search_fails": fails,
        "candidates": len(ranked),
        "fetched": got,
        "skipped": skipped,
        "docs": docs,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    total_words = sum(d.get("words", 0) for d in docs)
    print(f"\n[3/3] {out}\n  本轮 {got} 篇 · 库内共 {len(docs)} 篇 · "
          f"{total_words} 字 · 跳过 {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
