# -*- coding: utf-8 -*-
"""dump_cdp_cookies.py — 从可调试的 Edge 里取出 B 站 cookie，写成 cookies.txt

由 Edge 自己解密（App-Bound 加密只能这么做），我们只通过 CDP 拿解密后的值。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BILI = Path(r"C:/Users/Lenovo/.workbuddy/skills/bilibili-video-summary/scripts")
sys.path.insert(0, str(BILI))
from config import DATA_DIR  # noqa: E402

OUT = Path(DATA_DIR) / "bilibili_cookies.txt"
PORT = sys.argv[1] if len(sys.argv) > 1 else "9223"
HEADER = "# Netscape HTTP Cookie File\n# exported by kog/dump_cdp_cookies.py\n\n"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        ctx = browser.contexts[0]
        ctx.new_page().goto("https://www.bilibili.com/", wait_until="domcontentloaded", timeout=30000)
        cookies = ctx.cookies()
        browser.close()

    bili = [c for c in cookies if "bilibili" in c.get("domain", "")]
    doms: dict[str, int] = {}
    for c in cookies:
        d = c.get("domain", "")
        doms[d] = doms.get(d, 0) + 1
    top = sorted(doms.items(), key=lambda kv: -kv[1])[:12]

    if not bili:
        print(json.dumps({"ok": False, "error": "no_bilibili_cookie",
                          "total": len(cookies), "top_domains": top},
                         ensure_ascii=False, indent=2))
        return 5

    lines = [HEADER]
    for c in bili:
        dom = c["domain"]
        flag = "TRUE" if dom.startswith(".") else "FALSE"
        exp = int(c.get("expires") or 0)
        if exp < 0:
            exp = 0
        lines.append("\t".join([dom, flag, c.get("path", "/"),
                                "TRUE" if c.get("secure") else "FALSE",
                                str(exp), c["name"], c["value"]]) + "\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(lines), encoding="utf-8")

    names = sorted({c["name"] for c in bili})
    sess = [c for c in bili if c["name"] == "SESSDATA"]
    import datetime
    exp_s = "MISSING"
    if sess:
        e = int(sess[0].get("expires") or 0)
        exp_s = datetime.datetime.fromtimestamp(e).strftime("%Y-%m-%d %H:%M") if e > 0 else "session"
    print(json.dumps({"ok": True, "out": str(OUT), "count": len(bili),
                      "total_all": len(cookies), "top_domains": top,
                      "has_sessdata": bool([c for c in bili if c["name"] == "SESSDATA"]),
                      "sessdata_expires": exp_s, "names": names[:15]},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
