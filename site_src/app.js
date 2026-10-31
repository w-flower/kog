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

  const heroOf = n => D.heroes.find(h => h.name === n);
  const byId = id => IDX.find(e => e.id === id);

  /* ── 条目折叠卡 ── */
  function entryCard(e, open) {
    return `<details class="entry" id="${esc(e.id)}"${open ? ' open' : ''}>
      <summary>
        <span class="id">${esc(e.id)}</span>
        <span class="tt"><b>${esc(e.title)}</b>
          <span>${esc(e.sum || '')}</span></span>
        <svg class="chev" viewBox="0 0 16 16" aria-hidden="true"><path d="M6 4l4 4-4 4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </summary>
      <div class="body">${e.html || ''}</div>
    </details>`;
  }

  /* ── 英雄卡 ── */
  function heroCard(h) {
    const pills = [];
    if (h.a.length) pills.push(`<span class="pill a">怎么玩 ${h.a.length}</span>`);
    if (h.b.length) pills.push(`<span class="pill b">对位 ${h.b.length}</span>`);
    if (!pills.length) pills.push('<span class="pill g">待补</span>');
    return `<a class="hcard" href="#H:${encodeURIComponent(h.name)}">
      <span class="avatar" style="--h:${h.hue}">${esc(h.name.slice(0, 1))}</span>
      <span class="hname">${esc(h.name)}</span>
      <span class="hmeta">${pills.join('')}</span>
    </a>`;
  }

  /* ── 首页 ── */
  function renderHome() {
    const heroes = D.heroes.map(heroCard).join('');
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
        <div class="sec-h"><h2>英雄</h2><span>${D.heroes.length} 个 · 点开看全部</span></div>
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

    view.innerHTML = `
      <a class="back" href="#">← 全部英雄</a>
      <div class="hhead">
        <span class="avatar" style="--h:${h.hue}">${esc(h.name.slice(0, 1))}</span>
        <div>
          <h1>${esc(h.name)}</h1>
          <div class="hmeta">
            <span class="pill g">${h.n} 条</span>
            ${h.b_n ? `<span class="pill b">对位 ${h.b_n}</span>` : ''}
          </div>
        </div>
      </div>
      ${secA}${secB}${inc}
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

  /* ── 路由 ── */
  function route() {
    const h = decodeURIComponent(location.hash.slice(1));
    qEl.value = '';
    if (!h) return renderHome();
    if (h.startsWith('H:')) return renderHero(h.slice(2));
    if (h.startsWith('doc:')) return renderDoc(h.slice(4));
    if (h.startsWith('cat:')) return renderCat(h.slice(4));
    const e = byId(h);
    if (e) {
      if (e.kind.startsWith('H:')) renderHero(e.kind.slice(2));
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
