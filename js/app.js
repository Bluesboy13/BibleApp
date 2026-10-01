/* KJV Bible — a simple, book-like reader.
   Plain JS, no dependencies. Everything is saved in localStorage. */
(() => {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const KEY = 'kjv-reader-v1';
  const PLAN_DAYS = 365;
  // Books set as poetry (one verse per line): Psalms, Proverbs, Song of Solomon, Lamentations, and Job 3–41.
  const POETRY = new Set([18, 19, 21, 24]);
  const isPoetry = (b, c) => POETRY.has(b) || (b === 17 && c >= 3 && c <= 41);

  let BIBLE = null;          // the text on screen: [[bookName, [[verse, ...], ...]], ...]
  let KJV = null;            // the King James text (always loaded; plan, bookmarks and "KJV under" use it)
  let CHAPTERS = [];         // flat list of [b, c] for the reading plan (KJV chapters)
  // Alternative texts. Old Testament books come from the text's file; New Testament books from `nt`.
  const TEXTS = {
    kjv: { name: 'KJV', short: '' },
    'lxx-gr': { name: 'Septuagint (Greek)', short: 'LXX', file: 'data/lxx-gr.json', nt: 'data/tr.json', lang: 'el' },
    'lxx-en': { name: 'Septuagint (Brenton English)', short: 'LXX', file: 'data/lxx-en.json', lang: 'en' },
  };
  const loadedTexts = {};    // file -> parsed JSON
  // Per book, for the text on screen: where it came from, printed chapter/verse labels, and its
  // map to KJV verses (null = same numbering as the KJV).
  let SRC = [], CHLABELS = [], VLABELS = [], MAP = [], REVERSE = [];

  // ---------- Saved state ----------
  const DEFAULTS = {
    settings: { vn: false, mode: 'scroll', theme: 'paper', font: 'literata', size: 20, align: 'left', voice: '', rate: 0.9, follow: 'word', text: 'kjv', under: false },
    ribbon: { b: 0, c: 1, v: 1 },
    ribbonText: 'kjv',         // which text's numbering the ribbon is in
    bookmarks: [],
    plan: { start: null, done: {}, active: null },
  };
  const state = loadState();
  function loadState() {
    let s = {};
    try { s = JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { /* ignore */ }
    return {
      settings: { ...DEFAULTS.settings, ...s.settings },
      ribbon: { ...DEFAULTS.ribbon, ...s.ribbon },
      ribbonText: s.ribbonText || 'kjv',
      bookmarks: Array.isArray(s.bookmarks) ? s.bookmarks : [],
      plan: { ...DEFAULTS.plan, ...s.plan, done: { ...(s.plan && s.plan.done) } },
      updatedAt: s.updatedAt || 0,   // last change to synced data (ribbon, bookmarks, plan)
      syncUid: s.syncUid || null,    // account this device last synced with
    };
  }
  let saveTimer = 0;
  function save() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* ignore */ }
    }, 250);
  }
  // Record a change to synced data. While signed in, changes are held until the first
  // cloud check finishes so opening the app can't overwrite newer reading from another device.
  let syncHold = !!state.syncUid;
  setTimeout(() => { syncHold = false; }, 10000);
  function touch() {
    if (!syncHold) {
      state.updatedAt = Date.now();
      document.dispatchEvent(new Event('kjv:changed'));
    }
    save();
  }

  // ---------- Helpers ----------
  const bookName = (b) => BIBLE[b][0];
  const chapterCount = (b) => BIBLE[b][1].length;
  const verseText = (b, c, v) => ((BIBLE[b][1][c - 1] || [])[v - 1] || '').replace('¶', '');
  const kjvText = (b, c, v) => ((KJV[b][1][c - 1] || [])[v - 1] || '').replace('¶', '');
  // Printed chapter and verse numbers (the LXX sometimes skips numbers or adds lettered verses).
  const chLabel = (b, c) => (CHLABELS[b] ? CHLABELS[b][c - 1] : String(c));
  const vLabel = (b, c, v) => (VLABELS[b] && VLABELS[b][c] ? VLABELS[b][c][v - 1] : String(v));
  const ref = (p) => `${bookName(p.b)} ${chLabel(p.b, p.c)}:${vLabel(p.b, p.c, p.v)}`;
  const kjvRef = (p) => `${KJV[p.b][0]} ${p.c}:${p.v}`;
  const isGreek = (b) => SRC[b] === 'lxx-gr' || SRC[b] === 'tr';

  // ----- Moving between a text's numbering and the KJV's -----
  function toKjv(p) {
    const m = MAP[p.b];
    if (!m) return { b: p.b, c: p.c, v: p.v };
    const ch = m[p.c - 1] || [];
    for (let v = p.v; v >= 1; v--) if (ch[v - 1] && ch[v - 1].length) return { b: p.b, c: ch[v - 1][0][0], v: ch[v - 1][0][1] };
    for (let c = p.c - 1; c >= 1; c--) {
      const prev = m[c - 1] || [];
      for (let v = prev.length; v >= 1; v--) if (prev[v - 1].length) return { b: p.b, c: prev[v - 1][0][0], v: prev[v - 1][0][1] };
    }
    return { b: p.b, c: 1, v: 1 };
  }
  function fromKjv(p) {
    const m = MAP[p.b];
    if (!m) {
      const c = Math.min(Math.max(1, p.c), chapterCount(p.b));
      return { b: p.b, c, v: Math.min(Math.max(1, p.v), BIBLE[p.b][1][c - 1].length) };
    }
    if (!REVERSE[p.b]) {
      const r = {};
      m.forEach((ch, ci) => ch.forEach((refs, vi) => refs.forEach(([kc, kv]) => { r[`${kc}:${kv}`] = { c: ci + 1, v: vi + 1 }; })));
      REVERSE[p.b] = r;
    }
    for (let v = p.v; v >= 1; v--) {
      const hit = REVERSE[p.b][`${p.c}:${v}`];
      if (hit) return { b: p.b, ...hit };
    }
    for (let c = p.c - 1; c >= 1; c--) {
      for (let v = 200; v >= 1; v--) { const hit = REVERSE[p.b][`${c}:${v}`]; if (hit) return { b: p.b, ...hit }; }
    }
    return { b: p.b, c: 1, v: 1 };
  }
  // Put the ribbon into the numbering of the text on screen.
  function syncRibbonText() {
    const id = state.settings.text;
    if (state.ribbonText === id) return;
    const fromId = state.ribbonText;
    let k = state.ribbon;
    if (fromId !== 'kjv') {
      // The ribbon is in another text's numbering: go through the KJV using that text's map.
      const saved = [BIBLE, SRC, CHLABELS, VLABELS, MAP, REVERSE];
      if (!buildText(fromId)) { k = { b: 0, c: 1, v: 1 }; } else k = toKjv(k);
      [BIBLE, SRC, CHLABELS, VLABELS, MAP, REVERSE] = saved;
    }
    state.ribbon = fromKjv(k);
    state.ribbonText = id;
  }
  // Assemble the text on screen. Returns false if its files aren't loaded yet.
  function buildText(id) {
    const t = TEXTS[id] || TEXTS.kjv;
    const ot = t.file ? loadedTexts[t.file] : null;
    const nt = t.nt ? loadedTexts[t.nt] : null;
    if ((t.file && !ot) || (t.nt && !nt)) return false;
    BIBLE = []; SRC = []; CHLABELS = []; VLABELS = []; MAP = []; REVERSE = [];
    KJV.forEach(([name, chapters], b) => {
      const fromOt = ot && ot.books[b];
      const fromNt = nt && nt.books[b];
      if (fromOt) {
        BIBLE.push([name, fromOt]);
        SRC.push(id);
        CHLABELS.push((ot.chapters || {})[b] || null);
        VLABELS.push((ot.labels || {})[b] || null);
        MAP.push((ot.map || {})[b] || null);
      } else if (fromNt) {
        BIBLE.push([name, fromNt]);
        SRC.push('tr');
        CHLABELS.push(null); VLABELS.push(null); MAP.push(null);
      } else {
        BIBLE.push([name, chapters]);
        SRC.push('kjv');
        CHLABELS.push(null); VLABELS.push(null); MAP.push(null);
      }
      REVERSE.push(null);
    });
    return true;
  }
  async function loadText(id) {
    const t = TEXTS[id] || TEXTS.kjv;
    for (const f of [t.file, t.nt].filter(Boolean)) {
      if (!loadedTexts[f]) loadedTexts[f] = await (await fetch(f)).json();
    }
  }
  const esc = (s) => s.replace(/[&<>]/g, (ch) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[ch]));

  let toastTimer = 0;
  function toast(msg) {
    const t = $('#toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
  }

  function setBars(show) { document.body.classList.toggle('bars-hidden', !show); }
  const barsShown = () => !document.body.classList.contains('bars-hidden');

  // ---------- Rendering ----------
  function titleHTML(b) {
    return `<h1 class="book-title">${esc(bookName(b))}</h1><div class="ornament">❧</div>`;
  }
  function chapterHTML(b, c) {
    const verses = BIBLE[b][1][c - 1];
    const poetry = isPoetry(b, c);
    const under = state.settings.under && SRC[b] !== 'kjv';
    let h = `<section class="chapter${poetry ? ' poetry' : ''}${under ? ' with-under' : ''}" data-c="${c}">`;
    h += `<p><span class="dropcap">${esc(chLabel(b, c))}</span>`;
    verses.forEach((t, i) => {
      // ¶ marks a paragraph break in the text; start a new paragraph there in prose.
      if (t[0] === '¶') {
        t = t.slice(1);
        if (i > 0 && !poetry && !under) h += '</p><p class="para">';
      }
      const label = vLabel(b, c, i + 1);
      h += `<span class="v${i === 0 ? ' first' : ''}" data-c="${c}" data-v="${i + 1}"><sup class="vn">${esc(label)}</sup>${esc(t)} </span>`;
      if (under) h += kjvUnderHTML(b, c, i + 1);
    });
    return h + '</p></section>';
  }
  // The matching KJV verse(s) under a verse of another text.
  function kjvUnderHTML(b, c, v) {
    const refs = MAP[b] ? ((MAP[b][c - 1] || [])[v - 1] || []) : [[c, v]];
    if (!refs.length) return '<span class="kjv-under none" lang="en">— not in the KJV —</span>';
    return '<span class="kjv-under" lang="en">' + refs.map(([kc, kv]) =>
      `<span class="kref">${MAP[b] ? `${kc}:${kv}` : ''}</span>${esc(kjvText(b, kc, kv))}`).join(' ') + '</span>';
  }
  function bookNavHTML(b) {
    const prev = b > 0 ? `<button data-book="${b - 1}">‹ ${esc(bookName(b - 1))}</button>` : '<span></span>';
    const next = b < BIBLE.length - 1 ? `<button data-book="${b + 1}">${esc(bookName(b + 1))} ›</button>` : '<span></span>';
    return `<div class="book-end">❧</div><nav class="book-nav">${prev}${next}</nav>`;
  }

  // ---------- Scroll mode ----------
  const bookEl = $('#book');
  let renderedBook = -1;
  let verseEls = [];

  function renderBook(b) {
    let h = titleHTML(b);
    for (let c = 1; c <= chapterCount(b); c++) h += chapterHTML(b, c);
    bookEl.innerHTML = h + bookNavHTML(b);
    renderedBook = b;
    verseEls = Array.from(bookEl.querySelectorAll('.v'));
  }

  const topOffset = () => $('#topbar').offsetHeight + 10;

  function scrollToVerse(c, v) {
    let y = 0;
    if (!(c === 1 && v <= 1)) {
      const el = v <= 1
        ? bookEl.querySelector(`.chapter[data-c="${c}"]`)
        : bookEl.querySelector(`.v[data-c="${c}"][data-v="${v}"]`);
      if (el) y = el.getBoundingClientRect().top + window.scrollY - topOffset();
    }
    window.scrollTo(0, Math.max(0, y));
    lastY = window.scrollY; // a jump shouldn't hide the top bar
  }

  // First verse whose start is at/below the top of the reading area.
  function scrollPosition() {
    if (!verseEls.length) return null;
    const y = topOffset() - 4;
    let lo = 0, hi = verseEls.length - 1, ans = verseEls.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (verseEls[mid].getClientRects()[0].top >= y) { ans = mid; hi = mid - 1; } else lo = mid + 1;
    }
    // If the previous verse still fills a good part of the screen top, it's the one being read.
    if (ans > 0) {
      const prev = verseEls[ans - 1].getBoundingClientRect();
      const lh = parseFloat(getComputedStyle(bookEl).lineHeight) || 30;
      if (prev.bottom > y + lh * 2 || verseEls[ans].getClientRects()[0].top > window.innerHeight) ans--;
    }
    const el = verseEls[ans];
    return { b: renderedBook, c: +el.dataset.c, v: +el.dataset.v };
  }

  let lastY = 0, ticking = false;
  window.addEventListener('scroll', () => {
    if (state.settings.mode !== 'scroll' || ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      const y = window.scrollY;
      if (!anyPanelOpen()) {
        if (y > lastY + 12 && y > 80) setBars(false);
        else if (y < lastY - 12) setBars(true);
      }
      lastY = y;
      const p = scrollPosition();
      if (p && !player.playing) setRibbon(p);   // while reading aloud, the voice sets the place
    });
  }, { passive: true });

  bookEl.addEventListener('click', (e) => {
    const nb = e.target.closest('[data-book]');
    if (nb) { goTo(+nb.dataset.book, 1, 1); return; }
    if (window.getSelection && String(window.getSelection())) return;
    setBars(!barsShown());
  });

  // ---------- Page mode ----------
  const pager = $('#pager');
  const flow = $('#flow');
  const pg = { b: 0, c: 1, page: 0, pages: 1, step: 1 };

  function layoutPager() {
    const padX = Math.max(24, Math.round((window.innerWidth - 680) / 2));
    const top = 40, bottom = document.body.classList.contains('playing') ? 96 : 48;   // room for the player bar
    flow.style.left = padX + 'px';
    flow.style.width = (window.innerWidth - padX * 2) + 'px';
    flow.style.top = `calc(env(safe-area-inset-top) + ${top}px)`;
    flow.style.bottom = `calc(env(safe-area-inset-bottom) + ${bottom}px)`;
    const W = flow.clientWidth, G = padX * 2;
    flow.style.columnWidth = W + 'px';
    flow.style.columnGap = G + 'px';
    pg.step = W + G;
  }

  function flowOffset(el) {
    const r = el.getClientRects()[0];
    return r ? r.left - flow.getBoundingClientRect().left : 0;
  }
  const pageOf = (el) => Math.max(0, Math.floor((flowOffset(el) + 2) / pg.step));

  function renderPageChapter(b, c) {
    flow.innerHTML = (c === 1 ? titleHTML(b) : '') + chapterHTML(b, c);
    pg.b = b; pg.c = c;
    measurePages();
  }
  function measurePages() {
    layoutPager();
    flow.classList.add('no-anim');
    flow.style.transform = 'none';
    const vs = flow.querySelectorAll('.v');
    const last = vs[vs.length - 1];
    const rects = last.getClientRects();
    const lastLeft = rects[rects.length - 1].left - flow.getBoundingClientRect().left;
    pg.pages = Math.floor((lastLeft + 2) / pg.step) + 1;
  }
  function showPage(p, animate) {
    pg.page = Math.max(0, Math.min(pg.pages - 1, p));
    flow.classList.toggle('no-anim', !animate);
    flow.style.transform = `translateX(${-pg.page * pg.step}px)`;
    $('#pagefoot').textContent = `${bookName(pg.b)} ${chLabel(pg.b, pg.c)}  ·  ${pg.page + 1} of ${pg.pages}`;
    setRibbon(pagePosition());
  }
  // First verse that starts on the current page (or the one running onto it).
  function pagePosition() {
    const vs = flow.querySelectorAll('.v');
    let pick = vs[0];
    for (const el of vs) {
      const p = pageOf(el);
      if (p === pg.page) { pick = el; break; }
      if (p > pg.page) break;
      pick = el;
    }
    return { b: pg.b, c: +pick.dataset.c, v: +pick.dataset.v };
  }
  function pageGoTo(b, c, v) {
    renderPageChapter(b, c);
    const el = flow.querySelector(`.v[data-v="${v}"]`);
    showPage(el && v > 1 ? pageOf(el) : 0, false);
  }
  function nextPage() {
    if (pg.page < pg.pages - 1) return showPage(pg.page + 1, true);
    const n = nextChapter(pg.b, pg.c);
    if (n) { renderPageChapter(n[0], n[1]); showPage(0, false); updateTitle(); }
  }
  function prevPage() {
    if (pg.page > 0) return showPage(pg.page - 1, true);
    const p = prevChapter(pg.b, pg.c);
    if (p) { renderPageChapter(p[0], p[1]); showPage(pg.pages - 1, false); updateTitle(); }
  }
  function nextChapter(b, c) {
    if (c < chapterCount(b)) return [b, c + 1];
    return b < BIBLE.length - 1 ? [b + 1, 1] : null;
  }
  function prevChapter(b, c) {
    if (c > 1) return [b, c - 1];
    return b > 0 ? [b - 1, chapterCount(b - 1)] : null;
  }

  let touchX = null, touchY = null, swiped = false;
  pager.addEventListener('touchstart', (e) => {
    touchX = e.touches[0].clientX; touchY = e.touches[0].clientY; swiped = false;
  }, { passive: true });
  pager.addEventListener('touchend', (e) => {
    if (touchX === null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    const dy = e.changedTouches[0].clientY - touchY;
    touchX = null;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) {
      swiped = true;
      dx < 0 ? nextPage() : prevPage();
    }
  });
  pager.addEventListener('click', (e) => {
    if (swiped) { swiped = false; return; }
    const x = e.clientX / window.innerWidth;
    if (x > 0.7) nextPage();
    else if (x < 0.3) prevPage();
    else setBars(!barsShown());
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') return closePanels();
    if (state.settings.mode !== 'page' || anyPanelOpen()) return;
    if (['ArrowRight', 'PageDown', ' '].includes(e.key)) { e.preventDefault(); nextPage(); }
    if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); prevPage(); }
  });

  // ---------- Navigation core ----------
  function setRibbon(p) {
    const r = state.ribbon;
    if (r.b === p.b && r.c === p.c && r.v === p.v) return;
    state.ribbon = p;
    updateTitle();
    touch();
  }
  function updateTitle() {
    const r = state.ribbon;
    const t = TEXTS[state.settings.text];
    $('#title').textContent = `${bookName(r.b)} ${chLabel(r.b, r.c)}${t.short && SRC[r.b] !== 'kjv' ? (SRC[r.b] === 'tr' ? ' · TR' : ' · ' + t.short) : ''}`;
  }

  function goTo(b, c, v, flash) {
    c = Math.min(Math.max(1, c), chapterCount(b));
    v = Math.max(1, v || 1);
    const o = state.ribbon;
    const moved = o.b !== b || o.c !== c || o.v !== v;
    state.ribbon = { b, c, v };
    if (state.settings.mode === 'page') {
      pageGoTo(b, c, v);
    } else {
      if (renderedBook !== b) renderBook(b);
      scrollToVerse(c, v);
    }
    updateTitle();
    if (moved) touch(); else save();
    if (flash && v > 1) flashVerse(c, v);
    if (player.active) afterNavigate(b, c, v);
  }
  function flashVerse(c, v) {
    const root = state.settings.mode === 'page' ? flow : bookEl;
    const el = root.querySelector(`.v[data-c="${c}"][data-v="${v}"]`);
    if (!el) return;
    el.classList.add('flash');
    setTimeout(() => el.classList.remove('flash'), 1600);
  }
  // Re-lay out the current view without moving the reader's place.
  function relayout() {
    const r = { ...state.ribbon };
    goTo(r.b, r.c, r.v);
  }

  // ---------- Settings ----------
  const THEME_COLORS = { paper: '#f4eddc', white: '#ffffff', night: '#161412' };
  function applySettings() {
    const s = state.settings;
    const body = document.body;
    body.classList.remove('theme-paper', 'theme-white', 'theme-night', 'font-literata', 'font-garamond');
    body.classList.add('theme-' + s.theme, 'font-' + s.font);
    body.classList.toggle('hide-vn', !s.vn);
    body.classList.toggle('justify', s.align === 'justify');
    $('#row-under').hidden = s.text === 'kjv';
    const lang = (TEXTS[s.text] || TEXTS.kjv).lang === 'el' ? 'el' : 'en';
    bookEl.lang = lang;
    flow.lang = lang;
    body.classList.toggle('follow-verse', s.follow === 'verse');
    body.classList.toggle('mode-page', s.mode === 'page');
    pager.hidden = s.mode !== 'page';
    document.documentElement.style.setProperty('--size', s.size + 'px');
    document.querySelector('meta[name="theme-color"]').content = THEME_COLORS[s.theme];
    $('#btn-vn').setAttribute('aria-pressed', String(s.vn));
    for (const [id, val] of [['#set-font', s.font], ['#set-theme', s.theme], ['#set-align', s.align], ['#set-text', s.text], ['#set-under', s.under ? 'on' : 'off'], ['#set-follow', s.follow], ['#set-mode', s.mode], ['#set-vn', s.vn ? 'on' : 'off']]) {
      $(id).querySelectorAll('button').forEach((btn) => btn.classList.toggle('on', btn.dataset.v === val));
    }
  }
  function changeSetting(key, val) {
    if (state.settings[key] === val) return;
    const r = { ...state.ribbon };
    const wasPage = state.settings.mode === 'page';
    state.settings[key] = val;
    applySettings();
    if (key === 'under') renderedBook = -1;   // the page itself changes, not just its styling
    if (key === 'mode') {
      if (val === 'scroll') { renderedBook = -1; flow.innerHTML = ''; setBars(true); }
      if (val === 'page' && !wasPage) setBars(false);
    }
    state.ribbon = r;
    goTo(r.b, r.c, r.v);
    save();
  }
  $('#btn-vn').addEventListener('click', () => {
    changeSetting('vn', !state.settings.vn);
    toast(state.settings.vn ? 'Verse numbers on' : 'Verse numbers off');
  });
  $('#size-down').addEventListener('click', () => changeSetting('size', Math.max(14, state.settings.size - 1)));
  $('#size-up').addEventListener('click', () => changeSetting('size', Math.min(34, state.settings.size + 1)));
  $('#set-font').addEventListener('click', (e) => e.target.dataset.v && changeSetting('font', e.target.dataset.v));
  $('#set-theme').addEventListener('click', (e) => e.target.dataset.v && changeSetting('theme', e.target.dataset.v));
  $('#set-align').addEventListener('click', (e) => e.target.dataset.v && changeSetting('align', e.target.dataset.v));
  $('#set-under').addEventListener('click', (e) => e.target.dataset.v && changeSetting('under', e.target.dataset.v === 'on'));
  $('#set-text').addEventListener('click', (e) => e.target.dataset.v && changeText(e.target.dataset.v));
  // Switch between the KJV and the Septuagint, keeping the reader's place.
  async function changeText(id) {
    if (id === state.settings.text || !KJV) return;
    const t = TEXTS[id];
    if ((t.file && !loadedTexts[t.file]) || (t.nt && !loadedTexts[t.nt])) {
      toast(`Loading ${t.name}…`);
      try { await loadText(id); } catch (e) { return toast('Couldn’t load that text. Check your connection.'); }
    }
    if (player.active) stopPlayer();
    const k = toKjv(state.ribbon);
    state.settings.text = id;
    buildText(id);
    state.ribbon = fromKjv(k);
    state.ribbonText = id;
    renderedBook = -1;
    applySettings();
    const r = state.ribbon;
    goTo(r.b, r.c, r.v);
    save();
    toast(t.name);
  }
  $('#set-mode').addEventListener('click', (e) => e.target.dataset.v && changeSetting('mode', e.target.dataset.v));
  $('#set-vn').addEventListener('click', (e) => e.target.dataset.v && changeSetting('vn', e.target.dataset.v === 'on'));

  // ---------- Panels ----------
  const PANELS = ['#panel-nav', '#panel-bm', '#panel-plan', '#panel-set'];
  const anyPanelOpen = () => PANELS.some((p) => !$(p).hidden);
  function openPanel(id) {
    closePanels();
    $(id).hidden = false;
    $('#scrim').hidden = false;
  }
  function closePanels() {
    PANELS.forEach((p) => { $(p).hidden = true; });
    $('#scrim').hidden = true;
  }
  $('#scrim').addEventListener('click', closePanels);
  document.querySelectorAll('.panel .close').forEach((b) => b.addEventListener('click', closePanels));

  // Book / chapter picker
  $('#btn-nav').addEventListener('click', () => { showBooks(); openPanel('#panel-nav'); });
  $('#nav-back').addEventListener('click', showBooks);
  // Book groupings. Indices are positions in the KJV order (Genesis = 0 ... Revelation = 65).
  const range = (a, z) => Array.from({ length: z - a + 1 }, (_, i) => a + i);
  const CHRISTIAN_ORDER = [
    ['Old Testament', [
      ['The Law', range(0, 4)],
      ['History', range(5, 16)],
      ['Poetry & Wisdom', range(17, 21)],
      ['Major Prophets', range(22, 26)],
      ['Minor Prophets', range(27, 38)],
    ]],
    ['New Testament', [
      ['Gospels', range(39, 42)],
      ['History', [43]],
      ['Letters of Paul', range(44, 56)],
      ['General Letters', range(57, 64)],
      ['Prophecy', [65]],
    ]],
  ];
  // The Hebrew Bible (Tanakh) in its traditional Jewish order: Torah, Nevi'im, Ketuvim.
  const TANAKH_ORDER = [
    ['Hebrew Bible · Tanakh', [
      ['Torah · The Law', range(0, 4)],
      ['Nevi’im · The Prophets: Former', [5, 6, 8, 9, 10, 11]],
      ['Nevi’im · The Prophets: Latter', [22, 23, 25]],
      ['Nevi’im · The Twelve', range(27, 38)],
      ['Ketuvim · The Writings', [18, 19, 17, 21, 7, 24, 20, 16, 26, 14, 15, 12, 13]],
    ]],
  ];
  function showBooks() {
    $('#nav-title').textContent = 'Books';
    $('#nav-back').hidden = true;
    const list = (books) => '<div class="book-list">' + books.map((b) =>
      `<button data-b="${b}" class="${b === state.ribbon.b ? 'current' : ''}">${esc(bookName(b))}</button>`).join('') + '</div>';
    const section = ([title, groups], extra = '') =>
      `<div class="testament${extra}">${title}</div>` +
      groups.map(([name, books]) => `<div class="book-group"><div class="group-name">${name}</div>${list(books)}</div>`).join('');
    const body = $('#nav-body');
    body.innerHTML = CHRISTIAN_ORDER.map((t) => section(t)).join('') +
      TANAKH_ORDER.map((t) => section(t, ' tanakh')).join('');
    body.scrollTop = 0;
  }
  function showChapters(b) {
    $('#nav-title').textContent = bookName(b);
    $('#nav-back').hidden = false;
    let h = '<div class="chap-grid">';
    for (let c = 1; c <= chapterCount(b); c++) {
      const cur = b === state.ribbon.b && c === state.ribbon.c;
      h += `<button data-b="${b}" data-c="${c}" class="${cur ? 'current' : ''}">${esc(chLabel(b, c))}</button>`;
    }
    $('#nav-body').innerHTML = h + '</div>';
    $('#nav-body').scrollTop = 0;
  }
  $('#nav-body').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const b = +btn.dataset.b;
    if (btn.dataset.c) { closePanels(); goTo(b, +btn.dataset.c, 1); }
    else if (chapterCount(b) === 1) { closePanels(); goTo(b, 1, 1); }
    else showChapters(b);
  });

  // Bookmarks
  $('#btn-bm').addEventListener('click', () => { renderBookmarks(); openPanel('#panel-bm'); });
  function renderBookmarks() {
    $('#ribbon-ref').textContent = ref(state.ribbon);
    $('#bm-add').textContent = `＋ Save this spot · ${ref(state.ribbon)}`;
    const list = $('#bm-list');
    const items = state.bookmarks.slice().sort((a, z) => z.t - a.t);
    list.innerHTML = items.map((bm) => `
      <li>
        <button class="go" data-t="${bm.t}">
          <div class="ref">${esc(kjvRef(bm))}</div>
          <div class="snip">${esc(kjvText(bm.b, bm.c, bm.v))}</div>
        </button>
        <button class="del" data-t="${bm.t}" aria-label="Delete bookmark">✕</button>
      </li>`).join('');
    $('#bm-empty').hidden = items.length > 0;
  }
  $('.ribbon-card').addEventListener('click', closePanels);
  $('#bm-add').addEventListener('click', () => {
    const r = toKjv(state.ribbon);   // bookmarks are kept in KJV numbering so they work in every text
    if (state.bookmarks.some((bm) => bm.b === r.b && bm.c === r.c && bm.v === r.v)) {
      toast('Already saved');
      return;
    }
    state.bookmarks.push({ b: r.b, c: r.c, v: r.v, t: Date.now() });
    touch();
    renderBookmarks();
    toast(`Saved ${ref(state.ribbon)}`);
  });
  $('#bm-list').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    const t = +btn.dataset.t;
    const bm = state.bookmarks.find((x) => x.t === t);
    if (!bm) return;
    if (btn.classList.contains('del')) {
      state.bookmarks = state.bookmarks.filter((x) => x.t !== t);
      touch();
      renderBookmarks();
    } else {
      closePanels();
      const p = fromKjv(bm);
      goTo(p.b, p.c, p.v, true);
    }
  });

  // Settings panel
  $('#btn-set').addEventListener('click', () => openPanel('#panel-set'));

  // ---------- Reading plan ----------
  const dayStart = (d) => Math.floor((d * CHAPTERS.length) / PLAN_DAYS);
  function dayLabel(d) {
    const a = CHAPTERS[dayStart(d)], z = CHAPTERS[dayStart(d + 1) - 1];
    if (a[0] !== z[0]) return `${bookName(a[0])} ${a[1]} – ${bookName(z[0])} ${z[1]}`;
    if (a[1] === z[1]) return `${bookName(a[0])} ${a[1]}`;
    return `${bookName(a[0])} ${a[1]}–${z[1]}`;
  }
  const toISO = (dt) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, '0')}-${String(dt.getDate()).padStart(2, '0')}`;
  const parseISO = (s) => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
  const daysBetween = (a, b) =>
    Math.round((Date.UTC(b.getFullYear(), b.getMonth(), b.getDate()) - Date.UTC(a.getFullYear(), a.getMonth(), a.getDate())) / 86400000);
  const fmtDate = (dt) => dt.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  function dayDate(d) { const dt = parseISO(state.plan.start); dt.setDate(dt.getDate() + d); return dt; }
  const isDone = (d) => !!state.plan.done[d];

  $('#btn-plan').addEventListener('click', () => {
    renderPlan();
    openPanel('#panel-plan');
    const today = $('#plan-body .day-list li.today');
    if (today) today.scrollIntoView({ block: 'center' });
    $('#plan-body').scrollTop = 0;
  });

  function renderPlan() {
    const body = $('#plan-body');
    const plan = state.plan;
    if (!plan.start) {
      body.innerHTML = `
        <p>Read straight through the Bible, Genesis to Revelation, in one year: about 3–4 chapters a day (${CHAPTERS.length} chapters over ${PLAN_DAYS} days).</p>
        <div class="plan-start">
          <label for="plan-date">Start date</label>
          <input type="date" id="plan-date" value="${toISO(new Date())}">
          <button class="primary wide" id="plan-begin">Start the plan</button>
        </div>`;
      $('#plan-begin').addEventListener('click', () => {
        const v = $('#plan-date').value || toISO(new Date());
        state.plan = { start: v, done: {}, active: null };
        touch();
        renderPlan();
      });
      return;
    }

    const doneCount = Object.keys(plan.done).length;
    const raw = daysBetween(parseISO(plan.start), new Date());
    const today = Math.min(PLAN_DAYS - 1, Math.max(0, raw));
    let firstOpen = -1;
    for (let d = 0; d < PLAN_DAYS; d++) if (!isDone(d)) { firstOpen = d; break; }
    const behind = Math.min(PLAN_DAYS, Math.max(0, raw)) - doneCount;   // days before today still unread
    const ahead = doneCount - Math.min(PLAN_DAYS, raw + 1);
    const plural = (n) => `${n} day${n > 1 ? 's' : ''}`;

    let status;
    if (firstOpen === -1) status = '🎉 You have read the whole Bible. Well done!';
    else if (raw < 0) status = `Your plan begins ${fmtDate(parseISO(plan.start))}.`;
    else if (behind > 0) status = `You're ${plural(behind)} behind — no worries, just pick up where you left off.`;
    else if (ahead > 0) status = `You're ${plural(ahead)} ahead.`;
    else status = "You're on track.";

    const pct = Math.round((doneCount / PLAN_DAYS) * 100);
    let h = `
      <div class="plan-progress"><div style="width:${pct}%"></div></div>
      <div class="plan-stats"><span>${doneCount} of ${PLAN_DAYS} days</span><span>${pct}%</span></div>
      <p class="status">${status}</p>`;

    if (firstOpen !== -1) {
      h += todayCard(`Today · Day ${today + 1} · ${fmtDate(dayDate(today))}`, today);
      if (firstOpen < today) h += todayCard(`Next unread · Day ${firstOpen + 1}`, firstOpen);
    }

    h += '<h3>All days</h3><ul class="list day-list">';
    for (let d = 0; d < PLAN_DAYS; d++) {
      h += `<li class="${isDone(d) ? 'done' : ''}${d === today && raw >= 0 ? ' today' : ''}">
        <button class="chk" data-toggle="${d}" aria-label="Mark day ${d + 1} done">${isDone(d) ? '✓' : ''}</button>
        <button class="go" data-read="${d}"><span class="dn">Day ${d + 1}</span><span class="ref">${esc(dayLabel(d))}</span><span class="date">${fmtDate(dayDate(d))}</span></button>
      </li>`;
    }
    h += '</ul><div class="plan-foot"><button id="plan-reset">Restart plan / change start date</button></div>';
    body.innerHTML = h;

    $('#plan-reset').addEventListener('click', () => {
      if (confirm('Restart the reading plan? This clears your checked-off days.')) {
        state.plan = { start: null, done: {}, active: null };
        touch();
        hidePlanPill();
        renderPlan();
      }
    });
  }
  function todayCard(kicker, d) {
    return `<div class="today-card">
      <div class="kicker">${kicker}</div>
      <div class="reading">${esc(dayLabel(d))}</div>
      <div class="actions">
        <button class="primary" data-read="${d}">Read</button>
        <button class="secondary" data-toggle="${d}">${isDone(d) ? 'Done ✓ (undo)' : 'Mark done'}</button>
      </div></div>`;
  }
  $('#plan-body').addEventListener('click', (e) => {
    const btn = e.target.closest('button');
    if (!btn) return;
    if (btn.dataset.toggle !== undefined) {
      const d = +btn.dataset.toggle;
      const y = $('#plan-body').scrollTop;
      setDayDone(d, !isDone(d));
      renderPlan();
      $('#plan-body').scrollTop = y;
    } else if (btn.dataset.read !== undefined) {
      startPlanDay(+btn.dataset.read);
    }
  });
  function setDayDone(d, done) {
    if (done) state.plan.done[d] = 1; else delete state.plan.done[d];
    if (done && state.plan.active === d) hidePlanPill();
    touch();
  }
  function startPlanDay(d) {
    closePanels();
    const [b, c] = CHAPTERS[dayStart(d)];
    state.plan.active = d;
    const p = fromKjv({ b, c, v: 1 });   // plan days are KJV chapters
    goTo(p.b, p.c, p.v);
    showPlanPill();
  }
  function showPlanPill() {
    const d = state.plan.active;
    if (d === null || d === undefined || !state.plan.start || isDone(d)) return hidePlanPill();
    $('#planpill-text').textContent = `Day ${d + 1}: ${dayLabel(d)}`;
    $('#planpill').hidden = false;
  }
  function hidePlanPill() {
    state.plan.active = null;
    $('#planpill').hidden = true;
    save();
  }
  $('#planpill-done').addEventListener('click', () => {
    const d = state.plan.active;
    setDayDone(d, true);
    hidePlanPill();
    toast(`Day ${d + 1} complete ✓`);
  });
  $('#planpill-x').addEventListener('click', hidePlanPill);

  // ---------- Read aloud ----------
  // Two engines: recorded audio in the app's own "Daniel" voice (the default, streamed per
  // chapter with verse timings), and the device's speech voices (offline, or chapters not yet
  // recorded). Both read from the current place, highlight the words and keep them in view.
  const synth = window.speechSynthesis || null;
  const BUILTIN = 'builtin:daniel';
  // Where recordings live: <book 01-66>/<chapter 001>.m4a + .json (verse start/end times).
  // The full Bible is in the BibleApp-audio repo's GitHub Pages site; a few chapters also ship here.
  const AUDIO_BASES = ['https://bluesboy13.github.io/BibleApp-audio/', 'audio/'];
  const AUDIO_SPEED = 0.9;       // speed the recordings were made at (plays at rate / this)
  const useBuiltin = () => !state.settings.voice || state.settings.voice === BUILTIN;
  const audio = new Audio();
  audio.preload = 'auto';
  const timings = new Map();     // 'b:c' -> timing object, or null when not recorded / unreachable
  const pad = (n, w) => String(n).padStart(w, '0');
  const chapterPath = (b, c) => `${pad(b + 1, 2)}/${pad(c, 3)}`;
  // URL of a chapter's recording, from whichever place its timing file was found.
  const audioUrl = (b, c) => {
    const t = timings.get(`${b}:${c}`);
    return new URL((t ? t.base : AUDIO_BASES[0]) + chapterPath(b, c) + '.m4a', location.href).href;
  };
  function loadTiming(b, c) {
    const key = `${b}:${c}`;
    if (timings.has(key)) return Promise.resolve(timings.get(key));
    const tryBase = (i) => {
      if (i >= AUDIO_BASES.length) return Promise.resolve(null);
      return fetch(AUDIO_BASES[i] + chapterPath(b, c) + '.json')
        .then((r) => (r.ok ? r.json() : null))
        .catch(() => null)
        .then((t) => (t && t.s ? Object.assign(t, { base: AUDIO_BASES[i] }) : tryBase(i + 1)));
    };
    return tryBase(0).then((t) => { timings.set(key, t); return t; });
  }
  const player = {
    active: false,     // player bar is open
    playing: false,
    pos: null,         // { b, c, v } being read
    word: 0,           // char index of the current word within the verse
    token: 0,          // bumps on every stop/restart so stale speech events are ignored
    internal: false,   // true while the player itself is moving the page
    lastUser: 0,       // last time the reader scrolled or turned a page by hand
    gotBoundary: false,
    estTimer: 0,
    wakeLock: null,
  };
  const RATES = [0.75, 0.9, 1, 1.1, 1.25];
  // Voices that suit a mature British reader, best first.
  const PREFERRED_VOICES = [/arthur/i, /daniel/i, /george/i, /oliver/i, /malcolm/i, /ryan/i, /thomas/i, /en-gb.*male/i];

  // Say "LORD"/"GOD" as words, not letters. Same length, so highlight positions still line up.
  const spoken = (t) => t.replace(/\b([A-Z])([A-Z]+)\b/g, (m, a, rest) => a + rest.toLowerCase());

  function englishVoices() {
    const vs = synth ? synth.getVoices().filter((v) => /^en[-_]/i.test(v.lang)) : [];
    const gb = (v) => (/^en[-_]gb/i.test(v.lang) ? 0 : 1);
    return vs.sort((a, z) => gb(a) - gb(z) || a.name.localeCompare(z.name));
  }
  function currentVoice() {
    const vs = englishVoices();
    const saved = vs.find((v) => v.voiceURI === state.settings.voice);
    if (saved) return saved;
    for (const re of PREFERRED_VOICES) {
      const hit = vs.find((v) => /^en[-_]gb/i.test(v.lang) && re.test(v.name + ' ' + v.voiceURI));
      if (hit) return hit;
    }
    return vs.find((v) => /^en[-_]gb/i.test(v.lang)) || vs[0] || null;
  }

  function readerRoot() { return state.settings.mode === 'page' ? flow : bookEl; }
  function verseEl(p) { return readerRoot().querySelector(`.v[data-c="${p.c}"][data-v="${p.v}"]`); }

  // Split the verse into word spans (only for the verse being read).
  function wrapVerse(el, text) {
    if (el.dataset.wrapped) return;
    const sup = el.querySelector('.vn');
    let h = sup ? sup.outerHTML : '';
    const re = /\S+/g;
    let m, last = 0;
    while ((m = re.exec(text))) {
      h += esc(text.slice(last, m.index)) + `<span class="w" data-i="${m.index}">${esc(m[0])}</span>`;
      last = m.index + m[0].length;
    }
    el.innerHTML = h + ' ';
    el.dataset.wrapped = '1';
  }
  function clearHighlight() {
    document.querySelectorAll('.v.reading').forEach((el) => el.classList.remove('reading'));
    document.querySelectorAll('.w.now').forEach((el) => el.classList.remove('now'));
  }
  function highlight(charIndex) {
    const el = verseEl(player.pos);
    if (!el) return;
    wrapVerse(el, verseText(player.pos.b, player.pos.c, player.pos.v));
    el.classList.add('reading');
    let target = null;
    for (const w of el.querySelectorAll('.w')) {
      if (+w.dataset.i <= charIndex) target = w; else break;
    }
    readerRoot().querySelectorAll('.w.now').forEach((w) => { if (w !== target) w.classList.remove('now'); });
    if (!target) return;
    target.classList.add('now');
    player.word = +target.dataset.i;
    keepInView(target);
  }
  function keepInView(el) {
    if (Date.now() - player.lastUser < 4000) return;   // don't fight the reader's own scrolling
    if (state.settings.mode === 'page') {
      const p = pageOf(el);
      if (p !== pg.page) showPage(p, true);
      return;
    }
    const r = el.getBoundingClientRect();
    const top = topOffset() + 30, bottom = window.innerHeight - 150;
    if (r.top < top || r.bottom > bottom) {
      window.scrollTo({ top: window.scrollY + r.top - window.innerHeight * 0.3, behavior: 'smooth' });
    }
  }
  ['touchstart', 'wheel'].forEach((ev) => window.addEventListener(ev, (e) => {
    if (!e.target.closest || !e.target.closest('#player')) player.lastUser = Date.now();
  }, { passive: true }));
  window.addEventListener('keydown', () => { player.lastUser = Date.now(); });

  function speakFrom(pos, offset) {
    const token = ++player.token;
    if (synth) synth.cancel();
    clearInterval(player.estTimer);
    player.pos = pos;
    player.word = offset;
    player.playing = true;
    renderPlayer();

    // Move the page to this verse if it isn't on screen (e.g. a new chapter).
    const r = state.ribbon;
    if (r.b !== pos.b || r.c !== pos.c || !verseEl(pos)) {
      player.internal = true;
      goTo(pos.b, pos.c, pos.v);
      player.internal = false;
    } else {
      setRibbon(pos);
    }
    clearHighlight();
    highlight(offset);

    if (useBuiltin() && SRC[pos.b] === 'kjv') {   // Daniel's recording is of the KJV
      const key = `${pos.b}:${pos.c}`;
      if (timings.has(key)) {
        if (timings.get(key)) return playAudio(token, pos, offset, timings.get(key));
      } else {
        // Start the audio element now, inside the tap, so phones allow playback once the timing arrives.
        primeAudio(pos);
        loadTiming(pos.b, pos.c).then((t) => {
          if (token !== player.token) return;
          if (t) playAudio(token, pos, offset, t);
          else speakDevice(token, pos, offset, true);
        });
        return;
      }
      return speakDevice(token, pos, offset, true);
    }
    speakDevice(token, pos, offset, false);
  }

  // ----- Recorded "Daniel" audio -----
  function primeAudio(pos) {
    const url = audioUrl(pos.b, pos.c);
    if (audio.src !== url) audio.src = url;
    audio.muted = true;
    audio.play().catch(() => {});
  }
  // Word timing inside a verse: share the verse's recorded time by word length and pauses.
  function wordShares(text) {
    const words = [...text.matchAll(/\S+/g)];
    const w = words.map((m) => m[0].length + 1 + (/[.?!]["’)]*$/.test(m[0]) ? 8 : /[,;:]["’)]*$/.test(m[0]) ? 4 : 0));
    const total = w.reduce((a, x) => a + x, 0) || 1;
    let acc = 0;
    return words.map((m, i) => { const at = acc / total; acc += w[i]; return { i: m.index, at }; });
  }
  function timeFor(t, pos, offset) {
    const s = t.s[pos.v - 1], e = t.e[pos.v - 1];
    if (pos.v === 1 && offset === 0) return 0;   // include the "Psalm 23." / "John, chapter 3." heading
    if (!offset) return s;
    const shares = wordShares(verseText(pos.b, pos.c, pos.v));
    const w = shares.find((x) => x.i >= offset) || shares[shares.length - 1];
    return s + (e - s) * w.at;
  }
  function playAudio(token, pos, offset, t) {
    player.engine = 'audio';
    player.timing = t;
    player.chapter = { b: pos.b, c: pos.c };
    const url = audioUrl(pos.b, pos.c);
    if (audio.src !== url) audio.src = url;
    audio.playbackRate = state.settings.rate / AUDIO_SPEED;
    const at = timeFor(t, pos, offset);
    const go = () => {
      if (token !== player.token) return;
      try { audio.currentTime = at; } catch (e) { /* not seekable yet */ }
      audio.muted = false;
      audio.play().catch(() => { if (token === player.token) { pausePlayer(); toast('Tap play to start.'); } });
    };
    if (audio.readyState >= 1) go(); else audio.addEventListener('loadedmetadata', go, { once: true });
    setMediaSession();
    clearInterval(player.estTimer);
    player.estTimer = setInterval(() => audioTick(token), 80);
    // Fetch the next chapter's timing ahead so moving on is instant.
    const n = nextChapter(pos.b, pos.c);
    if (n) loadTiming(n[0], n[1]);
  }
  function audioTick(token) {
    if (token !== player.token || audio.paused || audio.seeking) return;
    const t = player.timing, ct = audio.currentTime;
    let i = 0;
    while (i + 1 < t.s.length && t.s[i + 1] <= ct + 0.02) i++;
    const v = i + 1;
    if (v !== player.pos.v) {
      player.pos = { b: player.chapter.b, c: player.chapter.c, v };
      setRibbon(player.pos);
      renderPlayer();
      setMediaSession();
      clearHighlight();
    }
    if (ct < t.s[i]) return highlight(0);   // chapter heading is being read
    const frac = (ct - t.s[i]) / Math.max(0.1, t.e[i] - t.s[i]);
    const shares = wordShares(verseText(player.pos.b, player.pos.c, v));
    let w = shares[0];
    for (const x of shares) { if (x.at <= frac) w = x; else break; }
    if (w) highlight(w.i);
  }
  audio.addEventListener('ended', () => {
    if (player.engine !== 'audio' || !player.playing) return;
    const n = nextChapter(player.chapter.b, player.chapter.c);
    if (n) speakFrom({ b: n[0], c: n[1], v: 1 }, 0); else stopPlayer();
  });
  audio.addEventListener('error', () => {
    // Couldn't load this chapter's recording (e.g. offline): carry on with the device voice.
    if (player.engine !== 'audio' || !player.playing || !player.chapter) return;
    if (audio.src !== audioUrl(player.chapter.b, player.chapter.c)) return;   // an old or pre-loaded file, not the one playing
    timings.set(`${player.chapter.b}:${player.chapter.c}`, null);
    speakFrom(player.pos, player.word);
  });
  function setMediaSession() {
    if (!('mediaSession' in navigator) || !player.pos) return;
    try {
      navigator.mediaSession.metadata = new MediaMetadata({ title: ref(player.pos), artist: SRC[player.pos.b] === 'kjv' ? 'King James Bible' : TEXTS[state.settings.text].name, album: bookName(player.pos.b) });
    } catch (e) { /* ignore */ }
  }
  if ('mediaSession' in navigator) {
    const on = (a, f) => { try { navigator.mediaSession.setActionHandler(a, f); } catch (e) { /* unsupported */ } };
    on('play', () => player.active && resumePlayer());
    on('pause', () => player.active && pausePlayer());
    on('previoustrack', () => player.active && prevVerse());
    on('nexttrack', () => player.active && nextVerse());
  }

  // ----- Device speech voices -----
  let fallbackNoted = false;
  function speakDevice(token, pos, offset, fellBack) {
    player.engine = 'device';
    audio.pause();
    if (!synth) { pausePlayer(); return toast('This chapter needs an internet connection to be read aloud.'); }
    if (fellBack && !fallbackNoted) {
      fallbackNoted = true;
      toast('Daniel isn’t available here yet (or you’re offline). Using the device voice.');
    }
    const full = spoken(verseText(pos.b, pos.c, pos.v));
    const u = new SpeechSynthesisUtterance(full.slice(offset));
    let voice = currentVoice();
    if (isGreek(pos.b)) {
      voice = synth.getVoices().find((v) => /^el/i.test(v.lang)) || null;
      if (!voice) {
        pausePlayer();
        return toast('No Greek voice on this device. Add one in your device settings, or switch to the English text.');
      }
    }
    if (voice) { u.voice = voice; u.lang = voice.lang; } else u.lang = 'en-GB';
    u.rate = state.settings.rate;
    u.pitch = 0.95;
    player.gotBoundary = false;
    u.onboundary = (e) => {
      if (token !== player.token) return;
      if (e.name && e.name !== 'word') {
        // Voices without word events may still report sentences: use them to resync the estimate.
        if (!player.gotBoundary) resyncEstimate(token, e.charIndex);
        return;
      }
      player.gotBoundary = true;
      clearInterval(player.estTimer);
      highlight(offset + e.charIndex);
    };
    u.onstart = () => { if (token === player.token) estimateWords(token, full, offset, voice); };
    u.onend = () => {
      if (token !== player.token) return;
      learnVoiceSpeed(token);
      nextVerse();
    };
    u.onerror = (e) => {
      if (token !== player.token || e.error === 'interrupted' || e.error === 'canceled') return;
      pausePlayer();
      toast('Could not play audio on this device.');
    };
    // A short pause after cancel() avoids a Chrome bug where the next utterance is dropped.
    setTimeout(() => { if (token === player.token) synth.speak(u); }, 60);
  }
  // Some voices don't report word positions; step through the words at speaking pace instead.
  // Some voices don't report word positions (common on iPhone). For those, estimate when each
  // word is spoken from the voice's measured speed, allowing extra time at punctuation.
  const voiceKey = (v) => (v ? v.voiceURI || v.name : 'default');
  function estimateWords(token, full, offset, voice) {
    clearInterval(player.estTimer);
    const words = [...full.slice(offset).matchAll(/\S+/g)];
    const speeds = state.settings.cps || {};
    const perSec = (speeds[voiceKey(voice)] || 15) * state.settings.rate;
    let t = 0;
    const times = words.map((w) => {
      const at = t;
      t += (w[0].length + 1 + (/[.?!]["’)]*$/.test(w[0]) ? 8 : /[,;:]["’)]*$/.test(w[0]) ? 4 : 0)) / perSec;
      return at;
    });
    player.est = { token, words, times, total: t, offset, voice, start: performance.now(), shown: -1 };
    player.estTimer = setInterval(() => {
      const est = player.est;
      if (!est || est.token !== player.token || player.gotBoundary) return clearInterval(player.estTimer);
      const elapsed = (performance.now() - est.start) / 1000;
      let i = est.shown < 0 ? 0 : est.shown;
      while (i + 1 < est.times.length && est.times[i + 1] <= elapsed) i++;
      if (i !== est.shown && est.words[i]) {
        est.shown = i;
        highlight(est.offset + est.words[i].index);
      }
    }, 60);
  }
  function resyncEstimate(token, charIndex) {
    const est = player.est;
    if (!est || est.token !== token) return;
    let i = 0;
    while (i + 1 < est.words.length && est.words[i + 1].index <= charIndex) i++;
    est.start = performance.now() - est.times[i] * 1000;
    est.shown = Math.min(est.shown, i - 1);
  }
  // After each verse, compare the estimate with how long the voice really took and adjust.
  function learnVoiceSpeed(token) {
    const est = player.est;
    if (!est || est.token !== token || player.gotBoundary) return;
    const elapsed = (performance.now() - est.start) / 1000;
    if (elapsed < 1.5 || est.total <= 0) return;
    const speeds = state.settings.cps || (state.settings.cps = {});
    const key = voiceKey(est.voice);
    const measured = (est.total / elapsed) * (speeds[key] || 15);
    const next = Math.min(40, Math.max(6, (speeds[key] || 15) * 0.2 + measured * 0.8));
    speeds[key] = Math.round(next * 100) / 100;
    save();
  }
  function nextVerse() {
    const p = player.pos;
    if (p.v < BIBLE[p.b][1][p.c - 1].length) return speakFrom({ b: p.b, c: p.c, v: p.v + 1 }, 0);
    const n = nextChapter(p.b, p.c);
    if (n) speakFrom({ b: n[0], c: n[1], v: 1 }, 0);
    else stopPlayer();
  }
  function prevVerse() {
    const p = player.pos;
    if (p.v > 1) return speakFrom({ b: p.b, c: p.c, v: p.v - 1 }, 0);
    const n = prevChapter(p.b, p.c);
    if (n) speakFrom({ b: n[0], c: n[1], v: BIBLE[n[0]][1][n[1] - 1].length }, 0);
    else speakFrom(p, 0);
  }
  function pausePlayer() {
    player.token++;
    player.playing = false;
    clearInterval(player.estTimer);
    if (synth) synth.cancel();
    audio.pause();
    releaseWake();
    renderPlayer();
  }
  function resumePlayer() {
    requestWake();
    speakFrom(player.pos, player.word);
  }
  function startPlayer() {
    if (!synth && !useBuiltin()) return toast('Read aloud is not supported on this device.');
    player.active = true;
    document.body.classList.add('playing');
    $('#player').hidden = false;
    if (state.settings.mode === 'page') relayout();
    requestWake();
    speakFrom({ ...state.ribbon }, 0);
  }
  function stopPlayer() {
    pausePlayer();
    clearHighlight();
    player.active = false;
    document.body.classList.remove('playing');
    $('#player').hidden = true;
    if (state.settings.mode === 'page') relayout();
  }
  // The reader jumped somewhere (book list, bookmark, plan): keep reading from there.
  function afterNavigate(b, c, v) {
    if (player.internal) return;
    const p = player.pos;
    if (p && p.b === b && p.c === c && p.v === v) {
      if (player.playing) highlight(player.word);   // same place, just re-drawn
      return;
    }
    if (player.playing) speakFrom({ b, c, v }, 0);
    else { player.pos = { b, c, v }; player.word = 0; clearHighlight(); renderPlayer(); }
  }
  function renderPlayer() {
    if (!player.pos) return;
    $('#player-ref').textContent = ref(player.pos);
    const btn = $('#player-toggle');
    btn.innerHTML = player.playing
      ? '<svg viewBox="0 0 24 24"><rect x="6.5" y="5" width="3.6" height="14" rx="1"/><rect x="13.9" y="5" width="3.6" height="14" rx="1"/></svg>'
      : '<svg viewBox="0 0 24 24"><path d="M8 5.5v13l10.5-6.5z"/></svg>';
    btn.setAttribute('aria-label', player.playing ? 'Pause' : 'Play');
    $('#player-rate').textContent = `${state.settings.rate}×`;
  }
  async function requestWake() {
    try { if ('wakeLock' in navigator && !player.wakeLock) player.wakeLock = await navigator.wakeLock.request('screen'); } catch (e) { /* ignore */ }
  }
  function releaseWake() {
    if (player.wakeLock) { player.wakeLock.release().catch(() => {}); player.wakeLock = null; }
  }
  // Phones stop speech when the app goes to the background; pause so it resumes in place.
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && player.playing && player.engine === 'device') pausePlayer();
  });

  $('#btn-play').addEventListener('click', () => {
    if (!player.active) startPlayer();
    else if (player.playing) pausePlayer();
    else resumePlayer();
  });
  $('#player-toggle').addEventListener('click', () => (player.playing ? pausePlayer() : resumePlayer()));
  $('#player-prev').addEventListener('click', () => { requestWake(); prevVerse(); });
  $('#player-next').addEventListener('click', () => { requestWake(); nextVerse(); });
  $('#player-close').addEventListener('click', stopPlayer);
  $('#player-rate').addEventListener('click', () => {
    const i = RATES.indexOf(state.settings.rate);
    state.settings.rate = RATES[(i + 1) % RATES.length];
    save();
    renderPlayer();
    if (player.playing) speakFrom(player.pos, player.word);
  });

  // Voice picker (Aa panel)
  function fillVoices() {
    const sel = $('#set-voice');
    const vs = englishVoices();
    const cur = useBuiltin() ? null : currentVoice();
    sel.innerHTML = `<option value="${BUILTIN}"${useBuiltin() ? ' selected' : ''}>Daniel – British (built in)</option>` +
      (vs.length ? '<optgroup label="This device’s voices">' + vs.map((v) => `<option value="${esc(v.voiceURI)}"${cur && v.voiceURI === cur.voiceURI ? ' selected' : ''}>${esc(v.name)} (${esc(v.lang)})</option>`).join('') + '</optgroup>' : '');
  }
  if (synth) {
    fillVoices();
    synth.addEventListener && synth.addEventListener('voiceschanged', fillVoices);
  }
  $('#btn-set').addEventListener('click', fillVoices);
  $('#set-follow').addEventListener('click', (e) => {
    if (!e.target.dataset.v) return;
    state.settings.follow = e.target.dataset.v;   // display only: no need to re-lay out the page
    applySettings();
    save();
  });
  $('#set-voice').addEventListener('change', (e) => {
    state.settings.voice = e.target.value;
    save();
    if (player.playing) speakFrom(player.pos, player.word);
  });
  $('#voice-test').addEventListener('click', () => {
    if (player.playing) pausePlayer();
    if (useBuiltin()) {
      // Play the first verse of Psalm 23 from the recording.
      primeAudio({ b: 18, c: 23 });
      loadTiming(18, 23).then((t) => {
        if (!t) { audio.pause(); return toast('Daniel needs an internet connection.'); }
        audio.currentTime = t.s[0];
        audio.playbackRate = state.settings.rate / AUDIO_SPEED;
        audio.muted = false;
        audio.play().catch(() => {});
        const stopAt = t.e[0];
        const stop = () => { if (audio.currentTime >= stopAt) { audio.pause(); audio.removeEventListener('timeupdate', stop); } };
        audio.addEventListener('timeupdate', stop);
      });
      return;
    }
    if (!synth) return;
    synth.cancel();
    const u = new SpeechSynthesisUtterance(spoken('The LORD is my shepherd; I shall not want.'));
    const v = currentVoice();
    if (v) { u.voice = v; u.lang = v.lang; }
    u.rate = state.settings.rate;
    u.pitch = 0.95;
    synth.speak(u);
  });

  // ---------- Startup ----------
  let resizeTimer = 0;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => { if (BIBLE) relayout(); }, 200);
  });

  async function init() {
    applySettings();
    try {
      const res = await fetch('data/kjv.json');
      KJV = await res.json();
    } catch (e) {
      $('#loading').textContent = 'Could not load the Bible text. Please check your connection and reload.';
      return;
    }
    KJV.forEach((book, b) => book[1].forEach((_, i) => CHAPTERS.push([b, i + 1])));
    buildText('kjv');
    if (state.settings.text !== 'kjv') {
      try { await loadText(state.settings.text); } catch (e) { /* offline before first download */ }
      if (!buildText(state.settings.text)) {
        state.settings.text = 'kjv';
        buildText('kjv');
        applySettings();
      }
    }
    $('#loading').remove();
    if (!TEXTS[state.ribbonText]) state.ribbonText = 'kjv';
    syncRibbonText();
    const r = state.ribbon;
    if (!BIBLE[r.b] || r.c > chapterCount(r.b)) state.ribbon = { ...DEFAULTS.ribbon };
    if (state.settings.mode === 'page') setBars(false);
    relayout();
    showPlanPill();
    // Re-measure once web fonts arrive so pages and position stay accurate.
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(relayout);
  }
  init();

  // ---------- Sync hooks (used by js/sync.js) ----------
  window.KJV = {
    get uid() { return state.syncUid; },
    // The data that follows you between devices. Display settings stay per-device.
    syncData() {
      return {
        // Shared in KJV numbering so devices reading different texts still agree on the place.
        ribbon: BIBLE && state.ribbonText === state.settings.text ? toKjv(state.ribbon) : state.ribbon,
        bookmarks: state.bookmarks,
        plan: { start: state.plan.start, done: state.plan.done },
        updatedAt: state.updatedAt,
      };
    },
    // Take in data from the cloud. On a device's first sync, merge instead of replacing.
    applyRemote(remote, uid) {
      const first = state.syncUid !== uid;
      const before = { ...state.ribbon };
      if (first) {
        const seen = new Set(state.bookmarks.map((x) => x.t));
        state.bookmarks = state.bookmarks.concat((remote.bookmarks || []).filter((x) => !seen.has(x.t)));
        if (remote.plan && remote.plan.start) {
          const sameStart = remote.plan.start === state.plan.start;
          state.plan.start = remote.plan.start;
          state.plan.done = sameStart ? { ...state.plan.done, ...remote.plan.done } : { ...remote.plan.done };
        }
        if ((remote.updatedAt || 0) > state.updatedAt && remote.ribbon) { state.ribbon = remote.ribbon; state.ribbonText = 'kjv'; }
        state.updatedAt = Date.now();
      } else {
        if (remote.ribbon) { state.ribbon = remote.ribbon; state.ribbonText = 'kjv'; }
        state.bookmarks = remote.bookmarks || [];
        state.plan.start = remote.plan ? remote.plan.start : null;
        state.plan.done = (remote.plan && remote.plan.done) || {};
        state.updatedAt = remote.updatedAt || 0;
      }
      state.syncUid = uid;
      save();
      if (!BIBLE) return first;
      syncRibbonText();
      const r = state.ribbon;
      if (r.b !== before.b || r.c !== before.c || r.v !== before.v) {
        const held = syncHold;
        syncHold = true;   // moving to the synced spot isn't a new change
        goTo(r.b, r.c, r.v);
        syncHold = held;
      }
      if (!$('#panel-bm').hidden) renderBookmarks();
      if (!$('#panel-plan').hidden) renderPlan();
      showPlanPill();
      return first;
    },
    setUid(uid) { state.syncUid = uid; save(); },
    releaseHold() { syncHold = false; },
    toast,
  };

  if ('serviceWorker' in navigator) {
    // When an updated version finishes installing, reload once so every file is the new version.
    const hadController = !!navigator.serviceWorker.controller;
    let reloaded = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (!hadController || reloaded) return;
      reloaded = true;
      location.reload();
    });
    window.addEventListener('load', () => navigator.serviceWorker.register('sw.js').catch(() => {}));
  }
})();
