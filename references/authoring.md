# Authoring a narrated talk

Everything the author writes lives in two files: `talk.qmd` (slides and narration) and
`figures.py` (numbers and drawings). The starter in `assets/talk/` uses every feature
below once.

## Contents

- [The say block](#the-say-block)
- [The title slide, sections, silent steps](#the-title-slide-sections-silent-steps)
- [Pointers and growing paths](#pointers-and-growing-paths)
- [Numbers: `values()`](#numbers-values)
- [Figures: `figure()`](#figures-figure)
- [Clips and images](#clips-and-images)
- [Front matter](#front-matter)
- [The player](#the-player)
- [A recorded voice or another speech engine](#a-recorded-voice-or-another-speech-engine)
- [What is cached, what is rebuilt](#what-is-cached-what-is-rebuilt)
- [When something fails](#when-something-fails)

## The say block

```markdown
## The walkers spread in proportion to time

::: say
Here is the mean squared displacement of our walkers, against time.
:::

- Blue: the average over all walkers

::: say
A straight line fits it.
:::

- Orange: a straight line through the origin
```

- One block is one sentence of narration (two short sentences that belong together are
  fine). The block itself is never shown; with captions on, its text is the caption.
- **What follows a block, up to the next block, appears when that sentence starts.**
  What follows the first block is on the slide from the start, and so is everything
  above it.
- Blocks work inside columns and other containers. Inside a column, "what follows"
  means the following siblings in that column.
- A sentence that reveals nothing still gets its block, where it belongs in the order.
- Keep markup out of the sentence: `*`, `_` and backticks are stripped before speech,
  math and backslashes are refused by the build.

## The title slide, sections, silent steps

- **Title slide.** Quarto builds it from the front matter, so its narration is given
  there, sentences separated by `|`:

  ```yaml
  title-slide-attributes:
    data-say: "First sentence.|Second sentence."
  ```

- **Sections.** A `#` heading makes a divider slide and names the section for the
  timeline, the outline and the slide footer. A slide can override it with
  `{sec="Name"}` on its heading. Narrate the divider with a short `say` block under it.
- **A silent step**: an empty block, `::: {.say wait="2" label="The axes appear"}`
  closed by `:::` on the next line. It lasts `wait` seconds (default 3) and what follows
  it appears in silence. `label` is its name in the outline; without one the outline
  uses the text it reveals.
- **A slide without any block** is one silent step of 3 seconds.

## Pointers and growing paths

Attributes of a `say` block:

| attribute | effect |
|---|---|
| `point="#id"` | a ring closes in on that element when the sentence starts. Any element with an id: a `::: {#id}` div, a named part of a figure |
| `grow="#id"` | that SVG line is drawn from start to end while the sentence is spoken (a trajectory, a curve) |
| `wait="2"` | length of a silent step in seconds |
| `label="..."` | the outline's name for a silent step |

An element that should be pointed at when it appears goes after the block that points
at it:

```markdown
::: {.say point="#msd-def"}
We square the length of that arrow, and average it over all walkers.
:::

::: {#msd-def}
$$\langle\Delta r^2\rangle(t)=\frac{1}{N}\sum_i\left|\Delta\mathbf{r}_i(t)\right|^2$$
:::
```

## Numbers: `values()`

`figures.py` runs before the narration is read. It computes or loads every number, and
hands the quoted ones over:

```python
from narrate import figure, values
assert abs(D - D0) < 0.05 * D0, "the narration says the measured D returns the one put in"
values(D=f"{D:.2f}", walkers=WALKERS)
```

`values()` writes `build/values.yml`; the deck lists it under `metadata-files`, and both
slides and sentences quote a number as `{{< meta v.D >}}`. Format the number in
`figures.py`, as it should be read and spoken. Put an `assert` beside every number the
narration makes a claim about, and one for every qualitative word ("twice", "no
change"), so that the build fails when the data moves.

## Figures: `figure()`

```python
fig, ax = plt.subplots(figsize=(5.4, 3.9))
ax.plot(t, msd, "o", gid="points")            # there from the start; id "msd-points"
ax.plot(t, slope * t, gid="s2-fit")           # appears with sentence 2; id "msd-fit"
figure(fig, "msd")                            # writes build/fig/msd.html and closes fig
```

On the slide: `{{< include build/fig/msd.html >}}`, usually inside a column, whose
width it fills.

- `gid="sN-name"`: the part appears with sentence N of its slide (counted from 1) and
  gets the id `<figure>-<name>`. `gid="name"` only names it. Use the id in `point=` and
  `grow=`, and Alt+click on the part replays its sentence.
- Sentence numbers count the slide's `say` blocks, silent steps included. The figure
  does not know which slide it is on: if the slide's sentences are reordered, renumber
  the gids.
- One figure per slide position. For two states of one plot, use parts that appear,
  not two figures on top of each other.
- Text in the figure stays text and takes the slide's font, so set sizes in points that
  work at the figure's `figsize` (13 or more for a figure that fills half a slide), and
  prefer plain Unicode ("Δr", "⟨Δr²⟩") over mathtext.
- Colours: take them from the theme's palette and give each one meaning for the whole
  talk; a colour named in the narration ("the orange arrow") must be that colour.
- An arrow that should appear by itself is a `FancyArrowPatch` with its own gid; an
  `annotate()` arrow cannot be named.

## Clips and images

- **A clip** (a simulation movie) is a silent `.mp4` rendered by the project's own
  tools, put on the slide as raw HTML:
  `<video src="media/clips/run.mp4" data-external="1" style="width:60%"></video>`.
  The player mutes it, loops it, and runs it on the slide's clock: it starts with the
  slide and pauses with the talk. `data-external="1"` keeps it a file beside
  `talk.html`; without it Quarto puts the whole clip inside the page.
- **An image** is ordinary Markdown or `<img>`. It can appear with a sentence and be
  pointed at as a whole, but not part by part.

## Front matter

```yaml
title-slide-attributes:
  data-say: "First sentence.|Second sentence."
narrate:
  voice: af_heart        # Kokoro voice; af_/am_ American, bf_/bm_ British
  speed: 1.0             # speaking rate
  lang: en-us            # only to override the voice's language
  lead: 0.7              # silence before a slide's first sentence, seconds
  gap: 0.4               # between sentences
  tail: 1.0              # after the last sentence, before the next slide
  embed: true            # speech inside talk.html; false: files in media/audio/
  spoken:                # written: spoken; changes the speech, not the captions
    "Péclet": "Pay-clay"
metadata-files: [build/values.yml]
format:
  revealjs:
    embed-resources: true            # keep: this is what makes the page work offline
    self-contained-math: true
    html-math-method: katex
    revealjs-plugins: [narrate]
    include-in-header:
      text: '<script src="media/manifest.js"></script>'
```

Everything under `narrate:` is optional. Changing the voice or the speed speaks every
sentence again; the old files stay cached. The rest of the `revealjs` block is the
`sci-talk` deck's; the theme, the canvas size and the slide number are set there.

With `embed: false`, ship `talk.html` together with `media/`.

## The player

| key | does |
|---|---|
| space | play / pause |
| ← → | previous / next slide |
| ↑ ↓ | previous / next sentence |
| Home, End | first / last slide |
| C | captions |
| T | outline: sections, slides, the sentences of the current slide |
| M | voice on / off; the talk keeps its pace |
| A | auto-advance to the next slide on / off |
| X | hide / show the bar |
| ? | the list of keys and mouse actions |

Mouse: click a slide on the timeline to jump; click a line of the outline to play from
there; Alt+click an element to replay the sentence that introduced it; Ctrl+click
zooms; a plain click or drag selects text. Keys with Ctrl, Alt or Meta are left to the
browser, and every other reveal.js key keeps its meaning (H J K L, F fullscreen, O
overview, S speaker view, where the notes are the slide's narration).

URL switches, for checks and links:

| URL | does |
|---|---|
| `talk.html#5.2` | open at slide 5, sentence 2 |
| `talk.html?shot#5` | slide 5 at its last sentence, no player, no transitions (screenshots) |
| `talk.html?fast` | play through without sound at 50 times the speed (the build's check) |
| `talk.html?autostart` | start without the click (works only where the browser allows sound unasked) |
| `talk.html?tl=sections` | force a timeline layout: `slides`, `sections` or `none` |

A browser plays no sound before the first click or key press, hence the start overlay.

## A recorded voice or another speech engine

An audio file that already exists under a sentence's name is used as it is. `--script`
prints the name of every sentence's file (`media/audio/<name>.mp3`); record or
synthesise the sentences elsewhere, save them under those names as mp3, and build. The
name depends on the voice, the speed and the sentence as spoken, so a changed sentence
asks for a new file. This path is described, not tested with another engine.

## What is cached, what is rebuilt

- `media/audio/*.mp3`: one file per sentence, kept across builds. Files of sentences
  that no longer exist stay there; delete the folder to start clean (everything is
  spoken again).
- `build/`: figures, values, screenshots. Rewritten by every build.
- `media/manifest.js`: the sentence files and lengths. Rewritten by every build; the
  page reports it when it does not match the slides ("Narration out of date").
- `~/.cache/kokoro/` (`KOKORO_DIR`): the voice model, 340 MB, downloaded once.

## When something fails

- **"Narration out of date" on the start overlay**: the slides were rendered without
  `narrate.py` (for example by `quarto preview`) after the narration changed. Run the
  build.
- **Check: "content that no sentence reveals"**: a reveal.js fragment or `. . .` pause
  of the author's own on that slide. The narration never steps through it, so it would
  stay hidden; stage with `say` blocks only.
- **Check: "reaches outside its slide"**: too much on the slide, or a figure taller
  than its column allows. Shorten, or shrink the figure's `figsize` height.
- **Check: "loads from the network"**: something on the slides is linked from a URL
  (an image, a font, a script); download it into the talk's directory.
- **No `chromium` on the PATH**: the check and `--shots` need Chromium or Chrome;
  `--no-check` builds without them.
- **`quarto preview`** works for layout, with the narration of the last build.
- **Kokoro, uv, Quarto versions, drives that cannot run executables**: see
  `../sci-video-talk/references/environment.md`; the tools are the same.
