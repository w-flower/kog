#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s14_tempo.py — 给每个英雄卡写入「大局观定位」（节奏曲线 / 节奏职责 / 一句话）

为什么要单独一层：英雄的"什么时候强、该干什么"是**位置级和英雄级之间的东西**。
放 L 类太粗（一路五个英雄定位不同），放 A 类正文里又容易被埋掉。
所以做成 front matter 的结构化字段 + 卡首的一个定位块，站点可以据此排序和打标签。

字段：
  tempo: early | mid | late | even     （强势期）
  job:   open | follow | hold | scout | split   （节奏职责）
  motto: 一句话定位（给用户看的那一句）

用法：
  python s14_tempo.py            # 全量写入（已存在的块会跳过）
  python s14_tempo.py --force    # 重写
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

KB = Path(r"C:/Users/Lenovo/WorkBuddy/kog/20_kb/A_英雄教学")

TEMPO_CN = {"early": "前期", "mid": "中期", "late": "后期", "even": "全期"}
JOB_CN = {"open": "开节奏", "follow": "跟节奏", "hold": "守节奏",
          "scout": "视野/侦察", "split": "带线牵制"}

# hero: (tempo, job, motto, 依据)
DATA: dict[str, tuple[str, str, str, str]] = {
    # ── 完整卡 ──
    "不知火舞": ("mid", "open", "四段位移找后排，一套没打死就退", "素材：卡内连招与进场时机"),
    "小乔": ("late", "follow", "二技能先手，团战里打满那一片", "素材：卡内团战定位"),
    "大乔": ("mid", "open", "摇人不是救人，是把人数差搬到任何一个点", "K-L11 / K-A32"),
    "女娲": ("late", "hold", "用石头和传送把战场切开，不追人", "素材：卡内地形与传送"),
    "夏洛特": ("mid", "split", "叠满三层再进场，没叠满就不打", "素材：卡内叠印记顺序"),
    "盾山": ("even", "open", "绕一点进塔，出塔就离对面远很多", "辅助篇：出塔方向=进塔方向延长线"),
    "苏烈": ("even", "open", "大闪开团，蓄大时手指按在取消键上", "辅助篇：大闪开团"),
    "鲁班大师": ("mid", "open", "链子拉回来，让队友敢进也敢出", "C 类 K-C06 组合补缺"),
    "韩信": ("early", "open", "反的是节奏权，不是野怪", "A 卡 K-L49 同源（BV1jd4y1373j）"),
    "铠": ("late", "split", "存两发强普，绕后之前先藏住视野", "A 卡：10 分钟龙团藏视野绕后"),
    "刘备": ("early", "open", "抓人必须顺路，经济差才是他的伤害", "A 卡：喜欢抓人的打野上不了高分段"),
    "雅典娜": ("late", "follow", "把距离变成伤害，两枪一个", "A 卡：大后期是雅典娜的发力期"),
    "元歌": ("mid", "scout", "傀儡是眼睛，本体是刀", "A 卡：傀儡被摧毁的代价决定不能硬拼"),
    # ── 硬辅 ──
    "张飞": ("even", "open", "永远用后段喷，喷边比喷脸好开", "辅助篇：后段才是击退加眩晕"),
    "牛魔": ("even", "open", "草里放大招，对面看不到预警圈", "辅助篇：草里放大招"),
    "东皇太一": ("early", "open", "反着扔二技能再闪现吸，正面扔等于报点", "辅助篇：二技能反着扔"),
    "大禹": ("mid", "hold", "开团一般，真正强在视野和拉扯", "辅助篇：大禹开团能力其实一般"),
    "刘邦": ("even", "follow", "飞之前先铺盾，盾破了伤害腰斩", "辅助篇：盾没破之前伤害不衰减"),
    "钟馗": ("early", "open", "勾的是前摇，不是人", "B 卡 K-B08（掐开炮前摇）"),
    # ── 软辅/功能 ──
    "太乙真人": ("late", "hold", "大招给除自己外血量最低，先看血条", "辅助篇：容易误给前排"),
    "孙膑": ("late", "hold", "二技能让队伍拉开再回来，别让人钉住", "B 卡 K-B10 / C 类 K-C02"),
    "鬼谷子": ("early", "open", "一二大，先大就直接破隐", "辅助篇：连招顺序是一二大"),
    "桑启": ("mid", "follow", "贴脸才有伤害，萤火虫就是血条", "辅助篇：近身普攻双伤害"),
    "瑶": ("mid", "follow", "打虞姬先把自己压半血，让大招自动选你", "辅助篇：打虞姬的换血法"),
    "蔡文姬": ("late", "hold", "大招别等残血，提前开才有双抗", "辅助篇：大招别等残血"),
    "明世隐": ("late", "hold", "牵谁伤谁，团战别刷链子", "辅助篇：团战别刷链子"),
    "少司缘": ("mid", "follow", "两个队友贴贴，回复比附身高", "辅助篇：贴贴回复量更高"),
    "空空儿": ("mid", "open", "开大前先把一二和被动都用掉", "辅助篇：开大会让一二进 CD"),
    "杨玉环": ("mid", "follow", "对线越乱越强，辅助位只做骚扰", "辅助篇：对线越乱越强"),
    "朵莉亚": ("mid", "follow", "刷大的前提是他敢再进一次场", "C 类 K-C08"),
    "元辅": ("late", "follow", "台子叠三层，靠墙折叠拉长弹射", "辅助篇：台子最多三层"),
    "安奈特": ("mid", "open", "大招霸体延后生效，要预判着开", "辅助篇：霸体延后生效"),
    # ── 非常规辅助 ──
    "张良": ("early", "open", "藏视野抓边，捏的是那一秒", "B 卡 K-B07"),
    "墨子": ("even", "hold", "二技能用末端打，刷盾别用二技能", "辅助篇：末端命中率更高"),
    "廉颇": ("even", "open", "被动变红才有免伤，黄条不算", "辅助篇：黄条再长也没有"),
    "项羽": ("even", "open", "辅助先点一后点二，边路反过来", "辅助篇：辅助连招顺序"),
    "刘禅": ("mid", "open", "20% CD 之前三连控必有缝", "辅助篇：CD 不够必有空白"),
    "庄周": ("mid", "hold", "河道挤视野，解控是反开团不是开团", "用户给的定位 + B 卡 K-B09"),
    "夏侯惇": ("mid", "open", "强化普攻每下减大招 1 秒 CD，越打越快", "辅助篇：减大招 CD"),
    "赵怀真": ("mid", "hold", "残血打 1234 回三格就重来", "辅助篇：不必等满四格"),
    "金蝉": ("mid", "hold", "二技能把兵吸到中心，守塔用", "辅助篇：二技能吸兵"),
    "姜子牙": ("late", "hold", "一二顺序不能反，封神别乱点", "辅助篇：一二技能顺序"),
    "王昭君": ("mid", "hold", "先减速再冻，二技能纯看预判", "辅助篇：先减速再冻"),
    # ── 科研位 ──
    "孙策": ("early", "open", "别带眩晕，正面开船会被前排挡", "辅助篇：孙策辅助建议"),
    "达摩": ("mid", "open", "全部强度在二技能的回复", "辅助篇：达摩强度来源"),
    "武则天": ("mid", "hold", "一闪接大接二接大，法阵打在密集处", "辅助篇：武则天连招"),
    "海月": ("mid", "follow", "不如张良，大招有前摇", "辅助篇：海月定位"),
    "白起": ("even", "open", "嘲讽时长吃装备，辅助很一般", "辅助篇：白起辅助很一般"),
}

BLOCK_HEAD = "## 0. 大局观定位"


def build_block(tempo: str, job: str, motto: str, basis: str) -> str:
    return (f"{BLOCK_HEAD}\n\n"
            f"| 项 | 内容 |\n|---|---|\n"
            f"| **强势期** | {TEMPO_CN[tempo]} |\n"
            f"| **节奏职责** | {JOB_CN[job]} |\n"
            f"| **一句话** | {motto} |\n"
            f"| **依据** | {basis} |\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    done = skipped = 0
    for hero, (tempo, job, motto, basis) in DATA.items():
        p = KB / f"{hero}.md"
        if not p.exists():
            print(f"[缺文件] {hero}")
            continue
        s = p.read_text(encoding="utf-8")

        # 1) front matter 补三个字段
        m = re.match(r"^---\n(.*?)\n---\n", s, re.S)
        if not m:
            print(f"[无 front matter] {hero}")
            continue
        fm = m.group(1)
        rest = s[m.end():]
        if re.search(r"^tempo:", fm, re.M):
            fm = re.sub(r"^tempo:.*$", f"tempo: {tempo}", fm, flags=re.M)
            fm = re.sub(r"^job:.*$", f"job: {job}", fm, flags=re.M)
            fm = re.sub(r"^motto:.*$", f"motto: {motto}", fm, flags=re.M)
        else:
            fm += f"\ntempo: {tempo}\njob: {job}\nmotto: {motto}"
        s = f"---\n{fm}\n---\n" + rest

        # 2) 正文插定位块（H1 之后）
        if BLOCK_HEAD in s:
            if not args.force:
                skipped += 1
                p.write_text(s, encoding="utf-8")
                continue
            s = re.sub(re.escape(BLOCK_HEAD) + r".*?(?=\n## )", "", s, count=1, flags=re.S)
        lines = s.splitlines()
        h1 = next((i for i, ln in enumerate(lines) if ln.startswith("# ")), None)
        if h1 is None:
            print(f"[无 H1] {hero}")
            continue
        block = build_block(tempo, job, motto, basis).splitlines()
        lines = lines[:h1 + 1] + [""] + block + lines[h1 + 1:]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        done += 1
    print(f"写入 {done}，跳过 {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
