# -*- coding: utf-8 -*-
"""给生成的站点截图做目检（开发用，不参与交付）。"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

SITE = Path(r"C:/Users/Lenovo/WorkBuddy/kog/site/index.html").as_uri()
OUT = Path(r"C:/Users/Lenovo/WorkBuddy/kog/site/_preview")
OUT.mkdir(parents=True, exist_ok=True)

shots = [
    ("desk_overview.png", 1440, 900, ""),
    ("desk_entry.png", 1440, 900, "#K-B01"),
    ("desk_cat.png", 1440, 900, "#cat:D"),
    ("mob_overview.png", 390, 844, ""),
]

with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, h, frag in shots:
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.goto(SITE + frag, wait_until="load")
        pg.wait_for_timeout(500)
        pg.screenshot(path=str(OUT / name), full_page=False)
        pg.close()
    b.close()
print("ok", len(shots))
