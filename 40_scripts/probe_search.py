# -*- coding: utf-8 -*-
"""匿名探测：B 站搜索是否可用 + 抽到的视频有没有字幕。"""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

FK = [
    ("杨玉环", "中路"), ("貂蝉", "中路"), ("打野", "节奏"),
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0")
CK = Path(r"C:/Users/Lenovo/.workbuddy/data/bilibili-video-summary/bilibili_cookies.txt")


def cookie_header() -> str:
    if not CK.exists():
        return ""
    parts = []
    for ln in CK.read_text(encoding="utf-8").splitlines():
        if not ln or ln.startswith("#"):
            continue
        f = ln.split("\t")
        if len(f) >= 7:
            parts.append(f"{f[5]}={f[6]}")
    return "; ".join(parts)


def search(kw: str) -> dict:
    q = urllib.parse.urlencode({"search_type": "video", "keyword": kw, "page": 1})
    req = urllib.request.Request(
        f"https://api.bilibili.com/x/web-interface/search/type?{q}",
        headers={"User-Agent": UA, "Referer": "https://www.bilibili.com/",
                 "Cookie": cookie_header()})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


for kw, tag in FK:
    try:
        d = search(f"王者荣耀 {kw} 教学")
        code = d.get("code")
        res = ((d.get("data") or {}).get("result") or [])
        rows = [{"bvid": (x.get("bvid") or ""), "title": (x.get("title") or "").replace('<em class="keyword">', "").replace("</em>", ""),
                 "play": x.get("play"), "duration": x.get("duration")} for x in res[:3]]
        print(json.dumps({"kw": kw, "code": code, "n": len(res), "sample": rows},
                         ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"kw": kw, "error": f"{type(e).__name__}: {e}"}, ensure_ascii=False))
