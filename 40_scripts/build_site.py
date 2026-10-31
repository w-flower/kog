#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_site.py — 把 20_kb 下的 Markdown + site_src 模板编成单个 index.html

产物是单文件（双击 file:// 能开、扔 GitHub Pages 也能开、不受 CORS 影响），
但**源码不是单文件**：
    site_src/template.html   页面骨架（改布局改这里）
    site_src/app.css         全部样式（改配色改这里）
    site_src/app.js          交互与路由（改行为改这里）
    20_kb/**.md             全部内容（改内容改这里）

改完任何一处，重跑本脚本即可。

用法：
  python build_site.py
  python build_site.py --out /tmp/x.html
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "20_kb"
SRC = ROOT / "site_src"
DEFAULT_OUT = ROOT / "site" / "index.html"
VERSION = "S45"

CAT_META = [
    ("A", "英雄教学", "A_英雄教学", "这个英雄怎么玩、什么时候强"),
    ("B", "克制关系", "B_克制关系", "打谁舒服、被谁克、为什么"),
    ("C", "BP", "C_BP", "选人阶段该怎么定"),
    ("D", "对局内", "D_对局内", "现在这一刻该干什么"),
]

ENTRY_RE = re.compile(r"^###\s+(K-([ABCD])\d{2,3})\s+(.+?)\s*$")
FM_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)


# ─────────────────────────── markdown → html（够用就行的子集）
def esc(s: str) -> str:
    return html.escape(s, quote=False)


def inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    # K-xxx 交叉引用 → 可点跳转
    s = re.sub(r"(?<![\w-])(K-[ABCD]\d{2,3})(?![\w-])", r'<a class="kref" href="#\1">\1</a>', s)
    return s


def md_to_html(md: str) -> str:
    lines, out, i, n = md.splitlines(), [], 0, len(md.splitlines())
    while i < n:
        ln = lines[i]

        if ln.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].startswith("```"):
                buf.append(lines[i]); i += 1
            i += 1
            out.append("<pre><code>" + esc("\n".join(buf)) + "</code></pre>")
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>")
            i += 1
            continue

        if re.match(r"^\s*\|.*\|\s*$", ln) and i + 1 < n \
                and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < n and re.match(r"^\s*\|.*\|\s*$", lines[i]):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            th = "".join(f"<th>{inline(c)}</th>" for c in head)
            tb = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div class="tw"><table><thead><tr>{th}</tr></thead>'
                       f"<tbody>{tb}</tbody></table></div>")
            continue

        if ln.startswith(">"):
            buf = []
            while i < n and lines[i].startswith(">"):
                buf.append(lines[i].lstrip(">").strip()); i += 1
            out.append("<blockquote>" + md_to_html("\n".join(buf)) + "</blockquote>")
            continue

        if re.match(r"^\s*[-*]\s+", ln):
            buf = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                buf.append(re.sub(r"^\s*[-*]\s+", "", lines[i])); i += 1
            out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in buf) + "</ul>")
            continue

        if re.match(r"^\s*\d+\.\s+", ln):
            buf = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                buf.append(re.sub(r"^\s*\d+\.\s+", "", lines[i])); i += 1
            out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in buf) + "</ol>")
            continue

        if re.match(r"^\s*---+\s*$", ln):
            out.append("<hr>"); i += 1
            continue

        if not ln.strip():
            i += 1
            continue

        buf = []
        while i < n and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|```|>|\s*[-*]\s|\s*\d+\.\s|\s*\|)", lines[i]):
            buf.append(lines[i].strip()); i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
    return "\n".join(out)


# ─────────────────────────── 解析知识库
def split_doc(path: Path) -> tuple[str, str, list[dict]]:
    raw = FM_RE.sub("", path.read_text(encoding="utf-8"), count=1)
    lines = raw.splitlines()

    title, body_start = path.stem, 0
    for idx, ln in enumerate(lines):
        if ln.startswith("# "):
            title, body_start = ln[2:].strip(), idx + 1
            break

    heads = [(i, m) for i, ln in enumerate(lines) if (m := ENTRY_RE.match(ln))]
    first = heads[0][0] if heads else len(lines)

    entries = []
    for k, (i, m) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        entries.append({
            "id": m.group(1), "cat": m.group(2), "title": m.group(3).strip(),
            "self": f"<h3>{inline(m.group(1))} {inline(m.group(3).strip())}</h3>",
            "html": md_to_html("\n".join(lines[i + 1:end]).strip()),
        })

    intro = md_to_html("\n".join(lines[body_start:first]).strip())
    return title, intro, entries


def collect() -> dict:
    cats = []
    for key, name, dname, desc in CAT_META:
        d = KB / dname
        if not d.exists():
            continue
        about = ""
        ap = d / "_说明.md"
        if ap.exists():
            _, about, _ = split_doc(ap)

        docs = []
        for f in sorted(d.glob("*.md")):
            if f.name.startswith("_"):
                continue
            title, intro, entries = split_doc(f)
            docs.append({"title": title, "file": f.name, "intro": intro, "entries": entries})
        cats.append({"key": key, "name": name, "desc": desc, "about": about, "docs": docs})

    overview = []
    for f in ["00_导航.md", "95_信源名单.md", "90_版本变更台账.md"]:
        p = KB / f
        if p.exists():
            title, intro, _ = split_doc(p)
            overview.append({"title": title, "file": f, "html": intro})
    return {"cats": cats, "overview": overview}


def compose(data: dict) -> str:
    tpl = (SRC / "template.html").read_text(encoding="utf-8")
    css = (SRC / "app.css").read_text(encoding="utf-8")
    js = (SRC / "app.js").read_text(encoding="utf-8")

    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    if "</script" in js.lower():
        raise SystemExit("app.js 里出现了 </script，会截断内联脚本，请改写")

    return (tpl.replace("{{VERSION}}", VERSION)
               .replace("{{CSS}}", css)
               .replace("{{DATA}}", payload)
               .replace("{{JS}}", js))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    for f in ("template.html", "app.css", "app.js"):
        if not (SRC / f).exists():
            print(f"[FATAL] 缺 site_src/{f}", file=sys.stderr)
            return 2

    data = collect()
    total = sum(len(d["entries"]) for c in data["cats"] for d in c["docs"])
    today = datetime.now().strftime("%Y-%m-%d")
    data["meta"] = {
        "sub": f"当前版本 {VERSION} · 共 {total} 条 · 更新 {today}",
        "foot": ("每条的「来源」都可回溯到 B 站视频的具体时间戳；无来源不写结论。<br>"
                 "内容改 <code>20_kb/*.md</code>，样式改 <code>site_src/app.css</code>，"
                 "交互改 <code>site_src/app.js</code>，然后重跑 <code>build_site.py</code>。"),
    }

    out_html = compose(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out_html, encoding="utf-8")
    print(f"built -> {args.out}  ({args.out.stat().st_size/1024:.1f} KB, {total} 条, "
          f"{len(data['cats'])} 类)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
