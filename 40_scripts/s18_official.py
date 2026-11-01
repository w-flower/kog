#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s18_official.py — 官方英雄名录 + 官方克制关系（唯一带"官方"字样的来源）

两件事：
  1. --roster-only   抓 herolist.json → 30_index/roster.json + 20_kb/94_英雄名录.md
  2. --relations     抓每个英雄的 herodetail 页「压制英雄 / 被压制英雄」→ 30_index/relations.json

纪律（和整个库一致）：
  · 官方只给"谁克谁"，不给条件。所以官方边一律是 **L0 统计口径**，可信度低。
  · 官方长文案不落库（版权边界），只留一个本地引用指针 10_sources/official/<ename>.json。

用法：
  python s18_official.py --roster-only
  python s18_official.py --relations            # 复用已有缓存，缺的才抓
  python s18_official.py --relations --force    # 全部重抓
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
IDX = ROOT / "30_index"
OFF = ROOT / "10_sources" / "official"
KB = ROOT / "20_kb"
OFF.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0")
LIST_JSON = "https://pvp.qq.com/web201605/js/herolist.json"
LIST_HTML = "https://pvp.qq.com/web201605/herolist.shtml"
DETAIL = "https://pvp.qq.com/web201605/herodetail/{ename}.shtml"

# 官方 roles 字段：1=对抗路 2=打野 3=中路 4=发育路 5=游走（实测：廉颇 "1|5"、小乔 "3"）
LANE_CODE = {"1": "solo", "2": "jungle", "3": "mid", "4": "adc", "5": "roam"}
LANE_CN = {"solo": "对抗路", "jungle": "打野", "mid": "中路", "adc": "发育路", "roam": "游走"}
LANE_ORDER = ["solo", "jungle", "mid", "adc", "roam"]
# 官方 hero_type：1战士 2法师 3坦克 4刺客 5射手 6辅助
TYPE_CODE = {1: "战士", 2: "法师", 3: "坦克", 4: "刺客", 5: "射手", 6: "辅助"}
# roles 缺失时用 hero_type 兜底
TYPE2LANE = {5: "adc", 6: "roam", 4: "jungle", 2: "mid", 1: "solo", 3: "solo"}

FORM_RE = re.compile(r"^(.+?)[（(]([^）)]+)[）)]$")


def get(url: str, referer: str = "https://pvp.qq.com/") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


# ────────────────────────── 1. 名录 ──────────────────────────
def fetch_herolist() -> list[dict]:
    """三级降级：json → html → 本地 lexicon。"""
    try:
        d = json.loads(get(LIST_JSON).decode("utf-8"))
        if isinstance(d, list) and len(d) >= 100:
            for x in d:
                x["_src"] = "json"
            return d
    except Exception as e:
        print(f"[warn] herolist.json 失败 {e}", file=sys.stderr)

    try:
        html = get(LIST_HTML).decode("gb18030", "ignore")
        out = []
        for m in re.finditer(r'herodetail/(\d+)\.shtml"[^>]*>.*?alt="([^"]+)"', html, re.S):
            out.append({"ename": int(m.group(1)), "cname": m.group(2),
                        "roles": "", "hero_type": 0, "_src": "html"})
        if out:
            return out
    except Exception as e:
        print(f"[warn] herolist.shtml 失败 {e}", file=sys.stderr)

    lex = IDX / "lexicon.yaml"
    if lex.exists():
        names = [ln.strip("- ").split(":")[0].strip()
                 for ln in lex.read_text(encoding="utf-8").splitlines() if ln.strip()]
        print(f"[warn] 退到 lexicon.yaml，{len(names)} 个名字（无分路）", file=sys.stderr)
        return [{"ename": 0, "cname": n, "roles": "", "hero_type": 0,
                 "_src": "lexicon"} for n in names]
    raise SystemExit("三个来源全部失败")


def build_roster(raw: list[dict]) -> list[dict]:
    """133 条 → 129 个唯一英雄（元流之子 5 形态归并）。"""
    by: dict[str, dict] = {}
    for x in raw:
        cname = (x.get("cname") or "").strip()
        if not cname:
            continue
        form = ""
        m = FORM_RE.match(cname)
        base = cname
        if m:
            base, form = m.group(1), m.group(2)

        lanes = []
        for c in re.split(r"[|,，]", str(x.get("roles") or "")):
            k = LANE_CODE.get(c.strip())
            if k and k not in lanes:
                lanes.append(k)
        lane_src = "official"
        if not lanes:
            k = TYPE2LANE.get(int(x.get("hero_type") or 0))
            if k:
                lanes = [k]
                lane_src = "type_fallback"
        if not lanes:
            lanes, lane_src = ["solo"], "unknown"

        h = by.get(base)
        if h is None:
            h = by[base] = {
                "name": base, "ename": [], "id_name": x.get("id_name") or "",
                "title": x.get("title") or "", "forms": [],
                "type": TYPE_CODE.get(int(x.get("hero_type") or 0), ""),
                "type_code": int(x.get("hero_type") or 0),
                "lanes": [], "main_lane": "", "cold_lanes": [],
                "since": x.get("time") or "", "lane_src": lane_src,
                "alias": [], "has_detail_page": False,
            }
        if x.get("ename"):
            h["ename"].append(int(x["ename"]))
        if form and form not in h["forms"]:
            h["forms"].append(form)
        for k in lanes:
            if k not in h["lanes"]:
                h["lanes"].append(k)
        cold = str(x.get("extra_cold_lane") or "")
        for c in re.split(r"[|,，]", cold):
            k = LANE_CODE.get(c.strip())
            if k and k not in h["cold_lanes"]:
                h["cold_lanes"].append(k)

    out = []
    for h in by.values():
        h["lanes"].sort(key=LANE_ORDER.index)
        # 主分路 = 第一个（官方 roles 的书写顺序就是推荐顺序）
        h["main_lane"] = h["lanes"][0] if h["lanes"] else ""
        if h["forms"]:
            h["alias"] = [f'{h["name"]}({f})' for f in h["forms"]]
        out.append(h)
    out.sort(key=lambda x: (LANE_ORDER.index(x["main_lane"]) if x["main_lane"] in LANE_ORDER else 9,
                            x["name"]))
    return out


def md_roster(heroes: list[dict]) -> str:
    """人类可读名录：按分路分组，标注已有 A/B 卡。"""
    a_cards = {p.stem for p in (KB / "A_英雄教学").glob("*.md") if not p.name.startswith("_")}
    b_cards = {p.stem for p in (KB / "B_克制关系").glob("*.md") if not p.name.startswith("_")}

    lines = [
        "---",
        "id: 94",
        "title: 英雄名录（S45 官方全量）",
        "updated: 2026-11-01",
        "---",
        "",
        "# 英雄名录：官方全量 129 个",
        "",
        "> 来源：`pvp.qq.com/web201605/js/herolist.json`（2026-11-01 抓取，133 条含元流之子 5 形态）。",
        "> 分路取自官方 `roles` 字段（1 对抗路 / 2 打野 / 3 中路 / 4 发育路 / 5 游走），**不是**推测。",
        "> 「卡」= 本库是否已有该英雄的 A 卡（怎么玩）/ B 卡（克制关系）。",
        "",
    ]

    for lane in LANE_ORDER:
        grp = [h for h in heroes if h["main_lane"] == lane]
        if not grp:
            continue
        lines.append(f"## {LANE_CN[lane]}（{len(grp)}）")
        lines.append("")
        lines.append("| 英雄 | 定位 | 分路 | A 卡 | B 卡 |")
        lines.append("|---|---|---|---|---|")
        for h in grp:
            ls = "／".join(LANE_CN[k] for k in h["lanes"])
            extra = f"（副 {len(h['lanes']) - 1}）" if len(h["lanes"]) > 1 else ""
            lines.append(
                f"| {h['name']} | {h['type']} | {ls}{extra} | "
                f"{'✅' if h['name'] in a_cards else '—'} | "
                f"{'✅' if h['name'] in b_cards else '—'} |")
        lines.append("")

    miss_a = [h["name"] for h in heroes if h["name"] not in a_cards]
    miss_b = [h["name"] for h in heroes if h["name"] not in b_cards]
    lines += [
        "## 缺口合计",
        "",
        f"- 官方英雄 **{len(heroes)}** 个；已有 A 卡 {len(a_cards & {h['name'] for h in heroes})} 个，"
        f"缺 {len(miss_a)} 个",
        f"- 已有 B 卡 {len(b_cards & {h['name'] for h in heroes})} 个，缺 {len(miss_b)} 个",
        "",
        f"**缺 A 卡的（{len(miss_a)}）**：{'、'.join(miss_a) or '无'}",
        "",
        f"**缺 B 卡的（{len(miss_b)}）**：{'、'.join(miss_b) or '无'}",
        "",
    ]
    return "\n".join(lines)


# ────────────────────────── 2. 官方克制关系 ──────────────────────────
# 三块关系容器的起点（实测 2026-11-01，公孙离 ename=199）
BLOCK_SPLIT_RE = re.compile(r'<div class="hero-info l info"')
HEAD_RE = re.compile(r'<div class="hero-f1 fl">(.*?)</div>', re.S)
HERO_LINK_RE = re.compile(r'href="(\d+)\.shtml"[^>]*>\s*<img', re.S)
DESC_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.S)
TITLE2KEY = {"最佳搭档": "mate", "压制英雄": "out", "被压制英雄": "in"}


def parse_detail(html: str, ename_map: dict[int, str]) -> dict:
    """返回 {'out': [名字], 'in': [名字], 'mate': [...], 'desc': {名字: 文案}}。

    页面结构（实测 2026-11-01）：
      <div class="hero-info-box">
        <ul class="hero-hd">          ← 三个 tab，**不是**分块标题，必须忽略
          <li class="curr">最佳搭档<span></span></li> …
        </ul>
        <div>
          <div class="hero-info l info" style="display:block;">
            <div class="hero-f1 fl"><i class="hr1 icon fl"></i>最佳搭档</div>
            <div class="hero-list hero-relate-list fl">
              <ul><li class="cur"><a href="120.shtml"><img src="…heroimg/120/120.jpg"></a></li>…</ul>
            </div>
            <div class="hero-list-desc">
              <p>白起可以稳定的开启团战…</p>
              <p style="display:none;">在阿离前期较为弱势时…</p>
            </div>
          </div>
          … 压制英雄 / 被压制英雄 同构
        </div>
      </div>

    所以：**按 `<div class="hero-info l info">` 切块**，块内标题取自 `.hero-f1`。
    文案不带英雄名前缀，按 `<p>` 顺序与 `<a>` 顺序一一对应。
    """
    anchor = html.find("英雄关系")
    body = html[anchor:] if anchor >= 0 else html

    out: dict[str, list[str]] = {"mate": [], "out": [], "in": []}
    desc: dict[str, str] = {}
    found_keys = []

    for chunk in BLOCK_SPLIT_RE.split(body)[1:]:
        # 末块后面接的是「出装建议 / 铭文」区，切掉，免得 <p> 错位
        for stop in ('class="equip', 'class="mingwen', "英雄关系", "技能介绍"):
            j = chunk.find(stop)
            if j > 0:
                chunk = chunk[:j]
        mh = HEAD_RE.search(chunk)
        if not mh:
            continue
        head = re.sub(r"<[^>]+>", "", mh.group(1)).strip()
        # 精确匹配：「被压制英雄」里含「压制英雄」，不能用 in 判断
        key = TITLE2KEY.get(head)
        if key is None:
            continue  # 极少数页面有第四块（如"最佳配合"），忽略
        found_keys.append(key)

        names: list[str] = []
        for m in HERO_LINK_RE.finditer(chunk):
            nm = ename_map.get(int(m.group(1)))
            if nm and nm not in names:
                names.append(nm)
        texts: list[str] = []
        for m in DESC_RE.finditer(chunk):
            t = re.sub(r"<[^>]+>", "", m.group(1))
            t = re.sub(r"\s+", "", t).strip()
            texts.append(t)
        for k, nm in enumerate(names):
            if k < len(texts) and texts[k] and nm not in desc:
                desc[nm] = texts[k][:300]
        for nm in names:
            if nm not in out[key]:
                out[key].append(nm)

    out["desc"] = desc
    out["blocks_found"] = found_keys
    return out


def fetch_relations(roster: list[dict], force: bool = False) -> dict:
    ename_map: dict[int, str] = {}
    for h in roster:
        for e in h["ename"]:
            ename_map[int(e)] = h["name"]

    edges: dict[tuple[str, str], dict] = {}
    hits, miss = [], []
    for i, h in enumerate(roster, 1):
        if not h["ename"]:
            miss.append(h["name"])
            continue
        ename = h["ename"][0]
        cache = OFF / f"{ename}.json"
        if cache.exists() and not force:
            d = json.loads(cache.read_text(encoding="utf-8"))
            if "err" in d:          # 上次就 404，别再当命中
                print(f"  [{i}/{len(roster)}] {h['name']} MISS(cached) {d['err']}",
                      file=sys.stderr)
                miss.append(h["name"])
                continue
        else:
            try:
                html = get(DETAIL.format(ename=ename))
                txt = html.decode("gb18030", "ignore")
                if len(txt) < 10000:
                    raise ValueError(f"too short {len(txt)}")
                d = parse_detail(txt, ename_map)
            except Exception as e:
                print(f"  [{i}/{len(roster)}] {h['name']} MISS {e}", file=sys.stderr)
                miss.append(h["name"])
                cache.write_text(json.dumps({"ename": ename, "err": str(e)}, ensure_ascii=False),
                                 encoding="utf-8")
                time.sleep(0.35)
                continue
            d["ename"] = ename
            cache.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
            time.sleep(0.35)
        hits.append(h["name"])

        me = h["name"]
        for opp in d.get("out", []):
            if opp == me:
                continue
            k = (me, opp)
            e = edges.setdefault(k, {"win": me, "lose": opp, "w": 0, "src": [],
                                     "desc": d.get("desc", {}).get(opp, "")})
            e["w"] += 1
            e["src"].append(f"{me}:out")
        for opp in d.get("in", []):
            if opp == me:
                continue
            k = (opp, me)
            e = edges.setdefault(k, {"win": opp, "lose": me, "w": 0, "src": [],
                                     "desc": d.get("desc", {}).get(opp, "")})
            e["w"] += 1
            e["src"].append(f"{me}:in")

    out = []
    for e in edges.values():
        e["conf"] = "consensus" if e["w"] >= 2 else "one-sided"
        # src 形如 "公孙离:out"（在她页面的"压制英雄"里直说）
        # 或 "铠:in"（在铠页面的"被压制英雄"里反着列）—— 两者都是官方口径，只是出处页不同
        e["src"] = sorted(set(e["src"]))
        out.append(e)
    out.sort(key=lambda x: (-x["w"], x["win"], x["lose"]))

    payload = {
        "captured": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source_kind": "official_hero_relation",
        "source_url": "pvp.qq.com/web201605/herodetail/{ename}.shtml",
        "note": "官方只给『谁克谁』，不给条件/分段/版本阈值。全部属 L0 统计口径，可信度低。",
        "coverage": {"total": len(roster), "hit": len(hits), "miss": miss},
        "edges": out,
    }
    return payload


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roster-only", action="store_true")
    ap.add_argument("--relations", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if not (args.roster_only or args.relations):
        ap.print_help()
        return 2

    # 名录总是先确保存在
    rf = IDX / "roster.json"
    if args.roster_only or not rf.exists():
        raw = fetch_herolist()
        heroes = build_roster(raw)
        payload = {"version": "S45", "captured": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "source": LIST_JSON, "raw_count": len(raw),
                   "count": len(heroes), "heroes": heroes}
        rf.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        (KB / "94_英雄名录.md").write_text(md_roster(heroes), encoding="utf-8")
        print(f"roster -> {rf}  {len(heroes)} 英雄（原始 {len(raw)} 条）")
        if args.roster_only:
            return 0
    roster = json.loads(rf.read_text(encoding="utf-8"))["heroes"]

    if args.relations:
        rel = fetch_relations(roster, args.force)
        (IDX / "relations.json").write_text(
            json.dumps(rel, ensure_ascii=False, indent=1), encoding="utf-8")
        c = rel["coverage"]
        both = sum(1 for e in rel["edges"] if e["conf"] == "consensus")
        print(f"relations -> {IDX/'relations.json'}  "
              f"命中 {c['hit']}/{c['total']}  边 {len(rel['edges'])}"
              f"（双向 {both} / 单向 {len(rel['edges'])-both}）  缺页 {len(c['miss'])}")
        if c["miss"]:
            print("  缺页：" + "、".join(c["miss"][:20]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
