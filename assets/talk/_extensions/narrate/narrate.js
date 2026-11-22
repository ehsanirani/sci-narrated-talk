/* reveal.js plugin of the sci-narrated-talk skill: a talk that tells itself.
 *
 * The narration of a slide is its `.say` blocks, one per sentence, in document order. Whatever follows the n-th block
 * (n >= 2) becomes a reveal fragment, so reveal's own machinery shows it when sentence n starts; every sentence is itself
 * a hidden fragment, so reveal's position (slide, fragment f) is always "sentence f + 1 of that slide".
 * A block without text is a silent step of wait= seconds (default 3); a slide without blocks is one silent step.
 * Attributes of a block: point="#a; #b@a phrase" (a pointer on #a for the sentence, on #b from that phrase on: a ring on
 * a point of a figure, a box around anything else), grow="#id" with="#dots" (that SVG line is drawn while the sentence
 * is spoken, and markers appear as it passes), label="..." (the outline's name for a silent step), wait="2".
 * Attributes of any other block: at="2" (appears with sentence 2 whatever its place in the source; a .note is there from
 * the start). Of a clip: data-clock="sentence" (starts with the sentence that reveals it), data-once, data-loop.
 * The title slide takes its narration from title-slide-attributes: data-say: "First sentence.|Second sentence."
 *
 * Audio: window.TALK (media/manifest.js, written by narrate.py) lists the spoken sentences in document order (src, dur)
 * and the pauses lead, gap, tail; pre is the beat by which a reveal precedes its sentence. Without a manifest, every
 * sentence lasts its words at 155 a minute and the talk runs silently. A sentence whose file does not load (a page
 * opened without its media/audio/) turns the talk silent from there on: each sentence then runs on its time, as a silent
 * step does, so the reveals, pointers, growing lines and clips keep the talk's pace. atime() is the one clock for all.
 *
 * Player: a bar over the bottom of the slide (fades when the mouse rests while playing or presented by hand) with a timeline (one segment per
 * slide, as wide as the slide is long; one per section when slides would be < 10 px; none on a phone), and an outline.
 * Keys: P play / pause; space, Enter, down, PageDown the next step (a sentence; after the last, the next slide);
 * Backspace, Shift+space, up, PageUp the step before; <- -> slide; C captions, T outline, M voice on/off, A auto-advance,
 * Y next theme, X hide the bar, # slide number, "," settings, ? help. Before the start a click or P plays, and the first
 * step key only lifts the start screen. A step taken without playing shows complete (line drawn, every pointer, clips
 * running): that is how one presents the talk oneself, with space or a clicker (PageDown, PageUp).
 * Nothing acts with Ctrl/Alt/Meta or in a text field, and space and Enter on a focused control are the control's. The
 * keys are handled before reveal.js and not entered in its table, so R and then a key gives that key to reveal.js and
 * its plugins (R ?: its list of keys, R M: its menu). window.TALK.keys renames (a key or a list) or frees (false) them.
 * Each button prints its key.
 * Settings (the gear, ","): theme, voice, captions, auto-advance, timeline, slide number, in a <dialog> that takes every
 * key while open. What the viewer changes is remembered per page in localStorage, never under ?rec ?shot ?fast nor in
 * the speaker view; the address beats what is remembered, which beats the talk's own.
 * Alt+click on an element replays the sentence that introduced it (data-k); Ctrl+click is reveal's zoom.
 * URL: #n.k = slide n, sentence k (1-based). ?fast: no audio, 50x speed; body[data-log] lists the visited positions,
 * body[data-over] what reaches outside its slide, body[data-done] the end. ?shot: no player, no transitions; #n alone
 * shows the slide's last sentence (for screenshots). Settings: ?theme=NAME, ?voice= ?cc= ?auto= ?num=on|off,
 * ?tl=auto|slides|sections|none (the timeline's mode).
 * ?rec: no player and nothing moving by itself; window.narrate.timeline() and .seek(t) give the talk as a function of
 * time, from which record.py makes a video.
 * Themes: window.TALK.themes maps a name to the values of the theme's CSS variables (--bg, --ink, ..., --font), which
 * are all the slides' styles and the figures refer to; Y, the bar's button or the settings go to another.
 * In reveal's speaker view (S) the two previews follow the main window silently; the notes are the narration.
 */
window.RevealNarrate = () => {
  let deck, T, N, slides, h = 0, k = 0, playing = false, auto = true, phase = 'idle', tok = 0, timer = null;
  let D, S0, TOTAL, groups, secOf, SEC, items = [], built = -1, idleT, theme, cues = [], raw = 0, rawT, DEF;
  const VERSION = '0.4.0', ARC = new WeakMap(), WPM = 155;  // narrate.py's words per minute: a sentence without audio
  let numFmt = 'c/t';
  const opened = new Set();  // outline parts the viewer opened by hand (or that the browser's find opened)
  const q = new URLSearchParams(location.search), FAST = q.has('fast'), REC = q.has('rec'), SHOT = q.has('shot') || REC;
  const RECV = q.has('receiver');  // one of the two previews in reveal's speaker view (S): follows the main window, silent
  let tl = 'auto';  // the timeline's mode: auto, slides, sections, none
  // where settings are remembered: per page; nowhere for a recording, a check run, a screenshot or the speaker view
  const STORE = !(FAST || SHOT || RECV) && 'narrate:' + location.pathname;
  const audio = new Audio(), body = document.body, $ = s => document.querySelector(s);
  let lost = false;  // the voice is not there (no manifest, or a file that did not load): the talk runs silently
  const voiced = s => s.src && !FAST && !lost;
  // a step taken without playing (the talk presented by hand): it shows complete, its line drawn, every pointer of it on
  // and its clips running, since no voice will bring them
  let hand = false;
  const byHand = () => hand && !playing && !SHOT && !FAST && !RECV;
  // Seconds into the current sentence, which the timeline, the clock, phrased pointers, growing lines and clips follow:
  // the voice's time, or the clock's for a sentence that runs without its voice (a silent step, the voice lost), which
  // started at vt0 or stands at vt while paused. Under ?rec vt is set from outside (window.narrate.seek), not played.
  let vt = 0, vt0 = 0;
  const atime = () => {
    if (REC) return vt;
    if (FAST) return 0;
    const s = T.scenes[h].say[k];
    return voiced(s) ? audio.currentTime : vt0 ? Math.min(s.dur, (performance.now() - vt0) / 1000) : vt;
  };
  const f = () => (FAST ? 0.02 : 1);  // time scale of the pauses
  const says = j => [...slides[j].querySelectorAll('.say')];
  const fmt = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
  const esc = s => String(s).replace(/[&<>"]/g, c => `&#${c.charCodeAt(0)};`);
  const words = s => s.trim().replace(/\s+/g, ' ');
  const short = s => { const w = s.split(' '); return w.length > 11 ? w.slice(0, 10).join(' ') + ' …' : s; };
  const heading = e => e ? words([...e.childNodes].filter(n => !n.matches?.('.part, .eyebrow')).map(n => n.textContent).join('')) : '';
  // the talk's keys: action -> keys (lower case, or the key's name); the manifest's keys: override them. Space steps,
  // as a clicker's PageDown does, so that the talk can be presented by hand; P plays.
  const KEYS = {play: 'p', next: 'ArrowRight', prev: 'ArrowLeft', down: [' ', 'Enter', 'ArrowDown', 'PageDown'],
                up: ['Backspace', 'ArrowUp', 'PageUp'], first: 'Home', last: 'End', captions: 'c', outline: 't', voice: 'm',
                auto: 'a', theme: 'y', hide: 'x', help: '?', number: '#', settings: ',', reveal: 'r'};
  const HELP = [['play', 'play / pause'], ['down', 'next step: the next sentence, after the last one the next slide'],
                ['up', 'previous step (Shift+space too)'], ['prev next', 'previous / next slide'], ['first last', 'first / last slide'],
                ['captions', 'captions'], ['outline', 'outline'], ['voice', 'voice on / off; the talk keeps its pace'],
                ['theme', 'next theme (colours and font)'], ['auto', 'auto-advance to the next slide on / off'],
                ['hide', 'hide / show the bar'], ['number', 'slide number on / off'],
                ['settings', 'settings: theme, voice, captions, auto-advance, timeline, slide number; a link with them'],
                ['help', 'this help']];
  const NAME = {' ': 'space', ArrowRight: '→', ArrowLeft: '←', ArrowDown: '↓', ArrowUp: '↑', PageDown: 'PgDn', PageUp: 'PgUp'};
  const key1 = x => (x = String(x), /^space$/i.test(x) ? ' ' : x.length === 1 ? x.toLowerCase() : x);  // as e.key gives it
  const keyName = x => NAME[x] || (x.length === 1 ? x.toUpperCase() : x);
  const kbd = (a, all) => KEYS[a].slice(0, all ? 9 : 1).map(x => `<kbd>${keyName(x)}</kbd>`).join(' ');  // a button: its first key
  const titleOf = j => heading(slides[j].querySelector('h1, h2')) || SEC[j] || document.title;

  // ------------------------------------------------------------ sentences -> reveal fragments
  function prepare(sec) {
    const ss = [...sec.querySelectorAll('.say')];
    ss.forEach((s, j) => { if (j) { s.classList.add('fragment'); s.dataset.fragmentIndex = j - 1; } });
    let cur = 0;
    sec.dataset.k = 0;
    sec.querySelectorAll('video').forEach(v => Object.assign(v, {muted: true, controls: false, playsInline: true}));
    (function visit(el) {
      for (const c of [...el.children]) {
        if (c.classList.contains('say')) { cur = ss.indexOf(c); continue; }
        if (c.querySelector('.say')) { visit(c); continue; }
        // at="2" pins a block to sentence 2 whatever its place in the source; a note is there from the start
        const kk = c.dataset.at ? Math.min(ss.length, +c.dataset.at) - 1 : c.matches('.note') ? 0 : cur;
        if (!c.classList.contains('fragment') && kk > 0) { c.classList.add('fragment'); c.dataset.fragmentIndex = kk - 1; }
        if (c.dataset.k === undefined)
          c.dataset.k = c.classList.contains('fragment') && !c.classList.contains('fade-out') ? +c.dataset.fragmentIndex + 1 : kk;
      }
    })(sec);
    if (!sec.querySelector('aside.notes'))  // reveal's speaker view (S) shows the slide's narration as its notes
      sec.insertAdjacentHTML('beforeend', `<aside class="notes">${ss.map(s => `<p>${esc(words(s.textContent))}</p>`).join('')}</aside>`);
  }

  // ------------------------------------------------------------ what the page shows
  function render() {
    const s = says(h)[k], sec = slides[h];
    $('#nar-cap span').textContent = s ? s.textContent.trim() : '';
    fit(sec);
    $('#nar-sec').textContent = SEC[h];  // the slide's frame: section, "n / N", progress
    $('#nar-prog b').style.width = (h + 1) / N * 100 + '%';
    $('#nar-num').textContent = `${h + 1} / ${N}`;
    if (built !== h) layout();
    syncOutline();
    history.replaceState(null, '', `${location.pathname}${location.search}#${h + 1}.${k + 1}`);
    body.dataset.log = (body.dataset.log || '') + `${h + 1}.${k + 1} `;
    for (const e of sec.querySelectorAll('[data-until], [data-dim]')) {  // figure parts that leave or dim (gid sA-B-, sA-dB-)
      e.classList.toggle('nar-gone', e.dataset.until !== undefined && k >= +e.dataset.until);
      e.classList.toggle('nar-dim', e.dataset.dim !== undefined && k >= +e.dataset.dim);
    }
    // point="#a; #b@a phrase": #a for the whole sentence, #b from where the phrase stands in it until the next phrased one
    document.querySelectorAll('.nar-ptr').forEach(e => e.remove());
    cues = [];
    const said = s ? words(s.textContent).toLowerCase() : '';
    for (const part of (s?.dataset.point || '').split(';').map(x => x.trim()).filter(Boolean)) {
      const [sel, phrase] = part.split('@').map(x => x.trim());
      const from = phrase ? Math.max(0, said.indexOf(phrase.toLowerCase())) / Math.max(1, said.length) : -1;
      for (const t of sec.querySelectorAll(sel)) cues.push({from, el: pointer(sec, t)});
    }
    cue();
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
  // A sketched pointer on one target: a ring on a point of a figure (a small, roughly square part, such as the mark
  // that narrate.mark() draws), a box around anything else. Sizes are the video engine's, in the slide's own units.
  function pointer(sec, t) {
    const r = t.getBoundingClientRect(), b = sec.getBoundingClientRect(), sc = deck.getScale(), p = document.createElement('div');
    const H = deck.getConfig().height, pad = H / 80, w = r.width / sc, hh = r.height / sc;
    const ring = t.closest('svg') && Math.max(w, hh) < H * 0.25 && Math.min(w, hh) / Math.max(w, hh, 1e-9) > 0.6;
    const R = Math.max(H * 0.024, Math.max(w, hh) / 2), cx = (r.left - b.left) / sc + w / 2, cy = (r.top - b.top) / sc + hh / 2;
    p.className = 'nar-ptr' + (ring ? ' ring' : '');
    Object.assign(p.style, ring ? {left: cx - R + 'px', top: cy - R + 'px', width: 2 * R + 'px', height: 2 * R + 'px', borderWidth: pad * 0.46 + 'px'}
      : {left: cx - w / 2 - pad + 'px', top: cy - hh / 2 - pad + 'px', width: w + 2 * pad + 'px', height: hh + 2 * pad + 'px',
         borderWidth: pad * 0.41 + 'px', borderRadius: pad + 'px'});
    sec.appendChild(p);
    return p;
  }
  function cue() {  // which phrased pointers show now: the one whose phrase the voice has reached last
    if (!cues.length) return;
    const s = T.scenes[h].say[k];
    const x = phase === 'say' && !FAST ? atime() / s.dur : phase === 'idle' && (REC || !SHOT) && !FAST ? 0 : 1;
    const on = Math.max(-1, ...cues.filter(c => c.from >= 0 && c.from <= x).map(c => c.from)), all = byHand();
    for (const c of cues) c.el.classList.toggle('off', !all && c.from >= 0 && c.from !== on);
  }
  // The slide's clips. A clip runs on the slide's clock, as a scene of a video does (data-clock="sentence": on the clock
  // of the sentence that reveals it, starting at 0 with it). It is set to its time again at every sentence, because the
  // voice and the clock part by a little with each one. It loops unless it is about as long as what it accompanies
  // (data-once / data-loop decide otherwise); a clip that plays once holds its last frame.
  function clipAt(v, j, now) {  // the clip v of slide j, at second now of that slide
    const say = T.scenes[j].say, k0 = +(v.closest('[data-k]')?.dataset.k || 0), own = v.dataset.clock === 'sentence';
    const base = own && k0 ? say[Math.min(k0, say.length - 1)].t0 - T.pre : 0, len = v.duration || 1e9;
    const once = 'once' in v.dataset || (!('loop' in v.dataset) && len >= D[j] - base - 1.5);
    return {once, len, k0: own ? k0 : 0, at: once ? Math.min(Math.max(0, now - base), len - 0.04) : Math.max(0, now - base) % len};
  }
  function media(seek) {
    if (REC) return;  // a recording takes the clips' frames from their files (record.clips)
    const say = T.scenes[h].say;
    const now = SHOT ? say[k].t0 + say[k].dur : phase === 'say' && !FAST ? say[k].t0 + atime() : k ? say[k].t0 - T.pre : 0;
    slides[h].querySelectorAll('video').forEach(v => {
      const go = () => {
        const c = clipAt(v, h, now);
        v.loop = !c.once;
        if (seek && Math.abs(v.currentTime - c.at) > 0.06) v.currentTime = c.at;
        (playing || byHand()) && k >= c.k0 && !(c.once && c.at >= c.len - 0.05) ? v.play().catch(() => {}) : v.pause();
      };
      v.readyState ? go() : v.addEventListener('loadedmetadata', go, {once: true});
    });
  }
  // where along the path p an element sits, 0 to 1; markers are matched in order, so a path that crosses itself is fine
  function along(p, els) {
    const L = p.getTotalLength(), m = p.getScreenCTM(), n = 600, pts = [];
    for (let i = 0; i <= n; i++) { const q = p.getPointAtLength(L * i / n); pts.push([q.x * m.a + q.y * m.c + m.e, q.x * m.b + q.y * m.d + m.f]); }
    let from = 0;
    for (const el of els) {
      const r = el.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      let best = from, bd = Infinity;
      for (let i = from; i <= n; i++) { const d = (pts[i][0] - cx) ** 2 + (pts[i][1] - cy) ** 2; if (d < bd - 0.5) { bd = d; best = i; } }
      ARC.set(el, best / n); from = best;
    }
  }
  function ui() {
    $('#nar-play').textContent = playing ? '❚❚' : '▶';
    $('#nar-play').title = (playing ? 'pause' : 'play') + (KEYS.play[0] ? ` (${keyName(KEYS.play[0])})` : '');
    body.classList.toggle('nar-playing', playing);
    wake();
  }

  // ------------------------------------------------------------ the clock
  function place(nh, nk) {  // move reveal to slide nh, sentence nk, without our listener reacting
    h = nh; k = nk; vt = vt0 = 0;
    const ix = deck.getIndices(slides[h]);  // a section heading (#) may stack its slides vertically
    deck.slide(ix.h, ix.v, k - 1);
    render();
  }
  function halt() { tok++; clearTimeout(timer); audio.pause(); phase = 'idle'; }
  function go(nh, nk, play = playing) {
    if (nh < 0 || nh >= N) return;
    if (RECV) play = false;
    hand = !play;
    halt();
    place(nh, Math.max(0, Math.min(nk, says(nh).length - 1)));
    playing = play; media(true); ui();
    if (play) wait(k ? T.pre : T.lead, speak);
  }
  function wait(sec, then) { const my = tok; timer = setTimeout(() => my === tok && then(my), sec * 1000 * f()); }
  function speak() {  // the sentence from where it stands (a sentence without its voice may have been paused halfway)
    const s = T.scenes[h].say[k], my = tok;
    phase = 'say';
    if (!voiced(s)) { vt0 = performance.now() - vt * 1000; return wait(s.dur - vt, done); }  // only takes its time
    audio.src = s.src;
    audio.onended = () => my === tok && done();
    audio.onplaying = () => my === tok && media(true);  // the voice has started: put the clips on its time
    audio.onerror = () => my === tok && lose();
    // a browser that wants a click first refuses (NotAllowedError): stop until there is one. AbortError: we moved on
    audio.play().catch(e => my === tok && (e.name === 'NotAllowedError' ? (playing = false, ui()) : e.name !== 'AbortError' && lose()));
  }
  // The file did not load (a page opened without its media/audio/): this sentence and all after it run silently, each
  // on its time, and no file is asked for again
  function lose() {
    if (lost) return;
    silent('audio not found — running silently');
    if (playing && phase === 'say') speak();
  }
  function silent(why) {  // the voice cannot be switched on; the bar says why (and so does the start screen, if up)
    lost = true;
    const b = $('#nar-voice');
    b.disabled = true; b.setAttribute('aria-pressed', false); b.title = why;
    $('#nar-note').textContent = why;
    if (!$('#nar-start small').textContent) $('#nar-start small').textContent = why;
    sync(); wake();
  }
  function done() {
    phase = 'after';
    // the next step waits for its sentence (idle): not 'after', which would end it at once on a pause and resume, and
    // show its line drawn and its clock at its end until the sentence starts
    if (k < says(h).length - 1) wait(T.gap - T.pre, () => { phase = 'idle'; place(h, k + 1); media(true); wait(T.pre, speak); });
    else if (auto && h < N - 1) wait(T.tail, () => { phase = 'idle'; place(h + 1, 0); media(true); wait(T.lead, speak); });
    else { playing = false; phase = 'end'; ui(); if (h === N - 1) body.dataset.done = 1; }
  }
  function toggle() {
    if (RECV) return;
    if (playing) {
      if (vt0) { vt = atime(); vt0 = 0; }  // a sentence without its voice holds where it is
      playing = false; tok++; clearTimeout(timer); audio.pause(); media(false); return ui();
    }
    playing = true; hand = false; ui(); media(false);
    const my = ++tok, s = T.scenes[h].say[k];
    if (phase === 'say' && voiced(s) && audio.currentTime > 0 && !audio.ended) {
      audio.onended = () => my === tok && done(); audio.play();
    } else if (phase === 'say' && !voiced(s)) speak();  // on from where it was paused
    else if (phase === 'after') done();
    else wait(k ? T.pre : T.lead, speak);
  }
  const nextS = () => (k < says(h).length - 1 ? go(h, k + 1) : go(h + 1, 0));
  const prevS = () => (k > 0 ? go(h, k - 1) : h > 0 && go(h - 1, 99));
  function local() {  // seconds since the start of the current slide (steps through the pauses, smooth while speaking)
    const s = T.scenes[h].say[k];
    if (phase === 'say') return s.t0 + atime();
    if (phase === 'after' || phase === 'end') return s.t0 + s.dur;
    return k ? s.t0 - T.pre : 0;
  }

  function tick() {  // every frame: the timeline's fill and the clock; growing paths (a sentence's grow=)
    const c = $('#nar-segs i.cur b'), t = local();
    if (c) c.style.width = Math.min(100, t / D[h] * 100) + '%';
    $('#nar-time').textContent = `${fmt(S0[h] + t)} / ${fmt(TOTAL)}`;
    cue(); grow();
    requestAnimationFrame(tick);
  }
  function grow() {
    says(h).forEach((s, j) => {  // grow="#id": the line is drawn while the sentence is spoken, and the markers on it
      const g = s.dataset.grow && slides[h].querySelector(s.dataset.grow);  // (its own, and those of with="#id") appear as it passes
      const p = g && (g.matches('path') ? g : g.querySelector('path'));
      if (!p) return;
      const L = p.getTotalLength();
      const x = (SHOT && !REC) || FAST || k > j ? 1 : k < j ? 0 : phase === 'say' ? Math.min(1, atime() / T.scenes[h].say[j].dur) : phase === 'after' || byHand() ? 1 : 0;
      p.style.strokeDasharray = L;
      p.style.strokeDashoffset = L * (1 - x);
      const marks = [...g.querySelectorAll('use'), ...(s.dataset.with ? slides[h].querySelectorAll(`${s.dataset.with} use`) : [])];
      if (marks.length && !ARC.has(marks[0]) && g.getBoundingClientRect().width) along(p, marks);
      for (const e of marks) e.style.visibility = x >= (ARC.get(e) ?? 0) ? '' : 'hidden';
    });
  }
  // ?rec, for record.py: the talk as a function of time. timeline() lists every step with its start in the talk's
  // running time. seek(t) puts the page at second t (slide, sentence, fades, pointers, growing lines) and returns
  // sig, a signature of what is on screen, so that equal frames are photographed once, and clips. The browser never
  // draws a clip's frame: clips lists every clip that shows, with the box its picture takes in the window and the
  // time it is at, and record.py puts the frame of the clip's file there.
  // The fades: every step is entered from the step before it with the page's own transitions and animations switched
  // on for that instant (nar-fx). What they start (a fragment or a slide fading, a pointer closing in) is copied,
  // keyframes and timing, into animations that do not run; each is then set to the time since its start. So a frame
  // shows what the page shows that long after the step began, whatever was recorded before it.
  const record = {
    fx: [],
    timeline: () => ({total: TOTAL, title: document.title, themes: Object.keys(T.themes || {}), steps: T.scenes.flatMap((sc, j) => sc.say.map((s, n) => (
      {slide: j + 1, sentence: n + 1, slideStart: S0[j], start: S0[j] + s.t0, dur: s.dur, src: s.src || null,
       text: words(says(j)[n].textContent), section: SEC[j], heading: titleOf(j)})))}),
    seek(t) {
      t = Math.max(0, Math.min(TOTAL - 0.001, t));
      const nh = S0.findLastIndex(x => x <= t), loc = t - S0[nh], say = T.scenes[nh].say;
      const nk = say.reduce((a, s, j) => (j && loc >= s.t0 - T.pre ? j : a), 0), s = say[nk], began = nk ? s.t0 - T.pre : 0;
      if (nh !== h || nk !== k || !record.on) {
        record.on = true; halt();
        record.fx.forEach(a => a.cancel());
        const [ph, pk] = nk ? [nh, nk - 1] : nh ? [nh - 1, says(nh - 1).length - 1] : [0, 0];  // the step before
        place(ph, pk);
        phase = 'after'; grow();  // as that step ended: its line drawn
        fit(slides[nh]);
        void body.offsetHeight;  // the styles the transitions start from
        body.classList.add('nar-fx');
        place(nh, nk);
        cues.forEach(c => c.el.classList.remove('off'));  // a pointer that waits for its phrase closes in when it comes
        record.fx = document.getAnimations().map(a => {
          const e = a.effect, c = new Animation(new KeyframeEffect(e.target, e.getKeyframes(), {...e.getTiming(), pseudoElement: e.pseudoElement}));
          const from = cues.find(q => q.el === e.target)?.from;
          c.narAt = from > 0 ? s.t0 + from * s.dur : began;
          c.pause();
          return c;
        });
        body.classList.remove('nar-fx');
      }
      const live = record.fx.filter(a => { a.currentTime = (loc - a.narAt) * 1000; return a.currentTime >= 0 && a.currentTime < a.effect.getComputedTiming().endTime; });
      vt = Math.max(0, Math.min(s.dur, loc - s.t0));
      phase = loc < s.t0 ? 'idle' : loc <= s.t0 + s.dur ? 'say' : 'after';
      cue(); grow();
      const moving = says(h).some((e, j) => e.dataset.grow && j === k && phase === 'say');
      return {clips: record.clips(loc), sig: [h, k, cues.map(c => +c.el.classList.contains('off')).join(''),
        moving ? vt.toFixed(3) : phase === 'idle' ? 'i' : '', [...new Set(live.map(a => Math.round(a.currentTime)))].join(',')].join('|')};
    },
    // every clip that shows (also one of a slide that is fading out, held where that slide ended): its number among the
    // page's clips, its file, the box of its picture in the window (object-fit, centred) and its time
    clips: loc => [...document.querySelectorAll('.reveal .slides video')].flatMap((v, id) => {
      const j = slides.indexOf(v.closest('section'));
      if (j < 0 || !v.videoWidth || !v.checkVisibility({opacityProperty: true, visibilityProperty: true})) return [];
      const r = v.getBoundingClientRect(), z = r.width / v.offsetWidth, W = v.clientWidth * z, H = v.clientHeight * z;
      const a = W / v.videoWidth, b = H / v.videoHeight, fit = getComputedStyle(v).objectFit;
      const [sx, sy] = fit === 'fill' ? [a, b] : Array(2).fill(fit === 'cover' ? Math.max(a, b) : fit === 'none' ? z : Math.min(a, b, fit === 'scale-down' ? z : 1e9));
      const w = v.videoWidth * sx, hh = v.videoHeight * sy;
      return [{id, src: v.currentSrc, x: r.x + v.clientLeft * z + (W - w) / 2, y: r.y + v.clientTop * z + (H - hh) / 2, w, h: hh,
               t: clipAt(v, j, j === h ? loc : D[j]).at}];
    }),
  };

  // ------------------------------------------------------------ timeline
  function layout() {  // one segment per slide, or per section with the current one expanded, or none
    built = h;
    const W = $('#nar-tl').clientWidth || innerWidth;
    const mode = ['slides', 'sections', 'none'].includes(tl) ? tl : innerWidth < 520 ? 'none' : W / N < 10 ? 'sections' : 'slides';
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
    const TH = Object.entries(T.themes || {}), play = KEYS.play[0], step = KEYS.down[0];
    const box = (n, what) => `<label><input type="checkbox" name="${n}">${what}</label>`;
    document.body.insertAdjacentHTML('beforeend', `
<div id="nar-bar"><div id="nar-tl"><div id="nar-labs"></div><div id="nar-segs"></div><div id="nar-tip"></div></div>
<div class="row"><button id="nar-play" aria-label="play or pause">▶</button>${kbd('play')}<span id="nar-time"></span><span id="nar-num"></span><span id="nar-note"></span>
<span class="sp"></span><button id="nar-voice" title="voice: off, the talk runs on silently at the same pace" aria-pressed="true">voice${kbd('voice')}</button>
<button id="nar-theme" title="next theme"><span></span>${kbd('theme')}</button>
<button id="nar-capt" title="captions" aria-pressed="false">CC${kbd('captions')}</button>
<button id="nar-auto" title="auto-advance: go on to the next slide at the end of this one" aria-pressed="true">auto${kbd('auto')}</button>
<button id="nar-olb" title="outline" aria-label="outline" aria-pressed="false">☰${kbd('outline')}</button><button id="nar-gear" title="settings" aria-label="settings">⚙&#xFE0E;${kbd('settings')}</button><button id="nar-helpb" title="keys and mouse" aria-label="keys and mouse">?</button>
<button id="nar-hide" title="hide / show the bar" aria-label="hide or show the bar"><span></span>${kbd('hide')}</button></div></div>
<div id="nar-out"></div><div id="nar-raw"></div>
<div id="nar-help"><div class="box"><h3>Keys</h3><table>
${HELP.filter(([a]) => a.split(' ').some(x => KEYS[x].length)).map(([a, d]) => `<tr><td>${a.split(' ').map(x => kbd(x, 1)).join(' ')}</td><td>${d}</td></tr>`).join('')}
</table><p>${play && step ? `To present the talk yourself, step with ${kbd('down')} or a clicker and leave ${kbd('play')} alone: the voice
stays off. ` : ''}${KEYS.reveal.length ? `Every other key is reveal.js's own (F fullscreen, O overview, S speaker view, …). ${kbd('reveal')} and then a key gives
that key to reveal.js even where this talk uses it: ${kbd('reveal')} <kbd>?</kbd> shows reveal.js's own list of keys, ${kbd('reveal')} <kbd>M</kbd> its menu.` : ''}</p>
<p><button id="nar-rkeys">reveal.js keys</button> <button id="nar-rmenu">reveal.js menu</button></p>
<h3>Mouse</h3><table><tr><td>timeline</td><td>click a slide to jump to it; inside the current slide, to the sentence under the pointer</td></tr>
<tr><td>outline</td><td>click a line to play from there; click a section to open it</td></tr>
<tr><td>Alt+click</td><td>an element on the slide: replay the sentence that introduced it</td></tr>
<tr><td>Ctrl+click</td><td>zoom in (reveal.js); again to zoom out</td></tr><tr><td>click, drag</td><td>select text</td></tr></table>
<p>Keys with Ctrl, Alt or Meta are left to the browser. Click anywhere to close.</p></div></div>
<div id="nar-start"><div>▶&nbsp; Click${play ? ` or press ${keyName(play)}` : ''} to start${step ? `<span>or step through it yourself with ${keyName(step)}</span>` : ''}<small>${esc(body.dataset.error || '')}</small></div></div>
<dialog id="nar-set" aria-label="settings"><form method="dialog"><div class="s-top">Settings<button aria-label="close" title="close (Esc)">×</button></div>
${TH.length > 1 ? `<fieldset><legend>Theme ${kbd('theme')}</legend><div class="s-themes">${TH.map(([n, v]) => `<label><input type="radio" name="theme" value="${esc(n)}">
<b style="background:${esc(v.bg)};color:${esc(v.ink)};border-color:${esc(v.light)};font-family:${esc(v.font)}">Aa${['accent', 'blue', 'green', 'purple'].map(c =>
  `<i style="background:${esc(v[c])}"></i>`).join('')}</b>${esc(n)}</label>`).join('')}</div></fieldset>` : ''}
<fieldset><legend>Play</legend>${box('voice', `voice ${kbd('voice')}<em></em>`)}${box('cc', `captions ${kbd('captions')}`)}
${box('auto', `go on to the next slide by itself ${kbd('auto')}`)}${box('num', `slide number ${kbd('number')}`)}</fieldset>
<fieldset><legend>Timeline</legend><div class="s-row">${['auto', 'slides', 'sections', 'none'].map(v => `<label><input type="radio" name="tl" value="${v}">${v}</label>`).join('')}</div></fieldset>
<fieldset><legend>A link that opens the talk with these settings</legend><input id="nar-link" readonly aria-label="link"></fieldset>
<p>${STORE ? 'What you change here is remembered for this talk, in this browser. ' : ''}<button type="button" id="nar-reset">back to the talk's own settings</button></p>
</form></dialog>`);
    deck.getRevealElement().insertAdjacentHTML('beforeend', '<div id="nar-cap"><span></span></div>');
    // the frame of every slide, inside the slide's own box so that it scales and letterboxes with it
    deck.getSlidesElement().insertAdjacentHTML('beforeend', `<div id="nar-frame"><div id="nar-sec"></div>
<div id="nar-ttl">${esc(document.title)}</div><div id="nar-no"></div><div id="nar-prog"><b></b></div></div>`);
    // the slide number is reveal.js's own element, moved into the frame: its format (slide-number: c/t, c, h.v, ...) and
    // its on/off state are reveal's, and the number key toggles it
    deck.on('ready', () => { const sn = deck.getRevealElement().querySelector('.slide-number'); if (sn) $('#nar-no').append(sn); });
    $('#nar-rkeys').onclick = () => deck.toggleHelp?.();
    $('#nar-rmenu').onclick = () => menu()?.toggle?.();
    $('#nar-rmenu').style.display = menu() ? '' : 'none';
    $('#nar-theme').onclick = () => { const n = Object.keys(T.themes || {}); set('theme', n[(n.indexOf(theme) + 1) % n.length]); };
    $('#nar-play').onclick = () => (started() ? toggle() : begin());
    $('#nar-auto').onclick = () => set('auto', !auto);
    $('#nar-capt').onclick = () => set('cc', !body.classList.contains('nar-captions'));
    $('#nar-olb').onclick = () => setOutline();
    $('#nar-voice').onclick = () => set('voice', audio.muted);
    $('#nar-gear').onclick = settings;
    const dlg = $('#nar-set');
    // (blocks, not expressions: an on... handler that returns false cancels the event, and with it the checkbox's click)
    dlg.onchange = e => { if (e.target.name in OPT) set(e.target.name, e.target.type === 'checkbox' ? e.target.checked : e.target.value); };
    dlg.onclick = e => { if (e.target === dlg) dlg.close(); };  // a click outside the panel lands on the dialog's backdrop
    $('#nar-reset').onclick = () => { remember(null); for (const n in OPT) set(n, DEF[n], false); };
    $('#nar-link').onclick = $('#nar-link').onfocus = e => e.target.select();
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
      dismiss();
      go(+l.dataset.j, +(l.dataset.n || 0), true);
    };
    $('#nar-out').addEventListener('beforematch', e => opened.add(e.target), true);  // Ctrl+F opened a closed part
    // the player's own surfaces: no text selection, no focus (space must not also "click" a focused button)
    for (const id of ['#nar-bar', '#nar-out', '#nar-help']) $(id).addEventListener('mousedown', e => e.preventDefault());
    addEventListener('mousemove', wake);
    addEventListener('resize', () => { layout(); syncOutline(); });
  }
  // a theme is only values: set them on the page's root, and everything that names them follows
  function setTheme(name) {
    const th = (T.themes || {})[name];
    $('#nar-theme').style.display = th && Object.keys(T.themes).length > 1 ? '' : 'none';  // one theme: locked (narrate: switch: false)
    if (!th) return;
    if (theme || name !== T.theme) for (const [k, v] of Object.entries(th)) document.documentElement.style.setProperty('--' + k, v);
    theme = name; $('#nar-theme span').textContent = name; body.dataset.theme = name;  // (the page was built in T.theme)
  }

  // ------------------------------------------------------------ settings
  // By their names in the address (?theme=dark&cc=on): how each is applied. The bar's buttons, the keys and the panel
  // all go through set(), so that they agree, and what the viewer sets there is remembered.
  const OPT = {
    theme: setTheme,
    voice: v => { audio.muted = !v; $('#nar-voice').setAttribute('aria-pressed', v && !lost); },  // muted, the sentence still plays: the talk keeps its pace
    cc: v => $('#nar-capt').setAttribute('aria-pressed', body.classList.toggle('nar-captions', v)),
    auto: v => { auto = v; $('#nar-auto').setAttribute('aria-pressed', v); },
    tl: v => { tl = v; layout(); },
    num: v => { const c = deck.getConfig().slideNumber; if (c) numFmt = c; deck.configure({slideNumber: v && numFmt}); },
  };
  const cur = () => ({theme, voice: !audio.muted, cc: body.classList.contains('nar-captions'), auto, tl, num: !!deck.getConfig().slideNumber});
  const valid = (n, v) => (n === 'theme' ? !!T.themes?.[v] : n === 'tl' ? ['auto', 'slides', 'sections', 'none'].includes(v) : typeof v === 'boolean');
  // storage may be blocked (a private window, a browser's rule for file://): then nothing is remembered, and nothing fails
  const recall = () => { try { return (STORE && JSON.parse(localStorage.getItem(STORE))) || {}; } catch { return {}; } };
  const remember = o => { try { if (STORE) o ? localStorage.setItem(STORE, JSON.stringify(o)) : localStorage.removeItem(STORE); } catch { /* blocked */ } };
  function set(n, v, keep = true) {
    OPT[n](v);
    if (keep) remember({...recall(), [n]: v});
    sync();
  }
  function setup() {  // each setting from the address, else from what this browser remembers, else the talk's own
    DEF = {...cur(), theme: T.theme};
    const mem = recall(), url = n => (n === 'theme' || n === 'tl' ? q.get(n) : {on: true, off: false}[q.get(n)]);
    for (const n in OPT) {
      const v = [url(n), mem[n], DEF[n]].find(x => valid(n, x)) ?? DEF[n];
      if (n === 'theme' || v !== cur()[n]) OPT[n](v);
    }
    sync();
  }
  function sync() {  // the panel shows the settings as they are, and the link that opens the talk with them
    const c = cur(), p = new URLSearchParams(), d = $('#nar-set');
    for (const i of d.querySelectorAll('input[name]')) i.checked = i.type === 'checkbox' ? c[i.name] && !(i.name === 'voice' && lost) : i.value === c[i.name];
    d.querySelector('[name=voice]').disabled = lost;
    d.querySelector('[name=voice] ~ em').textContent = lost ? ` (${$('#nar-note').textContent})` : '';
    // every setting, not only those that differ from the talk's own: the address beats what the receiver's browser remembers
    for (const n in OPT) if (c[n] !== undefined) p.set(n, typeof c[n] === 'boolean' ? (c[n] ? 'on' : 'off') : c[n]);
    $('#nar-link').value = location.href.replace(/[?#].*/, '') + (String(p) ? '?' + p : '');
  }
  function settings() {  // open or close the panel
    const d = $('#nar-set');
    if (d.open) d.close(); else { sync(); d.showModal(); }
  }
  // Two things the video engine does that a style sheet cannot, on the slide that shows (only a theme that sets
  // --bullet-gap asks for them). Bullets: the engine steps less per line of a bullet than it draws the lines apart,
  // so the gap after a bullet shrinks with its number of lines. Title card: a title of more than two lines is set
  // smaller, and the byline sits at y = 0.33 of the frame or below the subtitle, whichever is lower.
  function fit(sec) {
    for (const li of sec.querySelectorAll('ul > li')) {  // --bullet-gap: 0 on a list or a block leaves its bullets alone
      const c = getComputedStyle(li), gap = parseFloat(c.getPropertyValue('--bullet-gap')), over = parseFloat(c.getPropertyValue('--bullet-overlap')) || 0;
      if (!gap) continue;
      const lines = Math.max(1, Math.round(li.clientHeight / parseFloat(c.lineHeight)));
      li.style.marginBottom = gap - over * parseFloat(c.fontSize) * lines + 'px';
    }
    if (!sec.matches('.title-card')) return;
    const t = sec.querySelector('h2'), by = sec.querySelector('.byline');
    if (t) t.classList.toggle('long', t.offsetHeight > 2.4 * parseFloat(getComputedStyle(t).lineHeight));
    if (by) { by.style.paddingTop = ''; by.style.paddingTop = Math.max(0, 716 * deck.getConfig().height / 1080 - by.offsetTop) + 'px'; }
  }
  const menu = () => (deck.hasPlugin?.('menu') ? deck.getPlugin('menu') : null);  // Quarto's reveal.js-menu, if it is on
  function setOutline(v = !body.classList.contains('nar-outline')) {
    body.classList.toggle('nar-outline', v); $('#nar-olb').setAttribute('aria-pressed', v); syncOutline();
  }
  // the bar shows on mouse move and on keys, and fades after 2.5 s while playing or presented by hand, unless the pointer is on it
  function wake() { body.classList.remove('nar-idle'); clearTimeout(idleT); idleT = setTimeout(sleep, 2500); }
  function sleep() { if ((playing || (byHand() && started()) || body.classList.contains('nar-hidden')) && !$('#nar-bar').matches(':hover') && !$('#nar-out').matches(':hover')) body.classList.add('nar-idle'); }
  const started = () => $('#nar-start').style.display === 'none';
  const dismiss = () => { $('#nar-start').style.display = 'none'; };
  function begin() { dismiss(); go(h, k, true); }

  // The talk's keys are handled here, before reveal.js sees them, and are not entered in reveal's own table: so the
  // keys of reveal.js and of its plugins stay as they are underneath, and the prefix key (R) hands the next key to them.
  // narrate: keys: in the front matter gives an action another key or a list of keys or, with false, frees it.
  function keys() {
    const step = act => () => { dismiss(); act(); };  // from the start screen too, without starting the voice
    const ACT = {
      play: () => (started() ? toggle() : begin()), next: step(() => go(h + 1, 0)), prev: step(() => go(h - 1, 0)),
      down: () => (started() ? nextS() : dismiss()), up: step(prevS),  // the first step only lifts the start screen first: step(() => go(0, 0)), last: step(() => go(N - 1, 0)),
      captions: () => $('#nar-capt').click(), outline: () => setOutline(),
      voice: () => $('#nar-voice').click(), auto: () => $('#nar-auto').click(), theme: () => $('#nar-theme').click(),
      // hide acts on what is on screen: it hides a bar that shows, and brings back one that is hidden or has faded
      hide: idle => body.classList.toggle('nar-hidden', !idle && !body.classList.contains('nar-hidden')),
      help: () => body.classList.toggle('nar-help'),
      number: () => set('num', !deck.getConfig().slideNumber), settings,
      reveal: () => { raw = 1; $('#nar-raw').textContent = 'reveal.js key …'; clearTimeout(rawT); rawT = setTimeout(unraw, 3000); },
    };
    const unraw = () => { raw = 0; $('#nar-raw').textContent = ''; };
    addEventListener('keydown', e => {
      const key = key1(e.key), plain = !(e.ctrlKey || e.altKey || e.metaKey);
      if ($('#nar-set').open) {  // the open panel has every key (Esc closes it, and must not reach reveal's overview)
        e.stopImmediatePropagation();
        if (plain && KEYS.settings.includes(key)) { e.preventDefault(); settings(); }
        return;
      }
      // no key acts with Ctrl, Alt or Meta held (copy, find, zoom, back stay the browser's), nor in a text field; space
      // and Enter on a focused control (a button reached with Tab) are the control's, and not reveal's next slide either
      if (!plain || e.target.closest?.('input, select, textarea, [contenteditable="true"]')) return;
      // (a link keeps Enter, not space: a link clicked in a slide keeps the focus, and the presenter's space must step)
      if (((key === ' ' || key === 'Enter') && e.target.closest?.('button, summary')) || (key === 'Enter' && e.target.closest?.('a[href]')))
        return e.stopImmediatePropagation();
      if (raw) return key === 'Shift' || key === 'CapsLock' || unraw();  // after the prefix: this key is reveal.js's (R ? takes Shift)
      if (menu()?.isOpen?.() || deck.isOverview()) return;      // their own keys while they show
      // Shift+space steps back, as in reveal.js and the browser, where space steps
      const act = key === ' ' && e.shiftKey && KEYS.down.includes(' ') ? 'up' : Object.keys(ACT).find(x => KEYS[x].includes(key));
      if (!act) return;
      e.preventDefault(); e.stopImmediatePropagation();
      const idle = body.classList.contains('nar-idle');
      wake(); ACT[act](idle);
    }, true);
    addEventListener('keypress', e => $('#nar-set').open && e.stopImmediatePropagation(), true);  // (reveal's ? there)
    // Alt+click replays the sentence that introduced the element; a plain click stays for selecting text
    deck.getRevealElement().addEventListener('click', e => {
      if (!e.altKey || e.ctrlKey) return;
      const t = e.target.closest('[data-k]');
      if (!t || !slides[h].contains(t)) return;
      e.preventDefault(); e.stopPropagation();
      dismiss();
      go(h, +t.dataset.k, true);
    }, true);
    // Ctrl+click is reveal's zoom on every platform (its default is Alt outside Linux); Alt+click replays a sentence,
    // so an Alt press must not reach the zoom plugin
    deck.configure({zoomKey: 'ctrl'});
    addEventListener('mousedown', e => { if (e.altKey && !e.ctrlKey) e.stopPropagation(); }, true);
    for (const ev of ['keydown', 'keyup', 'blur']) addEventListener(ev, e => body.classList.toggle('nar-alt', !!e.altKey));
    // reveal's own navigation (overview, touch, a hash typed by hand, the speaker view's keys): follow it and narrate
    // from there; it lifts the start screen, as a step key does
    const follow = () => {
      const nh = slides.indexOf(deck.getCurrentSlide()), nk = (deck.getIndices().f ?? -1) + 1;
      if (nh >= 0 && (nh !== h || nk !== k)) { dismiss(); go(nh, nk); }
    };
    deck.on('slidechanged', follow); deck.on('fragmentshown', follow); deck.on('fragmenthidden', follow);
    // (under ?shot a hash without a sentence means the slide's last one, as at start-up)
    addEventListener('hashchange', () => { const [a, b] = location.hash.slice(1).split('.').map(Number); if (a) go(a - 1, (b || (SHOT ? 100 : 1)) - 1); });
  }

  return {
    id: 'narrate',
    init(d) {
      deck = d; T = {lead: 0.7, gap: 0.4, tail: 1.0, pre: 0.2, say: [], ...window.TALK};
      for (const a in KEYS) KEYS[a] = [].concat(T.keys && a in T.keys ? T.keys[a] ?? [] : KEYS[a]).filter(x => x !== false).map(key1);
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
          const w = words(e.textContent), a = w ? T.say[n++] || {dur: Math.max(1, w.split(' ').length * 60 / WPM)} : {dur: +(e.dataset.wait || 3)};
          if (a.t !== undefined && a.t !== norm(e.textContent)) stale++;
          const o = {...a, t0: t}; t += a.dur + T.gap; return o;
        });
        return {say, T: t - T.gap + T.tail};
      });
      body.dataset.steps = T.scenes.reduce((a, sc) => a + sc.say.length, 0);
      if (T.version && T.version !== VERSION) console.warn(`narrate: the player is ${VERSION}, the build script ${T.version}; update the talk's copies of the skill together`);
      if (window.TALK && (n !== T.say.length || stale)) body.dataset.error = `Narration out of date: the slides have ${n} spoken sentences, the audio ${T.say.length}` +
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
      deck.configure({respondToHashChanges: false, hash: false, history: false, scrollActivationWidth: null, ...(SHOT && !REC ? {transition: 'none'} : {})});
      body.classList.toggle('nar-shot', SHOT || RECV); body.classList.toggle('nar-fast', FAST); body.classList.toggle('nar-rec', REC);
      chrome(); keys(); outline(); setup();
      if (!window.TALK) silent('no narration audio — running silently');
      audio.ontimeupdate = () => {  // for checks: where the voice is, and how far the slide's first clip is from it
        body.dataset.audio = `${h + 1}.${k + 1}@${audio.currentTime.toFixed(1)}`;
        const v = slides[h].querySelector('video:not([data-clock])');
        if (v && v.duration) body.dataset.clip = (v.currentTime - (T.scenes[h].say[k].t0 + audio.currentTime) % v.duration).toFixed(2);
      };
      deck.on('ready', () => {
        deck.sync(); deck.layout();
        document.fonts?.ready.then(() => fit(slides[h]));
        const [a, b] = hash.slice(1).split('.').map(Number);
        h = Math.min(N - 1, Math.max(0, (a || 1) - 1));
        k = SHOT && !b ? 99 : (b || 1) - 1;
        if (FAST) { dismiss(); go(h, k, true); } else go(h, k, false);
        if (q.has('autostart')) begin();
        if (REC) window.narrate = record; else tick();
      });
    },
  };
};
