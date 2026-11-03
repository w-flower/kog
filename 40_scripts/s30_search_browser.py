#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s30_search_browser.py — 用登录态浏览器补采被风控英雄的候选视频

背景：s8_harvest 跑到第 18 个英雄时触发 B 站风控，匿名 wbi 搜索返回
data 只有 v_voucher（code=0 但 result 空）。登录态搜索不走这个坑。

做法：persistent context 打开一次 bilibili.com，之后全部在页面上下文里
fetch wbi 搜索接口（签名和 cookie 由浏览器自己搞定），过滤逻辑完全复用
s8_harvest.harvest——只把 B.search 换成浏览器版。

用法：
  "C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
      s30_search_browser.py --hero 马超 云缨
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import bili_api as B
import s8_harvest as S

PROFILE = Path(r"C:/Users/Lenovo/.workbuddy/data/bilibili-video-summary/browser-profile")
OUT = S.OUT

JS = """
async ([kw, page, order]) => {
  const p = new URLSearchParams({search_type:'video', keyword:kw, page:String(page)});
  if (order) p.set('order', order);
  const r = await fetch('https://api.bilibili.com/x/web-interface/wbi/search/type?' + p,
                        {credentials:'include'});
  return await r.json();
}
"""


def make_browser_search(pg):
    state = {"n": 0}

    def browser_search(kw: str, page: int = 1, order: str = "") -> list[dict]:
        state["n"] += 1
        if state["n"] % 12 == 0:
            time.sleep(3.0)                     # 每 12 次 query 歇一下
        d = pg.evaluate(JS, [kw, page, order])
        if d.get("code") != 0:
            raise RuntimeError(f"search code={d.get('code')} {d.get('message')}")
        return ((d.get("data") or {}).get("result") or [])
    return browser_search


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero", nargs="+", required=True)
    args = ap.parse_args()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=True,
            viewport={"width": 1400, "height": 900},
            args=["--disable-blink-features=AutomationControlled"])
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto("https://www.bilibili.com/", wait_until="domcontentloaded",
                timeout=45000)
        pg.wait_for_timeout(1200)
        logged = pg.evaluate("() => document.cookie.includes('SESSDATA')")
        print("登录态:", "有" if logged else "无（匿名搜也可能被风控）")

        B.search = make_browser_search(pg)
        for h in args.hero:
            print(f"\n=== {h} ===")
            rows = S.harvest(h)
            d = OUT / h
            d.mkdir(parents=True, exist_ok=True)
            (d / "videos.json").write_text(
                json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {len(rows)} 条 / {len({r['up'] for r in rows})} 个 UP")
        ctx.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
