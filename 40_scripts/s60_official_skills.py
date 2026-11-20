# -*- coding: utf-8 -*-
"""s60_official_skills.py — 抓取全部英雄「技能/被动官方描述」数据层。

数据源（权威）：腾讯王者荣耀官网
  - 英雄列表: https://pvp.qq.com/web201605/js/herolist.json
  - 英雄详情: https://pvp.qq.com/web201605/herodetail/<ename>.shtml  (GBK)
详情页内 `.skill-info .show-list` 逐条含：
  - <p class="skill-name"><b>技能名</b><span>冷却值：X</span><span>消耗：Y</span></p>
  - <p class="skill-desc">官方描述全文（含成长数值/加成比例）</p>
第 1 条为被动，其后为一/二/三技能（部分英雄有第 4 技能）。

产出（10_sources/official/）：
  herolist.json          官网原始英雄列表
  skills.json            结构化全量数据
  md/<英雄>.md            每个英雄可读卡片（被动 + 各技能）
  INDEX.md               覆盖率/技能数索引

用法:
  python 40_scripts/s60_official_skills.py            # 全量
  python 40_scripts/s60_official_skills.py --limit 3  # 只抓前 N 个（联调）
  python 40_scripts/s60_official_skills.py --ename 105 106
"""
from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "10_sources/official"
MD = OUT / "md"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"

LIST_URL = "https://pvp.qq.com/web201605/js/herolist.json"
DETAIL = "https://pvp.qq.com/web201605/herodetail/{ename}.shtml"

TAG = re.compile(r"<[^>]+>")
NUM = re.compile(r"\d+(?:\.\d+)?%?")


def fetch(url: str, retries: int = 3) -> bytes:
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://pvp.qq.com/"})
            return urllib.request.urlopen(req, timeout=25).read()
        except Exception as e:  # noqa
            last = e
            time.sleep(1.2 * (i + 1))
    raise last


def decode(raw: bytes) -> str:
    for enc in ("gbk", "utf-8"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


def clean(s: str) -> str:
    s = TAG.sub("", s)
    s = html.unescape(s)
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"[ \t\r\n]+", " ", s).strip()


def parse_skills(page: str) -> list[dict]:
    blocks = re.findall(r'<div class="show-list"[^>]*>(.*?)</div>', page, re.S)
    rows = []
    for b in blocks:
        mn = re.search(r'<p class="skill-name">(.*?)</p>', b, re.S)
        md = re.search(r'<p class="skill-desc">(.*?)</p>', b, re.S)
        name_html = mn.group(1) if mn else ""
        nm = re.search(r"<b>(.*?)</b>", name_html, re.S)
        name = clean(nm.group(1)) if nm else clean(name_html)
        spans = [clean(x) for x in re.findall(r"<span>(.*?)</span>", name_html, re.S)]
        cooldown = next((s.split("：", 1)[1] for s in spans if "冷却" in s), "")
        cost = next((s.split("：", 1)[1] for s in spans if "消耗" in s), "")
        desc = clean(md.group(1)) if md else ""
        # 跳过占位空块（官网第 5 格 no5 常有空 show-list）
        if not name and not desc:
            continue
        rows.append((name, cooldown, cost, desc))
    kinds = ["被动", "一技能", "二技能", "三技能", "四技能", "五技能"]
    skills = []
    for i, (name, cooldown, cost, desc) in enumerate(rows):
        kind = kinds[i] if i < len(kinds) else f"技能{i + 1}"
        skills.append({
            "idx": i,
            "kind": kind,
            "name": name,
            "cooldown": cooldown,
            "cost": cost,
            "desc": desc,
            "numbers": NUM.findall(desc),
        })
    return skills


def hero_md(h: dict) -> str:
    lines = [
        "---",
        f"id: {h['cname']}",
        "cat: S",
        f"title: {h['cname']}（{h.get('title','')}）",
        f"ename: {h['ename']}",
        "source: pvp.qq.com/web201605/herodetail/%s.shtml" % h.get("source_path", h["ename"]),
        "status: official",
        "---",
        "",
        f"# {h['cname']} · 技能官方描述",
        "",
        f"> 权威来源：王者荣耀官网英雄详情页（ename={h['ename']}）。描述与冷却/消耗为官网原文摘录，未改写。",
        f"> 定位标签：hero_type={h.get('hero_type','')}，roles={h.get('roles','')}。",
        "",
    ]
    for s in h["skills"]:
        lines.append(f"## {s['kind']} · {s['name']}")
        meta = []
        if s["cooldown"]:
            meta.append(f"冷却值：{s['cooldown']}")
        if s["cost"]:
            meta.append(f"消耗：{s['cost']}")
        if meta:
            lines.append("")
            lines.append("`" + " ｜ ".join(meta) + "`")
        lines.append("")
        lines.append(s["desc"] or "（官网未给出描述）")
        if s["numbers"]:
            lines.append("")
            lines.append("> 描述内数值：`" + ", ".join(dict.fromkeys(s["numbers"])) + "`")
        lines.append("")
    lines += [
        "## 待核对数值（可能未标注）",
        "",
        "- 官网文案有时未随平衡性更新同步（如隐性削弱/加强未改描述）。凡正文数值与当前版本实测或更新公告不一致的，在此逐条记录：",
        "  - [ ] （英雄/技能）官网写 X，实测/公告为 Y —— 出处：待补",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--ename", nargs="*", default=[])
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    MD.mkdir(parents=True, exist_ok=True)

    raw = fetch(LIST_URL)
    heroes = json.loads(decode(raw))
    (OUT / "herolist.json").write_text(json.dumps(heroes, ensure_ascii=False, indent=1), encoding="utf-8")

    todo = heroes
    if args.ename:
        keep = {int(x) for x in args.ename}
        todo = [h for h in heroes if int(h["ename"]) in keep]
    elif args.limit:
        todo = heroes[: args.limit]

    result, fails = [], []
    for n, h in enumerate(todo, 1):
        ename = int(h["ename"])
        try:
            page = ""
            skills = []
            # 旧站用数字 ename；新英雄可能只在 id_name 路径下
            cand_paths = [str(ename)]
            if h.get("id_name"):
                cand_paths.append(str(h["id_name"]))
            used = ""
            for cp in cand_paths:
                try:
                    page = decode(fetch(DETAIL.format(ename=cp)))
                except Exception:
                    continue
                skills = parse_skills(page)
                if skills:
                    used = cp
                    break
            if not skills:
                fails.append({"ename": ename, "cname": h["cname"], "reason": "no_skill_block"})
                print(f"[{n}/{len(todo)}] {h['cname']}({ename}) NO_BLOCK")
                continue
            item = {**h, "ename": ename, "source_path": used, "skills": skills}
            result.append(item)
            (MD / f"{h['cname']}.md").write_text(hero_md(item), encoding="utf-8")
            print(f"[{n}/{len(todo)}] {h['cname']}({ename}) skills={len(skills)} nums={sum(len(s['numbers']) for s in skills)}")
        except Exception as e:  # noqa
            fails.append({"ename": ename, "cname": h["cname"], "reason": str(e)[:80]})
            print(f"[{n}/{len(todo)}] {h['cname']}({ename}) ERR {str(e)[:60]}")
        time.sleep(0.35)

    (OUT / "skills.json").write_text(
        json.dumps({"source": "pvp.qq.com", "count": len(result), "heroes": result, "fails": fails},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    idx = ["# 英雄技能官方描述 · 索引", "",
           f"- 数据源：pvp.qq.com 官网英雄详情页",
           f"- 覆盖：{len(result)} / {len(todo)} 个英雄；失败 {len(fails)}",
           f"- 结构化数据：`10_sources/official/skills.json`；可读卡：`10_sources/official/md/<英雄>.md`", "",
           "| 英雄 | ename | 技能数 | 数值个数 |", "|---|---|---|---|"]
    for h in result:
        idx.append(f"| {h['cname']} | {h['ename']} | {len(h['skills'])} | {sum(len(s['numbers']) for s in h['skills'])} |")
    if fails:
        idx += ["", "## 失败", "", "| 英雄 | ename | 原因 |", "|---|---|---|"]
        idx += [f"| {f['cname']} | {f['ename']} | {f['reason']} |" for f in fails]
    (OUT / "INDEX.md").write_text("\n".join(idx), encoding="utf-8")
    print(f"\nDONE heroes={len(result)} fails={len(fails)} -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
