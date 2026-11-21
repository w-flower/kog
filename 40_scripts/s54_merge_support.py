# -*- coding: utf-8 -*-
"""把 写作规范 + 素材 + 任务 合并成一个自包含附件，规避多附件上传失败。"""
from pathlib import Path

BASE = Path(r"D:/Projects/kog")
SKILL = (BASE / "50_logs/upload/skill_system_card_spec.md").read_text(encoding="utf-8").strip()
BATCH = (BASE / "50_logs/upload/batch_support_decision.md").read_text(encoding="utf-8").strip()
OUT = BASE / "50_logs/upload/support_task.md"

head = """# 任务：写一张 D 类系统卡《12 辅助决策》

本文件共三部分，请**从头读到尾**再动笔：
- 第一部分：写作规范（硬要求，违反即返工）
- 第二部分：素材包（唯一信源，含转写全文与 ASR 存疑点）
- 第三部分：这次的具体任务（写哪个文件、编号区段、内容要求）

产出：把文件写到 `/workspace/系统卡_辅助决策.md`（只写这一个文件）。

---

# 第一部分：写作规范

"""

mid = """

---

# 第二部分：素材包

"""

tail = """

---

# 第三部分：这次的具体任务

卡的身份：
- 文件名（卡内 id）：12
- 标题：`12 辅助决策：这一波我该跟谁、去哪、开不开`
- cat: D
- depends_on: [05, 11]
- unlocks: []
- role: [roam]
- version: S45
- status: draft
- updated: 2026-11-20
- sources: [BV1S8sn6zEJq]

K 条目编号区段：**K-D111 ~ K-D135**（最多 25 条，不许越界，不许重复；条目少于 25 条完全允许，宁少勿凑）。

内容要求：
1. **判断顺序**那一节要写成「辅助在一波里到底按什么顺序做决定」的可执行步骤（第 1 步到第 N 步），每步指向具体 K 条目。这是整张卡的骨架。
2. 六种局势（前期队友零节奏+敌方卡线 / 中期逆风防守 / 后期打龙时队友掉点 / 蹲人 / 抓敌方工具人 / 敌方带线人数差 / 后期终结比赛）都要有对应条目，但**不要按视频顺序罗列**，要按「辅助做决策的顺序」重组。
3. 每条必须带 `（@ mm:ss）`，时间戳以素材包第二部分全文为准，误差 ≤3 秒。
4. 素材「已知 ASR 存疑点」表里的五处，**严格按表中「判断」列处理**，不许指名存疑英雄。
5. 作者的核心方法论「过程型而非结论型教学」要单独成条，放在开头附近。
6. 素材没讲的（铭文、出装顺序、段位差异等）一律进「待补」，不许补常识。

文末必须附「## 自检」小节。
"""

OUT.write_text(head + SKILL + mid + BATCH + tail, encoding="utf-8")
print("merged ->", OUT, len(head + SKILL + mid + BATCH + tail), "chars")
