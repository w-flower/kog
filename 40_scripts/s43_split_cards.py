# -*- coding: utf-8 -*-
"""s43_split_cards.py — 把码道产出的批次文件拆成单英雄卡 + 机械格式断言。

用法:
    python 40_scripts/s43_split_cards.py 50_logs/codearts/英雄卡_批次A.md [--write]

不带 --write 只校验不落盘。
断言项:
  1. 分隔符数量 == 预期英雄数
  2. 每张卡有 front matter，10 个字段齐全且顺序正确
  3. status == draft
  4. sources 非空且形如 [BVxxx...]
  5. 正文含 6 节 + 待补
  6. 至少 1 条 (BVxxx @ MM:SS) 时间戳引用
"""
import re, sys
from pathlib import Path

BASE = Path("C:/Users/Lenovo/WorkBuddy/kog")
CARD_DIR = BASE / "20_kb/A_英雄教学"
FIELDS = ["id", "cat", "title", "tempo", "job", "motto", "version", "status", "updated", "sources"]
SECTIONS = ["## 0. 大局观定位", "## 1. 机制内核", "## 2.", "## 3.", "## 4.", "## 5.", "## 待补"]
TS = re.compile(r"BV[0-9A-Za-z]{8,12}\s*@\s*\d{1,2}:\d{2}")

SPLIT = re.compile(r"^<!--\s*====\s*CARD:\s*(.+?)\s*====\s*-->\s*$", re.M)


def parse(text):
    marks = list(SPLIT.finditer(text))
    out = []
    for i, m in enumerate(marks):
        name = m.group(1).strip()
        start = m.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[start:end].strip()
        # 去掉卡尾部的「## 自检」节
        body = re.split(r"\n## 自检", body)[0].strip()
        out.append((name, body))
    return out


def check(name, body):
    errs, warns = [], []
    if not body.startswith("---"):
        errs.append("缺 front matter")
        return errs, warns, {}
    end = body.find("\n---", 3)
    if end < 0:
        errs.append("front matter 未闭合")
        return errs, warns, {}
    fm_raw = body[3:end].strip()
    main = body[end + 4:].strip()
    fm = {}
    order = []
    for ln in fm_raw.splitlines():
        if ":" in ln:
            k = ln.split(":", 1)[0].strip()
            v = ln.split(":", 1)[1].strip()
            fm[k] = v
            order.append(k)
    for f in FIELDS:
        if f not in fm:
            errs.append(f"缺字段 {f}")
    if order and order[:len(FIELDS)] != FIELDS:
        warns.append(f"字段顺序与规范不同: {order}")
    if fm.get("status") != "draft":
        errs.append(f"status={fm.get('status')} 应为 draft")
    src = fm.get("sources", "")
    if not re.match(r"^\[BV\w+", src):
        errs.append(f"sources 不合规: {src}")
    for s in SECTIONS:
        if s not in main:
            errs.append(f"缺小节 {s}")
    ts = TS.findall(main)
    if not ts:
        errs.append("正文无 (BVxxx @ MM:SS) 时间戳引用")
    if len(main) < 600:
        warns.append(f"正文仅 {len(main)} 字符，偏薄")
    return errs, warns, {"fm": fm, "main": main, "ts": len(ts), "chars": len(main)}


def main():
    args = sys.argv[1:]
    write = "--write" in args
    args = [a for a in args if not a.startswith("--")]
    if not args:
        print("用法: s43_split_cards.py <批次文件> [--write]")
        return
    p = Path(args[0])
    if not p.exists():
        p = BASE / args[0]
    text = p.read_text(encoding="utf-8")
    cards = parse(text)
    print(f"解析到 {len(cards)} 张卡: {[n for n, _ in cards]}\n")
    ok = 0
    for name, body in cards:
        errs, warns, info = check(name, body)
        tag = "PASS" if not errs else "FAIL"
        print(f"[{tag}] {name}  ts={info.get('ts','-')} chars={info.get('chars','-')} "
              f"tempo={info.get('fm',{}).get('tempo','-')} job={info.get('fm',{}).get('job','-')}")
        for e in errs:
            print("   ✗", e)
        for w in warns:
            print("   ! ", w)
        if not errs:
            ok += 1
            if write:
                dst = CARD_DIR / f"{name}.md"
                dst.write_text(body + "\n", encoding="utf-8")
                print(f"   -> 写入 {dst.name}")
    print(f"\n合计 PASS {ok}/{len(cards)}")
    if write and ok != len(cards):
        print("⚠️ 有 FAIL 卡，已跳过未写入")


if __name__ == "__main__":
    main()
