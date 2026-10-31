#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s3_chunk.py — cues -> 三级分块

L1 原子块 = 单条 cue，保留 from/to。条目里写的 "@03:12" 唯一合法来源就是它。
L2 抽取块 = 目标 60s、按句末标点/静默切分、**不重叠**（重叠会让同一段被抽两遍）
            头尾各带 3 条锚点 cue，抽取时只许引用锚点行的时间
L3 大纲块 = 每 60s 桶取信息量最大的一句，拼成 <=2000 字，用于先出整片骨架

用法：
  python s3_chunk.py --raw ../10_sources/raw --out ../10_sources/blocks
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FILLER = {
    "啊", "哦", "嗯", "呃", "唉", "咦", "哎", "对吧", "就是", "然后", "那么",
    "这个", "那个", "好吧", "是吧", "对不对", "知道吧", "好", "行",
}
END_PUNCT = "。！？!?.；;…"


def normalize(s: str) -> str:
    s = re.sub(r"([Bb])\s+([Vv])\s*", r"\1\2", s)
    s = re.sub(r"([Ss])\s+(\d)\s+(\d)", r"\1\2\3", s)
    s = re.sub(r"[ \t]+", " ", s).strip()
    return s


def clean(cues: list[dict]) -> list[dict]:
    out: list[dict] = []
    prev = None
    for c in cues:
        txt = normalize(str(c.get("content", "")))
        if not txt:
            continue
        if txt == prev:            # 连续重复（B 站 AI 字幕常见）
            continue
        if len(txt) <= 3 and txt.strip("，,。.~ ") in FILLER:
            continue               # 纯语气词；但保留 >=4 字的口头语（是判断"闲聊还是下结论"的信号）
        out.append({"from": float(c.get("from", 0)), "to": float(c.get("to", 0)), "content": txt})
        prev = txt
    return out


def build_l2(cues: list[dict], target: float = 60.0, hard_max: float = 120.0) -> list[dict]:
    blocks, cur = [], []
    for c in cues:
        cur.append(c)
        span = cur[-1]["to"] - cur[0]["from"]
        ends_sentence = bool(cur[-1]["content"]) and cur[-1]["content"][-1] in END_PUNCT
        if span >= hard_max or (span >= target and ends_sentence):
            blocks.append(cur)
            cur = []
    if cur:
        if blocks and (cur[-1]["to"] - cur[0]["from"]) < 15:   # 尾巴太短，并回上一块
            blocks[-1].extend(cur)
        else:
            blocks.append(cur)
    return blocks


def make(bvid: str, cues: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for i, c in enumerate(cues):
        rows.append({"bvid": bvid, "i": i, "lvl": 1,
                     "t0": c["from"], "t1": c["to"], "text": c["content"]})

    for j, blk in enumerate(build_l2(cues)):
        anchors = [[c["from"], c["content"]] for c in blk[:3] + blk[-3:]]
        rows.append({"bvid": bvid, "i": j, "lvl": 2,
                     "t0": blk[0]["from"], "t1": blk[-1]["to"],
                     "text": "".join(c["content"] for c in blk),
                     "anchors": anchors,
                     "n_cues": len(blk)})

    outline, bucket_end = [], 60.0
    cur_best = None
    for c in cues:
        while c["from"] >= bucket_end:
            if cur_best:
                outline.append([round(bucket_end - 60), cur_best])
            cur_best = None
            bucket_end += 60.0
        if cur_best is None or len(c["content"]) > len(cur_best):
            cur_best = c["content"]
    if cur_best:
        outline.append([round(bucket_end - 60), cur_best])

    text, acc = [], 0
    for t, s in outline:
        line = f"[{int(t)//60:02d}:{int(t)%60:02d}] {s}"
        if acc + len(line) > 2000:
            break
        text.append(line)
        acc += len(line)
    rows.append({"bvid": bvid, "i": 0, "lvl": 3, "t0": 0, "t1": cues[-1]["to"],
                 "text": "\n".join(text)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, default=Path("../10_sources/raw"))
    ap.add_argument("--out", type=Path, default=Path("../10_sources/blocks"))
    ap.add_argument("--bvid", nargs="*", default=[])
    args = ap.parse_args()

    raw, out = args.raw.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(raw.glob("*.cues.json"))
    if args.bvid:
        files = [f for f in files if f.stem.split(".")[0] in set(args.bvid)]
    if not files:
        print("[FATAL] raw 目录下没有 .cues.json", file=sys.stderr)
        return 2

    for f in files:
        data = json.loads(f.read_text(encoding="utf-8"))
        bvid = data.get("meta", {}).get("bvid") or f.stem.split(".")[0]
        cues = clean(data.get("cues") or [])
        if not cues:
            print(f"SKIP {bvid} 无有效 cue")
            continue
        rows = make(bvid, cues)
        (out / f"{bvid}.blocks.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8")
        n2 = sum(1 for r in rows if r["lvl"] == 2)
        print(f"OK {bvid} cues={len(cues)} l2_blocks={n2} span={cues[-1]['to']:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
