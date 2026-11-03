#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s28_card_audit.py — A 类旧卡体检：过薄 / 全局通用思路 / 无证据

三类问题：
  1. thin    内容过薄：非表格 bullet < 6
  2. generic 全局通用思路：正文句子里不含「本英雄名 / 技能词 / 该英雄专属机制词」
             的占比 > 50%。通用词表来自历次审计（走位/支援/发育/打团这类放之四海皆准的句子）
  3. noev    证据缺失：引用了具体数值/思路却没有 (BV… @ mm:ss) 来源标记

用法：
  python s28_card_audit.py            # 全量体检，打印清单
  python s28_card_audit.py --json     # 机器可读
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
DIR = ROOT / "20_kb" / "A_英雄教学"

# 通用思路词：任何英雄都成立的句子特征。命中 ≥2 个才算通用句（防误伤）。
GENERIC = ("支援", "发育", "打团", "站位", "心态", "多看小地图", "别上头",
           "跟上队友", "做好视野", "注意走位", "不要急", "稳住", "经济差",
           "推塔", "控龙", "拿龙", "抱团", "分推", "运营节奏")

# 技能词：出现在句子里说明在讲这个英雄本身（数字+技能/普攻/被动/大/闪）
SKILL = re.compile(r"[一二三1234]{1,2}技能|被动|大招|普攻|闪现|连招|铭文|出装|"
                   r"@\s*\d{1,2}:\d{2}|BV\w+")


def bullets(text: str) -> list[str]:
    out = []
    for ln in text.splitlines():
        t = ln.strip()
        if t.startswith(("-", "*", ">")) or re.match(r"^\d+\.\s", t):
            out.append(t)
    return out


def evidence(line: str) -> bool:
    """一行自身带来源，或明说来源是官方面板（官方口径不是编的，是 L0）。"""
    return bool(re.search(r"BV\w+|@\s*\d{1,2}:\d{2}|来源|官方技能面板", line))


def has_evidence_nearby(lines: list[str], i: int, back: int = 8) -> bool:
    """列表项的结论往往继承自上方被引用的段落：往上回溯找 BV/时间戳。

    为什么要回溯：像「1. 卡草 / 卡视野」这种 bullet 是「BV1fj411U7tr @ 02:01
    直接把这张表念了出来」下面的分支，证据在小节头部，不在 bullet 自己身上。
    第一版只看 bullet 本行，把 5 张其实有据的卡全误判成 noev。
    """
    for j in range(max(0, i - back), i + 1):
        if evidence(lines[j]):
            return True
    return False


def audit(path: Path) -> dict:
    name = path.stem
    text = path.read_text(encoding="utf-8")
    bs = [b for b in bullets(text)
          if not b.startswith(">") and "AUTO:" not in b]
    issues = []
    if len(bs) < 6:
        issues.append(f"thin: 只有 {len(bs)} 条 bullet")

    # 通用思路检测：取正文段落里的「结论句」（含「要/别/先/一定/记住」等祈使语气）
    plain = [ln.strip() for ln in text.splitlines()
             if ln.strip() and not ln.strip().startswith(("#", "|", "-", "*", ">"))
             and "---" not in ln]
    concl = [p for p in plain if re.search(r"(要|别|先|一定|记住|核心|关键|重点)", p)]
    if concl:
        gen = sum(1 for p in concl
                  if sum(w in p for w in GENERIC) >= 2 and not SKILL.search(p))
        ratio = gen / len(concl)
        if ratio > 0.5:
            issues.append(f"generic: 结论句 {gen}/{len(concl)} 是全局通用思路")
    # 证据缺失：bullet 里像结论，且本行与上方 8 行都没有来源标记
    all_lines = text.splitlines()
    noe = []
    for b in bs:
        if not re.search(r"\d|%|要|先|别|核心", b) or evidence(b):
            continue
        try:
            i = all_lines.index(b)
        except ValueError:
            i = -1
        if i >= 0 and has_evidence_nearby(all_lines, i):
            continue
        noe.append(b)
    if len(noe) > max(2, len(bs) // 3):
        issues.append(f"noev: {len(noe)}/{len(bs)} 条 bullet 无来源")

    return {"hero": name, "bullets": len(bs), "issues": issues,
            "status": "ok" if not issues else "bad"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = [audit(p) for p in sorted(DIR.glob("*.md")) if p.stem != "_说明"]
    bad = [r for r in rows if r["status"] == "bad"]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return 0
    print(f"A 卡体检：{len(rows)} 张，问题 {len(bad)} 张\n")
    for r in bad:
        print(f"  {r['hero']:<8} bullets={r['bullets']:>2}  {'；'.join(r['issues'])}")
    n_ok = len(rows) - len(bad)
    print(f"\nok={n_ok} bad={len(bad)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
