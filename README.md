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
cd mytalk
uv run --no-project --with kokoro-onnx --with soundfile --with pyyaml --with matplotlib --with pillow \
    python narrate.py --shots
chromium talk.html
```

The copies need `-L` because the installed skill is a tree of read-only links into the
Nix store. The first build downloads the voice model (340 MB) to `~/.cache/kokoro/`.
The starter is a four-slide talk about a random walk, the twin of the video skill's
starter: 1.3 minutes, 6.8 MB as one file.

## How a talk is written

Slides and narration live in one `talk.qmd`. A `::: say` block is one spoken sentence;
what follows it appears when it starts.

```markdown
## The walkers spread in proportion to time {#result sec="The measurement"}

:::: {.beside}
::: {.fig}
{{< include build/fig/msd.html >}}
:::

::::: {.text}
::: say
Here is the mean squared displacement of our {{< meta v.walkers >}} walkers, against time.
:::

- Points: the average over {{< meta v.walkers >}} walkers

::: {.say point="#msd-fit"}
A straight line fits it. Its slope gives a diffusion constant of {{< meta v.D >}}.
:::

- Line: a least-squares fit through the origin

::: {.takeaway}
The slope returns the D we put in
:::
:::::
::::
```

Numbers and drawings come from `figures.py`, which the build runs first:

```python
values(D=f"{D:.2f}", walkers=WALKERS)                   # quoted as {{< meta v.D >}}
fig = plt.figure(figsize=FIG); ax = fig.add_axes(PLOT)  # the figure box of the layout
ax.plot(t, msd, "o", color=C.blue, gid="points")        # on the slide from the start
ax.plot(t, slope * t, color=C.accent, gid="s2-fit")     # appears with sentence 2; id "msd-fit"
figure(fig, "msd")                                      # inline SVG, build/fig/msd.html
```

So the second sentence brings in the fitted line and its bullet, and a ring closes in on
the line. Every number is computed once and used by the slide, the figure and the voice
alike. `references/authoring.md` has the full syntax.

## The video's look, to the pixel

`.beside` above is one of the layouts that copy the scenes of the `sci-video-talk`
engine: the title card, the divider, a figure beside staged bullets, bullets only, the
takeaway box, the note at the foot. The theme takes every position and size from the
engine's code, and text sizes and wrap widths are available by the engine's own numbers
(`.s24`, `.w40`). The player draws the frame inside the slide: section, talk title,
"n / N" and the progress bar.

Measured on the starter, whose video twin exists: the title, its rule, the plot's axes
and labels, the bullets, the note and the footer sit within 3 px of the video frame at
1920 x 1080, and the takeaway box within 5 px.

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
| Y | next theme | | | |
| X | hide / show the bar | | | |
| # | slide number on / off | | | |
| R, then a key | that key as reveal.js has it (R ? its keys, R M its menu) | | | |
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
- The talk handles its keys before reveal.js and does not enter them in its table, so
  every other reveal.js key keeps its meaning and R reaches the shadowed ones. Keys
  can be renamed or freed in the front matter; keys with Ctrl, Alt or Meta are left to
  the browser. In the speaker view (S) the notes are the slide's narration and
  the previews stay silent.

## Themes

![One build of the starter, switched through the nine themes in the browser](docs/themes.png)

The look is the frame of the `sci-video-talk` videos: the title bar with its accent
rule, accent bullets, the boxed takeaway, the note at the foot, a footer with section,
talk title and slide number, and the progress bar along the bottom edge. The themes
are that skill's nine: `light` (default), `dark`, `paper`, `sci-talk`, `sea`,
`journal`, `chalk`, `midnight`, `contrast`.

`narrate: theme:` in the front matter sets the theme the talk opens in, by name or as
colours of your own on a base (`{base: light, accent: "#0b7285"}`). All of them travel
in the page: the viewer goes to the next one with the Y key or the bar's theme button,
at any moment and without interrupting the voice, and `?theme=dark` opens in one. The
picture above is a single build.

This works because a theme has no style rules. `theme/narrated-talk.scss` holds the
layout, and every colour in it is a name (`var(--accent)`, `var(--ink)`, ...). A theme
is the nine values behind those names: eight colours and the font. `figures.py` draws
with the same names (`C.blue`, `C.accent`), and the build writes them into each SVG as
names instead of fixed colours, so text, equations and drawn figures change together.
The fonts are carried inside the talk. Clips and pasted images keep their own colours.

## What is in the skill

```
sci-narrated-talk/
├── SKILL.md                      # the instructions Claude follows
├── README.md                     # this file
├── docs/                         # the two pictures of this file
├── references/authoring.md       # say blocks, figures, numbers, clips, settings, player, failures
├── scripts/narrate.py            # the build: figures, speech, manifest, render, check, screenshots
└── assets/talk/                  # the starter talk
    ├── talk.qmd                  # slides and narration
    ├── figures.py                # numbers and drawings
    ├── .gitignore
    ├── theme/narrated-talk.scss  # the videos' frame and scene layouts; every colour is a name a theme gives a value
    └── _extensions/narrate/      # the reveal.js plugin (Quarto extension)
        ├── _extension.yml
        ├── narrate.js            # player, timeline, outline, pointers, growing paths
        └── narrate.css
```

## How it works

1. **Theme.** `narrate.py` resolves `narrate: theme:` to eight colours and a font,
   checks their contrast, and writes `build/theme.scss`: the values the page opens
   with, and the fonts of all themes. The values of every theme go into the manifest.
2. **`figures.py`** writes `build/values.yml` and `build/fig/*.html`. A figure is
   matplotlib's SVG with its ids made unique per figure; a part named
   `gid="s2-fit"` is turned into a reveal.js fragment that belongs to sentence 2.
3. **Speech.** `narrate.py` collects the `say` sentences in document order and speaks
   each one with Kokoro into `media/audio/<name>.mp3`. The name is a hash of the voice,
   the speed and the text as spoken, so unchanged sentences are never spoken twice.
4. **Manifest.** `media/manifest.js` lists, per sentence, the audio (inside the file
   as base64, or a path), its length, and its letters and digits. The lengths are the
   talk's clock.
5. **Render.** `quarto render` builds `talk.html` with everything embedded.
6. **In the browser**, the plugin turns each slide's `say` blocks into hidden reveal.js
   fragments and makes what follows a block a fragment with the same index. Reveal's
   own position (slide, fragment) is therefore always "sentence k of slide n", and the
   plugin only has to play the right audio file and advance. It compares each
   sentence's text with the manifest and says so on the start overlay when the page
   was rendered with older narration.
7. **Check.** `narrate.py` opens the page in headless Chromium with the network cut and
   `?fast` (no sound, 50 times the speed), and fails the build unless every sentence
   was reached in order, every equation is rendered, nothing reaches outside its slide,
   nothing stays hidden, and nothing is loaded from a URL.

## Requirements

- `uv` (the Python packages are fetched per run: `kokoro-onnx`, `soundfile`, `pyyaml`,
  `matplotlib`, optionally `pillow` for contact sheets)
- Quarto 1.4 or newer (built and tested with 1.10.19)
- Chromium or Chrome on the PATH, for the check and the screenshots only
- the theme's font installed on the build machine (Source Sans 3; IBM Plex Serif for
  `journal`); without it the talk falls back to the viewer's system font
- no ffmpeg, no node, no network after the first download of the voice model

## Tested

On the starter talk and on variants of it, in headless Chromium on Linux:

- the build from the copied starter, end to end, and the check passing offline;
- real playback: audio time advances, sentences and slides follow, the path grows with
  the voice, the pointer lands on its SVG target;
- Alt+click on a figure part replays its sentence; the outline and the timeline follow;
- a clip running on the slide's clock, a silent step, a slide without narration;
- speech inside the page and speech in files beside it;
- all nine themes from one build, switched in the browser: slides, figures, outline
  and font follow, the voice plays on, and the embedded fonts load with the network cut;
- a custom accent, and a custom theme refused for low contrast;
- the check failing on purpose: content hidden behind the author's own pause, and
  narration changed after the last build.

The player itself (bar, timeline, outline, keys, zoom, speaker-view silence) was
developed on a 22-slide, 15-minute research talk before it was generalised here.

## Not tested, not built

- **By ear.** Nobody has to have listened for the check to pass. Say so in a report.
- **Other browsers.** Firefox, Safari and touch devices are untried.
- **The speaker view as a real window.** Its previews were tested as pages, not as the
  pop-up reveal.js opens.
- **A long talk as one file.** The starter is 6.8 MB, of which about 5.5 MB is the
  empty deck with its fonts. Fifteen minutes of speech add about 10 MB; that size is an estimate.
- **A recorded voice or another speech engine.** The file-by-file replacement is
  described in `references/authoring.md` and follows from how files are named; it has
  not been run with another engine.
- **Video export.** Recording the page to an `.mp4` is the planned next step, so that
  the talk becomes the single source of both forms. Until then, a video is made with
  `sci-video-talk`.
- **Themes on clips and pasted images.** They keep their own colours.
- **Every slide in every theme.** Two slides per theme were looked at.
- **Vertical slide stacks beyond section dividers**, a two-voice dialogue, music.
