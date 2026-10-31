/* ══════════════════════════════════════════════════════════
   kog 站点交互
   数据来自 <script id="DATA" type="application/json">，构建时注入
   路由用 hash：#K-B01 / #doc:xx.md / #cat:A —— 因为要能 file:// 直接打开
   ══════════════════════════════════════════════════════════ */
(function () {
  const D = JSON.parse(document.getElementById('DATA').textContent);
  const view = document.getElementById('view');
  const nav = document.getElementById('nav');
  const crumb = document.getElementById('crumb');
  const res = document.getElementById('res');
  const q = document.getElementById('q');
  const side = document.getElementById('side');
  const mask = document.getElementById('mask');
  const root = document.documentElement;

  /* 扁平索引：搜索用 */
  const IDX = [];
  D.cats.forEach(c => c.docs.forEach(d => d.entries.forEach(e => {
    IDX.push({ id: e.id, cat: c.key, cname: c.name, doc: d.title, title: e.title, file: d.file });
  })));

  document.getElementById('subline').textContent = D.meta.sub;
  document.getElementById('foot').innerHTML = '<p>' + D.meta.foot + '</p>';

  /* ─────────── 侧栏 ─────────── */
  (function buildNav() {
    let h = '<div class="grp"><button class="gh"><span class="k">·</span>总览</button><ul>';
    D.overview.forEach(o => { h += '<li><a href="#doc:' + o.file + '">' + o.title + '</a></li>'; });
    h += '</ul></div>';

    D.cats.forEach(c => {
      const n = c.docs.reduce((s, d) => s + d.entries.length, 0);
      h += '<div class="grp"><button class="gh"><span class="k">' + c.key + '</span>' +
        c.name + '<span class="n">' + n + '</span></button><ul>';
      h += '<li><a href="#cat:' + c.key + '">类说明</a></li>';
      c.docs.forEach(d => {
        h += '<li><a href="#doc:' + d.file + '">' + d.title + '</a></li>';
        d.entries.forEach(e => {
          h += '<li class="sub-item"><a href="#' + e.id + '"><code>' + e.id + '</code>' +
            esc(e.title) + '</a></li>';
        });
      });
      h += '</ul></div>';
    });
    nav.innerHTML = h;
  })();

  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

  /* ─────────── 渲染 ─────────── */
  function renderDoc(cat, doc) {
    let h = '<div class="doc"><h1>' + esc(doc.title) + '</h1>' + (doc.intro || '') + '</div>';
    if (doc.entries.length) {
      h += '<div class="doc">';
      doc.entries.forEach(e => {
        h += '<div class="card" id="' + e.id + '">' + e.self + e.html + '</div>';
      });
      h += '</div>';
    }
    crumb.textContent = cat.name + ' / ' + doc.title;
    view.innerHTML = h;
  }

  function renderCat(c) {
    let h = '<div class="doc"><h1>' + c.key + ' 类 · ' + esc(c.name) + '</h1><p>' + esc(c.desc) + '</p>';
    if (c.about) h += '<div class="about">' + c.about + '</div>';
    h += '</div>';
    crumb.textContent = c.name;
    view.innerHTML = h;
  }

  function renderOverview(o) {
    crumb.textContent = '总览 / ' + o.title;
    view.innerHTML = '<div class="doc">' + o.html + '</div>';
  }

  function findByFile(f) {
    for (const c of D.cats) for (const d of c.docs) if (d.file === f) return { c, d };
    return null;
  }
  function findEntry(id) {
    for (const c of D.cats) for (const d of c.docs) for (const e of d.entries)
      if (e.id === id) return { c, d, e };
    return null;
  }

  /* ─────────── 路由 ─────────── */
  function route() {
    const h = decodeURIComponent(location.hash.slice(1));
    if (!h) { renderOverview(D.overview[0]); setActive(null); return; }

    if (h.startsWith('cat:')) {
      const c = D.cats.find(x => x.key === h.slice(4));
      if (c) { renderCat(c); setActive(location.hash); }
      return;
    }
    if (h.startsWith('doc:')) {
      const hit = findByFile(h.slice(4));
      if (hit) { renderDoc(hit.c, hit.d); setActive(location.hash); return; }
      const o = D.overview.find(x => x.file === h.slice(4));
      if (o) { renderOverview(o); setActive(location.hash); }
      return;
    }
    const e = findEntry(h);
    if (e) {
      renderDoc(e.c, e.d);
      setActive('#' + h);
      requestAnimationFrame(() => {
        const el = document.getElementById(h);
        if (el) {
          el.scrollIntoView({ block: 'start' });
          el.classList.add('flash');
          setTimeout(() => el.classList.remove('flash'), 1700);
        }
      });
    }
  }

  function setActive(hash) {
    nav.querySelectorAll('a').forEach(a => a.classList.toggle('on', a.getAttribute('href') === hash));
  }
  window.addEventListener('hashchange', route);

  /* ─────────── 主题 ─────────── */
  const saved = localStorage.getItem('kog-theme');
  if (saved) root.dataset.theme = saved;
  document.getElementById('theme').onclick = () => {
    root.dataset.theme = root.dataset.theme === 'dark' ? 'light' : 'dark';
    localStorage.setItem('kog-theme', root.dataset.theme);
  };

  /* ─────────── 搜索 ─────────── */
  function search(kw) {
    kw = kw.trim().toLowerCase();
    if (!kw) { res.classList.remove('on'); res.innerHTML = ''; return; }
    const hits = IDX.filter(x =>
      (x.id + ' ' + x.title + ' ' + x.doc + ' ' + x.cname).toLowerCase().includes(kw)
    ).slice(0, 12);
    res.innerHTML = hits.length
      ? hits.map(x => '<a href="#' + x.id + '"><span class="m">' + x.id + '</span>' + esc(x.title) + '</a>').join('')
      : '<a style="color:var(--fg3)">没有匹配的条目</a>';
    res.classList.add('on');
  }
  q.addEventListener('input', e => search(e.target.value));
  q.addEventListener('keydown', e => {
    if (e.key === 'Enter') { const a = res.querySelector('a[href]'); if (a) { a.click(); q.blur(); } }
    if (e.key === 'Escape') { q.value = ''; search(''); }
  });
  document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); }
  });
  document.addEventListener('click', e => {
    if (!res.contains(e.target) && e.target !== q) res.classList.remove('on');
  });

  /* ─────────── 移动端抽屉 ─────────── */
  document.getElementById('menu').onclick = () => {
    side.classList.add('open'); mask.classList.add('on');
  };
  function closeDrawer() { side.classList.remove('open'); mask.classList.remove('on'); }
  mask.onclick = closeDrawer;
  nav.addEventListener('click', e => { if (e.target.closest('a')) closeDrawer(); });

  /* ─────────── 回到顶部 ─────────── */
  const bt = document.getElementById('backtop');
  window.addEventListener('scroll', () => bt.classList.toggle('on', window.scrollY > 600), { passive: true });
  bt.onclick = () => window.scrollTo({ top: 0, behavior: 'smooth' });

  route();
})();
