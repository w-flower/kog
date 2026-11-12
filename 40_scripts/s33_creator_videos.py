#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s33_creator_videos.py — 取某 UP 全部投稿 → 按英雄归类 → 接入现有管线

重点消化「梦辰溪_专注王者教学」(mid=1078678010) 的全部投稿。
先试 bili_api.uploads（纯 HTTP、快）；返回量偏少/风控则切登录态浏览器
页内 fetch 翻页（s30 套路），保证「一条不漏」。

产物：
  - 10_sources/creators_cache/mengchenxi_all.json     全量清单 + 归类结果
  - 10_sources/creators_cache/mengchenxi_batch.json   subs_browser --from-json 格式
  - 10_sources/creators_cache/mengchenxi_map.json     {bvid: 主英雄}
  - 10_sources/creators_cache/mengchenxi_multi.json   {bvid: [英雄...]}（多英雄视频）
  - 10_sources/creators_cache/hero_batch_map.json     追加合并（不覆盖原映射）
  - 10_sources/heroes/<英雄>/videos.json              合并追加（不覆盖其他 UP）
  - 50_logs/梦辰溪_投稿清单.md                         人类可读，供抽检

用法：
  python s33_creator_videos.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(r"C:/Users/Lenovo/WorkBuddy/kog")
CACHE = ROOT / "10_sources" / "creators_cache"
HEROES = ROOT / "10_sources" / "heroes"
CACHE.mkdir(parents=True, exist_ok=True)

MID = 1078678010
UP_NAME = "梦辰溪_专注王者教学"

sys.path.insert(0, str(ROOT / "40_scripts"))
import bili_api as B  # noqa: E402
import names as N  # noqa: E402

TEACH = ["教学", "思路", "技巧", "连招", "出装", "铭文", "全局", "讲解",
         "解析", "意识", "细节", "打法", "公式", "干货", "进阶"]


def ds(s: str) -> int:
    """'12:34' / '1:02:03' → 秒。"""
    p = [int(x) for x in re.findall(r"\d+", s or "")]
    if len(p) == 2:
        return p[0] * 60 + p[1]
    if len(p) == 3:
        return p[0] * 3600 + p[1] * 60 + p[2]
    return 0


def score_of(title: str) -> int:
    return sum(1 for w in TEACH if w in title) * 10


def norm(raw: dict) -> dict:
    """统一成 s8_harvest.videos.json 的条目格式。"""
    title = B.clean_text(raw.get("title") or "")
    length = raw.get("length") or ""
    return {
        "bvid": raw.get("bvid"),
        "title": title,
        "up": UP_NAME,
        "mid": MID,
        "dur": ds(length),
        "play": int(raw.get("play") or 0),
        "pub": int(raw.get("created") or 0),
        "score": score_of(title),
    }


# ── 浏览器兜底：登录态页内 fetch 翻页 ──────────────────────────────
# 关键点：x/space/arc/search 即使带登录 cookie 也必须 wbi 签名，否则 -799。
# 所以「Python 端用 bili_api.wbi 签名出完整 URL → 浏览器端带着登录 cookie 去 fetch」。
PROFILE = Path(r"C:/Users/Lenovo/.workbuddy/data/bilibili-video-summary/browser-profile")
JS_ARC = """
async ([url]) => {
  const r = await fetch(url, {credentials: 'include'});
  return await r.json();
}
"""


def fetch_all_browser() -> list[dict]:
    from playwright.sync_api import sync_playwright
    out: list[dict] = []
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=True,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto("https://www.bilibili.com/", wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(1500)
        cookie_ok = pg.evaluate(
            "() => fetch('https://api.bilibili.com/x/web-interface/nav', "
            "{credentials:'include'}).then(r=>r.json()).then(d=>d.data&&d.data.isLogin)")
        print("登录态(nav.isLogin):", cookie_ok)
        # 预热：先打一个 search/type（该接口稳定），给会话"热身"，
        # 否则 x/space/arc/search 首调极易 -799。
        try:
            wu = B.wbi("x/web-interface/wbi/search/type",
                       {"search_type": "video", "keyword": "王者荣耀", "page": 1})
            pg.evaluate(JS_ARC, [wu])
            time.sleep(2.5)
        except Exception as e:
            print("  预热调用异常（忽略）:", e)
        pn, fails = 1, 0
        while True:
            signed = B.wbi("x/space/wbi/arc/search",
                           {"mid": MID, "ps": 30, "pn": pn})
            d = None
            try:
                d = pg.evaluate(JS_ARC, [signed])
            except Exception as e:
                print(f"  pn={pn} fetch ERR {type(e).__name__}")
                time.sleep(3)
                fails += 1
                if fails >= 5:
                    break
                continue
            if not d or d.get("code") != 0:
                print(f"  arc search code={d.get('code') if d else 'None'} {d.get('message') if d else ''}")
                if d and d.get("code") == -799:
                    print("  -799 风控，冷却 15s 后重试本页")
                    time.sleep(15)
                    fails += 1
                    if fails >= 5:
                        print("  连续 5 次 -799，停止。冷却后重跑本脚本即可续跑。")
                        break
                    continue
                break
            fails = 0
            vl = ((d.get("data") or {}).get("list") or {}).get("vlist") or []
            if not vl:
                break
            out.extend(vl)
            print(f"  pn={pn} 取到 {len(vl)} 条，累计 {len(out)}")
            pn += 1
            time.sleep(2.5)
        ctx.close()
    return out


def fetch_all() -> tuple[list[dict], str]:
    """先 uploads，偏少则浏览器兜底。返回 (raw_vlist, source_tag)。"""
    try:
        up = B.uploads(MID, pages=15, ps=30)
        if len(up) >= 20:
            print(f"uploads 取到 {len(up)} 条（纯 HTTP）。")
            return up, "uploads"
    except Exception as e:
        print(f"uploads 异常 {type(e).__name__}: {e}")
    print("→ 切浏览器页内 fetch 翻页")
    return fetch_all_browser(), "browser"


def merge_hero_video(hero: str, entry: dict) -> None:
    d = HEROES / hero
    d.mkdir(parents=True, exist_ok=True)
    fp = d / "videos.json"
    rows = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else []
    seen = {r.get("bvid") for r in rows}
    if entry["bvid"] not in seen:
        rows.append(entry)
        rows.sort(key=lambda r: (-r.get("score", 0), -r.get("dur", 0)))
        fp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--browser-only", action="store_true", help="跳过 uploads 直接浏览器")
    args = ap.parse_args()

    nm = N.load()
    raw, src = (fetch_all_browser(), "browser") if args.browser_only else fetch_all()
    raw = [r for r in raw if r.get("bvid")]
    print(f"\n原始投稿 {len(raw)} 条（来源 {src}）")

    all_manifest: list[dict] = []
    batch_vids: list[dict] = []
    mmap: dict[str, str] = {}
    multi: dict[str, list[str]] = {}
    hero_count: dict[str, int] = {}

    for r in raw:
        e = norm(r)
        bv = e["bvid"]
        heroes = nm.find_all(e["title"])
        if len(heroes) >= 2:
            primary = heroes[0]
            multi[bv] = heroes
            mmap[bv] = primary
            batch_vids.append({"bvid": bv})
            merge_hero_video(primary, e)
            hero_count[primary] = hero_count.get(primary, 0) + 1
            tag = "MULTI"
        elif len(heroes) == 1:
            h = heroes[0]
            mmap[bv] = h
            batch_vids.append({"bvid": bv})
            merge_hero_video(h, e)
            hero_count[h] = hero_count.get(h, 0) + 1
            tag = h
        else:
            tag = "general"
            batch_vids.append({"bvid": bv})  # 通用/BP 视频也取字幕，供 BP 体系页引用
        all_manifest.append({"bvid": bv, "title": e["title"], "hero": tag,
                             "multi": heroes, "play": e["play"], "dur": e["dur"]})

    # 落盘
    (CACHE / "mengchenxi_all.json").write_text(
        json.dumps(all_manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (CACHE / "mengchenxi_batch.json").write_text(
        json.dumps([{"vids": batch_vids}], ensure_ascii=False), encoding="utf-8")
    (CACHE / "mengchenxi_map.json").write_text(
        json.dumps(mmap, ensure_ascii=False, indent=1), encoding="utf-8")
    (CACHE / "mengchenxi_multi.json").write_text(
        json.dumps(multi, ensure_ascii=False, indent=1), encoding="utf-8")

    # 追加合并进 hero_batch_map.json（不覆盖原映射）
    hbm = CACHE / "hero_batch_map.json"
    base = json.loads(hbm.read_text(encoding="utf-8")) if hbm.exists() else {}
    base.update(mmap)
    hbm.write_text(json.dumps(base, ensure_ascii=False, indent=1), encoding="utf-8")

    # 人类可读清单
    lines = [f"# 梦辰溪_专注王者教学 投稿清单（mid {MID}）\n",
             f"- 来源：{src} | 原始投稿 {len(raw)} 条 | 命中英雄 {len(mmap)} 条 | 通用 {len(raw)-len(mmap)} 条\n",
             f"- 多英雄视频 {len(multi)} 条\n", "\n## 按英雄覆盖量（降序）\n"]
    for h, c in sorted(hero_count.items(), key=lambda kv: -kv[1]):
        lines.append(f"- {h}: {c}")
    lines.append("\n## 全部投稿\n")
    for m in all_manifest:
        flag = m["hero"] if m["hero"] != "general" else "通用"
        lines.append(f"- [{flag}] {m['bvid']} {m['title']}")
    (ROOT / "50_logs" / "梦辰溪_投稿清单.md").write_text(
        "\n".join(lines), encoding="utf-8")

    print(f"\n命中英雄 {len(mmap)} 条，覆盖英雄 {len(hero_count)} 个：")
    for h, c in sorted(hero_count.items(), key=lambda kv: -kv[1]):
        print(f"  {h}: {c}")
    print(f"通用攻略 {len(raw)-len(mmap)} 条，多英雄 {len(multi)} 条")
    print("产物：mengchenxi_all/batch/map/multi.json + hero_batch_map.json + 各英雄 videos.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
