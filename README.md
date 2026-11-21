# sci-narrated-talk

A scientific talk that tells itself: a Quarto + reveal.js deck in which a synthetic
voice narrates every slide, sentence by sentence, while the slide builds. The result is
one HTML page that opens offline. The viewer can let it run like a video, or steer it
like a deck.

![The starter talk playing, with the outline open](docs/player.png)

`SKILL.md` tells Claude how to make such a talk. This file explains what the skill
contains, how the pieces fit, and what has and has not been tested.

## Why not a video

`sci-video-talk` renders the same kind of talk to an `.mp4`. A video is a recording of
a sequence of events; this skill ships the sequence itself.

| | video (`sci-video-talk`) | narrated talk (this skill) |
|---|---|---|
| the viewer can | play, pause, scrub | also step by sentence, jump by slide or outline, replay the sentence behind an element, zoom, select and copy text, switch the voice off |
| a slide is | pixels | text, KaTeX, inline SVG, clips |
| size of a static slide | about 1 MB per slide, mostly sound | its sound only, about 8 kB per second |
| after a text change | re-render the scene | speak the changed sentences, render the page: seconds |
| plays in | any video player | a browser |

Use the video when the talk must play in a video player or on a platform that takes
only video. Use the narrated talk otherwise.

## Quick start

```sh
skill=~/.claude/skills/sci-narrated-talk
cp -rL --no-preserve=mode $skill/assets/talk mytalk
cp -L --no-preserve=mode $skill/scripts/narrate.py mytalk/
cp -rL --no-preserve=mode $skill/../sci-talk/assets/quarto-deck/theme mytalk/
cd mytalk
uv run --no-project --with kokoro-onnx --with soundfile --with pyyaml --with matplotlib --with pillow \
    python narrate.py --shots
chromium talk.html
```

The copies need `-L` because the installed skill is a tree of read-only links into the
Nix store. The first build downloads the voice model (340 MB) to `~/.cache/kokoro/`.
The starter is a six-slide talk about a random walk, 1.4 minutes, 6 MB as one file.

## How a talk is written

Slides and narration live in one `talk.qmd`. A `::: say` block is one spoken sentence;
what follows it appears when it starts.

```markdown
## The walkers spread in proportion to time

::: {.columns}
::: {.column width="56%"}
{{< include build/fig/msd.html >}}
:::

::: {.column width="44%"}
::: say
Here is the mean squared displacement of our {{< meta v.walkers >}} walkers, against time.
:::

- Blue: the average over {{< meta v.walkers >}} walkers

::: {.say point="#msd-fit"}
A straight line fits it. Its slope gives a diffusion constant of {{< meta v.D >}}.
:::

- Orange: a straight line through the origin
:::
:::
```

Numbers and drawings come from `figures.py`, which the build runs first:

```python
values(D=f"{D:.2f}", walkers=WALKERS)            # quoted as {{< meta v.D >}}
ax.plot(t, msd, "o", gid="points")               # on the slide from the start
ax.plot(t, slope * t, gid="s2-fit")              # appears with sentence 2; id "msd-fit"
figure(fig, "msd")                               # inline SVG, build/fig/msd.html
```

So the second sentence above brings in the fitted line and its bullet, and a ring
closes in on the line. Every number is computed once and used by the slide, the figure
and the voice alike. `references/authoring.md` has the full syntax.

## The player

| key | does | | mouse | does |
|---|---|---|---|---|
| space | play / pause | | timeline | click a slide to jump to it |
| ← → | previous / next slide | | outline | click a line to play from there |
| ↑ ↓ | previous / next sentence | | Alt+click | replay the sentence that introduced the element |
| C | captions | | Ctrl+click | zoom in and out |
| T | outline | | click, drag | select text |
| M | voice on / off | | | |
| A | auto-advance on / off | | | |
| X | hide / show the bar | | | |
| ? | help | | | |

- The bar lies over the foot of the slide and fades while the talk plays and the mouse
  rests. Each button prints its key.
- The timeline has one segment per slide, as wide as the slide is long, grouped and
  labelled by section. In a narrow window it falls back to one segment per section, and
  on a phone to none.
- The outline lists sections, slides and the sentences of the current slide, with start
  times.
- With the voice off the talk runs on silently at the same pace; with auto-advance off
  it waits at the end of each slide.
- The address bar shows `#slide.sentence`; such a link opens the talk there.
- Keys with Ctrl, Alt or Meta are left to the browser, and every other reveal.js key
  keeps its meaning. In the speaker view (S) the notes are the slide's narration and
  the previews stay silent.

## What is in the skill

```
sci-narrated-talk/
├── SKILL.md                      # the instructions Claude follows
├── README.md                     # this file
├── docs/player.png
├── references/authoring.md       # say blocks, figures, numbers, clips, settings, player, failures
├── scripts/narrate.py            # the build: figures, speech, manifest, render, check, screenshots
└── assets/talk/                  # the starter talk
    ├── talk.qmd                  # slides and narration
    ├── figures.py                # numbers and drawings
    ├── .gitignore
    └── _extensions/narrate/      # the reveal.js plugin (Quarto extension)
        ├── _extension.yml
        ├── narrate.js            # player, timeline, outline, pointers, growing paths
        └── narrate.css
```

The theme is not duplicated here: a talk copies `sci-talk`'s `ehsan-sci-theme.scss`.

## How it works

1. **`figures.py`** writes `build/values.yml` and `build/fig/*.html`. A figure is
   matplotlib's SVG with its ids made unique per figure; a part named
   `gid="s2-fit"` is turned into a reveal.js fragment that belongs to sentence 2.
2. **Speech.** `narrate.py` collects the `say` sentences in document order and speaks
   each one with Kokoro into `media/audio/<name>.mp3`. The name is a hash of the voice,
   the speed and the text as spoken, so unchanged sentences are never spoken twice.
3. **Manifest.** `media/manifest.js` lists, per sentence, the audio (inside the file
   as base64, or a path), its length, and its letters and digits. The lengths are the
   talk's clock.
4. **Render.** `quarto render` builds `talk.html` with everything embedded.
5. **In the browser**, the plugin turns each slide's `say` blocks into hidden reveal.js
   fragments and makes what follows a block a fragment with the same index. Reveal's
   own position (slide, fragment) is therefore always "sentence k of slide n", and the
   plugin only has to play the right audio file and advance. It compares each
   sentence's text with the manifest and says so on the start overlay when the page
   was rendered with older narration.
6. **Check.** `narrate.py` opens the page in headless Chromium with the network cut and
   `?fast` (no sound, 50 times the speed), and fails the build unless every sentence
   was reached in order, every equation is rendered, nothing reaches outside its slide,
   nothing stays hidden, and nothing is loaded from a URL.

## Requirements

- `uv` (the Python packages are fetched per run: `kokoro-onnx`, `soundfile`, `pyyaml`,
  `matplotlib`, optionally `pillow` for contact sheets)
- Quarto 1.4 or newer (built and tested with 1.10.19)
- Chromium or Chrome on the PATH, for the check and the screenshots only
- no ffmpeg, no node, no network after the first download of the voice model

## Tested

On the starter talk and on variants of it, in headless Chromium on Linux:

- the build from the copied starter, end to end, and the check passing offline;
- real playback: audio time advances, sentences and slides follow, the path grows with
  the voice, the pointer lands on its SVG target;
- Alt+click on a figure part replays its sentence; the outline and the timeline follow;
- a clip running on the slide's clock, a silent step, a slide without narration;
- speech inside the page and speech in files beside it;
- the check failing on purpose: content hidden behind the author's own pause, and
  narration changed after the last build.

The player itself (bar, timeline, outline, keys, zoom, speaker-view silence) was
developed on a 22-slide, 15-minute research talk before it was generalised here.

## Not tested, not built

- **By ear.** Nobody has to have listened for the check to pass. Say so in a report.
- **Other browsers.** Firefox, Safari and touch devices are untried.
- **The speaker view as a real window.** Its previews were tested as pages, not as the
  pop-up reveal.js opens.
- **A long talk as one file.** The starter is 6 MB, of which about 5 MB is the empty
  deck. Fifteen minutes of speech add about 10 MB; that size is an estimate.
- **A recorded voice or another speech engine.** The file-by-file replacement is
  described in `references/authoring.md` and follows from how files are named; it has
  not been run with another engine.
- **Video export.** Recording the page to an `.mp4` is the planned next step, so that
  the talk becomes the single source of both forms. Until then, a video is made with
  `sci-video-talk`.
- **The video engine's colour themes.** The look is a Quarto theme. Figures and clips
  carry their own colours, so a different theme restyles the text only.
- **Vertical slide stacks beyond section dividers**, a two-voice dialogue, music.
