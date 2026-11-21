# -*- coding: utf-8 -*-
"""s61_patch_index.py — 抓取王者荣耀官网新闻索引里的「版本更新公告 / 英雄平衡性调整」条目。

源: https://pvp.qq.com/web201706/newsindex.shtml (GBK)
产出: 10_sources/official/patches/index.json  [{tid,title,date,kind}]
详情页是 JS 渲染，正文由 ego 脚本 ego_patch_fetch.mjs 二次抓取。
"""
import json, re, urllib.request
from pathlib import Path

BASE = Path(r"D:/Projects/kog")
OUT = BASE / "10_sources/official/patches"
OUT.mkdir(parents=True, exist_ok=True)
URL = "https://pvp.qq.com/web201706/newsindex.shtml"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/156.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://pvp.qq.com/"})
    return urllib.request.urlopen(req, timeout=25).read()


def main():
    t = fetch(URL).decode("gbk", "ignore")
    links = re.findall(r'<a[^>]+href="([^"]+newsdetail[^"]*)"[^>]*>(.*?)</a>', t, re.S)
    rows, seen = [], set()
    for href, txt in links:
        title = re.sub("<[^>]+>", "", txt).strip()
        tid = re.search(r"tid=(\d+)", href)
        if not tid:
            continue
        tid = tid.group(1)
        if tid in seen:
            continue
        kind = ""
        if "版本更新公告" in title:
            kind = "版本更新"
        elif "英雄平衡性调整" in title or "平衡性调整" in title:
            kind = "平衡性调整"
        elif "体验服" in title and "更新公告" in title:
            kind = "体验服更新"
        if not kind:
            continue
        seen.add(tid)
        dm = re.search(r"(\d{1,2})月(\d{1,2})日", title)
        date = f"{dm.group(1)}月{dm.group(2)}日" if dm else ""
        rows.append({"tid": tid, "title": title, "kind": kind, "date": date,
                     "url": f"https://pvp.qq.com/web201706/newsdetail.shtml?tid={tid}"})
    (OUT / "index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("patches", len(rows))
    for r in rows[:15]:
        print(" ", r["kind"], r["date"], r["title"][:40], r["tid"])


if __name__ == "__main__":
    main()
