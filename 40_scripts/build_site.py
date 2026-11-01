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
    ("L", "分路", "L_分路", "这个位置该按什么顺序想事"),
]

# 分路：key / 显示名 / 文件 / 图标首字 / 一句话定位
LANES = [
    ("mid", "中路", "01_中路.md", "中", "清完这波线往哪走"),
    ("roam", "游走", "02_游走.md", "游", "第一步去哪"),
    ("adc", "发育路", "03_发育路.md", "射", "这波兵敢不敢吃"),
    ("solo", "对抗路", "04_对抗路.md", "抗", "压线还是放线"),
    ("jungle", "打野", "05_打野.md", "野", "该刷还是该抓"),
]

ENTRY_RE = re.compile(r"^###\s+(K-([ABCDL])\d{2,3})\s+(.+?)\s*$")
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
    s = re.sub(r"(?<![\w-])(K-[ABCDL]\d{2,3})(?![\w-])", r'<a class="kref" href="#\1">\1</a>', s)
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


def first_sentence(html_text: str, limit: int = 96) -> str:
    """从条目正文里抽一句摘要，卡片上只显示这一句。"""
    m = re.search(r"<p>(.*?)</p>", html_text, re.S)
    raw = m.group(1) if m else html_text
    raw = re.sub(r"<[^>]+>", "", raw).strip()
    raw = raw.replace("\n", "")
    raw = re.split(r"(?<=[。！？；])", raw)[0] if raw else ""
    return raw[:limit] + ("…" if len(raw) > limit else "")


def hue_of(name: str) -> int:
    """英雄图标色相：同名恒定，不同英雄自动分开。"""
    h = 0
    for ch in name:
        h = (h * 131 + ord(ch)) % 360
    return (h * 7 + 190) % 360


def parse_opp(title: str) -> str:
    m = re.search(r"^对([\u4e00-\u9fa5]{2,4})[：:]", title)
    return m.group(1) if m else ""


LANE_ALIAS = {"中路": "mid", "中": "mid", "mid": "mid",
              "游走": "roam", "辅助": "roam", "roam": "roam",
              "发育路": "adc", "射手": "adc", "adc": "adc",
              "对抗路": "solo", "边路": "solo", "solo": "solo",
              "打野": "jungle", "jungle": "jungle"}


def lanes_in_title(title: str) -> list[str]:
    """「苏烈（游走／对抗路）」→ ['roam','solo']"""
    m = re.search(r"[（(]([^）)]+)[）)]", title)
    if not m:
        return []
    out = []
    for part in re.split(r"[／/、,，]", m.group(1)):
        k = LANE_ALIAS.get(part.strip())
        if k and k not in out:
            out.append(k)
    return out


def fm_field(path: Path, key: str) -> str:
    """读 front matter 里的单行字段。"""
    try:
        head = path.read_text(encoding="utf-8").split("---")[1]
    except (IndexError, OSError):
        return ""
    for ln in head.splitlines():
        if ln.strip().startswith(key + ":"):
            return ln.split(":", 1)[1].strip()
    return ""


def sections_as_entries(path: Path) -> list[dict]:
    """叙述式文档（没有 K 编号的 A 类英雄卡）→ 按 `## 二级标题` 切成伪条目。

    为什么要这个：A 类里有两种写法，一种是 K 条目，一种是"讲透一篇"的叙述卡
    （机制内核 / 出装 / 全局思路 / 弱点）。后者没有 K 编号，如果不切，英雄页会显示"还没有条目"。
    """
    raw = FM_RE.sub("", path.read_text(encoding="utf-8"), count=1)
    lines = raw.splitlines()
    start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            start = i + 1
            break
    body = lines[start:]
    heads = [i for i, ln in enumerate(body) if ln.startswith("## ")]
    out: list[dict] = []
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(body)
        title = body[i][3:].strip()
        html = md_to_html("\n".join(body[i + 1:end]).strip())
        if not html.strip():
            continue
        out.append({"id": "", "cat": "", "title": title,
                    "self": f"<h3>{inline(title)}</h3>", "html": html,
                    "sum": first_sentence(html)})
    return out


def collect() -> dict:
    cats = []
    lane_docs: list[dict] = []
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
            if not entries and key in ("A", "B"):
                entries = sections_as_entries(f)
            for e in entries:
                e["sum"] = first_sentence(e["html"])
            doc = {"title": title, "file": f.name, "intro": intro,
                   "entries": entries, "hero": f.stem, "cat": key,
                   "fm_title": fm_field(f, "title")}
            docs.append(doc)
            if key == "L":
                lane_docs.append(doc)
        cats.append({"key": key, "name": name, "desc": desc, "about": about, "docs": docs})

    # ── 按英雄归拢：A 文档 / B 文档的文件名就是英雄名
    heroes: dict[str, dict] = {}
    general: list[dict] = []
    for c in cats:
        if c["key"] == "L":
            continue
        for d in c["docs"]:
            if c["key"] in ("A", "B"):
                h = heroes.setdefault(d["hero"], {
                    "name": d["hero"], "hue": hue_of(d["hero"]), "a": [], "b": [],
                    "lanes": []})
                if c["key"] == "A":
                    h["lanes"] = lanes_in_title(d.get("fm_title") or d["title"])
                slot = "a" if c["key"] == "A" else "b"
                for e in d["entries"]:
                    if slot == "b":
                        e["opp"] = parse_opp(e["title"])
                    h[slot].append(e)
            else:
                general.append({"key": c["key"], "cat": c["name"], "title": d["title"],
                                "file": d["file"], "intro": d["intro"],
                                "entries": d["entries"]})

    hero_list = []
    for h in heroes.values():
        h["n"] = len(h["a"]) + len(h["b"])
        h["b_n"] = len(h["b"])
        # 被谁打：从所有 B 条目里反查对手是不是他
        h["vs"] = sorted({e["opp"] for e in h["b"] if e.get("opp")})
        hero_list.append(h)
    hero_list.sort(key=lambda x: (-x["n"], x["name"]))

    # 反向索引：这个英雄在谁的 B 条目里被点名
    for h in hero_list:
        h["incoming"] = [x["name"] for x in hero_list
                         if h["name"] in x["vs"] and x["name"] != h["name"]]

    overview = []
    for f in ["00_导航.md", "95_信源名单.md", "96_素材缺口.md", "90_版本变更台账.md"]:
        p = KB / f
        if p.exists():
            title, intro, _ = split_doc(p)
            overview.append({"title": title, "file": f, "html": intro})

    # ── 分路层：每条分路挂上「本路英雄」+「相关对局内环节」+「交叉分路」
    by_file = {d["file"]: d for d in lane_docs}
    stages = []          # D 类各节的 role，用于双向链接
    ddir = KB / "D_对局内"
    if ddir.exists():
        for f in sorted(ddir.glob("*.md")):
            if f.name.startswith("_"):
                continue
            roles = [LANE_ALIAS.get(x.strip()) for x in
                     re.split(r"[\[\],、]", fm_field(f, "role").strip("[]"))]
            roles = [r for r in roles if r]
            title, _, _ = split_doc(f)
            stages.append({"file": f.name, "title": title, "roles": roles,
                           "id": fm_field(f, "id")})

    lane_list = []
    for key, name, fname, icon, motto in LANES:
        d = by_file.get(fname)
        if not d:
            continue
        lane_list.append({
            "key": key, "name": name, "icon": icon, "motto": motto,
            "file": fname, "title": d["title"], "intro": d["intro"],
            "entries": d["entries"], "hue": hue_of(name),
            "heroes": [h["name"] for h in hero_list if key in h["lanes"]],
            "stages": [s for s in stages if key in s["roles"]],
            "cross": [n for k, n, *_ in LANES if k != key],
        })
    lane_map = {l["key"]: l["name"] for l in lane_list}
    for h in hero_list:
        h["lane_names"] = [lane_map.get(k, "") for k in h["lanes"]]

    lane_about = ""
    lap = KB / "L_分路" / "_说明.md"
    if lap.exists():
        _, lane_about, _ = split_doc(lap)

    return {"version": VERSION, "heroes": hero_list, "general": general,
            "lanes": lane_list, "stages": stages, "lane_about": lane_about,
            "cats": [{"key": c["key"], "name": c["name"], "desc": c["desc"],
                      "n": sum(len([e for e in d["entries"] if e.get("id")]) for d in c["docs"])} for c in cats],
            "overview": overview}


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
    total = sum(c["n"] for c in data["cats"])
    today = datetime.now().strftime("%Y-%m-%d")
    data["meta"] = {
        "total": total,
        "heroes": len(data["heroes"]),
        "sub": f"当前版本 {VERSION} · 共 {total} 条 · 更新 {today}",
    }

    out_html = compose(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out_html, encoding="utf-8")
    print(f"built -> {args.out}  ({args.out.stat().st_size/1024:.1f} KB, {total} 条, "
          f"{len(data['cats'])} 类)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
