# -*- coding: utf-8 -*-
"""s52_build_batch.py — 通用装配器：按 JSON 规格把一批英雄的素材装配成码道任务包 + prompt。

用法:
    python 40_scripts/s52_build_batch.py --spec 50_logs/upload/batch_spec.json

规格 JSON:
{
  "date": "2026-11-19",
  "groups": {
    "G1": {"赵云": ["BV1...","BV2..."], "妲己": ["BV..."]},
    "G2": {...}
  }
}

产出（50_logs/upload/）:
    batch_<tag>.md   给码道的任务包（规范 + 样例卡 + 素材）
    prompt_<tag>.md  给码道的 prompt（写死输出路径 /workspace/英雄卡_<tag>.md）
复用的 SPEC / EXAMPLE_NOTE 从 s42_build_upload.py 抽取，避免重复维护。
"""
import argparse
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SUB = BASE / "10_sources/creators_cache/subs"
UP = BASE / "50_logs/upload"

src = (BASE / "40_scripts/s42_build_upload.py").read_text(encoding="utf-8")
i = src.index('SPEC = """'); j = src.index('"""', i + 10) + 3
k = src.index('EXAMPLE_NOTE = """'); l = src.index('"""', k + 20) + 3
ns = {}
exec(src[i:j], ns); exec(src[k:l], ns)
SPEC, EXAMPLE_NOTE = ns["SPEC"], ns["EXAMPLE_NOTE"]


def mmss(s):
    try:
        s = int(float(s))
    except Exception:
        return "00:00"
    return f"{s // 60:02d}:{s % 60:02d}"


def dump(bv):
    p = SUB / f"{bv}.json"
    if not p.exists():
        return ""
    d = json.loads(p.read_text(encoding="utf-8"))
    body = d.get("body") or []
    return "\n".join(f"[{mmss(c.get('from', 0))}] {c.get('content', '')}" for c in body)


def build_group(tag, heroes_map, date):
    parts = [SPEC.replace("2026-11-18", date).format(tag=tag)]
    counts = {}
    for h, bvs in heroes_map.items():
        items = []
        for bv in bvs:
            txt = dump(bv)
            if not txt.strip():
                print(f"  [WARN] {h} {bv} 无字幕，跳过")
                continue
            items.append((bv, txt))
        counts[h] = len(items)
        for bv, txt in items:
            parts.append(f"\n### 素材：{h}（{bv}）\n\n```text\n{txt}\n```\n")
    example = (BASE / "20_kb/A_英雄教学/老夫子.md").read_text(encoding="utf-8")
    parts.append(EXAMPLE_NOTE.format(example=example))
    out = UP / f"batch_{tag}.md"
    out.write_text("".join(parts), encoding="utf-8")

    # prompt
    hero_line = " → ".join(heroes_map.keys())
    cnt_line = "、".join(f"{h} {c} 条" for h, c in counts.items())
    single = [h for h, c in counts.items() if c == 1]
    n = len(heroes_map)
    prompt = f"""你是一名王者荣耀英雄教学作者。附件 `batch_{tag}.md` 是任务包：含英雄卡格式规范、写作铁律、样例卡，以及这些英雄的实战/教学字幕（带 [MM:SS] 时间戳）。每个英雄的素材条数：{cnt_line}。

要你写 **1 个文件**：`/workspace/英雄卡_{tag}.md`（**必须真的写文件，不要只在对话里贴内容**）。

文件里用分隔符切成 {n} 张卡，每张卡前必须有这一行（缺了会算少一张）：

```
<!-- ==== CARD: 英雄名 ==== -->
```

顺序：{hero_line}。

硬性要求：

1. 每张卡开头直接是 `---` 的 YAML front matter，字段照任务包第二节的 10 个，`updated: {date}`，`status: draft`，`sources` 只填本卡实际用到的 BV。
2. 正文固定 6 节：`0. 大局观定位` / `1. 机制内核` / `2. 对线 / 打法` / `3. 连招` / `4. 中后期 / 节奏` / `5. 出装铭文`，外加 `## 待补`。
3. 每条结论必须带来源时间戳，格式严格写成 `（BV1xxxxxxxxx @ 03:12）`。
4. **素材没有的不许编。** 素材少的卡可以薄，但必须在开头 ⚠️ 行如实说明"素材条数少、覆盖不全"，没讲到的进「待补」。以下英雄素材只有 1 条，尤其要写清局限：{('、'.join(single) if single else '无')}。
5. 素材是 ASR 转写，有错别字，做语义归并但不要改原意；引用最多 1~2 句。
6. 不要输出 PDF、图片。
7. 文件末尾加：

```
## 自检
- 卡片数：{n}（{hero_line}）
- 各卡来源 BV 数
- 哪些方面素材没覆盖
```
"""
    pout = UP / f"prompt_{tag}.md"
    pout.write_text(prompt, encoding="utf-8")
    print(f"batch_{tag}.md {out.stat().st_size}B  prompt_{tag}.md {pout.stat().st_size}B  counts={counts}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    date = spec.get("date", "2026-11-19")
    for tag, heroes_map in spec["groups"].items():
        build_group(tag, heroes_map, date)


if __name__ == "__main__":
    main()
