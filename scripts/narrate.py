"""Build a narrated talk from a Quarto deck (the sci-narrated-talk skill). Run inside the talk's directory:

    uv run --no-project --python ">=3.10" --with kokoro-onnx --with soundfile --with pyyaml --with matplotlib python narrate.py [talk.qmd]

The slides and the voice are separate layers. talk.html holds the slides, the narration's text and the player, and
no voice; a voice is a folder beside it, media/voices/<name>/ (its audio and a voice.js), which the page finds when it
opens. A voice can be added, replaced or deleted without rendering the slides again.

The steps of a build, in order:
  1. figures.py, if there is one: the drawings (build/fig/*.html) and the numbers (build/values.yml);
  2. media/manifest.js, rendered into the page: pauses, themes, keys and the voice the talk opens with;
  3. the talk's own synthetic voice (narrate: voice:, Kokoro), one mp3 per sentence in media/voices/<voice>/; only
     sentences it lacks are spoken. media/voices/index.js lists the voice folders;
  4. quarto render;
  5. a run-through in headless Chromium, offline and without a voice: every sentence reached in order, the equations
     rendered, nothing outside its slide, nothing loaded from the network; and per voice, the steps it lacks.

  --script             print the narration: words per sentence and the name of its file for a recording (03.2 is
                       slide 3, step 2, as in the address talk.html#3.2); build nothing
  --no-voice           build the slides without speaking anything
  --voice=NAME         add or complete a synthetic voice (a Kokoro voice) without rendering the slides; with
                       --speed=X and --lang=L; its folder is NAME, NAME-1.2 at speed 1.2, NAME-1.2-en-gb ...
  --import-voice=NAME  bind the recordings in media/voices/NAME/ (03.2.wav, .mp3, .ogg or .flac, named as --script
                       lists them) to their sentences: your own reading of the script, or another engine's
  --bundle=WHAT        write a one-file copy of the page, with WHAT inside (say which: there is no default):
                         voice   talk-NAME.html: the talk's own voice inside; its clips stay files beside it
                         clips   talk-none.html: the clips inside (every video, sound and image the page shows
                                 from a file beside it) and no voice: a deck to present by hand, which looks for none
                         both    talk-NAME.html: the voice and the clips inside; it needs nothing beside it
                       voice:NAME, both:NAME: with the voice of media/voices/NAME/ instead of the talk's own
  --shots              after the build: a screenshot of every slide's last stage in build/shots/ (contact sheets with pillow)
  --shots=all          ... and of every sentence of every slide (build/shots/all/NN-K.png)
  --size=WxH           the size of the screenshots (default 1280x720)
  --themes             run the check in every theme the talk can be switched to, not only the one it opens in
  --no-check           skip step 5
  --voices             list the Kokoro voices
  --version            the version of the skill these files come from
--voice, --import-voice and --bundle leave talk.html as it is: build the slides first.

Settings, in the deck's front matter (all optional):
    narrate: {voice: af_heart, speed: 1.0, lang: en-us, lead: 0.7, gap: 0.4, tail: 1.0, spoken: {"Péclet": "Pay-clay"},
              theme: light, switch: true, keys: {theme: false}}
voice: the Kokoro voice the build speaks and the talk opens with; false: none, a deck to present by hand (each step
then lasts its words at WPM). The viewer picks among the voices beside the page in the settings, or ?narrator=NAME.
theme: one of THEMES below, or colours of your own on a base, {base: light, accent: "#0b7285"}. It is the theme the
talk opens in; all of THEMES travel in the page and the viewer can switch between them (key Y, or ?theme=dark in the
address). Figures drawn with `C` follow, because figure() writes the theme's colours into the SVG by name.
switch: false locks the talk to its theme (for a talk whose clips, images or narration fix the colours).
keys: the player's keys by action (play, next, prev, up, down, first, last, captions, outline, voice, auto, theme, hide,
help, number, settings, reveal); a key or a list of keys ([n, PageDown]; "space" for the space bar) replaces an action's
keys, false frees them.
embed: voice, clips or both: every build also writes that one-file copy, as --bundle=WHAT does (true: voice, as in
0.4.0, when the voice was inside talk.html).
"""

import base64
import hashlib
import json
import mimetypes
import os
import re
import runpy
import shutil
import subprocess
import sys
import types
import urllib.parse
import urllib.request
from pathlib import Path

VERSION = "0.5.2"  # of the skill; the player (narrate.js) carries the same number
WPM = 155  # spoken words per minute, pauses included
LONG = 45  # words; a longer sentence is flagged
KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
LANG = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi", "i": "it", "j": "ja", "p": "pt-br", "z": "cmn"}
SAY = re.compile(r"^:::+ *(?:\{[^}\n]*\.say\b[^}\n]*\}|say) *\n(.*?)^:::+ *$", re.M | re.S)
os.environ.setdefault("MPLBACKEND", "Agg")  # figures are drawn to files: no window toolkit, which macOS and Windows would pick
BUILD, MEDIA = Path("build"), Path("media")
VOICES = MEDIA / "voices"  # a folder per voice, each with its audio and voice.js; index.js names them
RECORDING = re.compile(r"\d+\.\d+(-[0-9a-f]{6})?")  # a recording's name: its place (03.2), and once bound its hash
AUDIO = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".flac": "audio/flac"}  # both browsers play these
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
    """[(title, [step, ...])] as the page has them: the title slide (data-say) or what stands before the first heading,
    if any, then a slide per heading. A step is its spoken sentence, '' for a silent step (a block without text)."""
    first = (meta.get("title-slide-attributes") or {}).get("data-say", "")
    out = [(meta.get("title", "(before the first heading)"), [plain(s) for s in first.split("|")] if first else [])]
    for part in re.split(r"^(?=#{1,2} )", body, flags=re.M):
        head = re.match(r"#{1,2} +(.*)", part)
        title = re.sub(r"\[[^\]]*\]\{\.eyebrow\}|\{[^}]*\}", "", head.group(1)).strip() if head else None
        says = [plain(s) for s in SAY.findall(part)]
        if head:
            out.append((title, says))
        else:
            out[0][1].extend(says)
    for title, says in out:
        for s in says:
            if "$" in s or "\\" in s:
                sys.exit(f"narration with math or a backslash on slide {title!r}: write the words instead\n  {s}")
    return out if out[0][1] or "title" in meta else out[1:]  # no title slide in the page, and nothing before the first heading


def spoken(deck):
    """[(position, sentence)] for every spoken sentence; position (3, 2) is slide 3, step 2, as the address #3.2."""
    return [((n, k), s) for n, (_, says) in enumerate(deck, 1) for k, s in enumerate(says, 1) if s]


def pos(p):
    return f"{p[0]:02d}.{p[1]}"


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
    c = dict(voice="af_heart", speed=1.0, lead=0.7, gap=0.4, tail=1.0, spoken={}, theme="light", switch=True,
             keys={}) | (meta.get("narrate") or {})
    if c["voice"] in (None, "none"):  # (`voice: none` in YAML is the word, not null)
        c["voice"] = False
    c["embed"] = "voice" if c.get("embed") is True else c.get("embed") or None
    if c["embed"] not in (None, *INSIDE):
        sys.exit(f"narrate: embed: {c['embed']!r}: say what goes into the one-file copy: {', '.join(INSIDE)}")
    if c["embed"] in ("voice", "both") and not c["voice"]:
        sys.exit(f"narrate: embed: {c['embed']} needs a voice, and voice: is false: use embed: clips, or give the talk a voice")
    c["speed"] = float(c["speed"])  # `speed: 1` and --speed=1 must name the same files (0.4.0's starter wrote 1.0)
    if c["voice"]:
        c.setdefault("lang", LANG.get(c["voice"][0], "en-us"))
    return c


def folder(c):
    """A synthetic voice's folder: the voice, then its speed and language where they are not the voice's own, so that
    af_heart at two speeds is two voices."""
    sp, own = float(c["speed"]), LANG.get(c["voice"][0], "en-us")
    return c["voice"] + (f"-{sp:g}" if sp != 1 else "") + (f"-{c['lang']}" if c["lang"] != own else "")


def mp3(sentence, c):
    """(file name, sentence as spoken): the name is a hash of voice, speed, language and the text as spoken, so that
    an unchanged sentence is never spoken twice. 0.4.0 used the same names, in media/audio/."""
    for a, b in c["spoken"].items():
        sentence = sentence.replace(a, b)
    key = hashlib.sha1(f"{c['voice']}|{c['speed']}|{c['lang']}|{sentence}".encode()).hexdigest()[:16]
    return f"{key}.mp3", sentence


def letters(sentence):
    """A sentence's letters and digits: its key, by which the page finds a step's audio in a voice (the player's norm)."""
    return re.sub(r"[\W_]", "", sentence).lower()


def manifest(c, name, path=None):
    """media/manifest.js, which the deck includes and Quarto renders into the page: what the talk is without a voice
    (pauses, themes, keys) and the voice it opens with (a folder name; null for none)."""
    path = path or MEDIA / "manifest.js"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("window.TALK = " + json.dumps(dict(
        version=VERSION, lead=c["lead"], gap=c["gap"], tail=c["tail"], pre=0.2, theme=name, themes=PALETTES,
        keys=c.get("keys") or {}, voice=opens_with(c) or None)) + ";\n")


def opens_with(c):
    """The folder of the voice the talk opens with: your own reading by its name, a synthetic voice by voice, speed and
    language."""
    return c["voice"] and (c["voice"] if kind(VOICES / c["voice"]) == "recorded" else folder(c))


# ---------------------------------------------------------------- voices
def write_voice(d, v):
    """d/voice.js. v: label, kind (synthetic | recorded), steps [{file, at, dur, t}] and anything else about the voice.
    One step per line, so that a recorded voice reads well in a diff. For speech made elsewhere (a video's), write the
    files into a folder of media/voices/ and call this."""
    head = json.dumps({"name": d.name, **{k: x for k, x in v.items() if k != "steps"}, "version": VERSION})
    steps = ",\n  ".join(json.dumps(s, ensure_ascii=False) for s in v["steps"])
    tmp = d / "voice.js.part"  # written whole, then renamed: an interrupted build never leaves half a voice.js
    tmp.write_text(f'window.VOICE = {head[:-1]}, "steps": [\n  {steps}\n]}};\n')
    tmp.replace(d / "voice.js")


def read_voice(d, strict=True):
    """d/voice.js as a dict. One that cannot be read stops the build (strict) or is reported and skipped (None)."""
    try:
        t = (d / "voice.js").read_text()
        return json.loads(t[t.index("{"):t.rindex("}") + 1])
    except ValueError as e:
        why = (f"{d / 'voice.js'} cannot be read ({e}). A synthetic voice: delete it and build the voice again (its "
               "audio is kept). Your own reading: the files carry their place in their names (03.2-1a2b3c.wav); rename "
               "them back to 03.2.wav, delete voice.js and --import-voice again, before the slides change")
        if strict:
            sys.exit(why)
        print("  " + why)


def voices():
    return sorted(p.parent.name for p in VOICES.glob("*/voice.js"))


def index():
    """media/voices/index.js: the voice folders, which the page cannot list for itself. Returns their names."""
    VOICES.mkdir(parents=True, exist_ok=True)
    (VOICES / "index.js").write_text("window.VOICES = " + json.dumps(voices()) + ";\n")
    return voices()


def kind(d):
    return (d / "voice.js").exists() and read_voice(d).get("kind")


def lacks(name, sentences):
    """The sentences the voice has no audio for (None: its voice.js cannot be read, which is reported)."""
    v = read_voice(VOICES / name, strict=False)
    return v and [s for s in sentences if letters(s) not in {x["t"] for x in v["steps"]}]


def speech(sentences, c):
    """The synthetic voice c (Kokoro voice, speed, lang) in media/voices/<folder>/: the sentences it lacks are spoken,
    the rest kept, and what a 0.4.0 build spoke into media/audio/ is moved in. Writes its voice.js; returns
    (folder, seconds of speech)."""
    import soundfile

    d = VOICES / folder(c)
    if kind(d) not in (False, "synthetic") or (d.is_dir() and any(RECORDING.fullmatch(p.stem) for p in d.iterdir())):
        sys.exit(f"{d} holds your own recordings, not a synthetic voice: --import-voice={d.name} binds them")

    def folder_made():  # only once a file goes in, so that a mistyped voice leaves no folder behind
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitignore").write_text("*\n")  # the build can make it again, so git leaves it out (a recorded voice it keeps)

    model, out, moved = None, [], 0
    for s in sentences:
        name, said = mp3(s, c)
        p, old = d / name, MEDIA / "audio" / name
        if not p.exists() and old.exists():
            folder_made()
            old.rename(p)
            moved += 1
        if not p.exists():
            if model is None:
                model = kokoro()
                if c["voice"] not in model.get_voices():
                    sys.exit(f"no Kokoro voice {c['voice']!r}: --voices lists them")
            folder_made()
            a, sr = model.create(said, voice=c["voice"], speed=c["speed"], lang=c["lang"])
            soundfile.write(p, a, sr, format="MP3")
            print(f"  spoke: {s[:70]}", flush=True)
        out.append(dict(file=name, at=0, dur=round(soundfile.info(p).duration, 3), t=letters(s)))
    folder_made()
    if moved:
        print(f"  {moved} sentences taken over from media/audio/, spoken by an earlier build")
    sp = float(c["speed"])
    write_voice(d, dict(label=c["voice"] + (f" ×{sp:g}" if sp != 1 else "") + (f" {c['lang']}" if d.name.endswith(c["lang"]) else ""),
                        kind="synthetic", engine="kokoro", voice=c["voice"], speed=c["speed"], lang=c["lang"], steps=out))
    return d.name, sum(x["dur"] for x in out)


def import_voice(name, steps):
    """A recorded voice: the files in media/voices/<name>/ named by position (03.2.wav, see --script) are bound to
    the sentence at that position and renamed 03.2-<hash of the file>.wav, so that a later recording under the same
    name never overwrites one already bound. What voice.js bound before stays bound to its sentence by the text, so a
    sentence inserted later moves nothing. A sentence whose text changed has no file until it is recorded again."""
    import soundfile

    d = VOICES / name
    if not d.is_dir():
        sys.exit(f"no folder {d}: put the recordings there, named as --script lists them (03.2.wav)")
    if kind(d) not in (False, "recorded"):
        sys.exit(f"{d} is a {kind(d)} voice: --voice={read_voice(d).get('voice', name)} builds it")
    at = {p: letters(s) for p, s in steps}
    bound = {}  # text key -> file
    for st in read_voice(d)["steps"] if kind(d) else []:
        if st["t"] in at.values() and (d / st["file"]).is_file():
            bound.setdefault(st["t"], st["file"])
    new = sorted(p for p in d.iterdir() if re.fullmatch(r"\d+\.\d+", p.stem))
    if bad := [p.name for p in new if p.suffix.lower() not in AUDIO]:
        sys.exit(f"{d}: {', '.join(bad)}: a recording must be .wav, .mp3, .ogg or .flac (both browsers play these); "
                 "convert it, e.g. ffmpeg -i 03.2.m4a 03.2.wav")
    for p in new:  # every new file is read before any is renamed: a bad one leaves the folder as it was
        try:
            soundfile.info(p)
        except Exception as e:  # noqa: BLE001  (soundfile raises its own errors and RuntimeError)
            sys.exit(f"{p}: cannot be read ({e}); convert it to wav. Nothing was renamed.")
    if (g := d / ".gitignore").is_file() and g.read_text().strip() == "*":  # left by a --voice= on this folder
        g.unlink()
        print(f"  removed {g}: git keeps your recordings")
    for p in new:
        n, k = map(int, p.stem.split("."))
        if (n, k) not in at:
            print(f"  {p.name}: no sentence at {pos((n, k))} (see --script); left as it is")
            continue
        q = p.with_name(f"{pos((n, k))}-{hashlib.sha1(p.read_bytes()).hexdigest()[:6]}{p.suffix.lower()}")
        p.replace(q)  # (replace: the same recording copied in again has this name already, which stops rename on Windows)
        if at[(n, k)] in bound:
            print(f"  {q.name} replaces {bound[at[(n, k)]]}, which stays in the folder unused")
        bound[at[(n, k)]] = q.name
    out = []
    for p, s in steps:
        if f := bound.get(letters(s)):
            try:
                dur = soundfile.info(d / f).duration
            except Exception as e:  # noqa: BLE001  (soundfile raises its own errors and RuntimeError)
                sys.exit(f"{d / f}: cannot be read ({e}); convert it to wav")
            out.append(dict(file=f, at=0, dur=round(dur, 3), t=letters(s)))
    write_voice(d, dict(label=name, kind="recorded", steps=out))
    missing = [(p, s) for p, s in steps if letters(s) not in bound]
    unused = sorted(p.name for p in d.iterdir() if p.suffix.lower() in AUDIO and p.name not in bound.values())
    print(f"voice {name}: {len(out)} of {len(steps)} sentences have a recording"
          + "".join(f"\n  no file for {pos(p)}: {s[:70]}  (record it as {d / pos(p)}.wav)" for p, s in missing)
          + (f"\n  not used: {', '.join(unused)} (earlier takes, or sentences no longer in the talk)" if unused else ""))


def inline(page, base, put):
    """The files the page shows from beside it (a clip: <video src=... data-external="1">), as (page, [files]); with
    `put` each goes into the page as a data: URL."""
    found = []

    def attr(m):
        ref, _, frag = m.group(2).partition("#")  # (run.mp4#t=5 keeps its fragment)
        f = base / urllib.parse.unquote(ref)
        if re.match(r"[a-z][a-z0-9+.-]*:|//", ref) or not f.is_file():
            return m.group(0)
        found.append(f)
        if not put:
            return m.group(0)
        # ponytail: a file shown twice goes in twice, and Firefox opens no data: URL over 32 MB; blob URLs made by a
        # script from one copy each would lift both, at the price of decoding them all when the page opens
        return (f'{m.group(1)}="data:{MIME.guess_type(f.name)[0] or mimetypes.guess_type(f.name)[0] or "application/octet-stream"};base64,'
                f'{base64.b64encode(f.read_bytes()).decode()}{"#" + frag if frag else ""}"')

    page = re.sub(r"<(?:video|audio|source|img|track)\b[^>]*>", lambda t: re.sub(r'\b(src|poster)="([^"]*)"', attr, t.group(0)), page)
    return page, sorted(set(found))


MIME = mimetypes.MimeTypes()  # Python's own table first: the module's functions put the Windows registry over it
INSIDE = ("voice", "clips", "both")  # what a one-file copy can hold: --bundle=WHAT, narrate: embed: WHAT


def bundle(name, html, clips=False):
    """talk-<name>.html: the page with the voice <name> inside (audio as data: URLs), one file that plays offline.
    It looks for no other voice; the folder version stays as it is. With `clips` the files the page shows from beside
    it go inside too; without, they are named, since the one file needs them beside it. The name "none": no voice
    inside, and the page looks for none (the player takes a VOICE without steps as that)."""
    d = VOICES / name
    if name != "none" and not (d / "voice.js").exists():
        sys.exit(f"no voice {name!r} to put in the page: {', '.join(voices()) or 'there is none'}")
    v = read_voice(d) | {"name": name} if name != "none" else {"name": "none", "steps": []}
    for s in v["steps"]:
        s["file"] = f"data:{AUDIO[Path(s['file']).suffix.lower()]};base64," + base64.b64encode((d / s["file"]).read_bytes()).decode()
    page, out = html.read_text(), html.with_name(f"{html.stem}-{name}.html")
    m = re.search(r"<head[^>]*>", page)  # before every script of the page: the player reads it when it starts
    js = json.dumps(v).replace("</", "<\\/")  # (a label must not close the script)
    page, files = inline(page[:m.end()] + f"\n<script>window.VOICE = {js};</script>" + page[m.end():], html.parent, clips)
    out.write_text(page)
    rel = [os.path.relpath(f, html.parent) for f in files]
    print(f"one file: {out}  ({out.stat().st_size / 1e6:.1f} MB, {'voice ' + name if name != 'none' else 'no voice'}"
          + (f", and inside it {', '.join(rel[:4])}{', ...' if len(rel) > 4 else ''}" if clips and files else "") + ")")
    if files and not clips:
        print(f"  it still shows {len(files)} file{'s' * (len(files) > 1)} from beside it ({', '.join(rel[:4])}{', ...' if len(rel) > 4 else ''}): "
              "to be sent along at the same paths (both, not voice, puts them inside)")
    for f, n in zip(files, rel):
        if clips and f.stat().st_size * 4 / 3 > 32e6:
            print(f"  {n} is {f.stat().st_size / 1e6:.0f} MB: Firefox opens no data: URL over 32 MB (24 MB of file), Chromium none over 512 MB; "
                  "a smaller clip, or the page sent with its folder, opens everywhere")


# ---------------------------------------------------------------- checks in headless Chromium
# ponytail: Browser gets its pipes as inherited fds 3 and 4, which Windows has not; --remote-debugging-io-pipes with handles is the way
NO_WINDOWS = "screenshots (--shots) and record.py do not run on Windows yet; the rest of the build does"


def browser():
    """Chromium, Chrome or Edge: $CHROME, else a name on the PATH, else where macOS and Windows install them."""
    names = (os.environ.get("CHROME", ""), "chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "chrome", "msedge")
    apps = [f"/Applications/{a}.app/Contents/MacOS/{a}" for a in ("Google Chrome", "Chromium", "Microsoft Edge")]
    apps += [f"{os.environ[v]}/{a}" for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA") if v in os.environ
             for a in ("Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe")]
    exe = next(filter(None, map(shutil.which, names)), None) or next(filter(os.path.isfile, apps), None)
    if not exe:
        sys.exit("no Chromium, Chrome or Edge found (CHROME=/path/to/one names it): the check and the screenshots need one; "
                 "--no-check builds without")
    return exe


def chromium(*args, timeout=600):
    return subprocess.run([browser(), "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                           "--host-resolver-rules=MAP * ~NOTFOUND", *args], capture_output=True, text=True, timeout=timeout).stdout


def check(html, seconds, theme=None, need=None):
    """Play the slides through at 50x without a voice and with the network cut (in `theme`, else the one it opens in).
    Also: every voice of the index loads in the page, which says how many steps each lacks; the voice `need` (made in
    this build from the same text) lacks none. Returns the positions reached, [(slide, sentence)]."""
    import html as h

    dom = chromium(f"--virtual-time-budget={int(60_000 + 40 * seconds * 1000 / 50 * 2)}", "--dump-dom",
                   f"{html.resolve().as_uri()}?fast&narrator=none" + (f"&theme={theme}" if theme else ""))
    body = re.search(r"<body[^>]*>", dom)
    if not body:
        sys.exit("check: Chromium returned no page")
    d = {k: h.unescape(v) for k, v in re.findall(r'data-(\w+)="([^"]*)"', body.group(0))}
    log = [tuple(map(int, x.split("."))) for x in d.get("log", "").split()]
    got = json.loads(d.get("voices") or "{}")
    bad = [f"voice {n}: its voice.js did not load in the page" for n in voices() if n not in got]
    if need and got.get(need):
        bad.append(f"voice {need}: the page finds no audio for {got[need]} of its sentences, by their text")
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
    if not theme:
        print("voices: " + ("; ".join(f"{n} " + (f"lacks {m} step{'s' * (m > 1)} (silent with it)" if m else "complete")
                                      for n, m in got.items()) or "none: a deck to present by hand"))
    return log


class Browser:
    """Headless Chromium driven over its DevTools pipe (no extra package): one page, moved from slide to slide, and a
    screenshot of each once its fonts and clips are ready. A screenshot taken at start-up does not wait for a clip."""

    def __init__(self, size):
        import fcntl
        import tempfile

        exe = browser()
        fds = [fcntl.fcntl(f, fcntl.F_DUPFD, 10) for pair in (os.pipe(), os.pipe()) for f in pair]  # clear of 3 and 4
        (r1, w1, r2, w2), self.n, self.buf, self.dir = fds, 0, b"", tempfile.mkdtemp()
        self.w, self.r = w1, r2
        self.p = subprocess.Popen(
            [exe, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--host-resolver-rules=MAP * ~NOTFOUND",
             "--remote-debugging-pipe", "--autoplay-policy=no-user-gesture-required", f"--user-data-dir={self.dir}",
             "about:blank"], preexec_fn=lambda: (os.dup2(r1, 3), os.dup2(w2, 4)), close_fds=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # the browser reads commands on 3 and answers on 4;
        # not pass_fds=(3, 4): that asks for 3 and 4 to be open here already, which a plain shell does not give
        os.close(r1), os.close(w2)
        tid = self.call("Target.createTarget", url="about:blank")["targetId"]
        self.sid = self.call("Target.attachToTarget", targetId=tid, flatten=True)["sessionId"]
        w, h = map(int, size.split("x"))
        self.call("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=False)

    def call(self, method, **params):
        self.n += 1
        msg = dict(id=self.n, method=method, params=params) | ({"sessionId": self.sid} if hasattr(self, "sid") else {})
        os.write(self.w, json.dumps(msg).encode() + b"\0")
        while True:
            while b"\0" not in self.buf:
                got = os.read(self.r, 1 << 20)
                if not got:
                    sys.exit("the browser has gone")
                self.buf += got
            raw, self.buf = self.buf.split(b"\0", 1)
            m = json.loads(raw)
            if m.get("id") == self.n:
                return m.get("result", {})

    def js(self, expr):
        return self.call("Runtime.evaluate", expression=expr, awaitPromise=True, returnByValue=True).get("result", {}).get("value")

    def shot(self, path):
        self.js("new Promise(r => { const t = Date.now(), vs = [...document.querySelectorAll('.present video')];"
                " (function w() { vs.every(v => v.readyState >= 2 && !v.seeking) || Date.now() - t > 6000"
                " ? document.fonts.ready.then(() => setTimeout(r, 250)) : setTimeout(w, 50); })(); })")
        Path(path).write_bytes(base64.b64decode(self.call("Page.captureScreenshot", format="png")["data"]))

    def close(self):
        self.p.terminate()
        self.p.wait()
        shutil.rmtree(self.dir, ignore_errors=True)


def shots(html, log, every=False, size="1280x720"):
    """A screenshot of every slide at its last sentence (and, with every, of every sentence); log is check()'s result."""
    out, n = BUILD / "shots", log[-1][0]
    (out / "all").mkdir(parents=True, exist_ok=True)
    files = [out / f"{i:02d}.png" for i in range(1, n + 1)]
    jobs = [(f"#{i}", f) for i, f in enumerate(files, 1)] + ([(f"#{a}.{b}", out / "all" / f"{a:02d}-{b}.png") for a, b in log] if every else [])
    b = Browser(size)
    try:
        b.call("Page.navigate", url=f"{html.resolve().as_uri()}?shot")
        b.js("new Promise(r => { (function w() { window.Reveal && Reveal.isReady() && document.body.dataset.log ? r() : setTimeout(w, 50); })(); })")
        for pos, f in jobs:
            b.js(f"location.hash = {pos!r}, new Promise(r => setTimeout(r, 60))")
            b.shot(f)
    finally:
        b.close()
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
VALUED = {"--size", "--voice", "--speed", "--lang", "--import-voice", "--bundle"}  # --voice=NAME or --voice NAME
FLAGS = VALUED | {"--script", "--shots", "--themes", "--no-check", "--no-voice", "--voices", "--version"}


def options(argv):
    args, opts = [], {}
    while argv:
        a = argv.pop(0)
        k, eq, v = a.partition("=")
        if a.startswith("--"):
            opts[k] = v if eq or k not in VALUED or not argv or argv[0].startswith("--") else argv.pop(0)
        else:
            args.append(a)
    return args, opts


def main():
    args, opts = options(sys.argv[1:])
    if unknown := set(opts) - FLAGS:
        sys.exit(f"unknown option {sorted(unknown)}\n{__doc__}")
    if "--bundle" in opts:  # what goes inside is always said: voice, clips or both; and whose voice, if not the talk's
        what, _, other = opts["--bundle"].partition(":")
        if what not in INSIDE or (other and what == "clips") or (":" in opts["--bundle"] and not other):
            sys.exit("--bundle: say what goes into the one-file copy: --bundle=voice, --bundle=clips or --bundle=both "
                     "(with another voice than the talk's own: --bundle=voice:NAME, --bundle=both:NAME)")
    if empty := [k for k in VALUED - {"--size"} if k in opts and not opts[k]]:
        sys.exit(f"{empty[0]} needs a value: {empty[0]}=NAME")
    if bad := [k for k in ("--speed", "--lang") if k in opts and "--voice" not in opts]:
        sys.exit(f"{bad[0]} goes with --voice=NAME (the front matter sets the talk's own: narrate: speed:, lang:)")
    if any((opts.get(k) or "").lower() == "none" for k in ("--voice", "--import-voice")) or opts.get("--bundle", "").lower().endswith(":none"):
        sys.exit("'none' is the page's name for no voice: give the voice another name")
    if os.name == "nt" and "--shots" in opts:
        sys.exit(NO_WINDOWS)
    if "--version" in opts:
        return print(VERSION)
    if "--voices" in opts:
        return print(" ".join(sorted(kokoro().get_voices())))
    qmd = Path(args[0] if args else "talk.qmd").resolve()
    os.chdir(qmd.parent)
    html, name = qmd.with_suffix(".html"), None
    layer = {"--voice", "--import-voice", "--bundle"} & set(opts)  # a voice, without rendering the slides
    if "--script" not in opts and not layer:
        if not shutil.which("quarto"):  # said before the figures are drawn and the voice is spoken, not after
            sys.exit("quarto is not on the PATH: the slides are rendered by Quarto 1.4 or newer (https://quarto.org/docs/get-started/)")
        c0 = settings(read(qmd, strict=False)[0])
        name = apply_theme(c0["theme"], Path("figures.py").exists(), c0["switch"])
        if Path("figures.py").exists():
            sys.modules["narrate"] = sys.modules[__name__]  # figures.py does `from narrate import figure, values, C`
            runpy.run_path("figures.py", run_name="__main__")
    meta, body = read(qmd, strict="--script" not in opts)
    c, deck = settings(meta), slides(meta, body)
    steps = spoken(deck)
    sentences = [s for _, s in steps]
    words = sum(len(s.split()) for s in sentences)
    # the talk's length without a voice, each sentence on its words (as the page estimates it), a silent step 3 s
    est = (sum(max(1, len(s.split()) * 60 / WPM) + c["gap"] for s in sentences) + len(deck) * (c["lead"] + c["tail"])
           + 3 * (sum(1 for _, says in deck for s in says if not s) + sum(1 for _, says in deck if not says)))
    if "--script" in opts:
        for n, (title, says) in enumerate(deck, 1):
            print(f"\n{n}. {title}  ({sum(len(s.split()) for s in says)} words)")
            for k, s in enumerate(says, 1):
                w = len(s.split())
                print(f"   {pos((n, k))}  " + (f"{w:3d} w{'  LONG' if w > LONG else ''}  {s}" if s else "  (silent step)"))
        return print(f"\n{len(deck)} slides, {len(sentences)} sentences, {words} words, about {words / WPM:.1f} min at {WPM} words "
                     "per minute.\nYour own reading: record each sentence as media/voices/NAME/03.2.wav (.mp3, .ogg, .flac), "
                     "then --import-voice=NAME")
    if layer:
        if not html.exists():
            sys.exit(f"no {html.name}: build the slides first (sh build.sh)")
        if v := opts.get("--voice"):
            own = c["voice"] == v
            cv = c | dict(voice=v, speed=float(opts["--speed"]) if opts.get("--speed") else c["speed"],
                          lang=opts.get("--lang") or (c["lang"] if own else LANG.get(v[0], "en-us")))
            made, secs = speech(sentences, cv)
            print(f"voice {made}: {len(sentences)} sentences, {secs / 60:.1f} min of speech")
        if v := opts.get("--import-voice"):
            import_voice(v, steps)
        names = index()
        if "--bundle" in opts:
            own = c["voice"] and (c["voice"] if kind(VOICES / c["voice"]) == "recorded" else folder(c))
            if what != "clips" and not (other or own):
                sys.exit(f"--bundle={what}: the talk has no voice of its own (voice: false): name one, --bundle={what}:NAME")
            bundle("none" if what == "clips" else other or own, html, what != "voice")
        for n in names:
            if n != opts.get("--import-voice") and (m := lacks(n, sentences)):  # (an import says which itself; None: unreadable, reported)
                print(f"voice {n} lacks {len(m)} of {len(sentences)} sentences, which run silently with it")
        if "--no-check" not in opts:
            check(html, est)
        return
    manifest(c, name)
    made = need = None
    if c["voice"] and "--no-voice" not in opts and kind(VOICES / c["voice"]) == "recorded":
        made, m = c["voice"], lacks(c["voice"], sentences)  # your own reading: nothing to speak
        print(f"voice {made} (your recording)" + (f": {len(m)} sentences to record (--script, --import-voice)" if m else "")
              + f"; theme {name}", flush=True)
    elif c["voice"] and "--no-voice" not in opts:
        made, secs = speech(sentences, c)
        need = made  # (the check fails if the voice it just spoke lacks a step)
        secs += len(sentences) * c["gap"] + len(deck) * (c["lead"] + c["tail"])
        print(f"speech: {len(sentences)} sentences, {secs / 60:.1f} min with pauses, voice {made}; theme {name}", flush=True)
    else:
        print(f"no voice spoken: about {est / 60:.1f} min at {WPM} words per minute; theme {name}", flush=True)
    index()
    subprocess.run([shutil.which("quarto"), "render", qmd.name], check=True)  # (which: quarto.cmd on Windows)
    if "--no-check" not in opts or "--shots" in opts or "--themes" in opts:
        log = check(html, est, need=need)
        if "--themes" in opts:
            for t in PALETTES:
                if t != name:
                    check(html, est, t)
        if "--shots" in opts:
            shots(html, log, opts["--shots"] == "all", opts.get("--size") or "1280x720")
    print(f"talk: {html}  ({html.stat().st_size / 1e6:.1f} MB, the slides; the voices are in {VOICES}/)")
    e = c["embed"]  # a one-file copy: the voice inside (0.4.0's embed: true), the clips, or both
    if e == "clips":
        bundle("none", html, True)
    elif e and made:
        bundle(made, html, e == "both")
    elif e:
        print(f"  embed: {e}: no one-file copy written, since this build spoke no voice (--bundle={e} writes it from a voice made before)")
    if made and e in (None, "clips"):  # (until 0.4.0 talk.html carried the speech by default; now it never does)
        print(f"  {html.name} holds no voice: send it with {MEDIA}/, or one file with --bundle=voice (--bundle=both: its clips inside too)")


if __name__ == "__main__":
    if os.name == "nt" and not sys.flags.utf8_mode:  # Windows reads and writes text in its own code page otherwise
        sys.exit(subprocess.run([sys.executable, "-X", "utf8", *sys.argv]).returncode)
    main()
