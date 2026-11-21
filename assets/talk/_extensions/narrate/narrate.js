/* reveal.js plugin of the sci-narrated-talk skill: a talk that tells itself.
 *
 * The narration of a slide is its `.say` blocks, one per sentence, in document order. Whatever follows the n-th block
 * (n >= 2) becomes a reveal fragment, so reveal's own machinery shows it when sentence n starts; every sentence is itself
 * a hidden fragment, so reveal's position (slide, fragment f) is always "sentence f + 1 of that slide".
 * A block without text is a silent step of wait= seconds (default 3); a slide without blocks is one silent step.
 * Attributes of a block: point="#id" (a ring closes in on that element), grow="#id" (that SVG path is drawn while the
 * sentence is spoken), label="..." (the outline's name for a silent step), wait="2".
 * The title slide takes its narration from title-slide-attributes: data-say: "First sentence.|Second sentence."
 *
 * Audio: window.TALK (media/manifest.js, written by narrate.py) lists the spoken sentences in document order (src, dur)
 * and the pauses lead, gap, tail; pre is the beat by which a reveal precedes its sentence.
 *
 * Player: a bar over the bottom of the slide (fades when the mouse rests while playing) with a timeline (one segment per
 * slide, as wide as the slide is long; one per section when slides would be < 10 px; none on a phone), and an outline.
 * Keys: <- -> slide, up/down sentence, space pause/resume, C captions, T outline, M voice on/off, A auto-advance,
 * Y next theme, X hide the bar, ? help; nothing with Ctrl/Alt/Meta; every other key stays reveal's. Each button prints its key.
 * Alt+click on an element replays the sentence that introduced it (data-k); Ctrl+click is reveal's zoom.
 * URL: #n.k = slide n, sentence k (1-based). ?fast: no audio, 50x speed; body[data-log] lists the visited positions,
 * body[data-over] what reaches outside its slide, body[data-done] the end. ?shot: no player, no transitions; #n alone
 * shows the slide's last sentence (for screenshots). ?tl=slides|sections|none forces a timeline mode.
 * Themes: window.TALK.themes maps a name to the values of the theme's CSS variables (--bg, --ink, ..., --font), which
 * are all the slides' styles and the figures refer to; ?theme=NAME opens in one, Y or the bar's button goes to the next.
 * In reveal's speaker view (S) the two previews follow the main window silently; the notes are the narration.
 */
window.RevealNarrate = () => {
  let deck, T, N, slides, h = 0, k = 0, playing = false, auto = true, phase = 'idle', tok = 0, timer = null;
  let D, S0, TOTAL, groups, secOf, SEC, items = [], built = -1, idleT, theme;
  const opened = new Set();  // outline parts the viewer opened by hand (or that the browser's find opened)
  const q = new URLSearchParams(location.search), FAST = q.has('fast'), SHOT = q.has('shot'), TL = q.get('tl');
  const RECV = q.has('receiver');  // one of the two previews in reveal's speaker view (S): follows the main window, silent
  const audio = new Audio(), body = document.body, $ = s => document.querySelector(s);
  const f = () => (FAST ? 0.02 : 1);  // time scale of the pauses
  const says = j => [...slides[j].querySelectorAll('.say')];
  const fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const esc = s => String(s).replace(/[&<>"]/g, c => `&#${c.charCodeAt(0)};`);
  const words = s => s.trim().replace(/\s+/g, ' ');
  const short = s => { const w = s.split(' '); return w.length > 11 ? w.slice(0, 10).join(' ') + ' …' : s; };
  const heading = e => e ? words([...e.childNodes].filter(n => !n.classList?.contains('eyebrow')).map(n => n.textContent).join('')) : '';
  const titleOf = j => heading(slides[j].querySelector('h1, h2')) || SEC[j] || document.title;

  // ------------------------------------------------------------ sentences -> reveal fragments
  function prepare(sec) {
    const ss = [...sec.querySelectorAll('.say')];
    ss.forEach((s, j) => { if (j) { s.classList.add('fragment'); s.dataset.fragmentIndex = j - 1; } });
    let cur = 0;
    sec.dataset.k = 0;
    sec.querySelectorAll('video').forEach(v => Object.assign(v, {muted: true, loop: true, controls: false, playsInline: true}));
    (function visit(el) {
      for (const c of [...el.children]) {
        if (c.classList.contains('say')) { cur = ss.indexOf(c); continue; }
        if (c.querySelector('.say')) { visit(c); continue; }
        if (!c.classList.contains('fragment') && cur > 0) { c.classList.add('fragment'); c.dataset.fragmentIndex = cur - 1; }
        if (c.dataset.k === undefined)
          c.dataset.k = c.classList.contains('fragment') && !c.classList.contains('fade-out') ? +c.dataset.fragmentIndex + 1 : cur;
      }
    })(sec);
    if (!sec.querySelector('aside.notes'))  // reveal's speaker view (S) shows the slide's narration as its notes
      sec.insertAdjacentHTML('beforeend', `<aside class="notes">${ss.map(s => `<p>${esc(words(s.textContent))}</p>`).join('')}</aside>`);
  }

  // ------------------------------------------------------------ what the page shows
  function render() {
    const s = says(h)[k], sec = slides[h];
    $('#nar-cap span').textContent = s ? s.textContent.trim() : '';
    $('#nar-sec').textContent = SEC[h];
    deck.getRevealElement().classList.toggle('nar-bare', sec.matches('#title-slide, .divider'));  // no footer texts there
    $('#nar-num').textContent = `${h + 1} / ${N}`;
    if (built !== h) layout();
    syncOutline();
    history.replaceState(null, '', `${location.pathname}${location.search}#${h + 1}.${k + 1}`);
    body.dataset.log = (body.dataset.log || '') + `${h + 1}.${k + 1} `;
    document.querySelectorAll('.nar-ptr').forEach(e => e.remove());
    const t = s && s.dataset.point && sec.querySelector(s.dataset.point);
    if (t) {  // a ring closing in on the named element
      const r = t.getBoundingClientRect(), b = sec.getBoundingClientRect(), sc = deck.getScale(), p = document.createElement('div');
      const pad = deck.getConfig().width / 140;  // sizes in the slide's own units, whatever its canvas
      p.className = 'nar-ptr';
      Object.assign(p.style, {left: (r.left - b.left) / sc - pad + 'px', top: (r.top - b.top) / sc - pad + 'px',
                              width: r.width / sc + 2 * pad + 'px', height: r.height / sc + 2 * pad + 'px',
                              borderWidth: pad * 0.45 + 'px', borderRadius: pad + 'px'});
      sec.appendChild(p);
    }
    if (FAST && k === says(h).length - 1) {  // the check run: what reaches outside the slide once all of it shows
      const b = deck.getSlidesElement().getBoundingClientRect();
      const out = [...sec.querySelectorAll('h1, h2, p, li, td, img, video, svg.nar-fig, .katex-display')].filter(e => {
        const r = e.getBoundingClientRect();
        return r.width && (r.right > b.right + 2 || r.bottom > b.bottom + 2 || r.left < b.left - 2 || r.top < b.top - 2);
      });
      if (out.length) body.dataset.over = (body.dataset.over || '') + `slide ${h + 1}: ${[...new Set(out.map(e => e.tagName.toLowerCase()))].join(', ')}; `;
      // and what no sentence reveals: a fragment or pause of the author's own
      if (sec.querySelector('.fragment:not(.visible):not(.say):not(.fade-out)')) body.dataset.hidden = (body.dataset.hidden || '') + `slide ${h + 1}; `;
    }
  }
  function media(seek) {  // the slide's clips run on the scene's clock, as in the video
    const say = T.scenes[h].say, at = k ? say[k].t0 - T.pre : 0;
    slides[h].querySelectorAll('video').forEach(v => {
      const go = () => { if (seek && Math.abs(v.currentTime - at) > 0.3) v.currentTime = at % (v.duration || 1e9);
                         playing ? v.play().catch(() => {}) : v.pause(); };
      v.readyState ? go() : v.addEventListener('loadedmetadata', go, {once: true});
    });
  }
  function ui() {
    $('#nar-play').textContent = playing ? '❚❚' : '▶';
    $('#nar-play').title = (playing ? 'pause' : 'play') + ' (space)';
    body.classList.toggle('nar-playing', playing);
    wake();
  }

  // ------------------------------------------------------------ the clock
  function place(nh, nk) {  // move reveal to slide nh, sentence nk, without our listener reacting
    h = nh; k = nk;
    const ix = deck.getIndices(slides[h]);  // a section heading (#) may stack its slides vertically
    deck.slide(ix.h, ix.v, k - 1);
    render();
  }
  function halt() { tok++; clearTimeout(timer); audio.pause(); phase = 'idle'; }
  function go(nh, nk, play = playing) {
    if (nh < 0 || nh >= N) return;
    if (RECV) play = false;
    halt();
    place(nh, Math.max(0, Math.min(nk, says(nh).length - 1)));
    playing = play; media(true); ui();
    if (play) wait(k ? T.pre : T.lead, speak);
  }
  function wait(sec, then) { const my = tok; timer = setTimeout(() => my === tok && then(my), sec * 1000 * f()); }
  function speak() {
    const s = T.scenes[h].say[k], my = tok;
    phase = 'say';
    if (FAST || !s.src) return wait(s.dur, done);  // a silent step only takes its time
    audio.src = s.src;
    audio.onended = () => my === tok && done();
    audio.play().catch(() => { playing = false; ui(); });
  }
  function done() {
    phase = 'after';
    if (k < says(h).length - 1) wait(T.gap - T.pre, () => { place(h, k + 1); wait(T.pre, speak); });
    else if (auto && h < N - 1) wait(T.tail, () => { place(h + 1, 0); media(true); wait(T.lead, speak); });
    else { playing = false; phase = 'end'; ui(); if (h === N - 1) body.dataset.done = 1; }
  }
  function toggle() {
    if (RECV) return;
    if (playing) { playing = false; tok++; clearTimeout(timer); audio.pause(); media(false); return ui(); }
    playing = true; ui(); media(false);
    const my = ++tok;
    if (phase === 'say' && !FAST && T.scenes[h].say[k].src && audio.currentTime > 0 && !audio.ended) {
      audio.onended = () => my === tok && done(); audio.play();
    } else if (phase === 'after') done();
    else wait(k ? T.pre : T.lead, speak);
  }
  const nextS = () => (k < says(h).length - 1 ? go(h, k + 1) : go(h + 1, 0));
  const prevS = () => (k > 0 ? go(h, k - 1) : h > 0 && go(h - 1, 99));
  function local() {  // seconds since the start of the current slide (steps through the pauses, smooth while speaking)
    const s = T.scenes[h].say[k];
    if (phase === 'say') return s.t0 + (FAST || !s.src ? 0 : audio.currentTime);
    if (phase === 'after' || phase === 'end') return s.t0 + s.dur;
    return k ? s.t0 - T.pre : 0;
  }

  function tick() {  // every frame: the timeline's fill and the clock; growing paths (a sentence's grow=)
    const c = $('#nar-segs i.cur b'), t = local();
    if (c) c.style.width = Math.min(100, t / D[h] * 100) + '%';
    $('#nar-time').textContent = `${fmt(S0[h] + t)} / ${fmt(TOTAL)}`;
    says(h).forEach((s, j) => {
      const p = s.dataset.grow && slides[h].querySelector(s.dataset.grow + ' path, path' + s.dataset.grow);
      if (!p) return;
      const L = p.getTotalLength();
      const x = SHOT || FAST || k > j ? 1 : k < j ? 0 : phase === 'say' ? Math.min(1, audio.currentTime / T.scenes[h].say[j].dur) : phase === 'after' ? 1 : 0;
      p.style.strokeDasharray = L;
      p.style.strokeDashoffset = L * (1 - x);
    });
    requestAnimationFrame(tick);
  }

  // ------------------------------------------------------------ timeline
  function layout() {  // one segment per slide, or per section with the current one expanded, or none
    built = h;
    const W = $('#nar-tl').clientWidth || innerWidth;
    const mode = ['slides', 'sections', 'none'].includes(TL) ? TL : innerWidth < 520 ? 'none' : W / N < 10 ? 'sections' : 'slides';
    $('#nar-bar').dataset.tl = mode;
    if (mode === 'none') return;
    items = [];
    groups.forEach((g, gi) => (mode === 'slides' || gi === secOf[h] ? g.js.forEach(j => items.push({j, g: gi, w: D[j]})) : items.push({g: gi, w: g.T})));
    const cur = items.filter(i => i.j !== undefined), cw = cur.reduce((a, i) => a + i.w, 0);
    if (mode === 'sections' && cw < TOTAL) {  // the open section gets >= 16 px per slide (<= 60 % of the bar): not to scale
      const p = Math.min(0.6, Math.max(cw / TOTAL, 16 * cur.length / W));
      cur.forEach(i => { i.w *= p * (TOTAL - cw) / (1 - p) / cw; });
    }
    const sum = items.reduce((a, i) => a + i.w, 0);
    let x = 0;
    items.forEach(i => { i.l = x / sum * 100; x += i.w; i.r = x / sum * 100; });
    $('#nar-segs').innerHTML = items.map(i => {
      const last = i.j ?? groups[i.g].js.at(-1), ticks = i.j === h ? T.scenes[h].say.slice(1).map(s => `<u style="left:${s.t0 / D[h] * 100}%"></u>`).join('') : '';
      return `<i class="${i.j === h ? 'cur' : last < h ? 'done' : ''}${i.j === undefined ? ' grp' : ''}" style="left:${i.l}%;width:calc(${i.r - i.l}% - 2px)"><b></b>${ticks}</i>`;
    }).join('');
    $('#nar-labs').innerHTML = groups.map((g, gi) => {
      const its = items.filter(i => i.g === gi);
      return `<span style="left:${its[0].l}%;width:${its.at(-1).r - its[0].l}%">${esc(g.name)}</span>`;
    }).join('');
    $('#nar-labs').querySelectorAll('span').forEach(s => { if (s.scrollWidth > s.clientWidth) s.style.visibility = 'hidden'; });
  }
  function itemAt(x) {  // the item under the pointer's x (the hit zone is the full height, gaps included), and where in it
    const segs = $('#nar-segs').children;
    for (let n = 0; n < items.length; n++) {
      const r = segs[n].getBoundingClientRect();
      if (x < r.right + 2 || n === items.length - 1) return [items[n], Math.max(0, Math.min(1, (x - r.left) / r.width))];
    }
  }
  const kAt = fr => T.scenes[h].say.reduce((n, s, i) => (s.t0 <= fr * D[h] ? i : n), 0);
  function tip(e) {
    const [it, fr] = itemAt(e.clientX), t = $('#nar-tip'), tl = $('#nar-tl').getBoundingClientRect();
    if (it.j === undefined) { const g = groups[it.g]; t.textContent = `${g.name} · slides ${g.js[0] + 1}–${g.js.at(-1) + 1} · ${fmt(g.t)}`; }
    else {
      t.textContent = `${it.j + 1} · ${titleOf(it.j)} · ${fmt(S0[it.j])}`;
      if (it.j === h) { const n = kAt(fr); t.textContent += ` · sentence ${n + 1} at ${fmt(S0[h] + T.scenes[h].say[n].t0)}`; }
    }
    t.style.display = 'block';
    t.style.left = Math.max(0, Math.min(tl.width - t.offsetWidth, e.clientX - tl.left - t.offsetWidth / 2)) + 'px';
  }
  function seek(e) {
    const [it, fr] = itemAt(e.clientX);
    if (it.j === undefined) go(groups[it.g].js[0], 0);
    else go(it.j, it.j === h ? kAt(fr) : 0);
  }

  // ------------------------------------------------------------ outline
  function stepLabel(j, n) {  // [line text, tooltip]: the sentence, the author's label, what the step reveals, its length
    const s = says(j)[n], text = words(s.textContent);
    if (text) return [short(text), text];
    const sl = slides[j], fr = [...sl.querySelectorAll(`[data-k="${n}"]`)].filter(e => [sl, null].includes(e.parentElement.closest(`[data-k="${n}"]`)));
    const lab = s.dataset.label || fr.find(e => e.dataset.label)?.dataset.label;
    if (lab) return [lab, lab];
    const fig = e => e.closest('svg') || e.querySelector('svg, img, video');
    const txt = fr.filter(e => !fig(e)).map(e => words(e.textContent)).find(Boolean);
    if (txt) return [short(txt), txt];
    const ids = fr.filter(fig).map(e => e.id || e.querySelector('img')?.getAttribute('src')?.split('/').pop()).filter(Boolean);
    const id = ids.find(i => !/_\d+$/.test(i)) || ids[0];  // a part the builder named (gid) beats matplotlib's line2d_12
    if (id) return ['figure: ' + id.replace(/^fig-/, '').replace(/-L\d+-/, ' · '), id];
    return [`step ${n + 1} · ${Math.round(T.scenes[j].say[n].dur)} s`, ''];
  }
  function outline() {
    const line = (cls, data, pre, text, t, full) =>
      `<div class="o-line ${cls}" ${data}${full ? ` title="${esc(full)}"` : ''}>${pre}<span>${esc(text)}</span><em>${fmt(t)}</em></div>`;
    $('#nar-out').innerHTML = '<div class="o-top">Outline<button id="nar-oclose" title="close (T)">×</button></div>' + groups.map((g, gi) =>
      `<div class="o-sec">${line('o-head', `data-g="${gi}"`, '', g.name, g.t)}<div class="o-body">${g.js.map(j =>
        line('o-slide', `data-j="${j}"`, `<b>${j + 1}</b>`, titleOf(j), S0[j]) + `<div class="o-says">${says(j).map((s, n) => {
          const [a, full] = stepLabel(j, n);
          return line('o-say', `data-j="${j}" data-n="${n}"`, '', a, S0[j] + T.scenes[j].say[n].t0, full);
        }).join('')}</div>`).join('')}</div></div>`).join('');
  }
  function syncOutline() {  // closed parts stay findable (hidden=until-found); the current sentence stays in view
    const out = $('#nar-out'), show = (b, v) => (v ? b.removeAttribute('hidden') : b.setAttribute('hidden', 'until-found'));
    out.querySelectorAll('.o-sec').forEach((s, gi) => {
      const b = s.lastElementChild, on = gi === secOf[h];
      s.classList.toggle('on', on); s.classList.toggle('open', on || opened.has(b)); show(b, on || opened.has(b));
    });
    out.querySelectorAll('.o-slide').forEach(l => { const on = +l.dataset.j === h; l.classList.toggle('on', on); show(l.nextElementSibling, on || opened.has(l.nextElementSibling)); });
    out.querySelectorAll('.o-say').forEach(l => l.classList.toggle('on', +l.dataset.j === h && +l.dataset.n === k));
    const c = out.querySelector('.o-say.on');
    if (c && body.classList.contains('nar-outline') && (c.offsetTop < out.scrollTop || c.offsetTop + c.offsetHeight > out.scrollTop + out.clientHeight - 90))
      out.scrollTop = c.offsetTop - out.clientHeight / 3;
  }

  // ------------------------------------------------------------ chrome
  function chrome() {
    document.body.insertAdjacentHTML('beforeend', `
<div id="nar-bar"><div id="nar-tl"><div id="nar-labs"></div><div id="nar-segs"></div><div id="nar-tip"></div></div>
<div class="row"><button id="nar-play" title="play (space)">▶</button><kbd>space</kbd><span id="nar-time"></span><span id="nar-num"></span>
<span class="sp"></span><button id="nar-voice" title="voice (M): off, the talk runs on silently at the same pace" aria-pressed="true">voice<kbd>M</kbd></button>
<button id="nar-theme" title="next theme (Y)"><span></span><kbd>Y</kbd></button>
<button id="nar-capt" title="captions (C)" aria-pressed="false">CC<kbd>C</kbd></button>
<button id="nar-auto" title="auto-advance (A): go on to the next slide at the end of this one" aria-pressed="true">auto<kbd>A</kbd></button>
<button id="nar-olb" title="outline (T)" aria-pressed="false">☰<kbd>T</kbd></button><button id="nar-helpb" title="keys and mouse (?)">?</button>
<button id="nar-hide" title="hide / show the bar (X)"><span></span><kbd>X</kbd></button></div></div>
<div id="nar-out"></div>
<div id="nar-help"><div class="box"><h3>Keys</h3><table>
<tr><td><kbd>space</kbd></td><td>play / pause</td></tr><tr><td><kbd>←</kbd> <kbd>→</kbd></td><td>previous / next slide</td></tr>
<tr><td><kbd>↑</kbd> <kbd>↓</kbd></td><td>previous / next sentence</td></tr><tr><td><kbd>Home</kbd> <kbd>End</kbd></td><td>first / last slide</td></tr>
<tr><td><kbd>C</kbd></td><td>captions</td></tr><tr><td><kbd>T</kbd></td><td>outline</td></tr>
<tr><td><kbd>M</kbd></td><td>voice on / off; the talk keeps its pace</td></tr>
<tr><td><kbd>Y</kbd></td><td>next theme (colours and font)</td></tr>
<tr><td><kbd>A</kbd></td><td>auto-advance to the next slide on / off</td></tr><tr><td><kbd>X</kbd></td><td>hide / show the bar</td></tr><tr><td><kbd>?</kbd></td><td>this help</td></tr>
<tr><td><kbd>F</kbd> <kbd>Esc</kbd> <kbd>F1</kbd></td><td>reveal.js: fullscreen, overview, all its keys</td></tr></table>
<h3>Mouse</h3><table><tr><td>timeline</td><td>click a slide to jump to it; inside the current slide, to the sentence under the pointer</td></tr>
<tr><td>outline</td><td>click a line to play from there; click a section to open it</td></tr>
<tr><td>Alt+click</td><td>an element on the slide: replay the sentence that introduced it</td></tr>
<tr><td>Ctrl+click</td><td>zoom in (reveal.js); again to zoom out</td></tr><tr><td>click, drag</td><td>select text</td></tr></table>
<p>Keys with Ctrl, Alt or Meta are left to the browser. Click anywhere to close.</p></div></div>
<div id="nar-start"><div>▶&nbsp; Click or press space to start<small>${esc(body.dataset.error || '')}</small></div></div>`);
    deck.getRevealElement().insertAdjacentHTML('beforeend', `<div id="nar-sec"></div><div id="nar-ttl">${esc(document.title)}</div><div id="nar-cap"><span></span></div>`);
    $('#nar-theme').onclick = () => { const n = Object.keys(T.themes || {}); setTheme(n[(n.indexOf(theme) + 1) % n.length]); };
    setTheme(T.themes?.[q.get('theme')] ? q.get('theme') : T.theme, !q.get('theme'));
    $('#nar-play').onclick = () => (started() ? toggle() : begin());
    $('#nar-auto').onclick = () => { auto = !auto; $('#nar-auto').setAttribute('aria-pressed', auto); };
    $('#nar-capt').onclick = () => $('#nar-capt').setAttribute('aria-pressed', body.classList.toggle('nar-captions'));
    $('#nar-olb').onclick = () => setOutline();
    // muted, the sentence still plays, so the talk keeps its timing
    $('#nar-voice').onclick = () => { audio.muted = !audio.muted; $('#nar-voice').setAttribute('aria-pressed', !audio.muted); };
    $('#nar-hide').onclick = () => { body.classList.toggle('nar-hidden'); wake(); };
    $('#nar-helpb').onclick = $('#nar-help').onclick = () => body.classList.toggle('nar-help');
    $('#nar-start').onclick = begin;
    const segs = $('#nar-segs');
    segs.onclick = seek; segs.onmousemove = tip; segs.onmouseleave = () => { $('#nar-tip').style.display = 'none'; };
    $('#nar-out').onclick = e => {
      const l = e.target.closest('.o-line');
      if (e.target.id === 'nar-oclose') return setOutline(false);
      if (!l) return;
      if (l.dataset.g) { const b = l.nextElementSibling; opened.has(b) ? opened.delete(b) : opened.add(b); return syncOutline(); }
      if (!started()) $('#nar-start').style.display = 'none';
      go(+l.dataset.j, +(l.dataset.n || 0), true);
    };
    $('#nar-out').addEventListener('beforematch', e => opened.add(e.target), true);  // Ctrl+F opened a closed part
    // the player's own surfaces: no text selection, no focus (space must not also "click" a focused button)
    for (const id of ['#nar-bar', '#nar-out', '#nar-help']) $(id).addEventListener('mousedown', e => e.preventDefault());
    addEventListener('mousemove', wake);
    addEventListener('resize', () => { layout(); syncOutline(); });
  }
  // a theme is only values: set them on the page's root, and everything that names them follows
  function setTheme(name, keep) {  // keep: the page was built in this theme, nothing to set
    const th = (T.themes || {})[name];
    $('#nar-theme').style.display = th ? '' : 'none';
    if (!th) return;
    theme = name; $('#nar-theme span').textContent = name; body.dataset.theme = name;
    if (!keep) for (const [k, v] of Object.entries(th)) document.documentElement.style.setProperty('--' + k, v);
  }
  function setOutline(v = !body.classList.contains('nar-outline')) {
    body.classList.toggle('nar-outline', v); $('#nar-olb').setAttribute('aria-pressed', v); syncOutline();
  }
  // the bar shows on mouse move and on keys, and fades after 2.5 s while playing, unless the pointer is on it
  function wake() { body.classList.remove('nar-idle'); clearTimeout(idleT); idleT = setTimeout(sleep, 2500); }
  function sleep() { if ((playing || body.classList.contains('nar-hidden')) && !$('#nar-bar').matches(':hover') && !$('#nar-out').matches(':hover')) body.classList.add('nar-idle'); }
  const started = () => $('#nar-start').style.display === 'none';
  function begin() { $('#nar-start').style.display = 'none'; go(h, k, true); }

  function keys() {
    const bind = (code, key, description, fn) => deck.addKeyBinding({keyCode: code, key, description}, () => { const idle = body.classList.contains('nar-idle'); wake(); fn(idle); });
    bind(39, '→', 'next slide', () => go(h + 1, 0)); bind(34, 'PgDn', 'next slide', () => go(h + 1, 0));
    bind(37, '←', 'previous slide', () => go(h - 1, 0)); bind(33, 'PgUp', 'previous slide', () => go(h - 1, 0));
    bind(40, '↓', 'next sentence', nextS); bind(38, '↑', 'previous sentence', prevS);
    bind(36, 'Home', 'first slide', () => go(0, 0)); bind(35, 'End', 'last slide', () => go(N - 1, 0));
    bind(32, 'Space', 'play / pause', () => (started() ? toggle() : begin()));
    bind(67, 'C', 'captions', () => $('#nar-capt').click());
    bind(84, 'T', 'outline of the talk', () => setOutline());
    // A takes over reveal's own auto-slide switch, which this talk has no use for; X is free in reveal and Quarto
    bind(65, 'A', 'auto-advance to the next slide on / off', () => $('#nar-auto').click());
    bind(77, 'M', 'voice on / off (the talk keeps its pace)', () => $('#nar-voice').click());
    // X acts on what is on screen: it hides a bar that shows, and brings back one that is hidden or has faded
    bind(89, 'Y', 'next theme', () => $('#nar-theme').click());
    bind(88, 'X', 'hide / show the bar', idle => body.classList.toggle('nar-hidden', !idle && !body.classList.contains('nar-hidden')));
    const help = () => body.classList.toggle('nar-help');
    bind(191, '?', 'keys and mouse of the talk (F1: this list)', help); bind(63, '?', 'keys and mouse of the talk (Firefox)', help);
    // no key acts with Ctrl, Alt or Meta held (copy, find, zoom, back stay the browser's), nor while a control has focus
    deck.configure({keyboardCondition: e => !(e.ctrlKey || e.altKey || e.metaKey) &&
      !document.activeElement?.matches('input, select, textarea, button, [contenteditable="true"]')});
    // Alt+click replays the sentence that introduced the element; a plain click stays for selecting text
    deck.getRevealElement().addEventListener('click', e => {
      if (!e.altKey || e.ctrlKey) return;
      const t = e.target.closest('[data-k]');
      if (!t || !slides[h].contains(t)) return;
      e.preventDefault(); e.stopPropagation();
      if (!started()) $('#nar-start').style.display = 'none';
      go(h, +t.dataset.k, true);
    }, true);
    // Ctrl+click is reveal's zoom on every platform (its default is Alt outside Linux); Alt+click replays a sentence,
    // so an Alt press must not reach the zoom plugin
    deck.configure({zoomKey: 'ctrl'});
    addEventListener('mousedown', e => { if (e.altKey && !e.ctrlKey) e.stopPropagation(); }, true);
    for (const ev of ['keydown', 'keyup', 'blur']) addEventListener(ev, e => body.classList.toggle('nar-alt', !!e.altKey));
    // reveal's own navigation (overview, touch, a hash typed by hand): follow it and narrate from there
    const follow = () => {
      const nh = slides.indexOf(deck.getCurrentSlide()), nk = (deck.getIndices().f ?? -1) + 1;
      if (nh >= 0 && (nh !== h || nk !== k)) go(nh, nk);
    };
    deck.on('slidechanged', follow); deck.on('fragmentshown', follow); deck.on('fragmenthidden', follow);
    addEventListener('hashchange', () => { const [a, b] = location.hash.slice(1).split('.').map(Number); if (a) go(a - 1, (b || 1) - 1); });
  }

  return {
    id: 'narrate',
    init(d) {
      deck = d; T = {lead: 0.7, gap: 0.4, tail: 1.0, pre: 0.2, say: [], ...window.TALK};
      const hash = location.hash;  // #n.k is ours: hide it from reveal, which would read #3 as its own slide index
      history.replaceState(null, '', location.pathname + location.search);
      slides = deck.getSlides().filter(sl => !sl.querySelector('section')); N = slides.length;  // not the stacks a # heading makes
      slides.forEach(sl => {  // the title slide's narration; a slide without narration is one silent step
        const add = t => sl.insertAdjacentHTML('beforeend', `<div class="say">${esc(t)}</div>`);
        if (!sl.querySelector('.say')) (sl.dataset.say || '').split('|').forEach(t => add(t.trim()));
      });
      slides.forEach(prepare);
      const norm = t => t.replace(/[^\p{L}\p{N}]/gu, '').toLowerCase();  // letters and digits: what narrate.py compares too
      let n = 0, stale = 0;  // the manifest lists the spoken sentences in document order: lay each slide's clock out from them
      T.scenes = slides.map((_, j) => {
        let t = T.lead;
        const say = says(j).map(e => {
          const a = words(e.textContent) ? T.say[n++] || {dur: 2} : {dur: +(e.dataset.wait || 3)};
          if (a.t !== undefined && a.t !== norm(e.textContent)) stale++;
          const o = {...a, t0: t}; t += a.dur + T.gap; return o;
        });
        return {say, T: t - T.gap + T.tail};
      });
      body.dataset.steps = T.scenes.reduce((a, sc) => a + sc.say.length, 0);
      if (n !== T.say.length || stale) body.dataset.error = `Narration out of date: the slides have ${n} spoken sentences, the audio ${T.say.length}` +
        `${stale ? `, and ${stale} differ in wording` : ''}. Run narrate.py again.`;
      D = T.scenes.map(s => s.T); S0 = D.map((_, j) => D.slice(0, j).reduce((a, b) => a + b, 0)); TOTAL = S0[N - 1] + D[N - 1];
      groups = [];
      let cur = '';  // a slide's section: its sec="..." attribute, else the last section heading (#) before it
      SEC = slides.map(s => { if (s.matches('.level1')) cur = heading(s.querySelector('h1')) || cur; return s.dataset.sec || cur; });
      secOf = slides.map((s, j) => {
        const name = SEC[j] || 'Start';
        if (groups.at(-1)?.name !== name) groups.push({name, js: []});
        groups.at(-1).js.push(slides.indexOf(s));
        return groups.length - 1;
      });
      groups.forEach(g => { g.t = S0[g.js[0]]; g.T = g.js.reduce((a, j) => a + D[j], 0); });
      // reveal turns a window below 435 px into a scrolling page, which the narration cannot follow: keep the deck
      deck.configure({respondToHashChanges: false, hash: false, history: false, scrollActivationWidth: null, ...(SHOT ? {transition: 'none'} : {})});
      body.classList.toggle('nar-shot', SHOT || RECV); body.classList.toggle('nar-fast', FAST);
      chrome(); keys(); outline();
      audio.ontimeupdate = () => { body.dataset.audio = `${h + 1}.${k + 1}@${audio.currentTime.toFixed(1)}`; };
      deck.on('ready', () => {
        deck.sync(); deck.layout();
        const [a, b] = hash.slice(1).split('.').map(Number);
        h = Math.min(N - 1, Math.max(0, (a || 1) - 1));
        k = SHOT && !b ? 99 : (b || 1) - 1;
        if (FAST) { $('#nar-start').style.display = 'none'; go(h, k, true); } else go(h, k, false);
        if (q.has('autostart')) begin();
        tick();
      });
    },
  };
};
