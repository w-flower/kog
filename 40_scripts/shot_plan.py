# -*- coding: utf-8 -*-
"""目检：首页宫格的定位标签 + 英雄页的大局观块（开发用，不参与交付）。"""
from pathlib import Path
from playwright.sync_api import sync_playwright

SITE = Path(r"C:/Users/Lenovo/WorkBuddy/kog/site/index.html").as_uri()
OUT = Path(r"C:/Users/Lenovo/WorkBuddy/kog/site/_preview")
OUT.mkdir(parents=True, exist_ok=True)

shots = [
    ("p_desk_home.png", 1440, 1000, ""),
    ("p_desk_hero.png", 1440, 1000, "#H:%E5%BA%84%E5%91%A8"),
    ("p_mob_home.png", 390, 844, ""),
    ("p_mob_hero.png", 390, 844, "#H:%E7%8E%8B%E7%BB%B4"),
]

errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, h, frag in shots:
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(SITE + frag, wait_until="load")
        pg.wait_for_timeout(600)
        pg.screenshot(path=str(OUT / name), full_page=False)
        pg.close()
    b.close()
print("ok", len(shots), "console errors:", errs)
