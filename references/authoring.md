# Authoring a narrated talk

Everything the author writes lives in two files: `talk.qmd` (slides and narration) and
`figures.py` (numbers and drawings). The starter in `assets/talk/` uses every feature
below once.

## Contents

- [The say block](#the-say-block)
- [Layouts and sizes](#layouts-and-sizes)
- [Sections and silent steps](#sections-and-silent-steps)
- [Pointers and growing paths](#pointers-and-growing-paths)
- [Numbers: `values()`](#numbers-values)
- [Figures: `figure()`](#figures-figure)
- [Themes](#themes)
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
- Blocks work inside containers such as the `.text` of a `.beside` slide. Inside a
  container, "what follows" means the following siblings in it.
- A sentence that reveals nothing still gets its block, where it belongs in the order.
- Keep markup out of the sentence: `*`, `_` and backticks are stripped before speech,
  math and backslashes are refused by the build.

## Layouts and sizes

The theme is the frame and the scenes of the `sci-video-talk` videos, on a 1920 x 1080
canvas. A slide written in one of the layouts below lands where the video engine would
draw it, to within a few pixels. The player draws the frame: section (left), talk title
and "n / N" (right), and the progress bar along the bottom edge.

| the video's scene | on the slide |
|---|---|
| title bar | the `##` heading: one line, with the accent rule under it. A title too long for the bar fails the check |
| `title_scene` | `## The talk's title {.title-card}` with `::: {.subtitle}`, `::: {.byline}`, optionally `::: {.coauthors}` and a picture in `::: {.art}` |
| `divider` | `# [Part 2]{.part} The section's claim {.divider}` with an optional `::: {.sub}` line and `::: {.art}` |
| `beside` | `:::: {.beside}` holding `::: {.fig}` (the figure) and `::::: {.text}` (the `say` blocks, staged bullets, the takeaway) |
| `bullet_scene` | `say` blocks and bullets directly under the heading |
| `callout` | `::: {.takeaway}`; `::: {.box .model}` (`.result`, `.info`, `.prov`) is the same box in another colour |
| `note` | `::: {.note}`, the small print above the footer: what the picture is made from |
| a scene drawn by hand | blocks pinned with `::: {.absolute left="56%" top="43.7%"}`: `left` is the engine's x, `top` is 1 − y, in per cent of the frame |

Sizes and widths are the engine's, by name:

- `.s24` sets text of 24 points, any size from 12 to 72. The body is 27 points; bullets
  are 29 on a slide of bullets and 26 beside a figure; a takeaway is 28 (24 beside a
  figure); a note is 17.
- `.w40` wraps about like the engine's `width=40` (characters). The engine breaks lines
  by counting characters and a browser by measuring them, so they agree on most lines
  and not on all. Where a break matters, write it with a backslash at the end of the
  line. Bullets beside a figure wrap at 28 characters; put `.w34` on the `.text` block
  for another width.
- `.muted`, `.accent`, `.blue`, `.green`, `.purple`, `.ink` colour a block; `.semibold`,
  `.bold`; `.tight` and `.loose` are the engine's linespacing 1.1 and 1.3.

Set the talk's title in the front matter as `pagetitle:` (it is the footer's text) and
not as `title:`, which would make Quarto add a title slide of its own.

## Sections and silent steps

- **Sections.** A slide's section, shown in the footer, the timeline and the outline, is
  `{sec="Name"}` on its heading, or the last `#` divider before it.
- **A silent step**: an empty block, `::: {.say wait="2" label="The axes appear"}`
  closed by `:::` on the next line. It lasts `wait` seconds (default 3) and what follows
  it appears in silence. `label` is its name in the outline; without one the outline
  uses the text it reveals.
- **A slide without any block** is one silent step of 3 seconds.

## Pointers and growing paths

Attributes of a `say` block:

| attribute | effect |
|---|---|
| `point="#id"` | a pointer on that element while the sentence is spoken |
| `point="#a@a phrase; #b@another phrase"` | several, one after another: each appears when the voice reaches its phrase and gives way to the next |
| `grow="#id"` | that SVG line is drawn from start to end while the sentence is spoken (a trajectory, a curve); its markers appear as the line reaches them |
| `with="#dots"` | with `grow=`: the markers of another artist appear as the line passes them (plot them in the line's order) |
| `wait="2"` | length of a silent step in seconds |
| `label="..."` | the outline's name for a silent step |

Any other block takes `at="2"`: it appears with sentence 2, wherever it stands in the
source. Without it, a block appears with the sentence it follows, and a block written
after a container that holds the narration would wait for the last sentence. A
`::: {.note}` is there from the start unless it says otherwise.

**Pointers.** A pointer on a point of a figure is a ring; on anything else it is a box
around it. Use them rarely (see the skill's rules) and prefer the ring:

```python
mark("fit", ax, 200, slope * 200, r=0.04)   # in figures.py: a point to ring, id "<figure>-fit"
```

```markdown
::: {.say point="#msd-fit"}
A straight line fits it.
:::
```

`mark()` is the video engine's: an invisible dot of radius `r` (a fraction of the
frame's height) at a data point. A phrase cue is timed by where the phrase stands in
the sentence, which is right to about a third of a second.

An element that should be pointed at when it appears goes after the block that points
at it.

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
from narrate import ART, FIG, PLOT, C, figure, values

fig = plt.figure(figsize=FIG)                 # the .fig box of a .beside slide
ax = fig.add_axes(PLOT)                       # where the video's beside() puts its plot
ax.plot(t, msd, "o", color=C.blue, gid="points")        # there from the start; id "msd-points"
ax.plot(t, slope * t, color=C.accent, gid="s2-fit")     # appears with sentence 2; id "msd-fit"
figure(fig, "msd")                            # writes build/fig/msd.html and closes fig
```

On the slide: `{{< include build/fig/msd.html >}}` inside `::: {.fig}`, `::: {.art}` or
a pinned block; the figure fills that box.

- **Size.** Draw a figure at the size of its box, at 100 px per inch of the frame. Text
  sizes are then the video's points: ticks 18, axis labels 20 (the defaults), labels in
  the picture 22 or more. `FIG` is the `.fig` box of `.beside` and `PLOT` the place of
  its axes; `ART` is the picture box of a title or divider card. For a pinned block of
  42 % x 66 % of the frame, `figsize=(8.06, 7.13)`.
- **Parts.** `gid="sN-name"`: the part appears with sentence N of its slide (counted
  from 1) and gets the id `<figure>-<name>`. `gid="name"` only names it. Use the id in
  `point=` and `grow=`; Alt+click on the part replays its sentence.
- **Parts that leave or step back.** `gid="s2-4-name"` appears with sentence 2 and is
  gone from sentence 4 on; `gid="s2-d4-name"` is dimmed from sentence 4 on. So one
  figure can show a curve, replace it, or push it into the background, and need not be
  drawn once per sentence. An arrow or a label for one sentence is such a part.
- Sentence numbers count the slide's `say` blocks, silent steps included. The figure
  does not know which slide it is on: if the slide's sentences are reordered, renumber
  the gids.
- One figure per box. For two states of one plot, use parts that appear, not two
  figures on top of each other.
- Text in the figure stays text and is set in the theme's font. Prefer plain Unicode
  ("Δr", "⟨Δr²⟩") to mathtext.
- **Colours.** Draw with `C.blue`, `C.green`, `C.purple` (the three series), `C.accent`
  (what the talk points at), `C.ink`, `C.muted`, `C.light`. Text, axes and the colour
  cycle follow the theme already. Give each colour one meaning for the whole talk.
- An arrow that should appear by itself is a `FancyArrowPatch` with its own gid; an
  `annotate()` arrow cannot be named.

## Themes

```yaml
narrate:
  theme: dark                                   # a name
  theme: {base: light, accent: "#0b7285"}       # or colours of your own on a base
```

| theme | look |
|---|---|
| `light` (default) | white, orange accent: the look of the videos |
| `dark` | near-black, for a dark room or a screen recording |
| `paper` | warm off-white, muted colours |
| `sci-talk` | the `sci-talk` deck's palette: white, indigo accent |
| `sea` | pale blue-grey, teal accent |
| `journal` | white, serif (IBM Plex Serif), print colours |
| `chalk` | a blackboard |
| `midnight` | dark blue, amber accent |
| `contrast` | black and white with yellow, for a weak projector |

They are the nine themes of `sci-video-talk`, so a video and a narrated talk of the
same story can match. `narrate: theme:` is the theme the talk opens in. All nine (and
a custom one) travel in the page, and the viewer moves to the next with the Y key or
the bar's theme button, or picks one in the settings (`,`), at any moment and without
interrupting the voice; `talk.html?theme=dark` opens in one.

How it works: a theme has no style rules. It is a set of values for nine names:
eight colours (`--bg`, `--ink`, `--muted`, `--light`, `--accent`, `--blue`, `--green`,
`--purple`) and `--font`. `theme/narrated-talk.scss` holds the layout, the frame of
the videos (title bar with the accent rule, footer with section, talk title and slide
number, progress bar), and every colour in it is one of those names. Switching a theme
sets the nine values. The build fails on a custom theme whose text or series colours
have too little contrast with the background.

What follows a switch, and what does not:

- **Slides**: everything styled by the theme file. On a slide of your own, use the
  classes (`.accent`, `.blue`, `.muted`, ...) or `var(--accent)`; a typed-in colour
  stays as it is.
- **Figures drawn in `figures.py`**: `figure()` writes every colour that is one of the
  theme's (`C.blue`, `C.ink`, ...) into the SVG by name. A colour typed in by hand, or
  mixed from two theme colours in Python, stays fixed; make a tint with `alpha=`.
- **The font**: the regular, semibold and italic cuts of every theme's font are put
  inside the talk (Latin, Greek, punctuation, arrows and math signs only), so it looks
  the same on a machine without them. If the build machine lacks a font, the build
  says so and that theme uses the viewer's system font.
- **Not**: clips and pasted images. They keep their own colours and background; on a
  dark theme a white figure from a paper stays a white card.
- **Not**: the player's bar, which is always dark. The outline takes the theme.
- **Not**: what the narration says. Never name a colour in a sentence or a bullet.

A talk whose clips, images or narration fix the colours should not offer the switch:
`narrate: {switch: false}` leaves only its own theme. `--themes` runs the check in
every theme, which finds text that fits in one font and not in another.

Changing `narrate: theme:` speaks nothing again; the build only renders.

On a slide, three more things come from the frame: `::: {.note}` is the small print at
the foot of the slide (what the picture is made from), `::: {.takeaway}` the boxed
conclusion, and `::: {.box .model}` (`.result`, `.info`, `.prov`) the same box in
another colour.

## Clips and images

- **A clip** (a simulation movie) is a silent `.mp4` rendered by the project's own
  tools, put on the slide as raw HTML:
  `<video src="media/clips/run.mp4" data-external="1" style="width:60%"></video>`.
  `data-external="1"` keeps it a file beside `talk.html`; without it Quarto puts the
  whole clip inside the page.
- **Its clock.** A clip runs on the slide's clock: it starts with the slide, pauses with
  the talk, and is set to the right time again at every sentence, so it does not drift
  from the voice. With `data-clock="sentence"` it starts at 0 with the sentence that
  reveals it.
- **Looping.** A clip about as long as what it accompanies plays once and holds its last
  frame; a shorter one loops. `data-once` and `data-loop` decide otherwise.
- **In a recording** (`record.py`) a clip's frames are read from its file by ffmpeg,
  not from the browser. So a clip has to be a file beside the page that ffmpeg can
  read (`data-external="1"`, not embedded), and what is drawn over it has to be drawn
  plainly over it: a pointer, a label, an SVG layer, a fade are kept; a CSS filter or
  blend mode on a clip or around it is not.
- **An image** is ordinary Markdown or `<img>`. It can appear with a sentence and be
  pointed at as a whole, but not part by part.
- With clips, keep `embed-resources: true` and mark the clips `data-external="1"`:
  then the equations' KaTeX stays inside the page and only the clips are files.

## Front matter

```yaml
pagetitle: "The talk's title"   # the footer's text; not `title:`
narrate:
  voice: af_heart        # Kokoro voice; af_/am_ American, bf_/bm_ British
  speed: 1.0             # speaking rate
  lang: en-us            # only to override the voice's language
  lead: 0.7              # silence before a slide's first sentence, seconds
  gap: 0.4               # between sentences
  tail: 1.0              # after the last sentence, before the next slide
  embed: true            # speech inside talk.html; false: files in media/audio/
  switch: true           # false: the viewer cannot change the theme (see Themes)
  keys: {theme: false}   # the player's keys by action: a key or a list replaces its keys, false frees them
  theme: light           # see Themes
  spoken:                # written: spoken; changes the speech, not the captions
    "Péclet": "Pay-clay"
metadata-files: [build/values.yml]
format:
  revealjs:
    theme: [default, theme/narrated-talk.scss, build/theme.scss]   # keep this order
    width: 1920
    height: 1080
    margin: 0                        # the frame has its own margins
    center: false
    slide-number: c/t                # reveal.js's own formats (c/t, c, h.v, h/v; false: none);
    show-slide-number: all           #   the player puts the number into the frame
    progress: false                  # the frame has its own progress bar
    menu: true                       # reveal.js's menu, reached with R then M
    embed-resources: true            # keep: this is what makes the page work offline
    self-contained-math: true
    html-math-method: katex
    revealjs-plugins: [narrate]
    include-in-header:
      text: '<script src="media/manifest.js"></script>'
```

Everything under `narrate:` is optional. Changing the voice or the speed speaks every
sentence again; the old files stay cached. The theme is laid out for the 1920 x 1080
canvas; sizes on a slide are in `em`, where 1em is the body text.

With `embed: false`, ship `talk.html` together with `media/`. Opened without it, the
page plays on silently: at the first sentence whose file is missing it says "audio not
found — running silently" and runs every sentence on its measured length.

## The player

| key | does |
|---|---|
| P | play / pause |
| space, Enter, ↓, PgDn | next step: the next sentence, after the last one the next slide |
| Backspace, ↑, PgUp | previous step |
| ← → | previous / next slide |
| Home, End | first / last slide |
| C | captions |
| T | outline: sections, slides, the sentences of the current slide |
| M | voice on / off; the talk keeps its pace |
| A | auto-advance to the next slide on / off |
| Y | next theme |
| X | hide / show the bar |
| # | slide number on / off |
| , | settings |
| ? | the talk's keys and mouse actions |
| R, then a key | that key as reveal.js defines it: R ? shows reveal.js's own list of keys, R M its menu |

Space steps and P plays. A step taken without playing shows that stage complete
without the voice (its `grow=` line drawn, every pointer of the sentence on, its clips
running), so the page can be presented by hand: never press P, and step with the space
bar or a presentation clicker (they send PageDown and PageUp); the bar fades as it
does while playing. On the start screen the first step only lifts it, so the audience
sees the title slide first. Shift+space steps back. Stepping while the talk plays
keeps it playing. Space and Enter on a button reached with Tab press that button
(Enter on a focused link follows it; space still steps). In the speaker view's own
window (S) the keys are reveal.js's: space, the arrows and a clicker step the same
way, but P there steps back and the voice cannot be started from it.

Mouse: click a slide on the timeline to jump; click a line of the outline to play from
there; Alt+click an element to replay the sentence that introduced it; Ctrl+click
zooms; a plain click or drag selects text.

The talk's keys are handled before reveal.js sees them and are not entered in its
table. So every key the talk does not use is reveal.js's as always (H J K L, F
fullscreen, O overview, S speaker view, where the notes are the slide's narration), and
the prefix R hands the next key to reveal.js and its plugins even where the talk uses
it. The help (`?`) has buttons for reveal.js's own list of keys and for its menu. Keys
with Ctrl, Alt or Meta are left to the browser.

`narrate: keys:` gives an action other keys or frees it: the action, then one key, a
list of keys, or `false`. A key is a letter or the name the browser gives it (`Enter`,
`PageDown`, `ArrowUp`, `space`). The actions: `play`, `next`, `prev`, `up`, `down`,
`first`, `last`, `captions`, `outline`, `voice`, `auto`, `theme`, `hide`, `number`,
`settings`, `help`, `reveal`.

```yaml
narrate:
  keys: {play: [p, k], down: [space, PageDown], up: PageUp, theme: false}
```

**Settings** (the gear on the bar, or `,`): the theme (one swatch per theme, in its own
colours; not shown when `switch: false` leaves one), voice, captions, auto-advance, the
timeline's layout (`auto`, `slides`, `sections`, `none`) and the slide number, the same
switches as the bar's buttons and keys, and a link that opens the talk with the
current settings. While the panel is open it takes every key; Esc, `,` or a click
outside closes it. What the viewer changes is remembered for that page in the
browser's local storage (nothing breaks where storage is blocked), and "back to the
talk's own settings" forgets it. A setting in the address wins over a remembered one,
which wins over the talk's own; recordings, screenshots, the build's check and the
speaker view never read or write what is remembered.

URL switches, for checks and links:

| URL | does |
|---|---|
| `talk.html#5.2` | open at slide 5, sentence 2 |
| `talk.html?shot#5` | slide 5 at its last sentence, no player, no transitions (screenshots) |
| `talk.html?fast` | play through without sound at 50 times the speed (the build's check) |
| `talk.html?autostart` | start without the click (works only where the browser allows sound unasked) |
| `talk.html?theme=dark` | open in that theme; combines with the others (`?shot&theme=dark#5`) |
| `talk.html?voice=off&cc=on&auto=off&num=off` | voice, captions, auto-advance, slide number: `on` or `off` |
| `talk.html?tl=sections` | the timeline's layout: `auto`, `slides`, `sections` or `none` |

A browser plays no sound before the first click or key press, hence the start overlay:
a click or P plays, a step key steps without the voice.

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
  page reports it when it does not match the slides ("Narration out of date"). A page
  rendered without one (`quarto render` before the first build) runs silently, each
  sentence lasting its words at 155 a minute, and says "no narration audio".
- `~/.cache/kokoro/` (`KOKORO_DIR`): the voice model, 340 MB, downloaded once.

## When something fails

- **"audio not found — running silently"** in the bar: the page was opened without
  the `media/audio/` it was built with (`embed: false`). Ship the folder with the page.
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
- **A broken `:::` block**: a `{{< meta ... >}}` shortcode at the very end of the line
  before a closing `:::` swallows the line break. Put a full stop or a space after it.
- **Screenshots** are taken by a browser that the build drives slide by slide and that
  waits for fonts and clips; a clip is shown at the end of the sentence.
- **No `chromium` on the PATH**: the check and `--shots` need Chromium or Chrome;
  `--no-check` builds without them.
- **`quarto preview`** works for layout, with the narration of the last build.
- **Kokoro, uv, Quarto versions, drives that cannot run executables**: see
  `../sci-video-talk/references/environment.md`; the tools are the same.
