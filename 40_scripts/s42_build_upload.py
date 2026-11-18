# -*- coding: utf-8 -*-
"""装配码道任务输入包：模板规范 + 样例卡 + 纯净素材，一批一个 .md。"""
import json, re
from pathlib import Path

BASE = Path("C:/Users/Lenovo/WorkBuddy/kog")
T = BASE / "50_logs/transcripts"
UP = BASE / "50_logs/upload"
UP.mkdir(parents=True, exist_ok=True)

BATCHES = {
    "A": ["甄姬", "杨戬", "亚连", "嬴政"],
    "B": ["兰陵王", "嫦娥", "哪吒", "扁鹊"],
    "C": ["钟无艳", "阿古朵", "马超", "典韦"],
    "D": ["娜可露露", "李元芳", "曹操", "司空震"],
}

SPEC = """# 王者荣耀英雄教学卡 · 写作任务包（批次 {tag}）

## 一、你要做什么

读本文件第四节的素材（每个英雄一段 B 站字幕转写，带 `[MM:SS]` 时间戳），
为**每一个**英雄写一张「英雄教学卡」。

卡片是本知识库的最终产物，读者是**想把英雄练好的玩家**。要求：能照着判断"什么时候强、什么时候不能打、连招怎么连、对线怎么处理"。

## 二、格式规范（必须逐字照抄字段名）

每张卡以 YAML front matter 开头，字段固定为这 10 个，**顺序不要改**：

```
---
id: 英雄名
cat: A
title: 英雄名（分路·定位）
tempo: early|mid|late|even|unknown
job: open|hold|follow|split|scout
motto: 一句话概括，不超过 25 字，必须来自素材
version: S45
status: draft
updated: 2026-11-18
sources: [BVxxx, BVyyy]
---
```

字段取值说明：
- `tempo` = 强势期。前期强=early，中期=mid，后期=late，全程均衡=even，判断不出=unknown
- `job` = 节奏职责。开团=open，守塔/抗压=hold，跟团/打输出=follow，单带=split，游走抓人=scout
- `sources` = 本卡实际用到的 BV 号（素材里出现的都可以用，至少 1 个）
- `status` 一律写 `draft`，**不要写 active**

正文结构固定为 6 节，标题逐字照抄：

```
# 英雄名：一句钩子标题

> 只讲英雄本身。分路思路见 `L_分路` 对应篇。
> 素材：<一句话说明素材来源与视角>
> ⚠️ <如果有明显局限，比如只有单份实录、缺出装，写一句>

## 0. 大局观定位

| 项 | 内容 |
|---|---|
| **强势期** | ... |
| **节奏职责** | ... |
| **一句话** | ... |
| **依据** | ... |

## 1. 机制内核

（编号列表，讲这个英雄的技能机制与他"为什么能打"）

## 2. 对线 / 打法

（按实际素材写，可以是分条，也可以是表格）

## 3. 连招

（有明确连招就写表格：场景 | 连招 | 依据；素材没讲连招就写"素材未覆盖连招细节"）

## 4. 中后期 / 节奏

## 5. 出装铭文

（素材只给到散点就如实写散点 + "完整出装未覆盖"）

## 待补

- 素材没讲到的部分，逐条列出
```

## 三、铁律（违反即返工）

1. **只写素材里真有的内容。** 每一条结论后面必须带来源时间戳，格式：`（BV1xxxxxxxxx @ 03:12）`。素材里没有的机制、数值、连招，**一个字都不许编**。
2. **素材没覆盖的，写进「待补」**，不要用常识补全。宁可卡片单薄，不许造假。
3. 素材是**直播/实战解说转写**，口语、有错别字（"亚索"可能是"亚连"、"联播"可能是"连招"）。要做语义归并，但**不要改写原意**。
4. 引用要短：引号里最多 1~2 句原话，不要整段抄。
5. 不要写"玩家应该…"这种空话；每条都要能落到具体动作（几级、第几件装备、往哪走、打谁）。

## 四、素材

"""

EXAMPLE_NOTE = """
## 五、样例卡（体例参考，照这个密度写）

下面是同库已完成的另一张卡，**只参考格式与信息密度，不要抄它的内容**：

````markdown
{example}
````
"""


def build(tag, heroes):
    parts = [SPEC.format(tag=tag)]
    for h in heroes:
        p = T / f"{h}.txt"
        txt = p.read_text(encoding="utf-8").strip()
        # 去掉 dump 脚本可能带的头部说明行，只留正文
        parts.append(f"\n### 素材：{h}\n\n```text\n{txt}\n```\n")
    ex = (BASE / "20_kb/A_英雄教学/老夫子.md").read_text(encoding="utf-8")
    parts.append(EXAMPLE_NOTE.format(example=ex))
    out = UP / f"batch_{tag}.md"
    out.write_text("".join(parts), encoding="utf-8")
    print(f"batch_{tag}.md  {out.stat().st_size} bytes  heroes={heroes}")


for tag, heroes in BATCHES.items():
    build(tag, heroes)
