# -*- coding: utf-8 -*-
"""目检第 27 项：同路对位矩阵页（#duel:mid）在桌面/手机上的表现。

用法：
  C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe shot_duel.py
"""
from pathlib import Path
from urllib.parse import quote
import sys

from playwright.sync_api import sync_playwright

SITE = Path(r"C:/Users/Lenovo/WorkBuddy/kog/site/index.html").as_uri()
OUT = Path(r"C:/Users/Lenovo/WorkBuddy/kog/site/_preview")
OUT.mkdir(parents=True, exist_ok=True)

# 需要在页面里点一下才能看到的态：网格视图 / 详情弹层 / 英雄页对位块
steps = [
    ("d_desk_list.png", 1440, 1100, "#duel:mid", None),
    ("d_desk_grid.png", 1440, 1100, "#duel:mid", "grid"),
    ("d_desk_modal.png", 1440, 1100, "#duel:mid", "modal"),
    ("d_desk_hero.png", 1440, 1400, "#H:" + quote("女娲"), None),
    ("d_mob_list.png", 390, 844, "#duel:mid", None),
    ("d_mob_grid.png", 390, 844, "#duel:mid", "grid"),
    ("d_mob_modal.png", 390, 844, "#duel:mid", "modal"),
    ("d_light_list.png", 1440, 1100, "#duel:mid", "light"),
]

errs = []
with sync_playwright() as p:
    b = p.chromium.launch()
    for name, w, h, frag, act in steps:
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(SITE + frag, wait_until="load")
        pg.wait_for_timeout(400)
        if act in ("grid", "light"):
            if act == "light":
                pg.evaluate("document.documentElement.dataset.theme='light'")
            pg.click("button.dtab[data-mode='grid']")
            pg.wait_for_timeout(250)
        elif act == "modal":
            # 从名单里第一个带档位的 chip 点开，拿真实数据而不是造
            pg.click("button.dchip")
            pg.wait_for_timeout(300)
        pg.screenshot(path=str(OUT / name), full_page=False)
        pg.close()
    b.close()

print("ok", len(steps), "console errors:", errs)
sys.exit(1 if errs else 0)
