#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s0_creators.py — 教学 UP 主「质量」评估（不看播放量）

为什么不用播放量：高播放 ≈ 情绪 + 流量分发，和「讲得对不对」几乎无关。
这里用字幕文本当证据，衡量四个能力：

  条件密度  如果/只要/除非/当…时   → 有没有给判据（而不是"视情况"）
  因果密度  因为/所以/导致/原因是   → 有没有讲机制
  数字密度  秒/%/码/身位/次数       → 有没有给阈值（判据必须可执行）
  术语浓度  机制/判定/前摇/冷却/收益  → 是不是在讲系统而不是喊口号
  空话密度  无脑/记住就行/直接上     → 扣分项

评分用**样本内百分位**归一化，不设拍脑袋的阈值。

用法：
  python s0_creators.py --stage pool      # 只捞候选 UP
  python s0_creators.py --stage all       # 全流程（含字幕测评，慢）
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import bili_api as B

OUT = Path(r"C:/Users/Lenovo/WorkBuddy/kog/10_sources")
CACHE = OUT / "creators_cache"
CACHE.mkdir(parents=True, exist_ok=True)

S45 = 1789056000  # 2026-09-23 00:00 (S45 首日)

KWS = [
    "王者荣耀 教学", "王者荣耀 意识 教学", "王者荣耀 对线 教学",
    "王者荣耀 上分 思路", "王者荣耀 打野 教学", "王者荣耀 中路 教学",
    "王者荣耀 辅助 教学", "王者荣耀 复盘 教学", "王者荣耀 运营 教学",
    "王者荣耀 bp 教学",
]
EXCLUDE = ["自走棋", "模拟战", "棋手", "吃鸡", "皮肤", "抽奖", "开箱",
           "英雄联盟", "LOL", "端游", "云顶", "高光", "集锦", "搞笑", "沙雕",
           "直播回放", "录播", "赛事", "KPL"]
TEACH = ["教学", "思路", "复盘", "整局", "意识", "细节", "对线", "运营",
         "上分", "节奏", "开局", "转线", "大局观", "讲解", "解析", "公式"]

# ---------- 字幕文本指标 ----------
PAT = {
    "cond": re.compile(r"如果|只要|除非|否则|一旦|假如|当.{0,8}的时候|什么情况下"),
    "causal": re.compile(r"因为|所以|由于|导致|原因是|这才|因此|意味着"),
    "num": re.compile(r"\d+\s*秒|\d+\s*%|百分之|\d+\s*码|\d+\s*个身位|"
                      r"两个身位|三秒|五秒|\d+\s*下|\d+\s*层|\d+\s*分钟"),
    "jargon": re.compile(r"机制|判定|前摇|后摇|冷却|收益|期望|视野|仇恨|"
                         r"护甲|魔抗|减伤|霸体|免伤|攻速|移速|经济|经验|"
                         r"血线|身位|卡位|拆解|变量|数值|蓝量|能量"),
    "empty": re.compile(r"无脑|记住就行|直接上|反正|就是干|简单粗暴|"
                        r"不用想|闭眼|随便玩|这波不亏"),
}
W = {"cond": 0.30, "causal": 0.25, "num": 0.25, "jargon": 0.20, "empty": -0.45}


def dur_s(s: str) -> int:
    p = [int(x) for x in re.findall(r"\d+", s or "")]
    if len(p) == 2:
        return p[0] * 60 + p[1]
    if len(p) == 3:
        return p[0] * 3600 + p[1] * 60 + p[2]
    return 0


def clean(t: str) -> str:
    return re.sub(r"<[^>]+>", "", t or "")


# 游戏语音/ASR 噪音：字幕轨若全是这些，说明转写的是游戏音效而非 UP 说话
NOISE = re.compile(r"技能正在冷却|请求集合|发起进攻|开始撤退|大招还未升级|"
                   r"集合进攻|进攻敌方|大招已经好了|正在冷却|Enemy has been|"
                   r"Ally has been|Killing spree|First blood|已击杀|敌人已|"
                   r"你已阵亡|敌方水晶|我方水晶|收到|进攻主宰|发起集合")
# 话题相关性：教学讲解必然高频出现这些词；没有就是跑题（修电脑/开箱/聊天）
TOPIC = re.compile(r"经济|兵线|视野|防御塔|打野|辅助|中路|对抗路|发育路|"
                   r"装备|铭文|技能|对线|团战|野区|蓝区|红区|阵容|大招|"
                   r"闪现|位移|控制|输出|前排|后排|走位|支援")


def validity(txt: str) -> tuple[bool, str, float]:
    n = len(txt)
    if n < 1200:
        return False, f"太短{round(n/1000,1)}k", 0.0
    noise = len(NOISE.findall(txt)) * 3 / n          # 每句约 3 字
    topic = len(TOPIC.findall(txt)) / n * 1000
    if noise > 0.10:
        return False, f"噪音{noise:.0%}", noise
    if topic < 4:
        return False, f"跑题(术语{topic:.1f}/k)", 0.0
    return True, "", noise


def serial_key(title: str) -> str:
    """系列标识：去掉 【】书名号内容、第N期、数字后取前 8 字。"""
    t = re.sub(r"[【\[](.{0,10}?)[】\]]", "", title)
    t = re.sub(r"(第\s*\d+\s*[期篇集话弹])|(EP?\d+)", "", t, flags=re.I)
    t = re.sub(r"[|｜丨:：\-—·,，。!！?？\s]", "", t)
    return t[:8]


# ---------- stage 1: 捞候选 ----------
def stage_pool(pages: int = 2) -> list[dict]:
    f = CACHE / "pool.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    vids: list[dict] = []
    seen: set[str] = set()
    rounds = [("", KWS), ("click", KWS[:6]), ("pubdate", KWS[:6])]
    for order, kws in rounds:
        for kw in kws:
            for pg in range(1, pages + 1):
                try:
                    res = B.search(kw, pg, order)
                except Exception as e:
                    print(f"[WARN] {kw}/{order} p{pg}: {e}", file=sys.stderr)
                    continue
                for x in res:
                    bv = x.get("bvid") or ""
                    if not bv or bv in seen:
                        continue
                    seen.add(bv)
                    title = clean(x.get("title"))
                    tag = x.get("tag") or ""
                    if "王者荣耀" not in tag and "王者荣耀" not in title:
                        continue
                    if any(w in title for w in EXCLUDE):
                        continue
                    d = dur_s(x.get("duration"))
                    if d < 480:
                        continue
                    vids.append({"bvid": bv, "title": title,
                                 "play": int(x.get("play") or 0),
                                 "pubdate": int(x.get("pubdate") or 0),
                                 "dur": d, "author": x.get("author", ""),
                                 "mid": int(x.get("mid") or 0)})
                time.sleep(1.2)
            time.sleep(0.8)
        print(f"[pool] round={order or 'rel'} -> {len(vids)}", file=sys.stderr)

    f.write_text(json.dumps(vids, ensure_ascii=False), encoding="utf-8")
    return vids


# ---------- stage 2: 按 UP 名查其近期投稿 ----------
def stage_ups(pool: list[dict], min_n: int = 2, top: int = 26) -> list[dict]:
    f = CACHE / "ups.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))

    by: dict[str, list[dict]] = defaultdict(list)
    for v in pool:
        by[v["author"]].append(v)
    cand = [(a, vs) for a, vs in by.items() if len(vs) >= min_n]
    cand.sort(key=lambda kv: -len(kv[1]))
    cand = cand[:top]

    out = []
    for i, (name, vs) in enumerate(cand, 1):
        mid = vs[0]["mid"]
        # 用搜索接口按 UP 名拉近期投稿（绕开 space 接口的 412）
        recent: list[dict] = []
        try:
            for pg in (1, 2):
                for x in B.search(name, pg, "pubdate"):
                    if int(x.get("mid") or 0) != mid:
                        continue
                    recent.append({
                        "bvid": x.get("bvid"), "title": clean(x.get("title")),
                        "pubdate": int(x.get("pubdate") or 0),
                        "dur": dur_s(x.get("duration")),
                        "play": int(x.get("play") or 0)})
                time.sleep(1.0)
        except Exception as e:
            print(f"[WARN] ups {name}: {e}", file=sys.stderr)

        allv = {v["bvid"]: v for v in vs}
        for v in recent:
            allv.setdefault(v["bvid"], v)
        vv = [v for v in allv.values() if v.get("bvid")]
        s45 = [v for v in vv if (v.get("pubdate") or 0) >= S45]

        cards = B.cards(mid) if hasattr(B, "cards") else {}
        series = defaultdict(int)
        for v in vv:
            series[serial_key(v["title"])] += 1
        out.append({
            "author": name, "mid": mid,
            "n": len(vv), "n_s45": len(s45),
            "avg_min": round(sum(v["dur"] for v in vv) / max(len(vv), 1) / 60, 1),
            "series_ratio": round(max(series.values()) / max(len(vv), 1), 2),
            "series_name": max(series, key=series.get),
            "teach_r": round(sum(1 for v in vv
                                 if any(w in v["title"] for w in TEACH)) / max(len(vv), 1), 2),
            "fans": cards.get("fans", 0), "official": cards.get("official", ""),
            "sign": cards.get("sign", ""),
            "vids": sorted(vv, key=lambda v: (-v["dur"], -(v.get("pubdate") or 0)))[:6],
        })
        print(f"  [{i}/{len(cand)}] {name} n={len(vv)} s45={len(s45)} "
              f"avg={out[-1]['avg_min']}m serial={out[-1]['series_ratio']}", file=sys.stderr)
        time.sleep(1.0)

    f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# ---------- stage 3: 字幕文本测评 ----------
def load_subs(bvid: str) -> list[dict]:
    """优先读 subs_browser.py 落盘的本地字幕（API 侧 SESSDATA 拿不到轨）。"""
    f = CACHE / "subs" / f"{bvid}.json"
    if not f.exists():
        return []
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return []
    return d.get("body") or []


def stage_text(ups: list[dict], per_up: int = 2) -> list[dict]:
    f = CACHE / "text.json"
    done: dict[str, dict] = {}
    if f.exists():
        done = {d["mid"]: d for d in json.loads(f.read_text(encoding="utf-8"))}

    for i, u in enumerate(ups, 1):
        if str(u["mid"]) in done:
            continue
        texts: list[str] = []
        used: list[dict] = []
        dropped: list[str] = []
        for v in u["vids"]:
            if len(texts) >= per_up:
                break
            cues = load_subs(v["bvid"])
            if not cues:
                dropped.append(f"{v['bvid']}:无字幕")
                continue
            txt = "".join(c.get("content", "") for c in cues)
            ok, why, _ = validity(txt)
            if not ok:
                dropped.append(f"{v['bvid']}:{why}")
                continue
            texts.append(txt)
            used.append({"bvid": v["bvid"], "title": v["title"], "chars": len(txt)})
            time.sleep(0.6)
        if not texts:
            done[str(u["mid"])] = {"mid": u["mid"], "author": u["author"],
                                   "chars": 0, "raw": {}, "used": [], "dropped": dropped,
                                   "n_valid": 0}
            continue
        joined = "\n".join(texts)
        n = len(joined)
        raw = {k: round(len(p.findall(joined)) / n * 1000, 2) for k, p in PAT.items()}
        raw["chars"] = n
        done[str(u["mid"])] = {"mid": u["mid"], "author": u["author"],
                               "chars": n, "raw": raw, "used": used,
                               "dropped": dropped, "n_valid": len(texts)}
        print(f"  [{i}/{len(ups)}] {u['author']} {n}字 {raw}", file=sys.stderr)
        time.sleep(0.6)
        f.write_text(json.dumps(list(done.values()), ensure_ascii=False, indent=1),
                     encoding="utf-8")
    return list(done.values())


def pct(vals: list[float], x: float) -> float:
    """样本内百分位 0-1（并列取中位）。"""
    if not vals:
        return 0.0
    lo = sum(1 for v in vals if v < x)
    eq = sum(1 for v in vals if v == x)
    return (lo + eq / 2) / len(vals)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all",
                    choices=["pool", "ups", "text", "all"])
    ap.add_argument("--per-up", type=int, default=2)
    args = ap.parse_args()

    pool = stage_pool()
    if args.stage == "pool":
        print(f"{len(pool)} 条视频 -> 候选池")
        return 0

    ups = stage_ups(pool)
    if args.stage == "ups":
        for u in sorted(ups, key=lambda u: -u["n"]):
            print(f"{u['n']:>2} 条 / S45:{u['n_s45']:>2} / {u['avg_min']:>5}m / "
                  f"系列{u['series_ratio']:.0%} / {u['author']}")
        return 0

    txs = stage_text(ups, args.per_up)
    by_mid = {str(t["mid"]): t for t in txs}

    rows = []
    for u in ups:
        t = by_mid.get(str(u["mid"])) or {}
        rows.append({**u, "text": t.get("raw") or {}, "used": t.get("used") or [],
                     "n_valid": t.get("n_valid", 0),
                     "dropped": t.get("dropped") or []})

    have = [r for r in rows if (r["text"].get("chars", 0) >= 3000
                                     and r.get("n_valid", 0) >= 2)]
    cols = ["cond", "causal", "num", "jargon", "empty"]
    dist = {c: [r["text"][c] for r in have] for c in cols}

    for r in rows:
        if not (r["text"].get("chars", 0) >= 3000 and r.get("n_valid", 0) >= 2):
            r["q"] = None
            continue
        q = sum(W[c] * pct(dist[c], r["text"][c]) for c in cols)
        r["q"] = round(max(q, 0) * 100, 1)

    mx = max([r["n_s45"] for r in rows] or [1]) or 1
    mxser = max([r["series_ratio"] for r in rows] or [1]) or 1
    mxdur = max([r["avg_min"] for r in rows] or [1]) or 1
    mxplay = max([math.log1p(u.get("fans") or 0) for u in rows] or [1]) or 1

    for r in rows:
        if r["q"] is None:
            r["total"] = None
            r["act"] = r["sysm"] = r["back"] = r["aud"] = 0
            continue
        act = min(r["n_s45"] / 3, 1) * 100
        sysm = (min(r["avg_min"] / 15, 1) * 50 + min(r["series_ratio"] / mxser, 1) * 50)
        back = (60 if r.get("official") else 0) + \
               (40 if re.search(r"国服|国一|巅峰|职业|教练|KPL", r.get("sign") or "") else 0)
        aud = math.log1p(r.get("fans") or 0) / mxplay * 100
        r["act"], r["sysm"], r["back"], r["aud"] = round(act), round(sysm), back, round(aud)
        r["total"] = round(0.55 * r["q"] + 0.15 * r["sysm"] + 0.15 * r["act"]
                           + 0.10 * r["back"] + 0.05 * r["aud"], 1)

    rows.sort(key=lambda r: -(r["total"] or -1))
    (OUT / "creators_scored.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n{'UP':<22}{'总分':>6}{'质量':>6}{'体系':>6}{'活跃':>6}{'背书':>6}{'受众':>6}"
          f"{'条':>4}{'S45':>5}{'均长':>6}{'条件':>6}{'因果':>6}{'数字':>6}{'术语':>6}{'空话':>6}")
    for r in rows:
        t = r["text"]
        print(f"{r['author'][:20]:<22}{str(r['total'] or '-'):>6}{str(r['q'] or '-'):>6}"
              f"{r['sysm']:>6}{r['act']:>6}{r['back']:>6}{r['aud']:>6}"
              f"{r['n']:>4}{r['n_s45']:>5}{r['avg_min']:>6}"
              f"{t.get('cond','-'):>6}{t.get('causal','-'):>6}{t.get('num','-'):>6}"
              f"{t.get('jargon','-'):>6}{t.get('empty','-'):>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
