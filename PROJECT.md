# PROJECT.md — 王者荣耀知识库（kog）

> **给接手的新 agent**：先读这页，再读 `00_README.md`（给"人"看的说明）和 `20_kb/00_导航.md`。
> 本文件只讲「怎么维护它」，不重复知识内容。

- **位置**：`D:\Projects\kog`（2026-11-19 从 `C:\Users\Lenovo\WorkBuddy\kog` 迁来）
- **线上**：https://w-flower.github.io/kog/
- **仓库**：`git@github.com:w-flower/kog.git`，分支 `main`，走 GitHub Actions 部署 Pages
- **规模**：20_kb 下 290 个 md（A 英雄卡 131 / B 克制 130 / C BP 6 / D 对局 16 / L 分路 6），K 条目 282 条，索引 717 行
- **定位**：可追溯的王者教学知识库。**每一条结论必须带 `BV号 @ MM:SS` 出处**，没素材就写"待补"，绝不凭常识编。

---

## 1. 快速上手

```bash
cd D:/Projects/kog
PY="C:/Users/Lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe"

$PY 40_scripts/s5_index.py --strict      # 重建索引，输出 indexed= / bad_timestamp=
$PY 40_scripts/s28_card_audit.py         # A 卡体检，输出 ok= / bad=
$PY 40_scripts/deploy.py                 # 索引 → 构建 → git commit&push（1-2 分钟后生效）
```

**所有脚本都用 `Path(__file__).resolve().parent.parent` 定位项目根，不依赖 cwd，也不含硬编码盘符——换目录不用改代码。**

---

## 2. 目录地图

```
D:\Projects\kog\
├── 00_README.md          给人读的完整说明（含路径地图、判定口诀）
├── README.md             仓库首页说明
├── 10_sources\           素材层（只进不改，可整层删了重采）
│   ├── heroes\<英雄>\videos.json     该英雄的候选视频清单（s30 写入）
│   ├── creators_cache\subs\          字幕缓存 <BV>.json（共 832 个）
│   ├── creators_cache\hero_batch_map.json  BV→英雄 映射
│   └── raw\              <BV>.cues.json / <BV>.txt（带时间戳）
├── 20_kb\                知识层（人读的唯一入口）
│   ├── 00_导航.md        四类入口 + 判定口诀
│   ├── A_英雄教学\       131 张英雄卡
│   ├── B_克制关系\       130 张克制卡
│   ├── C_BP\             6 张 BP 卡
│   ├── D_对局内\         16 张对局系统卡
│   ├── L_分路\           6 张分路卡
│   ├── 95_信源名单.md    ★权威 UP 名册（§十是当前唯一可信的评级）
│   └── 96_素材缺口.md    ★素材缺口台账（幽灵字幕/串源/重采记录都在这）
├── 30_index\index.jsonl  检索索引（s5_index 生成，717 行）
├── 40_scripts\           63 个脚本，全部 `s<数字>_<用途>.py` 命名
├── 50_logs\              日志 / 转录 / 摘要 / 码道输入包与产物
│   ├── transcripts\      带 [MM:SS] 的纯文本转录
│   ├── digest\           教学高信号摘要
│   ├── upload\           给码道的 prompt_*.md + batch_*.md + skill_*.md
│   └── codearts\         码道产物 raw.md 与备份
├── site\                 构建产物（单文件 index.html，不要手改）
└── site_src\             模板 template.html / app.css / app.js
```

---

## 3. 内容生产流水线（六步）

```
① 搜候选  s30_search_browser.py --hero 英雄名 [多个]
             ↓ 写 10_sources/heroes/<英雄>/videos.json
② 取字幕  subs_browser.py --bvid BVxxx [多个]
             ↓ 写 10_sources/creators_cache/subs/<BV>.json
③ 预检    s47_precheck_subs.py / s50_precheck_heroes.py
             ↓ 判据：英雄名命中 >=2 或 王者术语密度 >=12/千字，否则 SUSPECT
④ 装配    s42 / s44 / s46 / s48 / s51 → 50_logs/upload/{prompt_*, batch_*}
             ↓ 素材 + 写作规范（skill_王者系统卡写作规范.md 等）一起当附件
⑤ 派码道  桌面 Agent交接包 09 的 ego-dispatch.mjs（见第 5 节）
             ↓ 产物回 50_logs/codearts/*_raw.md
⑥ 落盘审计 s43_split_cards.py <raw> --write / s45_split_system.py
             ↓ 再跑 s5_index --strict + s28_card_audit → deploy.py
```

**关键：创作一律交码道（CodeArts），本地只做搜索、取字幕、预检、装配、收件、落盘、断言。** 这是用户定的硬规则，别在本地写卡。

### ③ 的特殊情况：视频根本没有字幕怎么办

B 站 AI 字幕只在**登录态**下暴露，且有些视频**只给 ai-en / ai-ja 机器翻译轨，没有 ai-zh**。这时候走本地 ASR：

```bash
# 1) 下音频（本机已装 ffmpeg + yt-dlp）
yt-dlp -f bestaudio -x --audio-format wav --postprocessor-args "-ar 16000 -ac 1" -o audio.%(ext)s "https://www.bilibili.com/video/<BV>"
# 2) 转写（medium 精度够用，10 分钟音频约 14 分钟）
python 40_scripts/s52_transcribe.py audio.wav out.txt 60_state/models/faster-whisper-medium zh prompt_domain.py
# 3) 转写有繁简混杂 + 专有名词错，要过一遍人工校订，再生成 cues 让索引可校验
python 40_scripts/s55_asr_to_cues.py out_clean.txt 10_sources/raw/<BV>.cues.json <时长秒>
```

- 第五个参数传 `.py` 文件时取其中 `PROMPT` 变量——**把本视频涉及的英雄名和术语塞进去，专有名词准确率明显提升**，这一步别省。
- small 模型够快但专有名词错得多（嫦娥→"长额"、河道视野→"核到视野"），medium 明显更好。

---

## 4. 卡片规范

### A 英雄卡（`20_kb/A_英雄教学/<英雄>.md`）
front matter 固定 10 字段、顺序不能乱：

```yaml
---
id: 英雄名
cat: A
title: 英雄名（分路·定位）
tempo: early|mid|late|unknown
job: scout|split|follow|hold|open
motto: 一句话金句（从素材原文摘）
version: S45
status: draft
updated: 2026-11-19
sources: [BV1xxxxxxxxx]
---
```

正文 6 节 + 待补：`## 0. 大局观定位` / `## 1. 机制内核` / `## 2. 对线·打法` / `## 3. 出装铭文` / `## 4. 强势期与节奏` / `## 5. 克制与被克制` / `## 待补`。
**至少要有一条 `（BVxxx @ MM:SS）` 时间戳引用**，`s43` 会断言。

### D 系统卡（`20_kb/D_对局内/`）
每条 K 条目含：适用版本 / 触发条件 / 判断依据 / 决策分支 / 反例 / 来源 / 可信度 / 状态。规范见 `50_logs/upload/skill_王者系统卡写作规范.md`。

---

## 5. 外部依赖

| 依赖 | 在哪 | 备注 |
|---|---|---|
| **码道 CodeArts 网页版** | 脚本：`C:\Users\Lenovo\Desktop\Agent交接包\09-CodeArts网页版\scripts\`（`ego-dispatch/status/fetch.mjs`） | 配置 `.ego-cfg.json`（派发）/ `.ego-watch.json`（轮询）/ `.ego-fetch.json`（取件）。**路径已同步到 D 盘** |
| 码道任务空间 | spaceId 会变 | **每次派活前先跑 `list_spaces` 确认**，旧空间常被回收（14、19 都没了） |
| B 站登录态 | `C:\Users\Lenovo\.workbuddy\data\bilibili-video-summary\browser-profile\` | 匿名也能搜（未风控），登录态用于取 AI 字幕 |
| ego-browser | `ego-browser nodejs -e "await import('file:///...')"` | 跑 `.mjs` 脚本的唯一入口 |
| GitHub | `ssh.github.com:443` | `github.com:443` 与 `:22` 在这台机器不通，SSH 已配好跳板 |
| 无 CC 字幕视频的取字幕 | `C:\Users\Lenovo\ego\kog-video-BV1nMLQ6XE7j\` | step1~step3.mjs + conv.py，见坑 #9 |

---

## 6. 已知坑（踩过的，按重要性排）

1. **幽灵字幕**：`x/player/wbi/v2` 返回 `subtitles: []` 且无 `ai_subtitle` → 这个 BV 永远取不到字幕。**换视频重搜，重取同一个 BV 无效**。
2. **串源（最坑）**：标题写着英雄名，内容却是别的游戏/别的英雄。已知案例：甄姬→LoL T1 vs Gen.G、芈月→分体水冷装机。**预检只是第一道闸，必须人工按标题再筛**。
3. **"X 对线 Y" 主体是 X**：给 Y 用会写偏。这类视频标题里的次要英雄名反而更显眼。
4. **UP 名含"万象棋"的一律排除**——那是棋类玩法，不是 MOBA。
5. **`s43_split_cards.py` 必须带 `--write`**，不带只校验不落盘（白跑过一轮）。
6. **`s43` 的时间戳正则只认 `BVxxx @ MM:SS`**，单来源卡写成 `（@ MM:SS）` 会漏计，不是卡的问题。
7. **核对站点不要 grep 标题**：A 卡渲染不输出 H1 标题，用 BV 号 / 金句 / 正文特征串核对。
8. **码道并发上限 3、标签预算 8**；满了就关页腾槽，**只 `page.close()`，绝不删会话**（用户在里面有正在生成的任务）。
9. **无 CC 字幕 ≠ 没字幕**：ego 登录态取 `wbi_img` → md5 算 `w_rid` → 调 `x/player/wbi/v2` 拿 `ai-zh` 轨。`hdslb` 域跨域，**必须 Node 端 `https.get` 带 `Referer` 下载**，页面内 fetch 一定失败。
10. **码道状态 `UNKNOWN` 不代表失败**：`len` 在涨就是在写（自检阶段），只有 `DONE` 才有 `artifacts`。
11. **bash 里给 `python -c` 传中文/反引号会出事**：反引号被当命令替换。写临时 `.py` 文件再跑，或用 `<<'EOF'`。
12. **PowerShell 的 stdout 不回显**：要拿输出就写文件再读。
13. **2026-11-19 迁移事故**：批量替换 `Path(r"...")` 时漏了收尾括号，产生 21 个语法错误文件。教训——**路径替换后必须逐个 `py_compile` 检查**，别只看 grep 残留为 0。
14. **码道登录态"假有效"**：`auth.huaweicloud.com` 打开能直接进控制台（华为云 SSO 是好的），但 `devcloud.../chat/home` 仍显示「登录华为云」。**必须 goto 带 service 的完整 URL**：`https://auth.huaweicloud.com/authui/login.html?service=<encodeURIComponent("https://devcloud.cn-north-4.huaweicloud.com/chat/home")>`，等 9 秒会自己跳回来并已登录。直接点页面上那个「登录华为云」按钮**没有任何反应**。
15. **ego 的 task space 是进程级的**：`taskSpace(name)` 建的空间，nodejs 进程一结束就销毁，下个进程去 `taskSpace(1)` 会报 `task space not found`。所以**派发 + 轮询 + 取件必须在同一个进程里跑完**。`dispatch_wait*.mjs` 就是为此写的。
16. **多附件容易上传失败**：两个附件曾卡在「上传失败，请重试」41 分钟。**合并成单附件**（规范+素材+任务塞进一个 md）+ 上传后检测 `上传失败` 文本 + 重试 3 次，成功率明显高。
17. **bash 重定向会吞 ego 的输出**：`ego-browser nodejs -e ... > log 2>&1` 是块缓冲，一个多小时看不到一行。要在脚本内部用 `fs.appendFileSync` 写日志。
18. **ASR 的 `unverified`**：新视频没有 B 站字幕时，索引会把该 BV 的所有条目判为 `unverified`（没有 cues 可校验）。跑一次 `s55_asr_to_cues.py` 补 cues 即可归零。
19. **`git add -A` 会误带杂物**：11-21 提交时混进了 `dsh-remote-qr.png`。提交前先 `git status` 看一眼。

---

## 7. 现状快照（2026-11-19 18:40）

- A 卡 131 张，审计 0 问题；索引 717 行，坏时间戳 0
- **其中 90 张仍是薄卡（< 2200 字符）**：苍 / 云缨 / 妲己 / 弈星 / 赵云 / 后羿 / 狂铁 / 蒙恬 / 蒙犽 / 黄忠 / 云中君 / 孙悟空 / 安琪拉 / 沈梦溪 / 米莱狄 / 盘古 / 孙尚香 / 程咬金 / 莱西奥 / 宫本武藏 / 干将莫邪 / 百里玄策 / 海月 / 白起 / 王昭君 / 达摩 / 孙策 / 蔡文姬 / 项羽 / 姜子牙 / 廉颇 / 鲁班七号 / 庄周 / 张良 / 朵莉亚 / 杨玉环 / 鬼谷子 / 金蝉 / 墨子 / 元辅 …
- 最新一轮（11-21）：新增 **D12 辅助决策**（25 条 K，K-D111~K-D135），来源 BV1S8sn6zEJq（欺压ya 辅助精讲课 02 期）——该视频无中文 CC 字幕，走本地 faster-whisper medium 转写 + 人工校订。索引 905 行、271 条站点节点、坏时间戳 0、未验证 0
- 上一轮（11-19）：10 个串源英雄重采成功，净 24 条真素材，产出 10 张卡（亚瑟 7305 字最厚；李信/猪八戒/甄姬 单素材偏薄）；D11 整局节奏系统卡 20 条 K 条目
- 最近部署：commit `9f75f91`（D12）← `b502500`（迁移）← `25d2511`（10 卡 + D11）

---

## 8. 下一步（优先级从高到低）

1. **继续救薄卡**：从 90 张薄卡里按 10 个一批走完整流水线，每批约需 40 分钟（搜索 5min + 字幕 6min + 预检 1min + 码道 10~15min + 落盘审计 5min）。
2. **单素材英雄补源**：李信 / 猪八戒 / 甄姬 目前只有 1 条素材，卡偏薄，值得再搜一轮换 UP。
3. **D 类系统卡**：目前 16 张，中后期运营（大龙决策、分推时机、视野布控）仍缺。
4. **信源名单刷新**：`95_信源名单.md` §十 是权威，但 `creators_scored.json` 是旧快照，别用。

---

## 9. 变更历史

| 日期 | 变更 |
|---|---|
| 2026-11-21 | 新增 D12 辅助决策（25 条 K）；打通本地 ASR 通道（s52）+ ASR→cues（s55）；新增 s53/s54 装配脚本 |
| 2026-11-19 | 从 `C:\Users\Lenovo\WorkBuddy\kog` 迁到 `D:\Projects\kog`；43 个脚本路径改 `__file__` 自动推导；新增本文件 |
| 2026-11-19 | 10 个串源英雄重采 + 10 张卡落盘；新增 D11 整局节奏；新增 s48~s51 脚本 |
| 2026-11-18 | 新增 s47 串源预检闸门（拦住 14/17 假素材） |
| 2026-11-17 | 首次部署 GitHub Pages；卡片体系定型 |
