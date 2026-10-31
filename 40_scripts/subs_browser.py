#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""subs_browser.py — 用带登录态的浏览器批量取 B 站字幕（绕开 SESSDATA 缺失）

思路：在页面上下文里发 fetch，等于浏览器自己请求，签名和 cookie 全由浏览器搞定。
只导航一次到 bilibili.com，之后纯 fetch，比逐页 goto 快一个量级，也不容易被当爬虫。

用法：
  python subs_browser.py --bvid BV1xxx --bvid BV1yyy
  python subs_browser.py --from-json ../10_sources/creators_cache/ups.json --per-up 2
"""
from __future__ import annotations

import argparse
import json
import urllib.request
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = Path(r"C:/Users/Lenovo/.workbuddy/data/bilibili-video-summary/browser-profile")
OUT = Path(r"C:/Users/Lenovo/WorkBuddy/kog/10_sources/creators_cache/subs")
OUT.mkdir(parents=True, exist_ok=True)

JS = """
async ([bvid]) => {
  const j = async (u) => (await fetch(u, {credentials: 'include'})).json();
  const p = await j(`https://api.bilibili.com/x/player/pagelist?bvid=${bvid}`);
  if (p.code !== 0) return {err: 'pagelist ' + p.code, cid: 0};
  const cid = p.data[0].cid;
  const v2 = await j(`https://api.bilibili.com/x/player/v2?bvid=${bvid}&cid=${cid}`);
  if (v2.code !== 0) return {err: 'v2 ' + v2.code, cid};
  const subs = (v2.data.subtitle && v2.data.subtitle.subtitles) || [];
  if (!subs.length) return {err: 'no_sub', cid};
  subs.sort((a, b) => (String(a.lan).includes('zh') ? -1 : 1));
  let url = subs[0].subtitle_url || '';
  if (url.startsWith('//')) url = 'https:' + url;
  return {err: '', cid, lan: subs[0].lan, url};
}
"""

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0")


def pull(url: str, bvid: str) -> list[dict]:
    """字幕正文在 hdslb 域，页面内会被 CORS 拦，必须由 Python 侧带 Referer 拉。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": f"https://www.bilibili.com/video/{bvid}"})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.loads(r.read().decode("utf-8"))
    return [{"from": x.get("from"), "to": x.get("to"), "content": x.get("content")}
            for x in (d.get("body") or [])]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bvid", action="append", default=[])
    ap.add_argument("--from-json", type=Path)
    ap.add_argument("--per-up", type=int, default=2)
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()

    targets: list[str] = list(args.bvid)
    if args.from_json and args.from_json.exists():
        ups = json.loads(args.from_json.read_text(encoding="utf-8"))
        for u in ups:
            for v in u["vids"][:args.per_up]:
                if v.get("bvid"):
                    targets.append(v["bvid"])

    seen = set()
    targets = [b for b in targets if not (b in seen or seen.add(b))]
    todo = [b for b in targets if not (OUT / f"{b}.json").exists()]
    print(f"目标 {len(targets)}，已有缓存 {len(targets)-len(todo)}，待取 {len(todo)}")

    if not todo:
        return 0

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=args.headless,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto("https://www.bilibili.com/", wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(1200)
        logged = pg.evaluate("() => document.cookie.includes('SESSDATA')")
        print("登录态:", "有" if logged else "无（会取不到字幕）")

        ok = 0
        for i, bv in enumerate(todo, 1):
            try:
                r = pg.evaluate(JS, [bv])
            except Exception as e:
                print(f"  [{i}/{len(todo)}] {bv} ERR {type(e).__name__}")
                continue
            if r.get("err"):
                print(f"  [{i}/{len(todo)}] {bv} {r['err']}")
                (OUT / f"{bv}.json").write_text(
                    json.dumps({"bvid": bv, "err": r["err"], "body": []}, ensure_ascii=False),
                    encoding="utf-8")
            else:
                try:
                    body = pull(r["url"], bv)
                except Exception as e:
                    print(f"  [{i}/{len(todo)}] {bv} pull-ERR {type(e).__name__}")
                    body = []
                (OUT / f"{bv}.json").write_text(
                    json.dumps({"bvid": bv, "lan": r.get("lan"), "body": body},
                               ensure_ascii=False), encoding="utf-8")
                if body:
                    ok += 1
                print(f"  [{i}/{len(todo)}] {bv} {len(body)} cues")
            time.sleep(0.3)
        ctx.close()
    print(f"完成 {ok} 条 -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
