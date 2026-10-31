# -*- coding: utf-8 -*-
"""探针：匿名调 player 接口，看 subtitle 字段到底是"没有轨"还是"未登录"."""
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36 Edg/156.0.0.0")
CK = Path(r"C:/Users/Lenovo/.workbuddy/data/bilibili-video-summary/bilibili_cookies.txt")


def ck() -> str:
    if not CK.exists():
        return ""
    p = []
    for ln in CK.read_text(encoding="utf-8").splitlines():
        if ln and not ln.startswith("#"):
            f = ln.split("\t")
            if len(f) >= 7:
                p.append(f"{f[5]}={f[6]}")
    return "; ".join(p)


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Referer": "https://www.bilibili.com/", "Cookie": ck()})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


for bv in sys.argv[1:]:
    try:
        v = get(f"https://api.bilibili.com/x/web-interface/view?bvid={bv}")
        if v.get("code") != 0:
            print(f"{bv} view_fail code={v.get('code')} msg={v.get('message')}")
            continue
        d = v["data"]
        aid = d["aid"]
        cid = d["pages"][0]["cid"]
        title = d["title"][:34]
        pub = d["pubdate"]
        p = get(f"https://api.bilibili.com/x/player/v2?aid={aid}&cid={cid}")
        sub = ((p.get("data") or {}).get("subtitle") or {})
        tracks = sub.get("subtitles") or []
        print(json.dumps({
            "bv": bv, "title": title, "pubdate": pub,
            "pcode": p.get("code"),
            "need_login_subtitle": sub.get("need_login_subtitle"),
            "lan_list": [t.get("lan") for t in tracks],
            "has_url": [bool(t.get("subtitle_url")) for t in tracks],
        }, ensure_ascii=False))
    except Exception as e:
        print(f"{bv} ERR {type(e).__name__}: {str(e)[:120]}")
