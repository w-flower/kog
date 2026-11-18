# -*- coding: utf-8 -*-
"""s45_split_system.py — 拆码道产出的 D 类系统卡 + 机械断言。

用法:
    python 40_scripts/s45_split_system.py 50_logs/codearts/系统卡_S1.md [--write]

断言:
  1. 分隔符数量 == 预期文件数（单文件任务可不带分隔符）
  2. front matter 字段齐全: id/cat/title/depends_on/unlocks/role/version/status/updated/sources
  3. cat == D, status == draft
  4. 有「## 判断顺序」代码块
  5. K-D 条目数 >= 6，编号在任务包给的小区间内
  6. 每条 K 条目八字段齐全
  7. 至少 1 处 (… @ MM:SS)
"""
import re, sys
from pathlib import Path

BASE = Path("C:/Users/Lenovo/WorkBuddy/kog")
DST = BASE / "20_kb/D_对局内"
FIELDS = ["id", "cat", "title", "depends_on", "unlocks", "role", "version", "status", "updated", "sources"]
KFIELDS = ["适用版本", "触发条件", "判断依据", "决策分支", "反例", "来源", "可信度", "状态"]
TS = re.compile(r"@\s*\d{1,2}:\d{2}")
FILE_SPLIT = re.compile(r"^<!--\s*====\s*FILE:\s*(.+?)\s*====\s*-->\s*$", re.M)


def parse(text):
    marks = list(FILE_SPLIT.finditer(text))
    if not marks:
        return [("__SINGLE__", text)]
    out = []
    for i, m in enumerate(marks):
        name = m.group(1).strip()
        s = m.end()
        e = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        out.append((name, text[s:e].strip()))
    return out


def check(name, body):
    errs, warns = [], []
    body = re.split(r"\n## 自检", body)[0].strip()
    if not body.startswith("---"):
        return ["缺 front matter"], warns, {}
    end = body.find("\n---", 3)
    fm_raw, main = body[3:end], body[end + 4:].strip()
    fm = {}
    for ln in fm_raw.splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            fm[k.strip()] = v.strip()
    for f in FIELDS:
        if f not in fm:
            errs.append(f"缺字段 {f}")
    if fm.get("cat") != "D":
        errs.append(f"cat={fm.get('cat')} 应为 D")
    if fm.get("status") != "draft":
        errs.append(f"status={fm.get('status')} 应为 draft")
    if "## 判断顺序" not in main:
        errs.append("缺 ## 判断顺序")
    ks = re.findall(r"^###\s*(K-D\d+)", main, re.M)
    if len(ks) < 6:
        warns.append(f"K 条目仅 {len(ks)} 条")
    nums = [int(k.replace("K-D", "")) for k in ks]
    if nums and max(nums) > 90:
        errs.append(f"K-D 编号越界: {max(nums)}")
    # 每条 K 条目字段完整性
    blocks = re.split(r"^###\s*", main, flags=re.M)[1:]
    for b in blocks:
        title = b.split("\n", 1)[0][:24]
        if not title.startswith("K-D"):
            continue
        miss = [f for f in KFIELDS if f"- **{f}**" not in b]
        if miss:
            errs.append(f"[{title}] 缺字段 {miss}")
    ts = TS.findall(main)
    if not ts:
        errs.append("无 @ MM:SS 时间戳")
    return errs, warns, {"fm": fm, "ks": ks, "ts": len(ts), "chars": len(main)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    write = "--write" in sys.argv
    if not args:
        print("用法: s45_split_system.py <文件> [--write]"); return
    p = Path(args[0])
    if not p.exists(): p = BASE / args[0]
    text = p.read_text(encoding="utf-8")
    items = parse(text)
    print(f"解析到 {len(items)} 个文件段\n")
    ok = 0
    for name, body in items:
        errs, warns, info = check(name, body)
        tag = "PASS" if not errs else "FAIL"
        print(f"[{tag}] {name}  K={len(info.get('ks',[]))} ts={info.get('ts','-')} chars={info.get('chars','-')}")
        for e in errs: print("   ✗", e)
        for w in warns: print("   ! ", w)
        if not errs:
            ok += 1
            if write and name != "__SINGLE__":
                dst = DST / name
                dst.write_text(body + "\n", encoding="utf-8")
                print(f"   -> 写入 {dst.name}")
    print(f"\n合计 PASS {ok}/{len(items)}")


if __name__ == "__main__":
    main()
