#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""login_once.py — 打开浏览器让用户扫码登录一次，成功即落盘登录态。

用法：python login_once.py [--timeout 240]
成功后在 profile 目录持久保存 cookie，后续 subs_browser.py 直接复用。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROFILE = Path(r"C:/Users/Lenovo/.workbuddy/data/bilibili-video-summary/browser-profile")
LOG = Path(r"C:/Users/Lenovo/WorkBuddy/kog/50_logs/login_once.log")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    LOG.parent.mkdir(parents=True, exist_ok=True)

    def say(m: str) -> None:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + m + "\n")
        print(m, flush=True)

    say("启动浏览器…")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE), headless=False,
            viewport={"width": 900, "height": 720},
            args=["--disable-blink-features=AutomationControlled",
                  "--start-maximized"])
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto("https://www.bilibili.com/", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(800)
        if "SESSDATA" in pg.evaluate("() => document.cookie"):
            say("已登录，无需扫码")
            ctx.close()
            return 0
        pg.goto("https://passport.bilibili.com/login",
                wait_until="domcontentloaded", timeout=60000)
        say("请扫码登录（窗口已弹出）…")
        t0 = time.time()
        while time.time() - t0 < args.timeout:
            pg.wait_for_timeout(2000)
            try:
                if "SESSDATA" in (pg.context.cookies() and
                                  "; ".join(c["name"] for c in pg.context.cookies())):
                    pass
                names = {c["name"] for c in pg.context.cookies()}
                if "SESSDATA" in names:
                    say(f"登录成功，用时 {int(time.time()-t0)}s")
                    pg.wait_for_timeout(1500)
                    ctx.close()
                    return 0
            except Exception:
                pass
        say("超时未登录")
        ctx.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
