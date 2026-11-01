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
    """搜索。2026-11 起旧接口 x/web-interface/search/type 未登录必 412，
    改走 wbi 签名的 x/web-interface/wbi/search/type（无 SESSDATA 也能用）。"""
    p = {"search_type": "video", "keyword": kw, "page": page}
    if order:
        p["order"] = order
    d = _get(wbi("x/web-interface/wbi/search/type", p))
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


# ══════════════════════════════════════════════════════════════
# 节流 / 重试 / 清洗 —— 专栏链要用的三件套
#
# 2026-11 实测：专栏搜索与全文接口匿名能跑，但 -352（风控）极容易触发。
# 连发 3 条成功率约 1/3；间隔拉到 8 秒 + 指数退避后基本稳定。
# 所以这里不是"优雅重试"，是"必须重试"——不加就是大半请求白跑。
# ══════════════════════════════════════════════════════════════

RETRY_CODES = {-352, -412, -799, -509, -504}
GAP = {"search": 8.0, "article": 14.0, "default": 1.0}
_last_call: dict[str, float] = {}


def throttle(kind: str = "default", gap: float | None = None) -> None:
    """同类请求之间强制拉开间隔。kind 不同的通道互不影响。"""
    g = GAP.get(kind, GAP["default"]) if gap is None else gap
    wait = _last_call.get(kind, 0.0) + g - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_call[kind] = time.time()


def wbi_get(path: str, params: dict, referer: str = "https://www.bilibili.com/",
            tries: int = 5, kind: str = "default", backoff: float = 7.0) -> dict:
    """带节流 + 指数退避的 wbi GET。每次重试都重新签名（wts 会过期）。

    返回最后一次的原始响应（含 code），由调用方决定算不算失败——
    这里不抛异常，是为了让上层能区分"没找到"和"被风控"。
    """
    last: dict = {"code": -1, "message": "no attempt"}
    for i in range(tries):
        throttle(kind)
        try:
            d = _get(wbi(path, params), referer)
        except Exception as exc:                      # 网络层错误也要退避重试
            last = {"code": -1, "message": f"{type(exc).__name__}: {exc}"}
            if i < tries - 1:
                time.sleep(backoff * (i + 1))
            continue
        if d.get("code") not in RETRY_CODES:
            return d
        last = d
        if i < tries - 1:
            time.sleep(backoff * (i + 1))
    return last


# 搜索结果是富文本，标题带 <em class="keyword">，直接进库会污染别名匹配
_TAG_RE = re.compile(r"</?[a-zA-Z][^<>]{0,120}>")
_ENT = {"&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'",
        "&apos;": "'", "&nbsp;": " ", "&ensp;": " ", "&emsp;": " ",
        "&ldquo;": "“", "&rdquo;": "”", "&mdash;": "—", "&middot;": "·"}


def clean_text(s: str) -> str:
    """去标签 / 去实体 / 去零宽字符 / 压空白。标题、摘要、正文都过这一道。"""
    s = _TAG_RE.sub("", s or "")
    for k, v in _ENT.items():
        s = s.replace(k, v)
    s = re.sub(r"[\u200b-\u200f\u202a-\u202e\ufeff]", "", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t\u3000]+", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def search_articles(kw: str, page: int = 1, tries: int = 4) -> list[dict]:
    """搜专栏。返回清洗过的元数据；被风控到彻底失败时抛 RuntimeError。

    字段比视频搜索少，但 `id`（cv 号）够后续取全文。
    """
    d = wbi_get("x/web-interface/wbi/search/type",
                {"search_type": "article", "keyword": kw, "page": page},
                kind="search", tries=tries)
    if d.get("code") != 0:
        raise RuntimeError(f"article search code={d.get('code')} {d.get('message')}")
    out = []
    for r in ((d.get("data") or {}).get("result") or []):
        cv = str(r.get("id") or "")
        if not cv.isdigit():
            continue
        out.append({
            "cv": cv,
            "title": clean_text(r.get("title")),
            "desc": clean_text(r.get("desc") or ""),
            "author": clean_text(r.get("author") or ""),
            "mid": r.get("mid") or 0,
            "view": r.get("view") or 0,
            "like": r.get("like") or 0,
            "pub_time": r.get("pub_time") or 0,
            "url": f"https://www.bilibili.com/read/cv{cv}",
        })
    return out


def _para_text(p: dict) -> str:
    """段落正文。opus 新格式是 {"nodes":[{"word":{"words":"..."}}]}，
    老格式是纯字符串，两种都要能吃。"""
    t = p.get("text")
    if isinstance(t, str):
        return t
    if not isinstance(t, dict):
        return ""
    out: list[str] = []
    for n in (t.get("nodes") or []):
        if not isinstance(n, dict):
            continue
        w = n.get("word")
        if isinstance(w, dict) and w.get("words"):
            out.append(str(w["words"]))
        elif isinstance(w, str):
            out.append(w)
    return "".join(out)


def article_view(cv: str | int, tries: int = 3) -> dict:
    """专栏全文。返回 {cv,title,author,text,url}，text 是纯文本段落。

    正文在 data.opus.content.paragraphs[]，每段是 nodes 树，不是纯字符串。
    老文章没有 opus 层，退回 data.content（HTML），同样清洗成纯文本。
    """
    cv = str(cv).lstrip("cv")
    # 实测：-352 在这个接口上多是"这篇要登录/已失效"，重试 5 次和 2 次结果一样，
    # 只是白等 60 秒。给 3 次就够，把时间让给下一篇。
    d = wbi_get("x/article/view", {"id": cv},
                referer=f"https://www.bilibili.com/read/cv{cv}",
                kind="article", tries=tries, backoff=5.0)
    if d.get("code") != 0:
        raise RuntimeError(f"article view cv{cv} code={d.get('code')} {d.get('message')}")
    data = d.get("data") or {}
    opus = data.get("opus") or {}
    paras = ((opus.get("content") or {}).get("paragraphs") or [])
    chunks = []
    for p in paras:
        t = _para_text(p)
        if t:
            chunks.append(t)
        elif p.get("para_type") == 2:
            chunks.append("[图]")
    text = "\n\n".join(chunks)
    if not text:
        text = clean_text(data.get("content") or "")
    return {
        "cv": cv,
        "title": clean_text(opus.get("title") or data.get("title") or ""),
        "author": clean_text(((opus.get("author") or {}).get("name")
                              or (data.get("author") or {}).get("name") or "")),
        "pub_time": data.get("publish_time") or data.get("ctime") or 0,
        "text": clean_text(text),
        "url": f"https://www.bilibili.com/read/cv{cv}",
    }


# ── 落盘缓存：抓一次就别再抓 ────────────────────────────────
# 放在 10_sources/ 下（该目录已 gitignore，正文有版权，不能进仓库）
CACHE = Path(__file__).resolve().parent.parent / "10_sources" / "bili_cache"


def cache_path(kind: str, key: str) -> Path:
    return CACHE / kind / f"{re.sub(r'[^0-9A-Za-z_.-]', '_', str(key))}.json"


def cache_get(kind: str, key: str) -> dict | None:
    p = cache_path(kind, key)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def cache_put(kind: str, key: str, obj: dict) -> None:
    p = cache_path(kind, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def cached(kind: str, key: str, fn, force: bool = False):
    """kind/key 命中缓存就直接返回，否则调 fn() 并落盘。"""
    if not force:
        hit = cache_get(kind, key)
        if hit is not None:
            return hit
    obj = fn()
    if obj:
        cache_put(kind, key, obj)
    return obj
