# -*- coding: utf-8 -*-
"""s46_build_wave2.py — 第二轮英雄卡装配（BV-keyed 专项教学素材）。
把无标题索引的专项教学 BV 按英雄打包成码道任务输入 + 任务书。
"""
from pathlib import Path

BASE = Path("C:/Users/Lenovo/WorkBuddy/kog")
T = BASE / "50_logs/transcripts"
UP = BASE / "50_logs/upload"

# 批次 -> [(英雄, BV, 素材说明)]
BATCHES = {
    "F": [("司马懿", "BV1LiqVBdEXV", "龙帝《18分钟司马懿精讲·33%输出全局思路》")],
    "F2": [("芈月", "BV12fp869EfY", "学长木兰导师《国服芈月思路打法教学》")],
    "G": [("亚瑟", "BV1Dkxc6XEz4", "故辞《免费复盘1-7亚瑟细节·全局+复盘》"),
          ("李信", "BV1bv4y1e75a", "秋白《国服李信·光信零基础教学》")],
    "H": [("猪八戒", "BV1GDAHzzEV9", "恨意《国一猪八戒全局思路教学》"),
          ("武则天", "BV1dMyhBWEA4", "余77《黑马武则天精讲教学》")],
    "I": [("桑启", "BV1Pk4d6KEvn", "萤火旅人《桑启教学》"),
          ("钟馗", "BV1FFHz6AEbY", "露露自信一点《银河系第一钟馗》")],
    "J": [("孙膑", "BV1oCxT6jEnH", "十六说《孙膑中单？打野教学》"),
          ("元歌", "BV1pb2uB7EZ9", "龙帝《突破瓶颈期的关键对局·元歌辅助》")],
}

# 复用 s42 的 SPEC / EXAMPLE_NOTE
src = (BASE / "40_scripts/s42_build_upload.py").read_text(encoding="utf-8")
i = src.index('SPEC = """'); j = src.index('"""', i + 10) + 3
k = src.index('EXAMPLE_NOTE = """'); l = src.index('"""', k + 20) + 3
ns = {}
exec(src[i:j], ns); exec(src[k:l], ns)
SPEC, EX = ns["SPEC"], ns["EXAMPLE_NOTE"]

for tag, heroes in BATCHES.items():
    parts = [SPEC.format(tag=tag)]
    for h, bv, label in heroes:
        txt = (T / f"{bv}.txt").read_text(encoding="utf-8").strip()
        parts.append(f"\n### 素材：{h}（{bv}）— {label}\n\n```text\n{txt}\n```\n")
    ex = (BASE / "20_kb/A_英雄教学/老夫子.md").read_text(encoding="utf-8")
    parts.append(EX.format(example=ex))
    out = UP / f"batch_{tag}.md"
    out.write_text("".join(parts), encoding="utf-8")
    print(f"batch_{tag}.md  {out.stat().st_size} B  heroes={[x[0] for x in heroes]}")
