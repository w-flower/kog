// v3：先走 SSO 登录 → 单附件 → 校验 → 发送 → 轮询 + 取件
import fs from "node:fs";

const DIR = "C:/Users/Lenovo/Desktop/Agent交接包/09-CodeArts网页版/scripts";
const cfg = JSON.parse(fs.readFileSync(`${DIR}/.ego-cfg.json`, "utf-8"));
const LOG = "D:/Projects/kog/50_logs/codearts/dispatch_v3.log";
const log = (...a) => { const s = a.join(" "); console.log(s); try { fs.appendFileSync(LOG, s + "\n", "utf-8"); } catch (e) {} };

const LOGIN = "https://auth.huaweicloud.com/authui/login.html?service=" +
  encodeURIComponent("https://devcloud.cn-north-4.huaweicloud.com/chat/home");
const HOME = "https://devcloud.cn-north-4.huaweicloud.com/chat/home";
const TARGET_FILE = cfg.targetFile || "系统卡_辅助决策.md";
const SAVE_TO = cfg.saveTo || "D:/Projects/kog/50_logs/codearts/support_raw.md";
const MAX_MIN = cfg.maxMinutes || 35;

fs.writeFileSync(LOG, "", "utf-8");
log("=== start", new Date().toISOString());

const task = await taskSpace(cfg.spaceName || "codearts-kog-support");
log("space:", task.spaceId, task.name);

const p = await task.newPage();
log("tab:", p.label);

// 1) 先走 SSO
await p.goto(LOGIN, { timeout: 60000 });
await p.waitForTimeout(9000);
let st = await p.evaluate(() => ({ url: location.href.slice(0, 90), len: document.body.innerText.length, needLogin: /登录华为云/.test(document.body.innerText) }));
log("after sso:", JSON.stringify(st));
if (st.needLogin) { log("STILL NOT LOGGED IN — abort"); process.exit(2); }

// 2) 新建任务页
await p.goto(HOME, { timeout: 60000 });
await p.waitForTimeout(6000);
try { await p.click("loc=css:button[aria-label='关闭']", { timeout: 1500 }); } catch (e) {}

// 3) 附件（校验 + 重试）
const atts = cfg.attachments || [];
let attached = false;
for (let i = 1; i <= 3 && atts.length && !attached; i++) {
  try { await p.setInputFiles("loc=css:input[type=file]:not([accept])", atts); } catch (e) { log(`upload ${i} err`, String(e).slice(0, 80)); }
  await p.waitForTimeout(7000);
  const s = await p.evaluate(() => ({ fail: /上传失败/.test(document.body.innerText), txt: document.body.innerText.slice(-160).replace(/\n/g, " ") }));
  log(`upload ${i}: fail=${s.fail} tail=${s.txt.slice(0, 80)}`);
  if (!s.fail) { attached = true; break; }
}

// 4) prompt
const prompt = fs.readFileSync(cfg.promptFile, "utf-8");
let text = prompt;
if (!attached && atts.length) {
  log("== fallback: 把附件全文塞进 prompt ==");
  text = prompt + "\n\n---\n\n" + fs.readFileSync(atts[0], "utf-8");
}
await p.fill("loc=css:textarea.mc-textarea", text);
await p.waitForTimeout(1200);
const plen = await p.evaluate(() => document.querySelector("textarea.mc-textarea")?.value.length ?? -1);
log("prompt chars:", plen, "attached:", attached);

// 5) 发送
try {
  await p.click("loc=css:.mc-input button.mc-button.mc-button-simple", { timeout: 8000 });
  log("clicked send");
} catch (e) { log("send click err:", String(e).slice(0, 90)); }
await p.waitForTimeout(8000);

const getSid = async () => ((await p.url()).match(/sessionId=([^&]+)/) || [])[1] || "";
let sid = await getSid();
log("url:", (await p.url()).slice(0, 110), "sid:", sid.slice(0, 10));
fs.writeFileSync(cfg.labelOut, `${p.label}\n${sid}\n${task.spaceId}`, "utf-8");

const tryFetch = async (s) => {
  const u = "/chat/codebaseservice/v1/cloudagent/sessions/" + s +
    "/files/download?path=" + encodeURIComponent("/workspace/" + TARGET_FILE) + "&recursive=false";
  return await p.evaluate(async (x) => {
    try {
      const res = await fetch(x, { headers: { "x-requested-with": "XMLHttpRequest", "language": "zh-cn" } });
      if (!res.ok) return { status: res.status, body: (await res.text()).slice(0, 80) };
      const bytes = new Uint8Array(await res.arrayBuffer());
      let bin = "";
      for (let i = 0; i < bytes.length; i += 0x8000) bin += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
      return { status: res.status, b64: btoa(bin), size: bytes.length };
    } catch (e) { return { status: 0, body: String(e).slice(0, 80) }; }
  }, u);
};

const deadline = Date.now() + MAX_MIN * 60 * 1000;
let round = 0;
while (Date.now() < deadline) {
  round++;
  await p.waitForTimeout(40000);
  if (!sid) { const s = await getSid(); if (s) { sid = s; log("sid acquired:", sid.slice(0, 10)); } }

  const s2 = await p.evaluate(() => {
    const t = document.body.innerText;
    return {
      len: t.length,
      done: /任务完成[\s\S]{0,80}共消耗积分/.test(t) || /共消耗积分[\s\S]{0,40}任务完成/.test(t),
      running: [...document.querySelectorAll("button")].some((b) => b.offsetParent !== null && /停止|stop/i.test(b.innerText || "")),
      artifacts: [...document.querySelectorAll(".artifact-item__name")].map((e) => e.textContent.trim()),
      tail: t.slice(-90).replace(/\n/g, " "),
    };
  });
  log(`[${round}] ${s2.running ? "RUNNING" : s2.done ? "DONE" : "UNK"} len=${s2.len} art=${JSON.stringify(s2.artifacts)} | ${s2.tail.slice(0, 55)}`);

  if (sid) {
    const r = await tryFetch(sid);
    if (r.b64) {
      fs.mkdirSync(SAVE_TO.replace(/[\\/][^\\/]+$/, ""), { recursive: true });
      fs.writeFileSync(SAVE_TO, Buffer.from(r.b64, "base64"));
      log(`FETCHED ${r.size}B -> ${SAVE_TO}`);
      process.exit(0);
    }
  }
}
log("TIMEOUT");
process.exit(4);
