"""Build a narrated talk from a Quarto deck (the sci-narrated-talk skill). Run inside the talk's directory:

    uv run --no-project --with kokoro-onnx --with soundfile --with pyyaml --with matplotlib python narrate.py [talk.qmd]

The steps, in order:
  1. figures.py, if there is one: the drawings (build/fig/*.html) and the numbers (build/values.yml);
  2. the speech of every `::: say` sentence (Kokoro, one mp3 per sentence, cached in media/audio/);
  3. media/manifest.js: the sentence files and their lengths, which are the talk's clock;
  4. quarto render;
  5. a run-through in headless Chromium, offline: every sentence reached in order, the equations rendered, nothing
     outside its slide, nothing loaded from the network.

  --script       print the narration with words, seconds and audio file per sentence; build nothing
  --shots        after the build: a screenshot of every slide's last stage in build/shots/ (contact sheets with pillow)
  --shots=all    ... and of every sentence of every slide (build/shots/all/NN-K.png)
  --size=WxH     the size of the screenshots (default 1280x720)
  --themes       run the check in every theme the talk can be switched to, not only the one it opens in
  --no-check     skip step 5
  --voices       list the voices
  --version      the version of the skill these files come from

Settings, in the deck's front matter (all optional):
    narrate: {voice: af_heart, speed: 1.0, lang: en-us, lead: 0.7, gap: 0.4, tail: 1.0, spoken: {"Péclet": "Pay-clay"},
              embed: true, theme: light, switch: true, keys: {theme: false}}
theme: one of THEMES below, or colours of your own on a base, {base: light, accent: "#0b7285"}. It is the theme the
talk opens in; all of THEMES travel in the page and the viewer can switch between them (key Y, or ?theme=dark in the
address). Figures drawn with `C` follow, because figure() writes the theme's colours into the SVG by name.
switch: false locks the talk to its theme (for a talk whose clips, images or narration fix the colours).
keys: the player's keys by action (play, next, prev, up, down, first, last, captions, outline, voice, auto, theme, hide,
help, number, reveal); a letter renames one, false frees it.
embed: the speech goes into talk.html (one file to send); false leaves it in media/audio/ beside the page.
An mp3 that already exists in media/audio/ under a sentence's name is used as it is, so a recorded voice or another
speech engine can replace Kokoro file by file (`--script` prints the names).
"""

import base64
import hashlib
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import types
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

VERSION = "0.2.0"  # of the skill; the player (narrate.js) carries the same number
WPM = 155  # spoken words per minute, pauses included
LONG = 45  # words; a longer sentence is flagged
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
LANG = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it", "j": "ja", "p": "pt-br", "z": "cmn"}
SAY = re.compile(r"^:::+ *(?:\{[^}\n]*\.say\b[^}\n]*\}|say) *\n(.*?)^:::+ *$", re.M | re.S)
BUILD, MEDIA = Path("build"), Path("media")
THEMES = {  # bg, ink (text), muted (small print), light (rules), accent (title rule, bullets, pointers), three series
    "light": dict(bg="#ffffff", ink="#1d2433", muted="#6b7280", light="#d9dde3", accent="#e8663d", blue="#2b74d6",
                  green="#12a37a", purple="#7b5ea7"),
    "dark": dict(bg="#11151c", ink="#e9edf3", muted="#9aa4b2", light="#2b3340", accent="#ff8757", blue="#6aa9ff",
                 green="#35c99a", purple="#b497e6"),
    "paper": dict(bg="#faf6ee", ink="#2b2622", muted="#7b7268", light="#e2d9c8", accent="#b5451b", blue="#2f5f8f",
                  green="#3b7d5c", purple="#6d4f8f"),
    "sci-talk": dict(bg="#ffffff", ink="#1e293b", muted="#64748b", light="#e5e7eb", accent="#6366f1", blue="#3b82f6",
                     green="#16a34a", purple="#e11d48"),  # the sci-talk deck theme; the third series is rose
    "chalk": dict(bg="#20352f", ink="#f2efe4", muted="#a9b8ae", light="#375049", accent="#ffd166", blue="#8ecbff",
                  green="#9be38f", purple="#e3a8f0"),  # a blackboard
    "midnight": dict(bg="#0b1f3a", ink="#eef3fb", muted="#9db0cc", light="#1f3558", accent="#ffb703", blue="#5cc8ff",
                     green="#5fd3a0", purple="#c4a1ff"),
    "journal": dict(bg="#ffffff", ink="#111111", muted="#5f6368", light="#d0d0d0", accent="#a61e2a", blue="#0072b2",
                    green="#009e73", purple="#aa4499", font="IBM Plex Serif"),  # print look; the serif runs wider
    "sea": dict(bg="#f3f8fa", ink="#102a33", muted="#5b7079", light="#cfdde2", accent="#0b7285", blue="#3b5bdb",
                green="#2f9e44", purple="#ae3ec9"),
    "contrast": dict(bg="#000000", ink="#ffffff", muted="#c4c4c4", light="#3a3a3a", accent="#ffd400", blue="#56b4e9",
                     green="#3ddc97", purple="#d59bff"),  # for a weak projector
}  # the same nine as sci-video-talk's video_engine.py
FONT = "Source Sans 3"
GLYPHS = [(0x20, 0x17F), (0x370, 0x3FF), (0x2000, 0x20CF), (0x2100, 0x214F), (0x2190, 0x22FF), (0x25A0, 0x25FF),
          (0x27E8, 0x27E9)]  # what a font shipped in the talk keeps: Latin, Greek, punctuation, arrows, math, shapes
# Figure sizes in inches at 100 px per inch of the 1920 x 1080 frame, so that text sizes are the videos' points:
FIG = (10.9, 7.7)  # the .fig box of a .beside slide (the video's plot rectangle plus room for its axis labels)
PLOT = (0.0866, 0.1247, 0.8807, 0.8416)  # the axes inside it, where the video's beside() puts its plot: fig.add_axes(PLOT)
ART = (7.49, 7.48)  # the .art picture box of a title or divider card
C = types.SimpleNamespace()  # the theme's colours for figures.py: C.bg, C.ink, C.muted, C.light, C.accent, C.blue, ...
PALETTES = {}  # what the page can switch between: name -> the eight colours and the font stack


# ---------------------------------------------------------------- for figures.py
def named(svg):
    """The SVG with every colour that is one of the theme's written by its name, so that it follows a change of theme."""
    names = {}
    for k in ("ink", "muted", "light", "accent", "blue", "green", "purple", "bg"):
        names.setdefault(str(getattr(C, k, "")).lower(), k)
    return re.sub(r"#[0-9a-fA-F]{6}\b", lambda m: f"var(--{names[m.group(0).lower()]})" if m.group(0).lower() in names else m.group(0), svg)


def mark(name, ax, x, y, r=0.024):
    """A pointer target at the data point (x, y), as the video engine's mark(): an invisible dot of radius r (in units
    of the frame's height) that `point="#<figure>-<name>"` rings. The figure must be drawn at 100 px per inch."""
    ax.plot([x], [y], "o", ms=2 * r * 1080 * 0.72, alpha=0, gid=name, clip_on=False)


def figure(fig, name):
    """Write build/fig/<name>.html, the matplotlib figure as inline SVG; put it on a slide with
    {{< include build/fig/<name>.html >}}. The gid of an artist names it and says when it shows:
      gid="fit"       only names the part: id "<name>-fit", for point= and grow=
      gid="s2-fit"    appears with sentence 2 of its slide
      gid="s2-4-fit"  appears with sentence 2 and is gone from sentence 4 on
      gid="s2-d4-fit" appears with sentence 2 and is dimmed from sentence 4 on"""
    import io

    import matplotlib.pyplot as plt

    buf = io.StringIO()
    with plt.rc_context({"svg.fonttype": "none", "svg.hashsalt": name}):  # text stays text; ids are stable
        fig.savefig(buf, format="svg", transparent=True, metadata={"Date": None})
    plt.close(fig)
    s = buf.getvalue()
    s = named(re.sub(r"<metadata>.*?</metadata>\s*", "", s[s.index("<svg"):], flags=re.S))

    def ident(m):
        k, dim, end, part = re.fullmatch(r"(?:s(\d+)(?:-(d?)(\d+))?-)?(.+)", m.group(1)).groups()
        k = int(k or 1) - 1  # the sentence that introduces the part, counted from 0 as the player does
        return (f'id="{name}-{part}"' + (f' class="fragment" data-fragment-index="{k - 1}"' if k else "")
                + (f' data-k="{k}"' if m.group(1) != part or k else "")
                + (f' data-{"dim" if dim else "until"}="{int(end) - 1}"' if end else ""))

    s = re.sub(r'\bid="([^"]+)"', ident, s)
    s = re.sub(r"url\(#([^)]+)\)", rf"url(#{name}-\1)", s)
    s = re.sub(r'href="#([^"]+)"', rf'href="#{name}-\1"', s)
    s = re.sub(r'<svg ([^>]*?)width="[^"]*" height="[^"]*"', rf'<svg id="{name}" class="nar-fig" \1', s, count=1)
    (BUILD / "fig").mkdir(parents=True, exist_ok=True)
    (BUILD / "fig" / f"{name}.html").write_text(f"```{{=html}}\n{s}\n```\n")


def values(**kw):
    """Write build/values.yml: numbers the slides and the narration quote as {{< meta v.NAME >}}."""
    BUILD.mkdir(exist_ok=True)
    (BUILD / "values.yml").write_text("v:\n" + "".join(f"  {k}: {json.dumps(str(x))}\n" for k, x in kw.items()))


# ---------------------------------------------------------------- theme
def contrast(a, b):
    lum = [0.2126 * r + 0.7152 * g + 0.0722 * bl for r, g, bl in
           [[((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in
             (int(x[i:i + 2], 16) / 255 for i in (1, 3, 5))] for x in (a, b)]]
    return (max(lum) + 0.05) / (min(lum) + 0.05)


def theme(spec):
    """The eight colours and the font of `narrate: theme:`; fails on a theme that cannot be read."""
    over = {k: v for k, v in spec.items() if k != "base"} if isinstance(spec, dict) else {}
    base = spec.get("base", "light") if isinstance(spec, dict) else spec
    if base not in THEMES:
        sys.exit(f"unknown theme {base!r}: one of {', '.join(THEMES)}, or {{base: light, accent: \"#0b7285\"}}")
    th = {"font": FONT} | THEMES[base] | over
    low = [f"{k} on bg ({contrast(th[k], th['bg']):.1f}, needs {need})" for k, need in
           dict(ink=7, muted=4, accent=3, blue=3, green=3, purple=3).items() if contrast(th[k], th["bg"]) < need]
    if low:
        sys.exit("theme: too little contrast: " + "; ".join(low))
    return th


def font_faces(family):
    """@font-face rules carrying the font's regular, semibold, bold and italic cuts (subset to GLYPHS), so that the talk
    looks the same on a machine without the font. '' when this machine lacks the font or the tools."""
    try:
        import io

        import logging

        from fontTools import subset
        from matplotlib import font_manager as fm
    except ImportError:
        return ""
    logging.getLogger("fontTools").setLevel(logging.ERROR)  # no notes about tables it leaves out
    css = ""
    for weight, style in ((400, "normal"), (600, "normal"), (700, "normal"), (400, "italic")):
        try:
            path = fm.findfont(fm.FontProperties(family=family, weight=weight, style=style), fallback_to_default=False)
        except ValueError:
            print(f"theme: the font {family!r} is not installed here; the talk uses the viewer's system font")
            return ""
        opt = subset.Options()
        font, sub, buf = subset.load_font(path, opt), subset.Subsetter(opt), io.BytesIO()
        sub.populate(unicodes=[u for a, b in GLYPHS for u in range(a, b + 1)])
        sub.subset(font)
        font.save(buf)
        css += (f'@font-face {{\n  font-family: "{family}";\n  font-weight: {weight};\n  font-style: {style};\n'
                f'  src: url("data:font/ttf;base64,{base64.b64encode(buf.getvalue()).decode()}");\n}}\n')
    return css


def stack(font):
    serif = "serif" in font.lower() and "sans" not in font.lower()
    return f'"{font}", ' + ("Georgia, serif" if serif else 'system-ui, -apple-system, "Segoe UI", sans-serif')


def apply_theme(spec, drawing, switch=True):
    """The talk's theme: build/theme.scss for the slides (its values, and the fonts of every theme), PALETTES for the
    page's theme switch (only this theme with switch=False), C and matplotlib's defaults for figures.py. Returns the
    theme's name."""
    name = spec if isinstance(spec, str) else "custom"
    all_ = ({n: theme(n) for n in THEMES} if switch else {}) | {name: theme(spec)}
    th = all_[name]
    C.__dict__.update(th)
    PALETTES.update({n: {k: v for k, v in t.items() if k != "font"} | {"font": stack(t["font"])} for n, t in all_.items()})
    BUILD.mkdir(exist_ok=True)
    (BUILD / "theme.scss").write_text(
        "/*-- scss:defaults --*/\n" + "".join(f"${k}: {v};\n" for k, v in th.items() if k != "font")
        + f"$font: unquote('{stack(th['font'])}');\n\n/*-- scss:rules --*/\n"
        + "".join(font_faces(f) for f in dict.fromkeys(t["font"] for t in all_.values())))
    if drawing:
        import matplotlib.pyplot as plt
        from cycler import cycler

        import logging

        logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)  # no notes about a font this machine lacks
        plt.rcParams.update({  # the video engine's: sizes of its style(), everything in ink, measured in the theme's font
            "font.family": [th["font"], "DejaVu Sans"], "mathtext.fontset": "stixsans", "font.size": 18,
            "axes.labelsize": 20, "lines.linewidth": 2.5, "text.color": C.ink, "axes.labelcolor": C.ink,
            "axes.edgecolor": C.ink, "xtick.color": C.ink, "ytick.color": C.ink, "grid.color": C.light, "patch.edgecolor": C.ink,
            "axes.spines.top": False,
            "axes.spines.right": False, "axes.prop_cycle": cycler(color=[C.blue, C.green, C.purple, C.accent])})
    return name


# ---------------------------------------------------------------- the deck
def read(qmd, strict=True):
    """(front matter with its metadata-files merged in, body with the {{< meta >}} shortcodes filled in)."""
    import yaml

    text = qmd.read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    meta = yaml.safe_load(m.group(1)) if m else {}
    for f in meta.get("metadata-files") or []:
        if Path(f).exists():
            meta.update(yaml.safe_load(Path(f).read_text()) or {})

    def fill(mm):
        v = meta
        for key in mm.group(1).split("."):
            v = v.get(key) if isinstance(v, dict) else None
        if v is None and strict:
            sys.exit(f"{mm.group(0)} has no value: figures.py writes them with values(), or set it in the front matter")
        return str(v if v is not None else f"<{mm.group(1)}>")

    return meta, re.sub(r"\{\{< meta ([\w.-]+) >\}\}", fill, text[m.end():] if m else text)


def plain(md):
    """A sentence as it is spoken: the text without its markup."""
    s = re.sub(r"\[([^\]]*)\]\{[^}]*\}", r"\1", md)
    return " ".join(re.sub(r"[*_`]", "", s).split())


def slides(meta, body):
    """[(title, [spoken sentence, ...])]: the title slide's data-say, then every `::: say` block under its heading."""
    first = (meta.get("title-slide-attributes") or {}).get("data-say", "")
    out = [(meta.get("title", "(before the first heading)"), [plain(s) for s in first.split("|") if s.strip()])]
    for part in re.split(r"^(?=#{1,2} )", body, flags=re.M):
        head = re.match(r"#{1,2} +(.*)", part)
        title = re.sub(r"\[[^\]]*\]\{\.eyebrow\}|\{[^}]*\}", "", head.group(1)).strip() if head else None
        says = [plain(s) for s in SAY.findall(part) if plain(s)]  # a block without text is a silent step
        if head:
            out.append((title, says))
        else:
            out[0][1].extend(says)
    for title, says in out:
        for s in says:
            if "$" in s or "\\" in s:
                sys.exit(f"narration with math or a backslash on slide {title!r}: write the words instead\n  {s}")
    return out


# ---------------------------------------------------------------- speech
def fetch(url, path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {path.name} to {path.parent} (once)", flush=True)
        tmp = path.with_name(path.name + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.rename(path)
    return path


def kokoro():
    """The Kokoro model, in KOKORO_DIR (default ~/.cache/kokoro); downloaded on first use (340 MB)."""
    from kokoro_onnx import Kokoro

    d = Path(os.environ.get("KOKORO_DIR", Path.home() / ".cache/kokoro"))
    return Kokoro(*(str(fetch(KOKORO_URL + f, d / f)) for f in ("kokoro-v1.0.onnx", "voices-v1.0.bin")))


def settings(meta):
    c = dict(voice="af_heart", speed=1.0, lead=0.7, gap=0.4, tail=1.0, spoken={}, embed=True, theme="light", switch=True,
             keys={}) | (meta.get("narrate") or {})
    c.setdefault("lang", LANG.get(c["voice"][0], "en-us"))
    return c


def mp3(sentence, c):
    """Where the sentence's audio lives: named by voice, speed, language and the text as spoken."""
    for a, b in c["spoken"].items():
        sentence = sentence.replace(a, b)
    key = hashlib.sha1(f"{c['voice']}|{c['speed']}|{c['lang']}|{sentence}".encode()).hexdigest()[:16]
    return MEDIA / "audio" / f"{key}.mp3", sentence


def letters(sentence):
    """A sentence's letters and digits: by these the page notices narration that changed after the build."""
    return re.sub(r"[\W_]", "", sentence).lower()


def manifest(say, c, name, path=None):
    """Write the page's manifest: say is [{src, dur, t}] in the order of the slides' spoken sentences (t = letters()).
    For a talk whose speech exists already (a conversion of a video), build `say` yourself and call this."""
    path = path or MEDIA / "manifest.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("window.TALK = " + json.dumps(dict(
        version=VERSION, lead=c["lead"], gap=c["gap"], tail=c["tail"], pre=0.2, theme=name, themes=PALETTES,
        keys=c.get("keys") or {}, say=say)) + ";\n")


def speech(sentences, c, embed):
    """Synthesise what is missing; return the manifest's entries (src, dur) in order."""
    import soundfile

    (MEDIA / "audio").mkdir(parents=True, exist_ok=True)
    model, out = None, []
    for s in sentences:
        p, spoken = mp3(s, c)
        if not p.exists():
            model = model or kokoro()
            a, sr = model.create(spoken, voice=c["voice"], speed=c["speed"], lang=c["lang"])
            soundfile.write(p, a, sr, format="MP3")
            print(f"  spoke: {s[:70]}", flush=True)
        src = "data:audio/mpeg;base64," + base64.b64encode(p.read_bytes()).decode() if embed else p.as_posix()
        out.append(dict(src=src, dur=round(soundfile.info(p).duration, 3), t=letters(s)))
    return out


# ---------------------------------------------------------------- checks in headless Chromium
def chromium(*args, timeout=600):
    exe = next((e for e in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable") if shutil.which(e)), None)
    if not exe:
        sys.exit("no chromium or google-chrome on the PATH: the check and the screenshots need one (or pass --no-check)")
    return subprocess.run([exe, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                           "--host-resolver-rules=MAP * ~NOTFOUND", *args], capture_output=True, text=True, timeout=timeout).stdout


def check(html, seconds, theme=None):
    """Play the talk through at 50x without sound and with the network cut (in `theme`, else the one it opens in).
    Returns the positions reached, [(slide, sentence)]."""
    dom = chromium(f"--virtual-time-budget={int(60_000 + 40 * seconds * 1000 / 50 * 2)}", "--dump-dom",
                   f"{html.resolve().as_uri()}?fast" + (f"&theme={theme}" if theme else ""))
    body = re.search(r"<body[^>]*>", dom)
    if not body:
        sys.exit("check: Chromium returned no page")
    d = dict(re.findall(r'data-(\w+)="([^"]*)"', body.group(0)))
    log = [tuple(map(int, x.split("."))) for x in d.get("log", "").split()]
    bad = []
    if d.get("error"):
        bad.append(d["error"])
    if not d.get("done"):
        bad.append(f"the talk stopped at slide.sentence {'.'.join(map(str, log[-1])) if log else '?'}")
    if log != sorted(set(log)) or len(log) != int(d.get("steps", -1)):
        bad.append(f"visited {len(log)} positions, the talk has {d.get('steps')} (or out of order): {d.get('log')}")
    raw = [m for m in re.findall(r'<span class="math (?:inline|display)">(.{0,40})', dom) if not m.startswith("<span class=\"katex")]
    if raw:
        bad.append(f"{len(raw)} equations left as raw TeX, e.g. {raw[0]!r}")
    remote = sorted(set(re.findall(r'<(?:script|link|img|video|audio|source|iframe)\b[^>]*?(?:src|href)="(https?://[^"]+)', dom)))
    if remote:
        bad.append(f"loads from the network, so not offline: {remote[:3]}")
    if d.get("over"):
        bad.append(f"reaches outside its slide: {d['over']}")
    if d.get("hidden"):
        bad.append(f"content that no sentence reveals (a fragment or `. . .` pause of your own; stage with say blocks): {d['hidden']}")
    if bad:
        sys.exit(f"check failed{f' in theme {theme}' if theme else ''}:\n- " + "\n- ".join(bad))
    print(f"check{f' ({theme})' if theme else ''}: {len(log)} steps on {log[-1][0]} slides reached in order, equations rendered, "
          "nothing outside a slide or left hidden, offline")
    return log


def shots(html, log, every=False, size="1280x720"):
    """A screenshot of every slide at its last sentence (and, with every, of every sentence); log is check()'s result."""
    out, n, win = BUILD / "shots", log[-1][0], "--window-size=" + size.replace("x", ",")
    (out / "all").mkdir(parents=True, exist_ok=True)
    files = [out / f"{i:02d}.png" for i in range(1, n + 1)]
    jobs = [(f"#{i}", f) for i, f in enumerate(files, 1)] + ([(f"#{a}.{b}", out / "all" / f"{a:02d}-{b}.png") for a, b in log] if every else [])
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(lambda j: chromium(win, "--virtual-time-budget=4000", f"--screenshot={j[1]}", f"{html.resolve().as_uri()}?shot{j[0]}"), jobs))
    if every:
        print(f"shots: {len(log)} sentences in {out}/all/")
    try:
        from PIL import Image
    except ImportError:
        return print(f"shots: {len(files)} in {out}/ (add --with pillow for contact sheets)")
    for j in range(0, n, 9):  # nine slides to a sheet
        sheet = Image.new("RGB", (1920, 1080), "white")
        for i, f in enumerate(files[j:j + 9]):
            sheet.paste(Image.open(f).convert("RGB").resize((640, 360)), (640 * (i % 3), 360 * (i // 3)))
        sheet.save(out / f"sheet-{j // 9 + 1}.png")
    print(f"shots: {len(files)} in {out}/, contact sheets sheet-*.png")


# ---------------------------------------------------------------- main
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = dict(a.split("=", 1) if "=" in a else (a, "") for a in sys.argv[1:] if a.startswith("--"))
    flags = set(opts)
    if unknown := flags - {"--script", "--shots", "--size", "--themes", "--no-check", "--voices", "--version"}:
        sys.exit(f"unknown option {sorted(unknown)}\n{__doc__}")
    if "--version" in flags:
        return print(VERSION)
    if "--voices" in flags:
        return print(" ".join(sorted(kokoro().get_voices())))
    qmd = Path(args[0] if args else "talk.qmd").resolve()
    os.chdir(qmd.parent)
    name = None
    if "--script" not in flags:
        c0 = settings(read(qmd, strict=False)[0])
        name = apply_theme(c0["theme"], Path("figures.py").exists(), c0["switch"])
        if Path("figures.py").exists():
            sys.modules["narrate"] = sys.modules[__name__]  # figures.py does `from narrate import figure, values, C`
            runpy.run_path("figures.py", run_name="__main__")
    meta, body = read(qmd, strict="--script" not in flags)
    c, deck = settings(meta), slides(meta, body)
    sentences = [s for _, says in deck for s in says]
    words = sum(len(s.split()) for s in sentences)
    if "--script" in flags:
        for n, (title, says) in enumerate(deck, 1):
            print(f"\n{n}. {title}  ({sum(len(s.split()) for s in says)} words)")
            for s in says:
                w = len(s.split())
                print(f"   {mp3(s, c)[0].name}  {w:3d} w{'  LONG' if w > LONG else ''}  {s}")
        return print(f"\n{len(deck)} slides, {len(sentences)} sentences, {words} words, about {words / WPM:.1f} min at {WPM} words per minute")
    say = speech(sentences, c, c["embed"])
    manifest(say, c, name)
    seconds = sum(s["dur"] + c["gap"] for s in say) + len(deck) * (c["lead"] + c["tail"])
    print(f"speech: {len(say)} sentences, {seconds / 60:.1f} min with pauses, voice {c['voice']}; theme {name}", flush=True)
    subprocess.run(["quarto", "render", qmd.name], check=True)
    html = qmd.with_suffix(".html")
    if "--no-check" not in flags or "--shots" in flags or "--themes" in flags:
        log = check(html, seconds)
        if "--themes" in flags:
            for t in PALETTES:
                if t != name:
                    check(html, seconds, t)
        if "--shots" in flags:
            shots(html, log, opts["--shots"] == "all", opts.get("--size") or "1280x720")
    print(f"talk: {html}  ({html.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
