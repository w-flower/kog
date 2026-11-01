/* ══════════════════════════════════════════════════════════
   kog 站点交互 —— 英雄宫格 + 折叠卡
   数据来自 <script id="DATA" type="application/json">，构建时注入
   路由用 hash（要支持 file:// 直接打开，不能用 History API）：
     # / 空        → 英雄宫格
     #H:苏烈       → 英雄页
     #doc:xx.md    → 长文档（信源名单 / 版本台账 / 导航）
     #cat:A        → 某一类的全部条目
     #K-B01        → 直达条目并展开
   ══════════════════════════════════════════════════════════ */
(function () {
  const D = JSON.parse(document.getElementById('DATA').textContent);
  const view = document.getElementById('view');
  const qEl = document.getElementById('q');
  const root = document.documentElement;

  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  /* ── 扁平分索引：搜索与直达用 ── */
  const IDX = [];
  D.heroes.forEach(h => {
    h.a.concat(h.b).forEach(e => IDX.push({ ...e, owner: h.name, kind: 'H:' + h.name }));
  });
  D.general.forEach(g => g.entries.forEach(e =>
    IDX.push({ ...e, owner: g.title, kind: 'doc:' + g.file })));
  (D.lanes || []).forEach(l => l.entries.forEach(e =>
    IDX.push({ ...e, owner: l.name, kind: 'lane:' + l.file })));

  const heroOf = n => D.heroes.find(h => h.name === n);
  const laneOf = f => (D.lanes || []).find(l => l.file === f);
  const byId = id => IDX.find(e => e.id === id);

  /* ── 条目折叠卡 ── */
  function entryCard(e, open) {
    const idAttr = e.id ? ` id="${esc(e.id)}"` : '';
    const idTag  = e.id ? `<span class="id">${esc(e.id)}</span>` : '';
    return `<details class="entry"${idAttr}${open ? ' open' : ''}>
      <summary>
        ${idTag}
        <span class="tt"><b>${esc(e.title)}</b>
          <span>${esc(e.sum || '')}</span></span>
        <svg class="chev" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </summary>
      <div class="body">${e.html || ''}</div>
    </details>`;
  }

  /* ── 大局观定位：强势期 / 节奏职责 / 一句话 ── */
  const TEMPO_CN = { early: '前期', mid: '中期', late: '后期', even: '全期' };
  const JOB_CN = { open: '开节奏', follow: '跟节奏', hold: '守节奏',
                   scout: '视野侦察', split: '带线牵制' };
  function planTags(h) {
    const out = [];
    if (h.tempo) out.push(`<span class="pill t-${esc(h.tempo)}">${esc(TEMPO_CN[h.tempo] || h.tempo)}</span>`);
    if (h.job) out.push(`<span class="pill j-${esc(h.job)}">${esc(JOB_CN[h.job] || h.job)}</span>`);
    return out.join('');
  }

  /* ── 英雄卡 ── */
  function heroCard(h) {
    const pills = [];
    if (h.a.length) pills.push(`<span class="pill a">怎么玩 ${h.a.length}</span>`);
    // 克制数来自官方口径（全英雄池都有），比"对位条目数"更能反映这张卡有多厚
    if (h.beats_n) pills.push(`<span class="pill kw">克 ${h.beats_n}</span>`);
    if (h.loses_n) pills.push(`<span class="pill kl">被克 ${h.loses_n}</span>`);
    if (!pills.length) pills.push('<span class="pill g">待补</span>');
    const plan = planTags(h);
    return `<a class="hcard" href="#H:${encodeURIComponent(h.name)}">
      <span class="avatar" style="--h:${h.hue}">${esc(h.name.slice(0, 1))}</span>
      <span class="hname">${esc(h.name)}${h.unlisted ? '<i class="unlisted" title="官方 129 英雄名录里没有这个名字">?</i>' : ''}</span>
      <span class="hmeta">${pills.join('')}</span>
      ${plan ? `<span class="hplan">${plan}</span>` : ''}
    </a>`;
  }

  /* ── 分路卡 ── */
  function laneCard(l) {
    return `<a class="lcard" href="#lane:${encodeURIComponent(l.file)}">
      <span class="avatar" style="--h:${l.hue}">${esc(l.icon)}</span>
      <span class="hname">${esc(l.name)}</span>
      <span class="hmeta">
        <span class="pill l">${l.entries.length} 条</span>
        ${l.heroes.length ? `<span class="pill g">${l.heroes.length} 英雄</span>` : ''}
      </span>
      <span class="lmotto">${esc(l.motto || '')}</span>
    </a>`;
  }

  /* ── 首页 ── */
  function renderHome() {
    const heroes = D.heroes.map(heroCard).join('');
    const lanes = (D.lanes || []).map(laneCard).join('');
    const gen = D.general.filter(g => g.entries.length || g.intro).map(g => {
      const icon = g.key === 'D' ? '⌁' : g.key === 'C' ? '⇄' : '·';
      const n = g.entries.length;
      return `<a class="gcard" href="#doc:${encodeURIComponent(g.file)}">
        <span class="gicon">${icon}</span>
        <span class="gtxt"><b>${esc(g.title)}</b>
          <span>${esc(g.cat)} · ${n ? n + ' 条判断' : '阅读'}</span></span>
      </a>`;
    }).join('');

    const docs = D.overview.filter(o => o.file !== '00_导航.md').map(o =>
      `<a class="gcard" href="#doc:${encodeURIComponent(o.file)}">
        <span class="gicon">▤</span>
        <span class="gtxt"><b>${esc(o.title.replace(/（.*?）/, ''))}</b>
          <span>参考文档</span></span>
      </a>`).join('');

    view.innerHTML = `
      <div class="hero-head">
        <p class="eyebrow">${esc(D.version)} · 决策手册</p>
        <h1>点英雄，看怎么打</h1>
        <p class="lede">每一条结论都能回溯到具体视频与秒数。有判据才写，没把握就留空。</p>
      </div>

      <section class="sec">
        <div class="sec-h"><h2>按分路看</h2><span>同一时间点，五个位置要做的决定不一样</span></div>
        <div class="grid lanes">${lanes}</div>
      </section>

      <section class="sec">
        <div class="sec-h"><h2>英雄</h2>
          <span>${D.heroes.length} 个 · 点开看全部 ·
            <a href="#matrix">对位总表 →</a>${duelHas()
              ? ` · <a href="#duel:${encodeURIComponent(Object.keys(D.duel)[0])}">同路五档矩阵 →</a>` : ''}</span></div>
        <div class="grid">${heroes}</div>
      </section>

      ${gen ? `<section class="sec">
        <div class="sec-h"><h2>不挑英雄的</h2><span>对线、节奏、BP</span></div>
        <div class="row">${gen}</div>
      </section>` : ''}

      ${docs ? `<section class="sec">
        <div class="sec-h"><h2>参考</h2></div>
        <div class="row">${docs}</div>
      </section>` : ''}
    `;
  }

  /* ── 英雄页 ── */
  function renderHero(name) {
    const h = heroOf(name);
    if (!h) return renderHome();

    const secA = h.a.length
      ? `<section class="sec"><div class="sec-h"><h2>怎么玩</h2>
           <span>${h.a.length} 条</span></div>
           ${h.a.map(e => entryCard(e, false)).join('')}</section>`
      : `<section class="sec"><div class="sec-h"><h2>怎么玩</h2></div>
           <p class="lede">还没有这个英雄的条目。</p></section>`;

    const secB = h.b.length
      ? `<section class="sec"><div class="sec-h"><h2>打谁 / 被谁克</h2>
           <span>${h.b.length} 条</span></div>
           ${h.b.map(e => entryCard(e, false)).join('')}</section>`
      : '';

    const inc = h.incoming.length
      ? `<section class="sec"><div class="sec-h"><h2>被这些英雄的条目点名</h2></div>
           <p class="lede">${h.incoming.map(n =>
             `<a href="#H:${encodeURIComponent(n)}">${esc(n)}</a>`).join('、')}
           的克制条目里提到了他，点进去看具体打法。</p></section>`
      : '';

    // 克制速览：官方口径的两组名字，点一下就能跳到对方
    const chip = n => `<a class="oppchip" href="#H:${encodeURIComponent(n)}">${esc(n)}</a>`;
    const secK = (h.beats.length || (h.loses_all || []).length)
      ? `<section class="sec"><div class="sec-h"><h2>克制速览</h2>
           <span>官方口径 L0 · 具体怎么打看下面的卡</span></div>
         <div class="oppbox">
           <div class="opprow">
             <span class="oppk win">我压</span>
             <span class="oppv">${(h.beats.length ? h.beats.map(chip).join('') : '<i class="dim">官方没列</i>')}</span>
           </div>
           <div class="opprow">
             <span class="oppk lose">压我</span>
             <span class="oppv">${((h.loses_all || []).length ? h.loses_all.map(chip).join('') : '<i class="dim">官方没列</i>')}</span>
           </div>
         </div>
         <p class="lede"><a href="#matrix">看全部 ${D.heroes.length} 个英雄的对位表 →</a></p>
         </section>`
      : '';

    const plan = (h.tempo || h.job || h.motto)
      ? `<div class="planbox">
           <div class="pb-cell">
             <span class="pb-k">强势期</span>
             <b>${esc(TEMPO_CN[h.tempo] || '—')}</b>
           </div>
           <div class="pb-cell">
             <span class="pb-k">节奏职责</span>
             <b>${esc(JOB_CN[h.job] || '—')}</b>
           </div>
           <div class="pb-cell wide">
             <span class="pb-k">一句话</span>
             <b>${esc(h.motto || '—')}</b>
           </div>
         </div>`
      : '';

    view.innerHTML = `
      <a class="back" href="#">← 全部英雄</a>
      <div class="hhead">
        <span class="avatar" style="--h:${h.hue}">${esc(h.name.slice(0, 1))}</span>
        <div>
          <h1>${esc(h.name)}</h1>
          <div class="hmeta">
            <span class="pill g">${h.n} 条</span>
            ${h.unlisted ? '<span class="pill w">不在官方名录</span>' : ''}
            ${h.beats_n ? `<span class="pill kw">克 ${h.beats_n}</span>` : ''}
            ${h.loses_n ? `<span class="pill kl">被克 ${h.loses_n}</span>` : ''}
            ${planTags(h)}
            ${(h.lanes || []).map(k => {
              const l = (D.lanes || []).find(x => x.key === k);
              return l ? `<a class="pill l" href="#lane:${encodeURIComponent(l.file)}">${esc(l.name)}大局观</a>` : '';
            }).join('')}
          </div>
        </div>
      </div>
      ${plan}
      ${duelBox(h.name)}${secK}${secA}${secB}${inc}
    `;
  }

  /* ── 分路页 ── */
  function renderLane(file) {
    const l = laneOf(file);
    if (!l) return renderHome();

    const heroRow = l.heroes.length
      ? `<div class="grid">${l.heroes.map(n => heroCard(heroOf(n))).filter(Boolean).join('')}</div>`
      : `<p class="lede">这个分路还没有英雄卡。${l.key === 'adc' || l.key === 'jungle'
          ? '（这是已知缺口：没有以该位置为第一视角的素材。）' : ''}</p>`;

    const others = (D.lanes || []).filter(x => x.key !== l.key).map(x =>
      `<a class="klink" href="#lane:${encodeURIComponent(x.file)}">${esc(x.name)} · ${esc(x.motto || '')}</a>`).join('');

    const stages = (l.stages || []).length
      ? `<div class="row">${l.stages.map(s =>
          `<a class="gcard" href="#doc:${encodeURIComponent(s.file)}">
            <span class="gicon">⌁</span>
            <span class="gtxt"><b>${esc(s.title)}</b><span>对局内 · ${s.id} 节</span></span>
          </a>`).join('')}</div>`
      : `<p class="lede">这一路还没有对应的对局内环节。</p>`;

    view.innerHTML = `
      <a class="back" href="#">← 返回</a>
      <div class="hhead">
        <span class="avatar" style="--h:${l.hue}">${esc(l.icon)}</span>
        <div>
          <h1>${esc(l.name)}</h1>
          <div class="hmeta">
            <span class="pill l">${l.entries.length} 条判断</span>
            <span class="pill g">只看位置，不看英雄</span>
          </div>
        </div>
      </div>

      <section class="sec"><div class="sec-h"><h2>这一路的大局观</h2></div>
        <div class="doc">${l.intro || ''}</div></section>

      <section class="sec"><div class="sec-h"><h2>分条判断</h2>
        <span>${l.entries.length} 条</span></div>
        ${l.entries.map(e => entryCard(e, false)).join('')}</section>

      <section class="sec"><div class="sec-h"><h2>这个位置的英雄</h2></div>${heroRow}</section>

      <section class="sec"><div class="sec-h"><h2>对应的时间环节</h2></div>${stages}</section>

      <section class="sec"><div class="sec-h"><h2>交叉的分路</h2>
        <span>同一件事，两边判据要对得上</span></div>
        <div class="row">${others}</div></section>
    `;
  }

  /* ── 长文档页 ── */
  function renderDoc(file) {
    const o = D.overview.find(x => x.file === file);
    const g = D.general.find(x => x.file === file);
    if (o) {
      view.innerHTML = `<a class="back" href="#">← 返回</a>
        <div class="doc">${o.html}</div>`;
      return;
    }
    if (g) {
      view.innerHTML = `<a class="back" href="#">← 返回</a>
        <div class="hero-head"><p class="eyebrow">${esc(g.cat)}</p>
          <h1>${esc(g.title)}</h1></div>
        <div class="doc">${g.intro || ''}</div>
        ${g.entries.map(e => entryCard(e, false)).join('')}`;
      return;
    }
    renderHome();
  }

  /* ── 分类页 ── */
  function renderCat(key) {
    const c = D.cats.find(x => x.key === key);
    if (!c) return renderHome();
    const list = IDX.filter(e => e.cat === key);
    view.innerHTML = `<a class="back" href="#">← 返回</a>
      <div class="hero-head"><p class="eyebrow">分类</p>
        <h1>${esc(c.name)}</h1><p class="lede">${esc(c.desc)}</p></div>
      ${list.length ? list.map(e => entryCard(e, false)).join('')
        : '<p class="empty">这一类还没有条目。</p>'}`;
  }

  /* ── 搜索 ── */
  function renderSearch(kw) {
    const k = kw.trim().toLowerCase();
    if (!k) return renderHome();
    const hs = D.heroes.filter(h => h.name.toLowerCase().includes(k));
    const es = IDX.filter(e =>
      (e.id + e.title + (e.sum || '') + (e.opp || '')).toLowerCase().includes(k));

    view.innerHTML = `
      <div class="hero-head"><p class="eyebrow">搜索</p>
        <h1>“${esc(kw.trim())}”</h1>
        <p class="lede">${es.length} 条结论${hs.length ? ` · ${hs.length} 个英雄` : ''}</p></div>
      ${hs.length ? `<section class="sec"><div class="sec-h"><h2>英雄</h2></div>
        <div class="grid">${hs.map(heroCard).join('')}</div></section>` : ''}
      ${es.length ? `<section class="sec"><div class="sec-h"><h2>结论</h2></div>
        ${es.map(e => entryCard(e, true)).join('')}</section>`
        : '<p class="empty">没有命中。换个词试试，比如英雄名或「对线」。</p>'}`;
  }

  /* ── 对位总表：129 个英雄一张表 ── */
  function renderMatrix() {
    const LANES = [['solo', '对抗路'], ['jungle', '打野'], ['mid', '中路'],
                   ['adc', '发育路'], ['roam', '游走']];
    const chip = (n, cls) => `<a class="oppchip ${cls || ''}" href="#H:${encodeURIComponent(n)}">${esc(n)}</a>`;
    const rowsOf = list => list.map(h => {
      const b = h.beats.length ? h.beats.map(n => chip(n, 'win')).join('') : '<i class="dim">—</i>';
      const l = (h.loses_all || []).length ? h.loses_all.map(n => chip(n, 'lose')).join('') : '<i class="dim">—</i>';
      return `<div class="mtx-row">
        <a class="mtx-h" href="#H:${encodeURIComponent(h.name)}">${esc(h.name)}</a>
        <div class="mtx-cell"><span class="mtx-lab win">他压制的</span>${b}</div>
        <div class="mtx-cell"><span class="mtx-lab lose">压制他的</span>${l}</div>
      </div>`;
    }).join('');

    const head = `<div class="mtx-row mtx-head">
        <span>英雄</span><span>他压制的</span><span>压制他的</span>
      </div>`;

    const blocks = LANES.map(([k, cn]) => {
      const list = D.heroes.filter(h => h.main_lane === k)
        .sort((a, b) => b.beats_n - a.beats_n || a.name.localeCompare(b.name, 'zh'));
      if (!list.length) return '';
      return `<section class="sec">
        <div class="sec-h"><h2>${cn}</h2><span>${list.length} 个</span></div>
        <div class="mtx">${head}${rowsOf(list)}</div>
      </section>`;
    }).join('');

    const noLane = D.heroes.filter(h => !LANES.some(([k]) => h.main_lane === k));
    const rest = noLane.length
      ? `<section class="sec"><div class="sec-h"><h2>分路未定</h2><span>${noLane.length} 个</span></div>
         <div class="mtx">${head}${rowsOf(noLane)}</div></section>` : '';

    view.innerHTML = `
      <a class="back" href="#">← 返回</a>
      <div class="hero-head">
        <p class="eyebrow">全英雄池</p>
        <h1>对位总表</h1>
        <p class="lede">名字全部可点。这一版是<b>官方口径（L0）</b>：
          官方每个英雄只给两个方向各 2~6 个例子，不是全量配对，也没给成立条件。
          要「在什么分段、什么出装下成立」，看英雄页里的 K-B 实测条目。</p>
      </div>
      ${duelHas() ? `<section class="sec">
        <div class="sec-h"><h2>同路五档矩阵</h2><span>只判同路，五档 + 证据三态</span></div>
        <div class="row">${Object.keys(D.duel).map(k => {
          const g = D.duel[k], cov = g.coverage || {};
          return `<a class="gcard" href="#duel:${encodeURIComponent(k)}">
            <span class="gicon">⇄</span>
            <span class="gtxt"><b>${esc(g.cn || k)} · ${g.heroes.length} 英雄</b>
              <span>${cov.measured || 0} 实测 / ${cov.total || 0} 格</span></span>
          </a>`;
        }).join('')}</div>
      </section>` : ''}
      ${blocks}${rest}
    `;
  }

  /* ══════════════════════════════════════════════════════════
     同路五档对位矩阵（30_index/duel/{lane}.grid.json）
     档位：克 / 小优 / 五五开 / 小劣 / 被克
     状态：measured 有人真讲过 · derived 有档位没实测 · empty 待补
     数据是位置数组，每格 6 个数字，见 build_site.duel_payload
     ══════════════════════════════════════════════════════════ */
  const DUEL_G = ['克', '小优', '五五开', '小劣', '被克'];
  const DUEL_SHORT = ['克', '优', '平', '劣', '被'];
  const DUEL_S_CN = ['待补', '推演', '实测'];
  const DUEL_LAYER = ['机制', '数值'];
  const DUEL_CONF = ['', '低', '中', '高'];
  const DUEL_BASIS = { column: '专栏', video: '视频',
                       official: '官方口径', mechanism: '机制推演' };
  const duelMode = {};
  let curDuel = '';

  const duelHas = () => !!(D.duel && Object.keys(D.duel).length);

  function duelCell(g, ia, ib) {
    const o = (ia * g.heroes.length + ib) * 6;
    return { grade: g.flat[o], status: g.flat[o + 1], conf: g.flat[o + 2],
             layer: g.flat[o + 3], ev: g.flat[o + 4], mirror: g.flat[o + 5] };
  }

  /* 某个英雄在这一路的所有对位 → 五个档位分桶 + 三态计数 */
  function duelBuckets(g, name) {
    const out = [[], [], [], [], []];
    const st = { empty: 0, derived: 0, measured: 0 };
    const ia = g.heroes.indexOf(name);
    if (ia < 0) return { out, st, n: 0 };
    g.heroes.forEach((b, ib) => {
      if (b === name) return;
      const c = duelCell(g, ia, ib);
      st[['empty', 'derived', 'measured'][c.status] || 'empty']++;
      if (c.grade >= 0) out[c.grade].push(b);
    });
    return { out, st, n: g.heroes.length - 1 };
  }

  /* ── 名单视图：一个英雄一行 ── */
  function duelRow(g, name, lane) {
    const b = duelBuckets(g, name);
    const h = heroOf(name);
    const groups = b.out.map((list, gi) => list.length
      ? `<span class="dgrp"><i class="dgk g${gi}">${DUEL_G[gi]}</i>${list.map(n =>
          `<button class="dchip g${gi}" data-lane="${esc(lane)}" data-a="${esc(name)}"
             data-b="${esc(n)}">${esc(n)}</button>`).join('')}</span>`
      : '').filter(Boolean).join('');
    const stat = [
      b.st.measured ? `<b class="dok">实测 ${b.st.measured}</b>` : '',
      b.st.derived ? `<b class="dder">推演 ${b.st.derived}</b>` : '',
      `<b class="demp">待补 ${b.st.empty}</b>`,
    ].join('');
    return `<div class="drow">
      <a class="drow-h" href="#H:${encodeURIComponent(name)}">
        <span class="avatar" style="--h:${h ? h.hue : 0}">${esc(name.slice(0, 1))}</span>
        <span class="drow-n">${esc(name)}</span>
      </a>
      <div class="drow-b">${groups || `<i class="dim">${b.n} 个对位全部待补</i>`}</div>
      <span class="drow-s">${stat}</span>
    </div>`;
  }

  /* ── 网格视图：24 × 24 ── */
  function duelGrid(g, lane) {
    const H = g.heroes;
    const head = `<tr><th class="dgx"></th>${H.map((b, i) =>
      `<th><span>${esc(b)}</span></th>`).join('')}</tr>`;
    const body = H.map((a, ia) => `<tr><th class="dgy">${esc(a)}</th>${H.map((b, ib) => {
      if (a === b) return '<td class="dself"></td>';
      const c = duelCell(g, ia, ib);
      const cls = c.grade >= 0 ? `g${c.grade} s${c.status}` : 'gx';
      const tip = `${a} vs ${b}` + (c.grade >= 0
        ? ` · ${DUEL_G[c.grade]} · ${DUEL_S_CN[c.status]}` : ' · 待补');
      return `<td><button class="dcell ${cls}" title="${esc(tip)}"
        data-lane="${esc(lane)}" data-a="${esc(a)}" data-b="${esc(b)}"
        aria-label="${esc(tip)}">${c.grade >= 0 ? DUEL_SHORT[c.grade] : ''}</button></td>`;
    }).join('')}</tr>`).join('');
    return `<div class="dgwrap"><table class="dgrid">
      <thead>${head}</thead><tbody>${body}</tbody></table></div>`;
  }

  /* ── 详情弹层 ── */
  const mmss = s => {
    const v = Math.max(0, Math.round(Number(s) || 0));
    return `${Math.floor(v / 60)}:${String(v % 60).padStart(2, '0')}`;
  };

  function openDuel(lane, a, b) {
    const g = (D.duel || {})[lane];
    if (!g) return;
    const ia = g.heroes.indexOf(a), ib = g.heroes.indexOf(b);
    if (ia < 0 || ib < 0) return;
    const c = duelCell(g, ia, ib);
    const d = (g.detail || {})[`${a}|${b}`] || null;

    const grade = c.grade >= 0
      ? `<span class="dgrade g${c.grade}">${DUEL_G[c.grade]}</span>`
      : `<span class="dgrade gx">待补</span>`;
    const pills = [
      `<span class="dpill s${c.status}">${DUEL_S_CN[c.status] || '待补'}</span>`,
      c.layer >= 0 ? `<span class="dpill">${DUEL_LAYER[c.layer]}差距</span>` : '',
      c.conf ? `<span class="dpill">可信度 ${DUEL_CONF[c.conf]}</span>` : '',
      c.ev ? `<span class="dpill">${c.ev} 条证据</span>` : '',
      d && d.basis ? `<span class="dpill">依据 ${esc(DUEL_BASIS[d.basis] || d.basis)}</span>` : '',
    ].filter(Boolean).join('');

    let note = '';
    if (c.status === 0) {
      note = `<p class="dnote">这一格还没有来源。官方关系页每边只列 2 个例子，
        同路对位覆盖率不到 5%，所以大部分格是空的——不猜、不凑。</p>`;
    } else if (c.status === 1) {
      note = `<p class="dnote">${d && d.basis === 'official'
        ? '官方口径只给了方向，没给强度和成立条件。这里按最保守的一档暂记，等实测覆盖。'
        : '按机制推的，没有视频或专栏实测过。可作参考，别当结论。'}</p>`;
    }
    if (c.mirror) {
      note += `<p class="dnote">这一格是反对偶：由「${esc(b)} vs ${esc(a)}」的结论取反得来，
        打法细节在对面那条里。</p>`;
    }

    const EV_KIND = { video: '视频', column: '专栏', official: '官方关系页' };
    const evList = (d && d.ev && d.ev.length)
      ? d.ev.map(e => {
          const tag = EV_KIND[e.k] || '出处';
          const when = (e.k === 'video' || e.k === 'column') && e.ts != null
            ? ` @ ${mmss(e.ts)}` : '';
          // 官方口径的 ref 是站点内部的文件名，对人没意义，只留可点的官方页面
          const tail = e.k === 'official' || !e.ref ? '' : ' · ' + esc(e.ref);
          const src = e.url
            ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(tag)}${tail}${when}</a>`
            : `<span class="devsrc">${esc(tag)}${tail}</span>`;
          return `<li>${src}${e.q ? `<q>${esc(e.q)}</q>` : ''}</li>`;
        }).join('')
      : '';

    const sec = (t, v) => v ? `<section class="dsec"><h4>${t}</h4><p>${esc(v)}</p></section>` : '';
    const body = `
      <div class="dhead">
        <div class="dvs">
          <a href="#H:${encodeURIComponent(a)}">${esc(a)}</a>
          <em>vs</em>
          <a href="#H:${encodeURIComponent(b)}">${esc(b)}</a>
        </div>
        <button class="dclose" aria-label="关闭">×</button>
      </div>
      <div class="dbadges">${grade}${pills}</div>
      ${d && d.cond ? `<p class="dcond">成立条件 · ${esc(d.cond)}</p>` : ''}
      ${sec('怎么打', d && d.how)}
      ${sec('他的破绽', d && d.counter)}
      ${evList ? `<section class="dsec"><h4>出处</h4><ul class="dev">${evList}</ul></section>` : ''}
      ${note}
      <p class="dfoot">${esc(g.cn || '')} · 对位矩阵</p>`;

    const el = duelModal();
    el.querySelector('.dbox').innerHTML = body;
    el.classList.add('on');
    document.body.style.overflow = 'hidden';
    el.querySelector('.dclose').addEventListener('click', closeDuel);
  }

  function duelModal() {
    let el = document.getElementById('dmodal');
    if (el) return el;
    el = document.createElement('div');
    el.id = 'dmodal';
    el.className = 'dmodal';
    el.innerHTML = '<div class="dmask"></div><div class="dbox" role="dialog" aria-modal="true"></div>';
    el.querySelector('.dmask').addEventListener('click', closeDuel);
    document.addEventListener('keydown', ev => {
      if (ev.key === 'Escape' && el.classList.contains('on')) closeDuel();
    });
    document.body.appendChild(el);
    return el;
  }

  function closeDuel() {
    const el = document.getElementById('dmodal');
    if (el) el.classList.remove('on');
    document.body.style.overflow = '';
  }

  /* 事件委托：所有 dchip / dcell 都走这一个入口 */
  document.addEventListener('click', ev => {
    const t = ev.target.closest('.dchip, .dcell');
    if (!t) return;
    ev.preventDefault();
    openDuel(t.dataset.lane, t.dataset.a, t.dataset.b);
  });

  /* ── 对位矩阵页 ── */
  function renderDuel(lane, mode) {
    const g = (D.duel || {})[lane];
    if (!g) return renderHome();
    curDuel = lane;
    const m = mode || duelMode[lane] || 'list';
    duelMode[lane] = m;

    const cov = g.coverage || {};
    const tot = cov.total || g.heroes.length * (g.heroes.length - 1);
    const pct = x => (x || 0) / tot * 100;
    const otherLanes = Object.keys(D.duel || {}).filter(k => k !== lane);

    const legend = `<div class="dlegend">
      <span class="dlegend-t">档位</span>
      ${DUEL_G.map((n, i) => `<span class="dgrade g${i}">${n}</span>`).join('')}
      <span class="dlegend-t">状态</span>
      <span class="dpill s2">实测</span>
      <span class="dpill s1">推演</span>
      <span class="dpill s0">待补</span>
    </div>`;

    const listBody = m === 'list'
      ? `<div class="dlist">${g.heroes.map(n => duelRow(g, n, lane)).join('')}</div>`
      : duelGrid(g, lane);

    view.innerHTML = `
      <a class="back" href="#">← 返回</a>
      <div class="hero-head">
        <p class="eyebrow">${esc(g.version || D.version)} · 同路对位</p>
        <h1>${esc(g.cn || lane)} · ${g.heroes.length} × ${g.heroes.length - 1} 全矩阵</h1>
        <p class="lede">这一路<b>所有</b>英雄两两配对，谁克谁一格一格摆出来。
          五档是判断，三态是证据强弱：<b>实测</b>有人真讲过并留了秒数，<b>推演</b>只有方向没有验证，
          <b>待补</b>就是还没人讲。点任意一格看依据、成立条件和出处。</p>
      </div>

      <section class="sec">
        <div class="dbar">
          <div class="dbar-n">
            <b>${cov.measured || 0}</b><span>实测</span>
          </div>
          <div class="dbar-n">
            <b>${cov.derived || 0}</b><span>推演</span>
          </div>
          <div class="dbar-n">
            <b>${cov.empty || 0}</b><span>待补</span>
          </div>
          <div class="dbar-b">
            <i class="dbar-m" style="width:${pct(cov.measured)}%"></i>
            <i class="dbar-d" style="width:${pct(cov.derived)}%"></i>
          </div>
          <div class="dbar-p">实测覆盖 ${pct(cov.measured).toFixed(1)}%</div>
        </div>
        ${legend}
        <div class="dswitch">
          <button class="dtab${m === 'list' ? ' on' : ''}" data-mode="list">名单</button>
          <button class="dtab${m === 'grid' ? ' on' : ''}" data-mode="grid">网格</button>
          <a class="dtab" href="#matrix">全英雄对位总表 →</a>
          ${otherLanes.map(k => `<a class="dtab" href="#duel:${encodeURIComponent(k)}">${esc(D.duel[k].cn || k)}</a>`).join('')}
        </div>
      </section>

      <section class="sec">${listBody}</section>

      <p class="dnofoot">为什么这么多格是空的：官方关系页每个方向固定只列 2 个例子，
        而且 77% 是跨路对位；同路对位要靠视频字幕与专栏逐条挖，通过率不高。
        补齐进度记在 <a href="#doc:96_素材缺口.md">素材缺口</a>里。</p>
    `;
    view.querySelectorAll('.dtab[data-mode]').forEach(btn => {
      btn.addEventListener('click', () => renderDuel(lane, btn.dataset.mode));
    });
  }

  /* ── 英雄页上的对位块 ── */
  function duelBox(name) {
    if (!duelHas()) return '';
    const lanes = Object.keys(D.duel).filter(k => D.duel[k].heroes.includes(name));
    if (!lanes.length) return '';
    const lane = lanes[0];
    const g = D.duel[lane];
    const b = duelBuckets(g, name);
    const rows = b.out.map((list, gi) => list.length
      ? `<div class="opprow">
           <span class="oppk g${gi}">${DUEL_G[gi]}</span>
           <span class="oppv">${list.map(n =>
             `<button class="dchip g${gi}" data-lane="${esc(lane)}" data-a="${esc(name)}"
                data-b="${esc(n)}">${esc(n)}</button>`).join('')}</span>
         </div>`
      : '').join('');
    return `<section class="sec"><div class="sec-h"><h2>同路对位（${esc(g.cn || lane)}）</h2>
        <span>实测 ${b.st.measured} · 推演 ${b.st.derived} · 待补 ${b.st.empty}</span></div>
      ${rows ? `<div class="oppbox">${rows}</div>`
             : `<p class="lede">这一路 ${b.n} 个对位全部待补。</p>`}
      <p class="lede"><a href="#duel:${encodeURIComponent(lane)}">看${esc(g.cn || lane)}全矩阵 →</a></p>
    </section>`;
  }

  /* ── 路由 ── */
  function route() {
    const h = decodeURIComponent(location.hash.slice(1));
    qEl.value = '';
    if (!h) return renderHome();
    if (h === 'matrix') return renderMatrix();
    if (h.startsWith('duel:')) return renderDuel(h.slice(5));
    if (h.startsWith('H:')) return renderHero(h.slice(2));
    if (h.startsWith('lane:')) return renderLane(h.slice(5));
    if (h.startsWith('doc:')) return renderDoc(h.slice(4));
    if (h.startsWith('cat:')) return renderCat(h.slice(4));
    const e = byId(h);
    if (e) {
      if (e.kind.startsWith('H:')) renderHero(e.kind.slice(2));
      else if (e.kind.startsWith('lane:')) renderLane(e.kind.slice(5));
      else renderDoc(e.kind.slice(4));
      requestAnimationFrame(() => {
        const el = document.getElementById(h);
        if (el) {
          el.open = true;
          el.scrollIntoView({ block: 'center', behavior: 'smooth' });
          el.querySelector('summary').style.background = 'var(--bg3)';
          setTimeout(() => { el.querySelector('summary').style.background = ''; }, 1600);
        }
      });
      return;
    }
    renderHome();
  }

  /* ── 搜索交互 ── */
  let t = null;
  qEl.addEventListener('input', () => {
    clearTimeout(t);
    const v = qEl.value;
    t = setTimeout(() => {
      if (v.trim()) renderSearch(v);
      else if (!location.hash) renderHome();
    }, 140);
  });
  qEl.addEventListener('keydown', ev => {
    if (ev.key === 'Escape') { qEl.value = ''; route(); }
  });
  document.addEventListener('keydown', ev => {
    if (ev.key === '/' && document.activeElement !== qEl) {
      ev.preventDefault(); qEl.focus();
    }
  });

  /* ── 主题 ── */
  const saved = localStorage.getItem('kog-theme');
  if (saved) root.dataset.theme = saved;
  document.getElementById('theme').addEventListener('click', () => {
    const next = root.dataset.theme === 'light' ? 'dark' : 'light';
    root.dataset.theme = next;
    localStorage.setItem('kog-theme', next);
  });

  window.addEventListener('hashchange', route);
  route();
})();
