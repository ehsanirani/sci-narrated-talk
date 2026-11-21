---
name: sci-narrated-talk
description: Make a scientific talk that tells itself, as one HTML page. A synthetic voice narrates a Quarto + reveal.js deck sentence by sentence while the slide builds, and the viewer can pause, step by sentence or slide, jump through a timeline or an outline, replay the sentence behind any element, zoom, read captions, or switch the voice off. Slides stay real slides (selectable text, KaTeX equations, inline SVG figures whose parts appear and are pointed at as they are mentioned, embedded clips), everything is built locally from one talk.qmd, and the result opens offline. Use whenever the user asks for a narrated talk, a narrated or self-playing presentation, slides with a voice-over, an interactive or clickable version of a video talk, a talk people can watch on their own, or wants such a talk revised (narration, voice, a slide, the figures), even if they only say "make the talk play by itself". Not for an .mp4 (sci-video-talk), a deck the user presents live without narration (sci-talk) or a written report (sci-report).
---

# sci-narrated-talk

A narrated talk is a Quarto reveal.js deck in which every slide carries its own
narration, one `::: say` block per sentence. The bundled build script speaks the
sentences, and a reveal.js plugin plays them in the browser: what follows a sentence in
the source appears on the slide when that sentence starts.

The speech is the clock. Each sentence is one audio file; the reveals, the timeline and
the outline follow the measured lengths. Nothing is timed by hand.

Unlike a video, the viewer steers: they can stop, go back one sentence, jump to a slide,
or click a curve to hear it explained again. Unlike a live talk, nobody can ask a
question, so the talk has to answer it before it comes up.

## Settle first

Ask only for what the project does not already answer.

- **The story**: the written piece the talk follows, and the one-sentence answer it
  defends.
- **Audience and length**: default a general seminar audience, 12 to 15 minutes. Budget
  155 spoken words per minute, pauses included.
- **Where every number comes from**: a numbers file or generated values. Nothing is
  typed in from memory.
- **Voice**: default `af_heart` (Kokoro; `--voices` lists them). For samples to choose
  from, use `sci-video-talk`'s `--voices NAME ...`.
- **One file or a folder**: one `talk.html` with the speech inside (default), or the
  speech beside the page (`narrate: {embed: false}`) for a long talk or one with clips.

## Start

Put the talk where the project keeps talks (for example `presentations/<slug>/`). The
skill's files are read-only links into the Nix store, so copy with `-L`:

```sh
cp -rL --no-preserve=mode <this skill>/assets/talk <dir>
cp -L --no-preserve=mode <this skill>/scripts/narrate.py <dir>/
cp -rL --no-preserve=mode <this skill>/../sci-talk/assets/quarto-deck/theme <dir>/
```

That is a complete six-slide talk that builds as it stands: `talk.qmd` (slides and
narration), `figures.py` (numbers and drawings), `_extensions/narrate/` (the player),
`theme/` (the `sci-talk` theme) and a `.gitignore`. Replace the content and keep the
structure. `narrate.py` and `_extensions/` stay unedited, so that a fix in the skill can
replace them. Read `references/authoring.md` before writing the first slide.

## Commands

`NT` stands for
`uv run --no-project --with kokoro-onnx --with soundfile --with pyyaml --with matplotlib --with pillow python narrate.py`
(add `--with` for what `figures.py` imports), run in the talk's directory. Write the
command out: a shell variable holding it does not split in zsh.

| command | does |
|---|---|
| `NT --script` | the narration per slide: words, flagged long sentences, audio file names, total minutes. Builds nothing |
| `NT` | the whole build: `figures.py`, speech for new or changed sentences, `quarto render`, then the run-through check |
| `NT --shots` | the build, then a screenshot of every slide's last stage and contact sheets in `build/shots/` |
| `NT --no-check` | the build without the run-through (no Chromium needed) |
| `NT --voices` | the voice names |

Output: `talk.html`. Speech is cached per sentence in `media/audio/`, so a rebuild after
a text change speaks only the changed sentences and takes seconds.

## Workflow

1. **Storyboard.** The shape of the talk is `sci-talk`'s: claim titles, question and
   answer up front, one section per sub-question, a summary. Read that skill's "shape of
   the talk" when the deck is new.
2. **Narration.** Write the `::: say` blocks of every slide, one stage of the slide per
   sentence. Run `--script`; cut until the length fits.
3. **Numbers.** `figures.py` reads every spoken or shown number from its source, asserts
   what the narration claims about it, and passes it on with `values()`. Slides and
   sentences quote it as `{{< meta v.NAME >}}`.
4. **Figures.** Draw with matplotlib, name the parts with `gid`, write them with
   `figure()`. Prefer a drawn figure over a pasted image: only its parts can appear one
   by one and be pointed at.
5. **Build** with `--shots` and look at every contact sheet.
6. **Play it.** Open `talk.html`, play at least two slides, and try the outline.
7. **Report back** (last section).

## Narration

The rules of a talk nobody can interrupt, as in `sci-video-talk`:

- **One narrator telling a story.** State the question early; let each section end on
  the question the next one answers.
- **Spoken sentences**: short, one idea each, at most about 45 words (`--script` flags
  longer ones).
- **Say what appears.** A sentence and what it reveals belong together: its first words
  fit the thing that comes on screen.
- **Write for the speech engine.** Punctuation is the only control of rhythm. No
  parentheses, no dashes inside a sentence, no symbols, no math: write "phi", "percent",
  "about". Names the engine misreads go in `narrate: spoken:`, which changes the speech
  and leaves the captions as written.
- **Keep the status of every claim.** A blessed result is stated as a result; a computed
  but uninterpreted one is announced as preliminary in the sentence and on the slide; a
  proposed reading is left out.

## Slides

- **Define a quantity before plotting it.** The formula and a picture of what it
  measures come before the first plot that uses it.
- **Point at what the sentence refers to** with `point="#id"` on its `say` block. A ring
  closes in when the sentence starts.
- **Build, do not show.** Something changes with every sentence: a curve, a bullet, a
  term. A slide whose sentences reveal nothing reads as a frozen frame.
- **Terse, as in `sci-talk`**: the voice carries the explanation, so the slide carries
  only the claim, the figure and a few bullets.
- **Every slide is numbered** (`slide-number: c/t` in the starter), so a question can
  name a slide; the address bar shows `#slide.sentence` and such a link opens there.
- **Stage with `say` blocks only.** Reveal.js fragments and `. . .` pauses of the
  author's own are not narrated and break the count.

## Checks before calling it done

1. `--script`: the length is what was asked for; no sentence flagged.
2. The build's check passes: every sentence reached in order, every equation rendered,
   nothing outside its slide, nothing loaded from the network.
3. Every contact sheet looked at: no overlapping or cramped text, each figure readable,
   every plotted quantity defined on an earlier slide.
4. Opened in a browser and played: the reveals fit the sentences, each pointer sits on
   its target.
5. The asserts in `figures.py` cover every quoted number and every qualitative word.

## Report back

The path of `talk.html` and its size; length, slide and sentence count; the voice; what
the check said; how the viewer steers it (space, arrows, T for the outline, `?` for the
rest); and plainly whether anyone has listened to the audio. The check proves that the
talk runs, not that the voice is pleasant or a name sounds right.

Record the build command in a short `README.md` beside the talk, and follow the
project's own rules for where status and dated records go.

## Not built

Say so when asked, rather than improvising: an `.mp4` from the talk (use
`sci-video-talk` for a video); the video engine's colour themes (the look is a Quarto
theme, `theme/*.scss`); speech engines other than Kokoro, except by dropping files into
`media/audio/`; a two-voice dialogue; background music.

## References

- `references/authoring.md`: the `say` block and its attributes, the title slide, silent
  steps, `figure()` and `values()`, clips, front-matter settings, the player's keys and
  URL switches, a recorded voice, what is cached. Read before writing the first slide.
- `README.md`: what the pieces are and how they fit; read when something in the player
  or the build has to change.
