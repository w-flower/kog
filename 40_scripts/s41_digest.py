"""s41_digest.py — 把某英雄/某BV 的字幕压缩成「教学高信号摘要」，带 [MM:SS]。

用法:
    python 40_scripts/s41_digest.py 甄姬 老夫子 ...
    python 40_scripts/s41_digest.py --chars 2500 甄姬

输出: 50_logs/digest/<英雄>.txt
策略:
  1) 收集该英雄在 hero_batch_map 里所有 body 非空的字幕
  2) 逐条 cue 打分: 命中教学词 +1/+2；过短丢弃；纯语气词丢弃
  3) 保留上下文: 命中点前后各 1 条，保证可读
  4) 按总分排序但保留时间序输出，超预算则均匀抽稀
"""
import json, re, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SUBS = BASE / "10_sources/creators_cache/subs"
MAP = BASE / "10_sources/creators_cache/hero_batch_map.json"
OUT = BASE / "50_logs/digest"

STRONG = ["一定要","千万不要","必须","记住","优先","核心","关键","原理","因为","所以","目的是","思路是",
          "节奏","经济","兵线","等级","装备","出装","连招","克制","强势","弱势","开局","前期","中期","后期",
          "分钟","秒","塔","视野","野区","龙","开团","切后排","poke","消耗","换血","拉扯","反打","蹲","绕后",
          "别","不要","避免","注意","最多","至少","直接"]
WEAK = ["大招","二技能","一技能","三技能","闪现","净化","伤害","血量","打野","中路","对抗路","发育路","辅助"]
FILLER = re.compile(r"^[嗯啊哦诶哎对对是那个就是这这个]*$")


def cue_score(t):
    s = 0
    for w in STRONG:
        if w in t: s += 2
    for w in WEAK:
        if w in t: s += 1
    if len(t) >= 18: s += 1
    if FILLER.match(t) or len(t) < 6: s -= 5
    return s


def mmss(sec):
    sec = int(sec)
    return f"{sec//60:02d}:{sec%60:02d}"


def build(hero, budget):
    mp = json.loads(MAP.read_text(encoding="utf-8"))
    bvs = [bv for bv, h in mp.items() if h == hero]
    lines = []
    total = 0
    for bv in bvs:
        p = SUBS / f"{bv}.json"
        if not p.exists(): continue
        try: d = json.loads(p.read_text(encoding="utf-8"))
        except Exception: continue
        body = d.get("body", [])
        if not body: continue
        txt = "".join(c.get("content","") for c in body)
        if len(txt) < 300: continue
        scored = []
        for i, c in enumerate(body):
            t = (c.get("content") or "").strip()
            if not t: continue
            scored.append((i, cue_score(t), t))
        # 选命中段: 分数>=3 的 cue，加入前后各 1 条
        keep = set()
        for i, s, t in scored:
            if s >= 3:
                for j in (i-1, i, i+1):
                    if 0 <= j < len(body): keep.add(j)
        if not keep:
            keep = {i for i,_,_ in scored[:40]}
        # 按时间序输出
        out = []
        prev = -99
        for i in sorted(keep):
            c = body[i]
            t = (c.get("content") or "").strip()
            if not t: continue
            ts = mmss(c.get("from", 0))
            if i - prev > 1:
                out.append(f"  …[跳]")
            out.append(f"  [{ts}] {t}")
            prev = i
        block = f"### {bv}  (原字 {len(txt)})\n" + "\n".join(out)
        if total + len(block) > budget and lines:
            break
        lines.append(block)
        total += len(block)
    return "\n\n".join(lines), total


def main():
    args = sys.argv[1:]
    budget = 2600
    if "--chars" in args:
        i = args.index("--chars"); budget = int(args[i+1]); del args[i:i+2]
    OUT.mkdir(parents=True, exist_ok=True)
    for hero in args:
        txt, n = build(hero, budget)
        if not txt:
            print(f"{hero}: NO_CONTENT"); continue
        p = OUT / f"{hero}.txt"
        p.write_text(txt, encoding="utf-8")
        print(f"{hero}: {n} chars -> {p.name}")


if __name__ == "__main__":
    main()
