#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s19_duel.py — 从已有字幕里挖「谁打谁」的实测片段（B 类专用）

为什么要它：B 类卡现在有 129 张，但「我该怎么打」全是空的。
专门去 B 站采对位视频成本高，先看看 399 份已有字幕里是不是已经讲过了。

做法（刻意保守，宁可漏不可错）：
  1. 把字幕按 3 句滑窗拼成「话块」，避免一句话被 ASR 切断
  2. 一句话里必须同时出现：① 触发词（打/对线/遇到/克制/怕/难打…）② 至少一个英雄名
  3. 英雄名支持别名（阿离→公孙离、老虎→裴擒虎…），但单字名（猪、曜）不参与，误伤太多
  4. 只输出候选，**不自动写卡**——方向（谁打谁）靠人读，脚本不猜

用法：
  python s19_duel.py                 # 全量扫，写 50_logs/duel_scan.md + 30_index/duel_hits.json
  python s19_duel.py --hero 铠,公孙离  # 只看这几个英雄
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
SUBS = ROOT / "10_sources" / "creators_cache" / "subs"
IDX = ROOT / "30_index"
LOGS = ROOT / "50_logs"

# 对位语义词：没有这些词，就只是"在讲那局游戏"，不是"在讲这两个英雄的关系"
DUEL_WORDS = [
    "难打", "好打", "打不过", "打得过", "随便打", "不好打", "挺好打", "很难打",
    "克制", "压制", "反制", "被克", "怕", "优势", "劣势", "五五开", "六四开",
    "七三开", "八二开", "换血", "对线", "单挑", "打他", "打她",
]
# 明确的对位句式：A 直接接动词再接 B（间隔不能大，否则就是把两句话拼一起了）
DUEL_PAT = re.compile(
    r"(?P<a>[\u4e00-\u9fa5]{2,5})"
    r"(打|对线|遇到|对上|面对|克|压|反制|怕|不怕)"
    r"(?P<b>[\u4e00-\u9fa5]{2,5})"
)
NEG = re.compile(r"(不|没|别)")

# 别名 → 官方名。单字名刻意不收（「猪」=猪八戒会被野猪/猪肉误伤）
ALIAS = {
    "阿离": "公孙离", "老虎": "裴擒虎", "猴子": "孙悟空", "鸟人": "云中君",
    "鱼": "庄周", "大鱼": "庄周", "奶妈": "蔡文姬", "小明": "明世隐",
    "东皇": "东皇太一", "上官": "上官婉儿", "婉儿": "上官婉儿",
    "干将": "干将莫邪", "莫邪": "干将莫邪", "鲁班": "鲁班七号",
    "香香": "孙尚香", "大小姐": "孙尚香", "马可": "马可波罗",
    "玄策": "百里玄策", "守约": "百里守约", "百里": "百里守约",
    "火舞": "不知火舞", "娜可": "娜可露露", "露露": "娜可露露",
    "宫本": "宫本武藏", "橘子": "橘右京", "曜曜": "东方曜",
    "太乙": "太乙真人", "鬼谷": "鬼谷子", "鲁班大师": "鲁班大师",
    "元芳": "李元芳", "贵妃": "杨玉环", "嬴政": "嬴政",
    "阿古": "阿古朵", "小满": "姬小满", "海月": "海月",
}
# 容易被当成英雄名的普通词，命中就丢
STOP = {"打野", "对抗", "辅助", "中路", "射手", "上路", "下路", "边路", "发育",
        "团战", "兵线", "经济", "装备", "阵容", "节奏", "视野", "大龙", "小龙"}


def load_names() -> tuple[set[str], dict[str, str]]:
    """返回（官方英雄名集合, 别名→官方名）。"""
    p = IDX / "roster.json"
    names: set[str] = set()
    if p.exists():
        names = {h["name"] for h in json.loads(p.read_text(encoding="utf-8"))["heroes"]}
    if not names:                     # 兜底用 lexicon
        lex = (IDX / "lexicon.yaml").read_text(encoding="utf-8")
        names = {ln.strip("- ").strip() for ln in lex.splitlines()
                 if ln.startswith("  - ")}
    names = {n for n in names if len(n) >= 2}
    alias = {k: v for k, v in ALIAS.items() if len(k) >= 2 and v in names}
    return names, alias


def cues_of(path: Path) -> list[dict]:
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    body = d.get("body") or []
    return [{"t": float(c.get("from") or 0), "s": (c.get("content") or "").strip()}
            for c in body if (c.get("content") or "").strip()]


def fmt_t(sec: float) -> str:
    return f"{int(sec) // 60:02d}:{int(sec) % 60:02d}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", default="")
    ap.add_argument("--per-hero", type=int, default=14)
    args = ap.parse_args()
    only = {x.strip() for x in args.hero.split(",") if x.strip()}

    names, alias = load_names()
    if not names:
        raise SystemExit("拿不到英雄名，先跑 s18_official.py --roster-only")

    # 长名优先匹配，避免「鲁班七号」被「鲁班」抢先
    keys = sorted(set(names) | set(alias), key=len, reverse=True)
    NAME_RE = re.compile("|".join(re.escape(k) for k in keys))

    def canon(tok: str) -> str:
        n = alias.get(tok, tok)
        return n if n in names else ""

    hits: dict[str, list[dict]] = defaultdict(list)
    files = sorted(SUBS.glob("*.json"))
    seen_sentence: set[str] = set()
    n_win = 0

    for f in files:
        cues = cues_of(f)
        if not cues:
            continue
        bv = f.stem
        # 2 句滑窗：ASR 经常把一句话切碎，但不能太长，否则把两段无关的话拼一起
        for i in range(len(cues)):
            seg = cues[i:i + 3]
            text = "".join(c["s"] for c in seg)
            if len(text) < 9 or len(text) > 110:
                continue
            if not any(w in text for w in DUEL_WORDS):
                continue
            toks = [canon(m.group(0)) for m in NAME_RE.finditer(text)]
            toks = [t for t in toks if t and t not in STOP]
            if not toks:
                continue
            uniq = []
            for t in toks:
                if t not in uniq:
                    uniq.append(t)
            # 必须出现两个不同英雄才有"对位"可言；单英雄的句子多半是局势播报
            if len(uniq) < 2:
                continue
            # 句式命中：A + 对位动词 + B，且 A/B 都是真英雄名
            strong = False
            for m in DUEL_PAT.finditer(text):
                x, y = canon(m.group("a")), canon(m.group("b"))
                if x and y and x != y:
                    strong = True
                    break
            key = re.sub(r"[^\u4e00-\u9fa5]", "", text)[:40]
            if key in seen_sentence:      # 85 份字幕有完全重复的，别重复收
                continue
            seen_sentence.add(key)
            n_win += 1
            for h in uniq:
                if only and h not in only:
                    continue
                hits[h].append({
                    "bv": bv, "t": round(seg[0]["t"], 1), "ts": fmt_t(seg[0]["t"]),
                    "text": text, "who": uniq, "strong": strong,
                })

    for h in hits:
        # 强句式优先，同视频最多留 3 条，避免一个视频刷屏
        lst = sorted(hits[h], key=lambda x: (not x["strong"], x["bv"], x["t"]))
        out, per_bv = [], defaultdict(int)
        for x in lst:
            if per_bv[x["bv"]] >= 3:
                continue
            per_bv[x["bv"]] += 1
            out.append(x)
            if len(out) >= args.per_hero:
                break
        hits[h] = out

    (IDX / "duel_hits.json").write_text(
        json.dumps(hits, ensure_ascii=False, indent=1), encoding="utf-8")

    L = ["# 对位证据扫描（本地 399 份字幕）", "",
         f"扫描窗口 {n_win} 句 → 命中 {len(hits)} 个英雄有对位片段。",
         "**这是候选，不是结论**：方向（谁打谁）得人读，脚本不猜。", ""]
    for h in sorted(hits, key=lambda x: -len(hits[x])):
        L.append(f"## {h}（{len(hits[h])}）")
        L.append("")
        for x in hits[h]:
            others = "、".join(t for t in x["who"] if t != h) or "—"
            L.append(f"- `{x['bv']} @ {x['ts']}` **{others}** — {x['text'][:70]}")
        L.append("")
    (LOGS / "duel_scan.md").write_text("\n".join(L), encoding="utf-8")

    print(f"字幕 {len(files)} 份 / 窗口 {n_win} 句 → {len(hits)} 英雄，"
          f"{sum(len(v) for v in hits.values())} 条候选")
    top = sorted(hits, key=lambda x: -len(hits[x]))[:12]
    print("  命中最多：" + "、".join(f"{h}({len(hits[h])})" for h in top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
