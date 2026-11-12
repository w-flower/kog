#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s33_export_library.py — 把 20_kb/ 全部 md 合并成一份可上传资料库的合集。

纯本地、不联网、不改动任何源文件。产物落在 50_logs/（已被 .gitignore 排除）。

做法：
  · 按「导航 → A/B/C/D/L 五类 → 根目录台账」固定顺序合并
  · 剥掉 YAML front matter，但把 status/sources/version/updated 压成一行保留溯源
  · 篇标题用正文首个 H1（删掉该行避免重复），其余标题降 1 级；代码块内的 # 不动
  · 正文原样保留：BV@秒数、K-Axx 编号、B 站链接、引用块、表格一律不动

用法：python s33_export_library.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
KB = ROOT / "20_kb"
OUT = ROOT / "50_logs" / "王者荣耀实战知识库_S45_全库合集.md"
MAX_BYTES = 1024 * 1024          # 1 MiB，超过就停下，别硬传

CATS = [
    ("A_英雄教学", "A 类 · 英雄教学", "这个英雄怎么玩、什么时候强"),
    ("B_克制关系", "B 类 · 克制关系", "打谁舒服、被谁克、为什么"),
    ("C_BP", "C 类 · BP", "选人阶段该怎么定"),
    ("D_对局内", "D 类 · 对局内", "现在这一刻该干什么"),
    ("L_分路", "L 类 · 分路", "这个位置该按什么顺序想事"),
]
LEDGERS = ["94_英雄名录", "95_信源名单", "96_素材缺口", "90_版本变更台账"]
SPECIAL = {"_说明": "分类说明", "_模板": "模板"}

HEADER = """# 王者荣耀实战知识库 · S45 全库合集

> 版本 S45 · 收录 285 篇卡片与台账 · 覆盖 131 个英雄 · 导出自本地知识库 `20_kb/`。
> 本合集只收「判断 + 证据引用」，**不含 B 站字幕原文**；结论尽量带 `BV... @ mm:ss`，可回原视频核对。

## 怎么用这份合集

- **五类边界**：A 讲英雄本身；B 讲两个英雄之间；C 讲选人之前；D 讲选人之后（带时间点）；L 讲位置。
- **状态含义**：`active` = ≥3 份有效字幕、逐条带证据；`draft` = 素材不足（薄卡或单/双素材）；`seed` = 单来源、只有实战动作，缺数值与出装。
- `draft` / `seed` 卡**不要当成品用**；卡里「待补」是如实留空，不是漏写。
- **规矩：没有来源就不写。** 官方口径（L0）只给方向、可信度低，当线索；带 BV+秒数的实测条目才当结论。
- `K-Axx` 等编号是原库内部交叉引用，合并后保留文字，但不再可点击跳转。

---
"""


def split_fm(text: str) -> tuple[dict, str]:
    """剥掉开头的 YAML front matter。无 front matter 时原样返回。"""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].lstrip("\ufeff").strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            d = {}
            for ln in "".join(lines[1:i]).splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    d[k.strip()] = v.strip()
            return d, "".join(lines[i + 1:])
    return {}, text


def meta_line(fm: dict) -> str:
    """溯源信息压成一行，YAML 块本身在渲染文档里是噪音。"""
    parts = []
    for key, label in (("status", "状态"), ("version", "版本"),
                       ("updated", "更新"), ("sources", "来源"),
                       ("beats", "官方称克"), ("loses", "官方称被克")):
        v = (fm.get(key) or "").strip()
        if v and v != "[]":
            parts.append(f"{label}: {v}")
    return "> " + " · ".join(parts) + "\n" if parts else ""


def demote(body: str, shift: int = 1) -> str:
    """标题降 shift 级（最高 6 级）；代码块围栏内的 # 不动。"""
    out, fence = [], False
    for ln in body.splitlines():
        if ln.lstrip().startswith("```"):
            fence = not fence
            out.append(ln)
            continue
        if not fence and ln.startswith("#"):
            hashes = ln.split(" ", 1)[0]
            if 1 <= len(hashes) <= 6 and set(hashes) == {"#"}:
                rest = ln[len(hashes):]
                ln = "#" * min(len(hashes) + shift, 6) + rest
        out.append(ln)
    return "\n".join(out).strip("\n")


def render(path: Path, label: str | None = None) -> str:
    """篇标题优先取正文首个 H1（信息量最大），并删掉该行避免重复。

    label 非空时强制用它（`_说明` 等 SPECIAL 文件，H1 会与大类标题撞车）。
    """
    fm, body = split_fm(path.read_text(encoding="utf-8"))
    lines = body.splitlines()
    h1 = next((i for i, ln in enumerate(lines[:30])
               if re.match(r"^#\s+\S", ln)), None)
    if h1 is not None:
        title = label or lines[h1][1:].strip()
        body = "\n".join(lines[:h1] + lines[h1 + 1:])
    else:
        title = label or path.stem

    chunk = f"## {title}\n\n"
    ml = meta_line(fm)
    if ml:
        chunk += ml + "\n"
    return chunk + demote(body, 1) + "\n"


def label_of(stem: str) -> str | None:
    """None = 用正文 H1 当篇标题；SPECIAL 文件用固定名。"""
    return SPECIAL.get(stem)


def main() -> int:
    chunks: list[str] = [HEADER]
    counts: dict[str, int] = {}
    n = 0

    # 1. 全库导航
    nav = KB / "00_导航.md"
    if nav.exists():
        chunks.append("# 全库导航\n\n")
        chunks.append(render(nav) + "\n---\n")
        n += 1
        counts["导航"] = 1

    # 2. 五类
    for dname, title, desc in CATS:
        d = KB / dname
        files = sorted(p for p in d.glob("*.md"))
        if not files:
            continue
        chunks.append(f"# {title}\n\n> {desc}\n")
        counts[dname] = 0
        for p in files:
            chunks.append(render(p, label_of(p.stem)) + "\n---\n")
            n += 1
            counts[dname] += 1

    # 3. 根目录台账
    leds = [KB / f"{s}.md" for s in LEDGERS]
    leds = [p for p in leds if p.exists()]
    if leds:
        chunks.append("# 附：台账与底表\n\n> 名录、信源判据、素材缺口、版本变更。用来判断「哪些结论能信、哪些还没写」。\n")
        counts["台账"] = 0
        for p in leds:
            chunks.append(render(p, label_of(p.stem)) + "\n---\n")
            n += 1
            counts["台账"] += 1

    doc = "\n".join(chunks).rstrip() + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(doc, encoding="utf-8")
    size = OUT.stat().st_size

    print(f"合并 {n} 篇 -> {OUT}")
    for k, v in counts.items():
        print(f"  {k:<16} {v}")
    print(f"总字节 {size:,} ({size/1024:.1f} KiB)")
    if size >= MAX_BYTES:
        print("✗ 超过 1 MiB，先停下检查，不要硬传", file=sys.stderr)
        return 1
    print("✓ < 1 MiB，可上传")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
