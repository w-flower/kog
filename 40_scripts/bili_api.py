#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bili_api.py — B 站接口公共层（搜索 / UP 投稿列表 / 字幕）

踩过的坑：
  · space/arc/search 不带 wbi 签名直接 -799 风控
  · cookies.txt 里个别 value 带换行，拼 header 会炸，必须清控制字符
"""
from __future__ import annotations

import functools
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0")
CK = Path(r"C:/Users/Lenovo/.workbuddy/data/bilibili-video-summary/bilibili_cookies.txt")

MIXIN = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
         27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
         37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
         22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52]


def cookies() -> dict[str, str]:
    out: dict[str, str] = {}
    if not CK.exists():
        return out
    for ln in CK.read_text(encoding="utf-8").splitlines():
        if not ln or ln.startswith("#"):
            continue
        f = ln.split("\t")
        if len(f) >= 7:
            v = re.sub(r"[\r\n\x00-\x1f]", "", f[6])
            out[f[5]] = v
    return out


def cookie_header() -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies().items())


def _get(url: str, referer: str = "https://www.bilibili.com/") -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": referer, "Cookie": cookie_header()})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


@functools.lru_cache(maxsize=1)
def mixin_key() -> str:
    d = _get("https://api.bilibili.com/x/web-interface/nav")
    w = (d.get("data") or {}).get("wbi_img") or {}
    img = (w.get("img_url") or "").rsplit("/", 1)[-1].split(".")[0]
    sub = (w.get("sub_url") or "").rsplit("/", 1)[-1].split(".")[0]
    raw = img + sub
    return "".join(raw[i] for i in MIXIN)[:32]


def wbi(path: str, params: dict) -> str:
    p = dict(params)
    p["wts"] = int(time.time())
    q = urllib.parse.urlencode(
        sorted((k, re.sub(r"[!'()*]", "", str(v))) for k, v in p.items()))
    p["w_rid"] = hashlib.md5((q + mixin_key()).encode()).hexdigest()
    return f"https://api.bilibili.com/{path}?{urllib.parse.urlencode(p)}"


def search(kw: str, page: int = 1, order: str = "") -> list[dict]:
    p = {"search_type": "video", "keyword": kw, "page": page}
    if order:
        p["order"] = order
    d = _get("https://api.bilibili.com/x/web-interface/search/type?"
             + urllib.parse.urlencode(p))
    if d.get("code") != 0:
        raise RuntimeError(f"search code={d.get('code')} {d.get('message')}")
    return ((d.get("data") or {}).get("result") or [])


def uploads(mid: int, pages: int = 2, ps: int = 30) -> list[dict]:
    """UP 投稿列表（按发布时间倒序），带 wbi 签名。"""
    out: list[dict] = []
    for pn in range(1, pages + 1):
        url = wbi("x/space/arc/search", {"mid": mid, "ps": ps, "pn": pn,
                                         "order": "pubdate"})
        ref = f"https://space.bilibili.com/{mid}/video"
        try:
            d = _get(url, ref)
        except Exception:
            break
        if d.get("code") != 0:
            break
        vl = ((d.get("data") or {}).get("list") or {}).get("vlist") or []
        if not vl:
            break
        for v in vl:
            out.append({"bvid": v.get("bvid"), "title": v.get("title") or "",
                        "created": v.get("created") or 0,
                        "length": v.get("length") or "",
                        "play": v.get("play") or 0,
                        "desc": (v.get("description") or "")[:200]})
        time.sleep(0.8)
    return out


def cards(mid: int) -> dict:
    """UP 主卡片：粉丝 / 认证 / 签名 / 投稿数。老接口，无需 wbi。"""
    try:
        d = _get(f"https://api.bilibili.com/x/web-interface/card?mid={mid}&photo=false",
                 f"https://space.bilibili.com/{mid}")
        if d.get("code") != 0:
            return {}
        c = (d.get("data") or {}).get("card") or {}
        return {"fans": c.get("fans", 0),
                "sign": re.sub(r"\s+", " ", c.get("sign") or "")[:90],
                "official": (c.get("Official") or {}).get("title") or "",
                "archives": c.get("archive_count", 0)}
    except Exception:
        return {}


def subtitles(bvid: str) -> list[dict]:
    """取字幕轨 cues（from/to/content）。无字幕返回 []。"""
    d = _get(f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid_of(bvid)}",
             f"https://www.bilibili.com/video/{bvid}")
    if d.get("code") != 0:
        return []
    subs = ((d.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
    if not subs:
        return []
    # 优先中文轨
    subs.sort(key=lambda s: 0 if ("zh" in (s.get("lan") or "") or
                                  "中文" in (s.get("lan_doc") or "")) else 1)
    u = subs[0].get("subtitle_url") or ""
    if u.startswith("//"):
        u = "https:" + u
    try:
        dd = _get(u, f"https://www.bilibili.com/video/{bvid}")
    except Exception:
        return []
    return (dd.get("body") or [])


@functools.lru_cache(maxsize=256)
def cid_of(bvid: str) -> int:
    d = _get(f"https://api.bilibili.com/x/player/pagelist?bvid={bvid}")
    ps = (d.get("data") or [])
    return int(ps[0].get("cid") or 0) if ps else 0
