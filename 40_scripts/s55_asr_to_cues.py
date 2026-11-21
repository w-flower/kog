# -*- coding: utf-8 -*-
"""s55_asr_to_cues.py — 把 ASR 转写 txt（[mm:ss] 内容）转成站点索引用的 cues.json。

用途：视频没有 B 站字幕时，用本地 ASR 结果补一份 cues，让 s5_index 能校验时间戳。
注意：cues 的粒度是"段落起点"，秒级精度，不是逐句 cue。
"""
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) < 3:
        print("用法: s55_asr_to_cues.py <转写txt> <输出cues.json> [duration秒]")
        return
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

    rows = []
    for ln in src.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\[(\d{1,2}):(\d{2})\]\s*(.+)", ln.strip())
        if not m:
            continue
        sec = int(m.group(1)) * 60 + int(m.group(2))
        rows.append((sec, m.group(3).strip()))

    if not rows:
        print("没解析到任何行")
        return

    if not duration:
        duration = rows[-1][0] + 10

    cues = []
    for i, (sec, text) in enumerate(rows):
        end = rows[i + 1][0] if i + 1 < len(rows) else duration
        if end <= sec:
            end = sec + 1
        cues.append({"from": float(sec), "to": float(end), "sid": i + 1, "location": 2, "content": text, "music": 0.0})

    data = {
        "meta": {
            "bvid": out.name.split(".")[0],
            "title": "",
            "pubdate": "",
            "play": "",
            "duration": duration,
            "cue_count": len(cues),
            "source": "faster-whisper medium ASR（本地转写，段落级）",
            "ok": True,
        },
        "cues": cues,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    print(f"{len(cues)} cues -> {out}")


if __name__ == "__main__":
    main()
