# -*- coding: utf-8 -*-
"""s44_build_system.py — 装配 D 类系统卡（对局内）的码道任务包。"""
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
T = BASE / "50_logs/transcripts"
UP = BASE / "50_logs/upload"

TASKS = {
    "S1": {
        "files": ["05_第一波转线.md"],
        "kd": "K-D41 ~ K-D52",
        "material": ["BV1oRJYzpEYb", "BV1WkKzzUEtq"],
        "focus": "「第一波转线」：兵线清完之后，动起来先去哪一路、凭什么判断",
    },
    "S2": {
        "files": ["08_顺风推进.md", "09_逆风止损.md"],
        "kd": "K-D53 ~ K-D66",
        "material": ["BV1T8hG6FEtp", "BV1NLHsexEPi"],
        "focus": "两个文件：「顺风怎么把优势推出去」与「逆风怎么把损失按住」。两者是同一节点的两个分支",
    },
    "S3": {
        "files": ["10_终结比赛.md"],
        "kd": "K-D67 ~ K-D78",
        "material": ["BV1B84y177A1", "BV1oRJYzpEYb"],
        "focus": "「终结比赛」：拿到优势之后怎么把它变成水晶（龙、兵线、高地、开团时机）",
    },
}

TITLES = {
    "BV1oRJYzpEYb": "浅梦《打野教科书》——12 位 KPL 职业打野的通用理解",
    "BV1WkKzzUEtq": "浅梦《中路教科书》——KPL 职业中路的通用理解",
    "BV1T8hG6FEtp": "益达兄弟《职业选手和国服的差距》——决策层差异",
    "BV1NLHsexEPi": "燕十叁《王者打野公式的本质，从 0 学打野》",
    "BV1B84y177A1": "猫萌《怎么玩好辅助·金牌辅助教学》",
}

SPEC = """# D 类系统卡写作任务包（{tag}）

## 一、这一类是什么

D 类是「**对局内**」，回答的是 **"现在这一刻该干什么"**。
硬规矩：**每一条都必须带时间点**（0:45 / 4 分钟 / 10 分钟）或游戏内状态（兵线到哪、龙几分钟刷）。
不带时间点的结论不属于 D 类——那是 A 类（英雄）或 L 类（分路）的内容，**不要写进来**。

本次要产出：{files}
编号区段：**{kd}**（不要用这个区间外的 K-D 号，库里已经用到 K-D40）
聚焦点：{focus}

## 二、文件格式（逐字照抄结构）

```
---
id: {fid}
cat: D
title: <这一节回答的那个「决定」，写成一个完整句子>
depends_on: [<上游节号>]
unlocks: [<下游节号>]
role: [adc, mid, jungle, roam]
version: S45
status: draft
updated: 2026-11-18
sources: [BVxxx, BVyyy]
---

# {fid} <标题>

> 素材：<一句话说明素材来源与视角>
> 上游接 `<上游文件>`。

## 判断顺序

```
第 1 步：<这一节遇到的第一个问题>  → K-Dxx
第 2 步：...                      → K-Dyy
```

### K-D41 <条目名：写成一个判断，不要写名词短语>

- **适用版本**：S45
- **触发条件**：<什么局面下你要问这个问题>
- **判断依据**：<看什么信号来判>（@ 03:12）
- **决策分支**：
  - <信号 A> → <怎么做>
  - <信号 B> → <怎么做>
- **反例**：<最常见的错误做法是什么>（@ 08:20）
- **来源**：BV1xxxxxxxxx @ 03:12
- **可信度**：高/中/低（说明理由）
- **状态**：draft
```

## 三、铁律

1. **文件名是一个「决定」，不是话题。** 不许出现"英雄""铭文""出装"这类名词短语。
2. **全篇第一节如果是续写，必须以「上一节留下的问题」开头**，并点名是哪个分支留下来的。
3. **易错点按环节归位，不单列。** 禁止"本节易错点：①②③"，错必须挂在它所属的判断节点下（写在 `反例` 里）。
4. **每条结论必须带来源时间戳**：`（@ 03:12）` 或 `（BV1xf... @ 03:12）`。素材里没有的内容**不许编**。
5. 素材是口语转写（KPL 解说 / 教学口播），有错别字和语气词，做语义归并但不改原意。
6. 职业选手的理解要和路人局区分：**如果素材明确是职业视角，条目里要写清"职业/路人局的差别"**，不要直接当路人局结论。
7. 写到「待补」时如实列出素材没覆盖的部分。

## 四、素材

"""

EX = """
## 五、体例参考（同库已完成的 D 类卡，只学格式与密度，不要抄内容）

````markdown
{example}
````
"""


def build(tag, cfg):
    parts = [SPEC.format(
        tag=tag,
        files="、".join(cfg["files"]),
        kd=cfg["kd"],
        focus=cfg["focus"],
        fid=cfg["files"][0][:2],
    )]
    for bv in cfg["material"]:
        p = T / f"{bv}.txt"
        if not p.exists():
            print("MISSING", bv); continue
        parts.append(f"\n### 素材：{bv} —— {TITLES.get(bv, bv)}\n\n```text\n{p.read_text(encoding='utf-8').strip()}\n```\n")
    ex = (BASE / "20_kb/D_对局内/07_发育路推进公式.md").read_text(encoding="utf-8")
    ex = ex[:6000]
    parts.append(EX.format(example=ex))
    out = UP / f"sys_{tag}.md"
    out.write_text("".join(parts), encoding="utf-8")
    print(f"sys_{tag}.md  {out.stat().st_size} bytes  files={cfg['files']}")


for tag, cfg in TASKS.items():
    build(tag, cfg)
