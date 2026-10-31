#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s10_outfit.py — 从视频简介里挖「出装 / 铭文」证据

口播里的铭文名 ASR 普遍转错（梦魇→明浩），但 UP 大多在简介里直接写。
这里只认简介原文里能对上的英雄/装备词，不做任何推断。
"""
from __future__ import annotations

import html
import json
import re
import time
from pathlib import Path

import bili_api as B

H = Path(r"C:/Users/Lenovo/WorkBuddy/kog/10_sources/heroes")
HEROES = ["不知火舞", "小乔", "大乔", "夏洛特", "盾山", "鲁班大师", "苏烈", "女娲"]

RUNES = ["梦魇", "圣人", "怜悯", "贪婪", "心眼", "献祭", "狩猎", "隐匿", "夺萃",
         "鹰眼", "异变", "传承", "虚空", "宿命", "调和", "祸源", "无双", "红月",
         "敬畏", "秘法", "阳炎", "逐月", "奇袭", "回声", "冥想", "繁荣"]
ITEMS = ["秘法之靴", "冷静之靴", "抵抗之靴", "疾步之靴", "回响之杖", "痛苦面具",
         "博学者之怒", "虚无法杖", "贤者之书", "日暮之流", "冰霜法杖", "辉月",
         "圣杯", "巫术法杖", "噬神之书", "破晓", "反伤刺甲", "极寒风暴", "冰痕之握",
         "暗影战斧", "无尽战刃", "宗师之力", "破军", "影刃", "闪电匕首", "极影",
         "救赎之翼", "奔狼纹章", "巨人之握", "不死鸟之眼", "霸者重装", "血魔之怒",
         "魔女斗篷", "碎星锤", "冰霜冲击", "痛苦之击", "末世", "熔炼之心",
         "净化之刃", "星泉", "巡守利斧", "学识宝石", "近卫荣耀", "不祥征兆",
         "魔女斗篷", "逐日之弓", "破晓"]

OUT_TXT = "outfit.md"


def scan(text: str) -> tuple[list[str], list[str], list[str]]:
    r = [x for x in RUNES if x in text]
    i = [x for x in ITEMS if x in text]
    lines = []
    for ln in re.split(r"[\n\r]", text):
        if any(k in ln for k in ("铭文", "出装", "六件", "装备")):
            lines.append(ln.strip()[:220])
    return r, i, lines


def main() -> int:
    for hero in HEROES:
        d = H / hero
        if not d.exists():
            continue
        rows = []
        for kw in (f"{hero} 出装 铭文", f"{hero} 教学"):
            for pg in (1, 2):
                try:
                    res = B.search(kw, pg, "")
                except Exception:
                    continue
                for x in res:
                    desc = re.sub(r"<[^>]+>", "", html.unescape(x.get("description") or ""))
                    title = re.sub(r"<[^>]+>", "", x.get("title") or "")
                    if hero not in (title + desc):
                        continue
                    r, i, lines = scan(desc)
                    if not (r or i or lines):
                        continue
                    rows.append({"bvid": x.get("bvid"), "title": title[:60],
                                 "up": x.get("author") or "", "runes": r, "items": i,
                                 "lines": lines[:3],
                                 "pub": int(x.get("pubdate") or 0)})
                time.sleep(1.0)
        # 去重并按「证据量」排序
        seen, uniq = set(), []
        for r in sorted(rows, key=lambda r: -(len(r["runes"]) + len(r["items"]) + len(r["lines"]))):
            if r["bvid"] in seen:
                continue
            seen.add(r["bvid"])
            uniq.append(r)

        out = [f"# {hero} · 出装铭文证据（来自视频简介原文）\n"]
        for r in uniq[:6]:
            t = time.strftime("%Y-%m", time.localtime(r["pub"]))
            out.append(f"\n## [{r['up']}] {r['title']}\n`{r['bvid']}` · {t}\n"
                       f"- 铭文命中：{'、'.join(r['runes']) or '—'}\n"
                       f"- 装备命中：{'、'.join(r['items']) or '—'}")
            for ln in r["lines"]:
                out.append(f"- 原文：{ln}")
        (d / OUT_TXT).write_text("\n".join(out), encoding="utf-8")
        print(f"{hero}: {len(uniq)} 条有简介证据")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
