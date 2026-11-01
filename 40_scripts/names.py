#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""names.py — 英雄名的唯一出口（别名归一 / 长名优先匹配 / 标题取对手）

为什么要有这个文件：
  s19 / s21 / s22 / s23 / s24 各自维护一份别名表，已经漂了：
    · s19 写 "曜曜" → "东方曜"，但官方名录里叫「曜」，这条永远匹配不上
    · 字幕里出现「云樱」，名录里是「云缨」，按原始字符串 join 会漏配
  所有"这个名字是不是英雄"的判断都走这里，别再在脚本里本地加 ALIAS。

用法：
    import names
    N = names.load()
    N.canon("火舞")        -> "不知火舞"
    N.find_all("火舞打小乔")  -> ["不知火舞", "小乔"]
    N.opponent_of("对戈娅：全时期被压制") -> "戈娅"
    names.by_lane("mid")   -> ["上官婉儿", ...]
"""
from __future__ import annotations

import functools
import json
import re
from pathlib import Path

IDX = Path(r"C:/Users/Lenovo/WorkBuddy/kog/30_index")

# 口语 / 错别字 / 简称 → 官方名。
# 目标名不在官方名录里的会被 _prune() 剔掉，所以这里可以放心写。
ALIAS: dict[str, str] = {
    # ── 中路 ──
    "火舞": "不知火舞", "上官": "上官婉儿", "婉儿": "上官婉儿",
    "干将": "干将莫邪", "莫邪": "干将莫邪",
    "昭君": "王昭君", "则天": "武则天", "米莱": "米莱狄",
    "高渐": "高渐离", "姜牙": "姜子牙", "安琪": "安琪拉",
    # ── 射辅 ──
    "阿离": "公孙离", "香香": "孙尚香", "大小姐": "孙尚香",
    "马可": "马可波罗", "守约": "百里守约", "百里": "百里守约",
    "玄策": "百里玄策", "元芳": "李元芳", "鲁班": "鲁班七号",
    "卤蛋": "鲁班七号", "奶妈": "蔡文姬", "牛头": "牛魔",
    "小明": "明世隐", "鬼谷": "鬼谷子", "太乙": "太乙真人",
    "贵妃": "杨玉环",
    # ── 对抗 / 打野 ──
    "凯": "铠", "老虎": "裴擒虎", "猴子": "孙悟空", "鸟人": "云中君",
    "大鱼": "庄周", "东皇": "东皇太一", "宫本": "宫本武藏",
    "橘子": "橘右京", "云樱": "云缨", "曜曜": "曜",
    "娜可": "娜可露露", "露露": "娜可露露", "阿古": "阿古朵",
    "小满": "姬小满", "钟魁": "钟馗",
}

# 这些词长得像英雄名但不是，命中就丢（判对位时用来降噪）
STOP = {
    "打野", "对抗", "辅助", "中路", "射手", "上路", "下路", "边路", "发育",
    "团战", "兵线", "经济", "装备", "阵容", "节奏", "视野", "大龙", "小龙",
    "中单", "上单", "法师", "坦克", "刺客", "战士", "软辅", "硬辅",
}


def _prune(alias: dict[str, str], names: set[str]) -> dict[str, str]:
    """只留「目标名确实是官方英雄」的条目，并且别名本身不能等于某个官方名。"""
    out = {}
    for k, v in alias.items():
        if v in names and k not in names:
            out[k] = v
    return out


class Names:
    def __init__(self, roster: list[dict]):
        self.roster = roster
        self.all_names = {h["name"] for h in roster}
        self.by_name = {h["name"]: h for h in roster}
        self.alias = _prune(ALIAS, self.all_names)
        # 长名优先：鲁班七号 要先于 鲁班 命中；别名和真名一起进 alternation
        keys = sorted(set(self.all_names) | set(self.alias), key=len, reverse=True)
        self._re = re.compile("|".join(re.escape(k) for k in keys)) if keys else None

    # ── 归一 ──
    def canon(self, tok: str) -> str:
        n = self.alias.get(tok, tok)
        return n if n in self.all_names else ""

    def is_hero(self, tok: str) -> bool:
        return bool(self.canon(tok))

    # ── 抽取 ──
    def find_all(self, text: str, drop_stop: bool = True) -> list[str]:
        """按出现顺序返回去重后的官方名。"""
        if not self._re or not text:
            return []
        out: list[str] = []
        for m in self._re.finditer(text):
            raw = m.group(0)
            n = self.canon(raw)
            if not n:
                continue
            if drop_stop and raw in STOP:
                continue
            if n not in out:
                out.append(n)
        return out

    def by_lane(self, lane: str, primary_only: bool = True) -> list[str]:
        """primary_only=True 用 main_lane（做过矩阵用），False 用 lanes（做过筛选用）。"""
        key = "main_lane" if primary_only else "lanes"
        out = []
        for h in self.roster:
            v = h.get(key)
            if (v == lane) if primary_only else (lane in (v or [])):
                out.append(h["name"])
        return out

    def lane_of(self, name: str) -> str:
        h = self.by_name.get(name)
        return (h or {}).get("main_lane", "")


@functools.lru_cache(maxsize=1)
def load() -> Names:
    p = IDX / "roster.json"
    if not p.exists():
        raise SystemExit("缺 30_index/roster.json，先跑 s18_official.py --roster-only")
    roster = json.loads(p.read_text(encoding="utf-8"))["heroes"]
    return Names(roster)


def opponent_of(title: str) -> str:
    """「对戈娅：全时期被压制」→ 戈娅。多对手「对铠／杨戬：…」只取第一个。

    build_site.parse_opp 和 s5_index 原来各写一个死正则
    `^对([\\u4e00-\\u9fa5]{2,4})[：:]`，遇到四字以上或带／的标题会静默返回空。
    这里改成最长前缀匹配，两处共用。
    """
    m = re.match(r"^对(.+?)[：:，,]", title)
    if not m:
        return ""
    head = m.group(1)
    N = load()
    # 先看有没有分隔符（对铠／杨戬：），拆开取第一个
    first = re.split(r"[／/、]", head)[0].strip()
    c = N.canon(first)
    if c:
        return c
    # 兜底：在 head 里找最长的英雄名
    hits = N.find_all(head)
    return hits[0] if hits else ""


def fmt_ts(sec: float) -> str:
    """1231.4 → 20:31"""
    try:
        s = int(float(sec))
    except (TypeError, ValueError):
        return ""
    return f"{s // 60:02d}:{s % 60:02d}"


if __name__ == "__main__":
    N = load()
    print(f"英雄 {len(N.all_names)}  可用别名 {len(N.alias)}")
    for lane in ("solo", "jungle", "mid", "adc", "roam"):
        print(f"  {lane:7s} {len(N.by_lane(lane))}")
    bad = [k for k, v in ALIAS.items() if k not in N.alias]
    print("被剔除的别名（目标不在名录 / 别名本身是英雄名）：" + "、".join(bad))
    print(N.find_all("火舞打小乔肯定没有线权，凯也怕她"))
    print(opponent_of("对铠／杨戬：劣势"), opponent_of("对戈娅：全压制"), opponent_of("没有对位"))
