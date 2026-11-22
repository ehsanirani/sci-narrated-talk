"""Record a narrated talk to a video (the sci-narrated-talk skill): any built talk.html whose player is 0.3.0 or later.

    nix shell nixpkgs#ffmpeg -c uv run --no-project --with soundfile --with numpy --with pillow python record.py talk.html

Writes talk.mp4 beside the page (h264 and aac, with the captions as a subtitle track and one chapter per slide) and
talk.srt. The recording is not a screen capture in real time. The page, opened with ?rec, is the talk as a function of
time: for every frame the browser is put at that instant (slide, sentence, fades, pointers, growing lines), and it is
photographed only when what it shows has changed. The browser never draws a clip: where one shows, the page is
photographed twice, with its clips black and with them white, which tells how much of a clip shows at each point
(under a pointer, in a fade), and the clip's frame for that instant is decoded from its file by ffmpeg and put there.
The sound is the talk's own sentence files, laid on the talk's clock. So the video does not depend on how fast the
machine is.

  --size=1920x1080   the picture (default: the size the deck is laid out for, read from the page)
  --fps=25           frames per second
  --from=S --to=S    only this stretch of the talk, in seconds (for a trial)
  --theme=NAME       record in that theme
  --voice=NAME       record with that voice (default: the one the talk opens with; a page of 0.5.0 or later)
  --crf=20           x264 quality (lower is better and larger)
  -o FILE            the output file, .mp4 (default: beside the page, under its name)

What the video does not keep: everything the viewer does with the page (stepping, the outline, replaying a sentence,
zoom, selecting text, switching the theme or the voice). The page plays a sentence for as long as its file lasts and
the video for the length the build measured; the two differ by less than a frame per sentence. A talk with no voice is
not recorded: it is a deck to present by hand. A sentence the voice lacks is silent in the video, on its estimated
length, as on the page.
Needs ffmpeg and chromium (or google-chrome) on the PATH, and narrate.py beside this file.
"""

import base64
import io
import math
import re
import shutil
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import narrate  # noqa: E402  (the driven browser)

OPTS = {"--size", "--fps", "--from", "--to", "--crf", "--theme", "--voice"}


def stamp(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def sound(steps, total, base, path, t0, t1):
    """The talk's sound track from t0 to t1: every sentence file at its start on the talk's clock."""
    import numpy as np
    import soundfile

    sr, pcm = None, None
    for st in steps:
        if not st["src"]:
            continue
        f = base / unquote(st["src"])  # (a path relative to the page, as a URL)
        if not st["src"].startswith("data:") and not f.is_file():
            sys.exit(f"the speech of slide {st['slide']}, sentence {st['sentence']} is missing: {f}")
        raw = base64.b64decode(st["src"].split(",", 1)[1]) if st["src"].startswith("data:") else f.read_bytes()
        a, r = soundfile.read(io.BytesIO(raw), dtype="float32", always_2d=True)
        if pcm is None:
            sr, pcm = r, np.zeros(int((total + 1) * r), dtype="float32")
        elif r != sr:
            sys.exit(f"the sentence files have different sample rates ({sr} and {r})")
        i = int(round(st["start"] * sr))
        a = a.mean(axis=1)[:len(pcm) - i]
        pcm[i:i + len(a)] += a
    if pcm is None:
        return None
    pcm = pcm[int(round(t0 * sr)):int(round(t1 * sr))]
    ramp = np.linspace(0, 1, min(len(pcm), int(0.01 * sr)), dtype="float32")  # a cut inside a sentence must not click
    pcm[:len(ramp)] *= ramp
    pcm[len(pcm) - len(ramp):] *= ramp[::-1]
    soundfile.write(path, pcm, sr)
    return path


def load(b, html, theme, sized, voice=None):
    """Open the talk in its record mode; returns its timeline."""
    b.call("Page.navigate", url=html.as_uri() + "?rec" + (f"&theme={theme}" if theme else "") + (f"&narrator={quote(voice)}" if voice else ""))
    if not b.js("new Promise(r => { let n = 0; (function w() {"  # the player says so when it is ready; a page without one never does
                " window.narrate ? r(1) : (n += document.readyState === 'complete' && !!(window.Reveal?.isReady() ?? 1)) > 40 ? r(0)"
                " : setTimeout(w, 50); })(); })"):
        sys.exit(f"{html.name} has no record mode: its player is older than 0.3.0, or it is not a narrated talk")
    if not sized:  # the size the deck is laid out for
        w, h = b.js("[Reveal.getConfig().width, Reveal.getConfig().height]")
        b.call("Emulation.setDeviceMetricsOverride", width=int(w), height=int(h), deviceScaleFactor=1, mobile=False)
    b.js("Promise.all([...document.fonts].map(f => f.load().catch(() => 0))).then(() => 1)")  # also those of later slides
    # a clip draws nothing, black or white, until the browser has its first frame
    bad = b.js("(async () => { const vs = [...document.querySelectorAll('.reveal .slides video')];"
               " await Promise.all(vs.map(v => v.readyState >= 2 || new Promise(r => { v.addEventListener('loadeddata', r);"
               " v.addEventListener('error', r); setTimeout(r, 20000); })));"
               " return vs.filter(v => v.readyState < 2).map(v => v.getAttribute('src') || 'a clip without src'); })()")
    if bad:
        sys.exit(f"the browser could not load {', '.join(bad)}")
    return b.js("narrate.timeline()")


def shot(b, white=()):
    """The page as it is, its clips black and those numbered in white white: a height x width x 3 array."""
    import numpy as np
    from PIL import Image

    b.js(f"document.querySelectorAll('.reveal .slides video').forEach((v, i) => v.toggleAttribute('data-white', {list(white)}.includes(i)))")
    png = base64.b64decode(b.call("Page.captureScreenshot", format="png", optimizeForSpeed=True)["data"])  # lossless
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))


def box(c):
    """The whole pixels that the picture of the clip c touches: left, top, right, bottom."""
    return math.floor(c["x"] + 0.01), math.floor(c["y"] + 0.01), math.ceil(c["x"] + c["w"] - 0.01), math.ceil(c["y"] + c["h"] - 0.01)


def clip_frame(decs, c, w, h):
    """The picture of the clip c (as seek() lists it) at its time, w x h: ffmpeg decodes the file, and the frames are
    read in order for as long as the time runs on; a jump (a loop, another size) starts ffmpeg again at that frame."""
    import numpy as np

    d = decs.setdefault(c["id"], {})
    if not d:
        u = urlparse(c["src"])
        if u.scheme != "file" or not Path(unquote(u.path)).is_file():
            sys.exit(f"a clip has to be a file beside the page, for ffmpeg to read: {c['src'][:80]}")
        got = dict(x.split("=") for x in subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
             "stream=avg_frame_rate,nb_read_packets", "-of", "default=nw=1", unquote(u.path)], capture_output=True, text=True).stdout.split())
        d.update(path=unquote(u.path), fps=float(Fraction(got["avg_frame_rate"])), n=int(got["nb_read_packets"]), i=-1, size=None, p=None)
    want = min(int(c["t"] * d["fps"] + 1e-3), d["n"] - 1)  # past the end the last frame stays, as on the page
    if d["size"] != (w, h) or not d["i"] <= want <= d["i"] + 50:
        if d["p"]:
            d["p"].kill(), d["p"].wait()
        at = ["-ss", f"{(want - 0.5) / d['fps']:.6f}"] if want else []  # ffmpeg drops what is before: the first frame out is `want`
        d.update(size=(w, h), i=want - 1, p=subprocess.Popen(
            ["ffmpeg", "-v", "error", *at, "-i", d["path"], "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE))
    while d["i"] < want:
        raw = d["p"].stdout.read(w * h * 3)
        if len(raw) < w * h * 3:
            sys.exit(f"ffmpeg could not read frame {d['i'] + 1} of {d['path']}")
        d["frame"], d["i"] = np.frombuffer(raw, np.uint8).reshape(h, w, 3), d["i"] + 1
    return d["frame"]


def main():
    argv = sys.argv[1:]
    out = Path(argv.pop(argv.index("-o") + 1)) if "-o" in argv[:-1] else None
    opts = dict(a.split("=", 1) if "=" in a else (a, "") for a in argv if a.startswith("--"))
    args = [a for a in argv if not a.startswith("-")]
    if len(args) != 1 or set(opts) - OPTS:
        sys.exit((f"unknown option {sorted(set(opts) - OPTS)}\n" if set(opts) - OPTS else "") + __doc__)
    html = Path(args[0]).resolve()
    out = out or html.with_suffix(".mp4")
    if not html.is_file():
        sys.exit(f"no such page: {html}")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg is not on the PATH (on NixOS: nix shell nixpkgs#ffmpeg -c ...)")
    import numpy as np

    fps, t0, size, theme, voice = (float(opts.get("--fps") or 25), float(opts.get("--from") or 0), opts.get("--size"),
                                   opts.get("--theme"), opts.get("--voice"))
    if size and not re.fullmatch(r"\d+x\d+", size):
        sys.exit(f"--size={size}: width x height, as in 1920x1080")
    began, tmp, decs, enc, shots = time.time(), Path(tempfile.mkdtemp()), {}, None, 0
    b = narrate.Browser(size or "1920x1080")
    try:
        tl = load(b, html, theme, size, voice)
        if theme and theme not in tl["themes"]:
            sys.exit(f"--theme={theme}: this talk has {', '.join(tl['themes'])}")
        if "voice" not in tl:  # a page of 0.4.0 or earlier: its one voice is the one the build put inside it
            if voice:
                sys.exit(f"--voice={voice}: this page's player is older than 0.5.0 and has only the voice it was built with")
        elif voice not in (None, tl["voice"]) or tl["voice"] == "none":
            has = f"its voices: {', '.join(tl['voices'])}" if tl["voices"] else "it has none; sh build.sh --voice=af_heart makes one"
            if voice not in (None, "none"):
                sys.exit(f"--voice={voice}: this talk has no such voice; {has}")
            if not tl["voices"]:
                sys.exit(f"no voice to record with: {has}")
            sys.exit(f"{'--voice=none' if voice else 'this talk opens with no voice'}: a talk without a voice is a deck to "
                     f"present by hand, not a video. Record it with one of {has}")
        elif tl["lacks"]:
            print(f"voice {tl['voice']} lacks {tl['lacks']} sentences: they are silent in the video (the slides changed after it was made)")
        t1 = min(float(opts.get("--to") or 1e9), tl["total"])
        if not 0 <= t0 < t1:
            sys.exit(f"--from={t0:g} --to={t1:g}: the talk runs from 0 to {tl['total']:.1f} s")
        n = int(round((t1 - t0) * fps))
        wav = sound(tl["steps"], tl["total"], html.parent, tmp / "sound.wav", t0, t1)

        # chapters (one per slide) and subtitles (one per spoken sentence), on the recording's own clock
        esc = lambda s: re.sub(r"([=;#\\\n])", r"\\\1", s)  # noqa: E731
        slides = {}
        for st in tl["steps"]:
            slides.setdefault(st["slide"], st)
        starts = [(min(t1, max(t0, st["slideStart"])) - t0, st["heading"] or f"Slide {j}") for j, st in slides.items()]
        meta = ";FFMETADATA1\ntitle=" + esc(tl["title"]) + "\n"
        for (a, name), (z, _) in zip(starts, starts[1:] + [(t1 - t0, "")]):
            if z > a:
                meta += f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(a * 1000)}\nEND={int(z * 1000)}\ntitle={esc(name)}\n"
        (tmp / "meta.txt").write_text(meta)
        subs = [(max(t0, st["start"]) - t0, min(t1, st["start"] + st["dur"]) - t0, st["text"]) for st in tl["steps"]
                if st["text"] and st["start"] < t1 and st["start"] + st["dur"] > t0]
        srt = out.with_suffix(".srt")
        if subs:
            srt.write_text("".join(f"{i}\n{stamp(a)} --> {stamp(z)}\n{text}\n\n" for i, (a, z, text) in enumerate(subs, 1)))

        last = None
        for i in range(n):
            st = b.js(f"narrate.seek({t0 + (i + 0.5) / fps!r})")  # the middle of the frame's time
            if not st:
                sys.exit(f"the page did not answer at second {t0 + i / fps:.2f}")
            if st["sig"] != last:  # the page shows something new: photograph it
                last, shots, solid, alpha, black = st["sig"], shots + 1, {}, {}, shot(b)
                plain, (H, W) = black.tobytes(), black.shape[:2]
                # How much of a clip shows at each point, 0 to 255: what turns white when the clip does. One photograph
                # for all clips, or one for each where two overlap (a slide with a clip fading into another with one).
                ids, bs = [c["id"] for c in st["clips"]], [box(c) for c in st["clips"]]
                apart = all(p[2] <= q[0] or q[2] <= p[0] or p[3] <= q[1] or q[3] <= p[1] for j, p in enumerate(bs) for q in bs[:j])
                for g in ([ids] if apart else [[j] for j in ids]) if ids else []:
                    alpha.update(dict.fromkeys(g, (shot(b, g).astype("int16") - black).clip(0, 255).astype("uint16")))
            if enc is None:
                ins = [x for x in (wav, srt if subs else None, tmp / "meta.txt") if x]
                cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", f"{fps:g}", "-i", "-"]
                for x in ins:
                    cmd += ["-i", str(x)]
                cmd += ["-map", "0:v"] + (["-map", "1:a"] if wav else []) + (["-map", f"{len(ins) - 1}:s"] if subs else [])
                cmd += ["-map_metadata", str(len(ins)), "-map_chapters", str(len(ins)),
                        "-vf", "crop=trunc(iw/2)*2:trunc(ih/2)*2,scale=out_color_matrix=bt709:out_range=tv", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", opts.get("--crf") or "20", "-preset", "medium", "-colorspace", "bt709",
                        "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv", "-c:a", "aac", "-b:a", "128k",
                        "-ar", "48000", "-c:s", "mov_text", "-movflags", "+faststart", str(out)]
                enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            frame = plain
            if alpha:  # the frame is the page with its clips black, plus each clip's picture as far as it shows
                frame = black.copy()
                for c in st["clips"]:
                    x0, y0, x1, y1 = box(c)
                    X0, Y0, X1, Y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)  # the part of the box inside the picture
                    if X1 <= X0 or Y1 <= Y0:
                        continue
                    at = (slice(Y0, Y1), slice(X0, X1))
                    pic, a = clip_frame(decs, c, x1 - x0, y1 - y0)[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0], alpha[c["id"]][at]
                    if c["id"] not in solid:  # nothing over the clip and no fade: its picture as it is
                        solid[c["id"]] = bool(a.min() == 255)
                    frame[at] = pic if solid[c["id"]] else np.minimum(frame[at] + (a * pic + 127) // 255, 255)
                frame = frame.data
            try:
                enc.stdin.write(frame)
            except BrokenPipeError:
                sys.exit("ffmpeg failed")
            if (i + 1) % int(60 * fps) == 0:
                print(f"  {(i + 1) / fps / 60:5.1f} of {n / fps / 60:.1f} min recorded, {time.time() - began:.0f} s", flush=True)
        enc.stdin.close()
        if enc.wait():
            sys.exit("ffmpeg failed")
    finally:
        b.close()
        for p in [enc] + [d["p"] for d in decs.values()]:
            if p and p.poll() is None:
                p.kill(), p.wait()
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"video: {out}  ({out.stat().st_size / 1e6:.1f} MB, {int(n / fps // 60)}:{n / fps % 60:04.1f}, {n} frames of which {shots} "
          f"photographed, {time.time() - began:.0f} s)" + (f"\nsubtitles: {srt}" if subs else ""))


if __name__ == "__main__":
    main()
