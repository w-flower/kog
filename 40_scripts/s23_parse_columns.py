#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""s23_parse_columns.py — 把专栏正文拆成有方向的克制边

三个分支，各自独立统计正确率，低于门槛的分支整体禁用：
  B1 箭头行    一行形如 `铠<-蒙恬、吕布`：箭头指向被克的一方
  B2 句内动词  「X克制Y」「X打不过Y」「X和Y五五开」——限制在同一句内
  B3 小标题聚合 整段只有英雄名（小标题），下一段的判断归到它名下

三条闸门（缺一个就满盘垃圾）：
  否定闸门    句子里出现「不克制/不算/谈不上/克制不是」整句丢弃
  跨句闸门    动词必须夹在两个英雄名中间，且三者同句
  自环闸门    X 与 X 不成边；同路才收（跨路对位留给对应分路自己去采）

输出：30_index/duel/{lane}.column_edges.jsonl
  {a, b, grade, cv, cv_title, quote, url, branch, layer, doubt}
  grade 是「a 对 b」的档位：a=克 b 时 grade="克"。

用法：
  python s23_parse_columns.py --lane mid
  python s23_parse_columns.py --lane mid --sample 6      # 每分支抽 6 条人工核对
"""
from __future__ import annotations

import argparse
import functools
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bili_api as B
import names as N

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "30_index" / "duel"

# 出现这些词说明这句在否定或做概念澄清，整句不可用
NEG_WORDS = ("不克制", "不算", "不是克制", "谈不上", "没有克制", "并不是",
             "不见得", "克制不是", "不叫克制", "不能算", "未必", "克不了",
             "反被", "然而", "但是其实")

# 分句：句号问号感叹号分号换行都算边界，逗号不算（「X 打不过 Y，因为…」要连起来看）
SENT_SPLIT = re.compile(r"(?<=[。！？!?；;\n])")

# 机制 / 数值：用来标这一条结论靠什么成立
MECH_WORDS = ("免控", "霸体", "位移", "手长", "射程", "控制", "沉默", "击飞",
              "减速", "护盾", "真伤", "无法选中", "拉扯", "突进", "探视野")
NUM_WORDS = ("爆发", "伤害", "血量", "输出", "数值", "经济", "清线", "续航")


def layer_of(sent: str) -> str:
    m = sum(1 for w in MECH_WORDS if w in sent)
    n = sum(1 for w in NUM_WORDS if w in sent)
    if m > n:
        return "机制"
    if n > m:
        return "数值"
    return ""


@functools.lru_cache(maxsize=1)
def all_names_re() -> re.Pattern:
    """全部 129 个英雄（含别名）的交替正则。

    分节标题的识别必须用它，不能用本路英雄池：
    一篇辅助文里，「孙膑：」这种标题如果识别不出来，cur 会停在上一个英雄身上，
    后面整段都被算到那个人头上——实测一篇里冒出 24 条「大乔克制XX」全是错的。
    """
    nm = N.load()
    keys = sorted(set(nm.all_names) | set(nm.alias), key=len, reverse=True)
    return re.compile("(?:" + "|".join(re.escape(k) for k in keys) + ")")


def build_name_re(heroes: list[str]) -> re.Pattern:
    """长名优先，否则「不知火舞」会被「火舞」抢走一半。"""
    pool = sorted(set(heroes), key=len, reverse=True)
    return re.compile("(?:" + "|".join(re.escape(x) for x in pool) + ")")


# (正则模板, 方向, 档位)
#   档位永远是「赢家那一侧的档位」：
#     方向 xy = 前一个名字是赢家 → 直接 (x, y, grade)
#     方向 yx = 后一个名字是赢家 → 产出 (y, x, grade)
#   draw = 五五开，两边都出
#   {N} 会被替换成英雄名交替式
#
# 这里踩过一次方向全反的坑：早期给「被克制」类模式写 grade="被克" 再取反，
# 结果「克制X的是Y」这种赢家在后的模式也被取反，姜子牙克甄姬被记成了姜子牙被甄姬克。
INLINE = [
    # 强克制：X 克制 Y
    (r"(?P<x>{N})(?:非常|最|极度|完全|十分|特别|会|能|可以|是|几乎)*"
     r"(?:死死|狠狠|直接)?克制(?:了|着|住)?(?P<y>{N})", "xy", "克"),
    (r"(?P<x>{N})(?:天克|完克|死克|血克)(?P<y>{N})", "xy", "克"),
    # 强克制：X 被 Y 克制（赢家在后）
    (r"(?P<x>{N})(?:会|都|也|很容易|很|直接)?被(?P<y>{N})"
     r"(?:死死|狠狠)?(?:克制|压制|吊打|克)", "yx", "克"),
    (r"(?P<x>{N})(?:打不过|拼不过|刚不过|压制不住)(?P<y>{N})", "yx", "克"),
    # 轻压制
    (r"(?P<x>{N})(?:可以|能|会|很|比较|稍微)?压制(?:住|了)?(?P<y>{N})", "xy", "小优"),
    (r"(?P<x>{N})(?:比较好打|很好打|好打)(?P<y>{N})", "xy", "小优"),
    (r"(?P<x>{N})(?:难打|不好打|吃亏)(?P<y>{N})", "xy", "小劣"),
    # 「好打 X 的英雄有 Y、Z」——纵列式，赢家在后
    (r"好打(?P<x>{N})的[^。；]{0,10}(?:有|是|例如|比如|如|像)(?P<y>{N})", "yx", "小优"),
    (r"(?P<x>{N})对线(?:上)?(?P<y>{N})(?:没有|没|毫无|不占)(?:什么)?优势", "yx", "小优"),
    (r"(?P<x>{N})对线(?:上)?(?P<y>{N})(?:有|占)(?:很大)?优势", "xy", "小优"),
    # 均势
    (r"(?P<x>{N})(?:跟|和|与|对)(?P<y>{N})(?:基本|大概|差不多|几乎)?"
     r"(?:五五开|均势|持平|差不多)", "draw", "五五开"),
    # 反向表述：克制 X 的（法师/英雄）是 Y / X 的天敌是 Y
    (r"克制(?P<x>{N})的[^。；]{0,8}?(?:还|也)*(?:莫过于|无非就是|无非|就是|是|有|例如|比如)"
     r"(?P<y>{N})", "yx", "克"),
    (r"(?P<x>{N})的(?:天敌|克星|counter)(?:莫过于|无非|就是|是|有)(?P<y>{N})", "yx", "克"),
]

ARROW = re.compile(
    r"^\s*(?P<left>[\u4e00-\u9fa5、，,/／和与]{2,24}?)\s*"
    r"(?P<arrow><-|←|<－|<=|->|→|-＞|=>)\s*"
    r"(?P<right>[\u4e00-\u9fa5、，,/／和与]{2,40})\s*$")

# B4 的主角：这类「克制关系汇总」专栏的通用写法
#   女娲（不知火舞）             → 不知火舞 克 女娲
#   甄姬（米莱狄，不知火舞，沈梦溪）→ 三个都克甄姬
# 括号里出现否定词就不收，避免把「女娲（不克制不知火舞）」读反。
LIST_HEAD = re.compile(
    r"^\s*(?P<who>[\u4e00-\u9fa5、，,/／]{2,20}?)\s*[（(]\s*(?P<list>[^）)]{2,60}?)\s*[）)]\s*$")
LIST_NEG = "不没无未非反难怕"


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if s.strip()]


def parse_arrow(line: str, nm: N.Names, name_re: re.Pattern) -> list[tuple[str, str, str]]:
    """B1：`铠<-蒙恬、吕布` → [(铠,蒙恬,克),(铠,吕布,克)]

    箭头头指向被克的一方，和正文「最克制铠的英雄莫过于蒙恬」对得上。
    """
    m = ARROW.match(line)
    if not m:
        return []
    left = name_re.findall(m.group("left"))
    right = name_re.findall(m.group("right"))
    if not left or not right:
        return []
    left = [nm.canon(x) for x in left]
    right = [nm.canon(x) for x in right]
    head_left = m.group("arrow") in ("<-", "←", "<－", "<=")
    out = []
    for x in left:
        for y in right:
            if x == y:
                continue
            out.append((y, x, "克") if head_left else (x, y, "克"))
    return out


def parse_inline(sent: str, nm: N.Names, name_re: re.Pattern) -> list[tuple[str, str, str]]:
    """B2：句内动词。命中即返回，同一句只取第一个模式，避免一句话被反复解读。"""
    if any(w in sent for w in NEG_WORDS):
        return []
    for tmpl, direction, grade in INLINE:
        pat = re.compile(tmpl.replace("{N}", name_re.pattern))
        m = pat.search(sent)
        if not m:
            continue
        x, y = nm.canon(m.group("x")), nm.canon(m.group("y"))
        if x == y:
            return []
        if direction == "xy":
            return [(x, y, grade)]
        if direction == "yx":
            return [(y, x, grade)]
        return [(x, y, "五五开"), (y, x, "五五开")]
    return []


def parse_list_head(line: str, nm: N.Names, name_re: re.Pattern) -> list[tuple[str, str, str]]:
    """B4：`女娲（不知火舞）` / `甄姬（米莱狄，不知火舞，沈梦溪）`

    这是「克制关系汇总」类专栏的通用写法：主角在括号外，括号里是能治他的人。
    方向在正文里能验：女娲那条下面写「法刺整体上就是克制炮台法师的」。
    """
    m = LIST_HEAD.match(line)
    if not m:
        return []
    # 先把英雄名抠掉再看有没有否定词——否则「不知火舞」的「不」会被当成否定
    rest = name_re.sub("", m.group("list"))
    if any(c in rest for c in LIST_NEG):
        return []
    who = name_re.findall(m.group("who"))
    if len(who) != 1:
        return []
    a = nm.canon(who[0])
    out = []
    for tok in name_re.findall(m.group("list")):
        b = nm.canon(tok)
        if b != a:
            out.append((b, a, "克"))     # b 克 a
    return out


# B3 小标题：这类专栏最常见的排版是「克星一：百里守约」+ 一段正文讲怎么打
# 标题给出赢家，正文里反复出现的那个英雄才是被打的人。
SEC_HEAD = re.compile(
    r"^\s*(?:克星|天敌|克制|针对|推荐|选择)\s*[一二三四五六七八九十\d]{0,3}\s*[：:、.．]\s*"
    r"(?P<rest>[\u4e00-\u9fa5、，,/／ ]{2,24})\s*$")
SEC_HEAD2 = re.compile(
    r"^\s*(?:第)?\s*[一二三四五六七八九十\d]{1,3}\s*[、.．:：]\s*"
    r"(?P<rest>[\u4e00-\u9fa5]{2,12})\s*$")
# 正文里出现这些词才算「在讲怎么打他」，否则只是顺带提到
FIGHT_WORDS = ("克制", "压制", "打", "优势", "劣势", "难", "怕", "针对", "秒",
               "耗", "对线", "拼", "躲", "削", "废", "治")
# 出现这些词说明这句在讲「和他配合/和他并列」，不是在讲「克制他」
COOP_WORDS = ("配合", "搭配", "组合", "联动", "队友", "一起", "并肩", "同样可以")


def parse_sections(lines: list[str], nm: N.Names, name_re: re.Pattern,
                   lane: str) -> list[dict]:
    """B3：小标题聚合。

    只靠句内动词会漏掉一大片——「克星三：兰陵王」后面那一段可能一次都不写
    「兰陵王克制沈梦溪」，但通篇都在说怎么打沈梦溪。
    这里用「标题给赢家 + 正文高频出现的那个英雄是被打的人」来补。
    """
    blocks: list[tuple[str, list[str]]] = []
    for ln in lines:
        if not ln or ln == "[图]":
            continue
        w = ""
        for pat in (SEC_HEAD, SEC_HEAD2):
            m = pat.match(ln)
            if not m:
                continue
            got = name_re.findall(m.group("rest"))
            if len(got) == 1:
                w = nm.canon(got[0])
                break
        if w:
            blocks.append((w, []))
        elif blocks and len(blocks[-1][1]) < 6:
            blocks[-1][1].append(ln)

    out: list[dict] = []
    for win, body in blocks:
        blob = " ".join(body)
        if len(blob) < 40:
            continue                       # 光有标题没有正文，方向无从判断
        if not any(x in blob for x in FIGHT_WORDS):
            continue
        cnt = Counter(nm.find_all(blob))
        cnt.pop(win, None)
        if not cnt:
            continue
        loser, hits = cnt.most_common(1)[0]
        if hits < 1 or not nm.in_lane(loser, lane) or not nm.in_lane(win, lane):
            continue
        out.append({"a": win, "b": loser, "grade": "克", "branch": "B3",
                    "quote": f"{win} ← 正文（提到 {loser} {hits} 次）",
                    "layer": layer_of(blob)})
    return out


# B5 分节列表：这类「全局克制关系整理」专栏的标准结构
#   金蝉：
#   全局克制关系：
#   1、……非常克制具有高爆发伤害的英雄，如铠、元歌、阿轲……
#   反向克制思路：
#   当面对嬴政、蒙犽……时，金蝉的被动减伤机制将会大幅降低作用
# 一节讲一个英雄，两段分别是他克的和他被克的，整段列名字。
SEC_ONLY = re.compile(r"^\s*(?P<n>.{2,14}?)\s*[：:]?\s*$")
SEC_SUFFIX = re.compile(r"[（(][^）)]{0,10}[）)]")


def header_of(ln: str, nm: N.Names, name_re: re.Pattern) -> str:
    """整行只有英雄名（可带「：」或「（游走）」这类后缀）才算分节标题。

    为什么要卡这么死：第一版只要求「行尾是冒号」，结果遇到没有冒号的
    「孙膑」标题时 cur 一直停在上一个英雄身上，后面所有段落全被算到那个人头上——
    一篇辅助文里冒出二十多条「大乔克制XX」，全是错的。
    """
    t = SEC_SUFFIX.sub("", ln.strip().strip("#*·-　 ")).strip(" ：:、.，,")
    if not t or len(t) > 10:
        return ""
    return nm.canon(t) if all_names_re().fullmatch(t) else ""


def parse_blocks(lines: list[str], nm: N.Names, name_re: re.Pattern,
                 lane: str) -> list[dict]:
    """B5：`金蝉：` 分节 + `全局克制关系` / `反向克制思路` 两段。

    和 B3 的区别在这里：B3 是「标题给赢家、正文提到谁就算输家」，方向靠猜；
    B5 的方向由小节名直接给出——「全局克制关系」段里的名字都是他克的，
    「反向克制思路」段里的名字都是克他的。方向不靠猜，所以能开。
    """
    out: list[dict] = []
    cur = ""
    mode = ""
    for ln in lines:
        if not ln or ln == "[图]":
            continue
        if "全局克制" in ln or "克制关系" in ln and ln.endswith(("：", ":")):
            mode = "win"
            continue
        if "反向克制" in ln or "克制思路" in ln:
            mode = "lose"
            continue
        h = header_of(ln, nm, name_re)
        if h:
            cur, mode = h, ""
            continue
        if not cur or not mode or len(ln) < 12:
            continue
        if not nm.in_lane(cur, lane):
            continue                       # 这一节讲的是别路英雄，不归本矩阵管
        # 逐句处理：一段里可能既有「克制他」也有「和他配合」，整段一起看必错。
        # 实测踩过：米莱狄那段写「还能与大乔配合打速推流」，整段扫名字就出了
        # 一条「米莱狄克制大乔」。
        for sent in sentences(ln):
            if len(sent) < 10 or any(w in sent for w in COOP_WORDS):
                continue
            if not any(w in sent for w in FIGHT_WORDS):
                continue
            names = []
            for tok in name_re.findall(sent):
                n = nm.canon(tok)
                if n and n != cur and n not in names and nm.in_lane(n, lane):
                    names.append(n)
            for n in names:
                a, b = (cur, n) if mode == "win" else (n, cur)
                out.append({"a": a, "b": b, "grade": "克", "branch": "B5",
                            "quote": f"[{mode}] {sent[:64]}", "layer": layer_of(sent)})
    return out


def parse_doc(doc: dict, text: str, nm: N.Names, lane: str,
              name_re: re.Pattern, branches: set[str] | None = None) -> list[dict]:
    on = branches if branches else {"B1", "B2", "B4", "B5"}
    edges: list[dict] = []
    lines = [ln.strip() for ln in text.splitlines()]

    for ln in lines:
        if not ln or ln == "[图]":
            continue
        # B1 箭头行：整行就是一条关系，不做句内再解析，避免重复
        arrow = parse_arrow(ln, nm, name_re) if "B1" in on else []
        if arrow:
            for a, b, grade in arrow:
                if not nm.in_lane(a, lane) or not nm.in_lane(b, lane):
                    continue
                edges.append({"a": a, "b": b, "grade": grade, "branch": "B1",
                              "quote": ln[:80], "layer": ""})
            continue
        # B4 括号列表：整行是小标题，解析完就走，别再把标题当句子读
        listed = parse_list_head(ln, nm, name_re) if "B4" in on else []
        if listed:
            for a, b, grade in listed:
                if not nm.in_lane(a, lane) or not nm.in_lane(b, lane):
                    continue
                edges.append({"a": a, "b": b, "grade": grade, "branch": "B4",
                              "quote": ln[:80], "layer": ""})
            continue
        # B2 句内动词
        if "B2" not in on:
            continue
        for sent in sentences(ln):
            if len(sent) > 160:            # 超长句多半是整段粘一起，可信度低
                continue
            for a, b, grade in parse_inline(sent, nm, name_re):
                if not nm.in_lane(a, lane) or not nm.in_lane(b, lane):
                    continue
                edges.append({"a": a, "b": b, "grade": grade, "branch": "B2",
                              "quote": sent[:80], "layer": layer_of(sent)})

    if "B3" in on:
        edges.extend(parse_sections(lines, nm, name_re, lane))
    if "B5" in on:
        edges.extend(parse_blocks(lines, nm, name_re, lane))

    for e in edges:
        e.update({"cv": doc["cv"], "cv_title": doc["title"][:60],
                  "url": f"{doc['url']}", "words": doc.get("words", 0)})
    return edges


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", default="mid")
    ap.add_argument("--sample", type=int, default=0, help="每分支抽样条数，人工核对用")
    # B3（小标题聚合）默认关闭：实测 12 条里 4 条与 B1/B2 直接矛盾，
    # 还有一篇自己跟自己打架。原因是「小标题给赢家 + 正文提到谁就把谁当输家」
    # 这个逻辑判不了方向——正文里的被提到，可能正好是在说"我不怕他"。
    # 要重开，得先给 B3 加一个方向分类器，不能只靠词频。
    ap.add_argument("--branches", default="B1,B2,B4,B5",
                    help="启用哪些分支（逗号分隔），B3 默认关")
    args = ap.parse_args()

    nm = N.load()
    pool = nm.by_lane(args.lane)
    name_re = build_name_re(pool)

    src = OUT / "columns.json"
    if not src.exists():
        print(f"[FATAL] 缺 {src}，先跑 s22_collect_columns.py", file=sys.stderr)
        return 1
    man = json.loads(src.read_text(encoding="utf-8"))

    on = {x.strip().upper() for x in args.branches.split(",") if x.strip()}
    all_edges: list[dict] = []
    used = missing = 0
    for doc in man["docs"]:
        cache = B.cache_get("article", doc["cv"])
        if not cache or not cache.get("text"):
            missing += 1
            continue
        used += 1
        all_edges.extend(parse_doc(doc, cache["text"], nm, args.lane, name_re,
                                   on))

    # 去重：同一 (a,b,grade) 同一 cv 只留一条
    uniq: dict[tuple, dict] = {}
    for e in all_edges:
        uniq.setdefault((e["a"], e["b"], e["grade"], e["cv"]), e)
    edges = list(uniq.values())

    by_branch = Counter(e["branch"] for e in edges)
    pairs = {(e["a"], e["b"]) for e in edges}
    undirected = {frozenset((e["a"], e["b"])) for e in edges}
    grade_mix = Counter(e["grade"] for e in edges)
    print(f"== 专栏解析 · {args.lane} ==")
    print(f"   文档 {used} 篇（缺正文 {missing}）· 原始边 {len(all_edges)} → 去重 {len(edges)}")
    print("   分支：" + " · ".join(f"{b} {by_branch[b]}"
                                   for b in ("B1", "B2", "B3", "B4", "B5")
                                   if by_branch[b]))
    print(f"   覆盖 {len(pairs)} 个有向对 / {len(undirected)} 个无序对 · "
          f"档位 {dict(grade_mix)}")

    # 矛盾检查：同一无序对被判成互相克制 → 必须人工裁决，不能自动落库
    clash: dict[frozenset, set] = defaultdict(set)
    for e in edges:
        clash[frozenset((e["a"], e["b"]))].add(e["grade"])
    bad = {k: v for k, v in clash.items() if len(v) > 1 and "五五开" not in v}
    if bad:
        print(f"   [WARN] {len(bad)} 个无序对出现互相克制的判断，需人工裁决：")
        for k, v in list(bad.items())[:8]:
            print(f"     {' vs '.join(sorted(k))} → {'/'.join(sorted(v))}")

    dst = OUT / f"{args.lane}.column_edges.jsonl"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", encoding="utf-8") as f:
        for e in sorted(edges, key=lambda x: (x["branch"], x["a"], x["b"])):
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"   -> {dst}")

    if args.sample:
        print("\n== 抽样核对（看方向对不对，不是看句子好不好看）==")
        for br in ("B1", "B2", "B3", "B4", "B5"):
            rows = [e for e in edges if e["branch"] == br][:args.sample]
            if not rows:
                continue
            print(f"\n-- {br} --")
            for e in rows:
                print(f"  {e['a']} {e['grade']} {e['b']}   cv{e['cv']}")
                print(f"     「{e['quote']}」")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
