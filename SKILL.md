---
name: sci-narrated-talk
description: Make a scientific talk that tells itself, as an HTML page. A synthetic voice (or the author's own recorded reading of the script) narrates a Quarto + reveal.js deck sentence by sentence while the slide builds, and the viewer can pause, step by sentence or slide, jump through a timeline or an outline, replay the sentence behind any element, zoom, read captions, pick another voice, or present it by hand with none. Slides stay real slides (selectable text, KaTeX equations, inline SVG figures whose parts appear and are pointed at as they are mentioned, embedded clips), everything is built locally from one talk.qmd, and the result opens offline. Use whenever the user asks for a narrated talk, a narrated or self-playing presentation, slides with a voice-over, an interactive or clickable version of a video talk, a talk people can watch on their own, or wants such a talk revised (narration, voice, a slide, the figures), even if they only say "make the talk play by itself". The finished talk can also be recorded to an .mp4. Not for a video made without the interactive page (sci-video-talk), a deck the user presents live without narration (sci-talk) or a written report (sci-report).
---

# sci-narrated-talk

A narrated talk is a Quarto reveal.js deck in which every slide carries its own
narration, one `::: say` block per sentence. The bundled build script speaks the
sentences, and a reveal.js plugin plays them in the browser: what follows a sentence in
the source appears on the slide when that sentence starts.

The speech is the clock. Each sentence is one audio file; the reveals, the timeline and
the outline follow the measured lengths. Nothing is timed by hand.

The slides and the voice are separate layers. `talk.html` is the slides, with no voice
inside; each voice is a folder beside it (`media/voices/<name>/`), found by the page when
it opens and offered in its settings, with "none" for presenting by hand. A voice is
added, completed or deleted without rendering the slides again, and a step whose
sentence changed after a voice was made runs silently on its estimated length.

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
  from, use `sci-video-talk`'s `--voices NAME ...`. More voices can sit beside the page
  (another Kokoro voice or speed, the author's own reading); `voice: false` builds slides
  to present by hand.
- **Theme**: the one the talk opens in: `light` (default), `dark`, `paper`, `sci-talk`,
  `sea`, `journal`, `chalk`, `midnight`, `contrast`, or colours of the user's own. The
  look is the videos' frame and the themes are the same nine as `sci-video-talk`. All
  of them travel in the page; the viewer switches with the Y key or in the settings
  (`,`) at any moment, and slides, drawn figures and font follow.
- **How it is sent**: `talk.html` with its `media/` folder (default), or one file with one
  voice inside (`--bundle=NAME` writes `talk-NAME.html`). A page that has lost its
  `media/` opens as slides to present by hand.

## Start

Put the talk where the project keeps talks (for example `presentations/<slug>/`). The
skill's files are read-only links into the Nix store, so copy with `-L`:

```sh
cp -rL --no-preserve=mode <this skill>/assets/talk <dir>
cp -L --no-preserve=mode <this skill>/scripts/narrate.py <this skill>/scripts/record.py <dir>/
```

That is a complete four-slide talk that builds as it stands: `talk.qmd` (slides and
narration), `figures.py` (numbers and drawings), `_extensions/narrate/` (the player),
`theme/narrated-talk.scss` (the look), `build.sh` (the build command), a `README.md` for
whoever works on the talk by hand, and a `.gitignore`. Replace the content and keep
the structure. The folder is the deliverable as much as the page: anyone can change
`talk.qmd` or `figures.py` and run `sh build.sh`. Revise a talk the same way, in its
source, never in `talk.html`. `narrate.py`, `record.py`, `_extensions/` and `theme/` stay unedited, so that a fix in
the skill can replace them; a talk's own style rules go in a further SCSS file at the
end of the `theme:` list. A talk works on its own copies: replace `narrate.py`,
`_extensions/` and `theme/` together, never one of them, and not while the talk is
being built. The page warns in the console when the player and the build script are
of different versions. Read `references/authoring.md` before writing the first slide.

## Commands

`NT` stands for
`uv run --no-project --with kokoro-onnx --with soundfile --with pyyaml --with matplotlib --with pillow python narrate.py`
(add `--with` for what `figures.py` imports, in `build.sh` too, which is the same
command: `sh build.sh --shots`), run in the talk's directory. Write the
command out: a shell variable holding it does not split in zsh.

| command | does |
|---|---|
| `NT --script` | the narration per slide: words, flagged long sentences, each sentence's recording name (`03.2`), total minutes. Builds nothing |
| `NT` | the whole build: `figures.py`, the talk's voice for new or changed sentences, `quarto render`, then the run-through check |
| `NT --no-voice` | the build without speaking anything |
| `NT --voice=bm_george` | add or complete a synthetic voice (`--speed=1.2`, `--lang=en-gb`), without rendering the slides |
| `NT --import-voice=me` | bind recordings in `media/voices/me/` (named `03.2.wav`, as `--script` lists them) to their sentences |
| `NT --bundle=af_heart` | `talk-af_heart.html`: the page with that voice inside, one file |
| `NT --shots` | the build, then a screenshot of every slide's last stage and contact sheets in `build/shots/` |
| `NT --shots=all --size=1920x1080` | also a screenshot of every sentence (`build/shots/all/`), at that size |
| `NT --themes` | the build, with the check run in every theme the talk can be switched to |
| `NT --no-check` | the build without the run-through (no Chromium needed) |
| `NT --voices` | the voice names |
| `NT --version` | the version of the skill these copies come from |

Output: `talk.html` (the slides) and `media/voices/<voice>/` (the voice). A voice keeps
one file per sentence, so a rebuild after a text change speaks only the changed
sentences and takes seconds; a talk built with 0.4.0 keeps its speech (the build moves
`media/audio/` into the voice's folder). Voices, the `voice.js` format and the import of
an own reading: `references/authoring.md`, Voices.

## Recording a video

`scripts/record.py` turns a built `talk.html` into an `.mp4`, so the talk is the single
source of both forms. It needs ffmpeg as well as Chromium, and `narrate.py` beside it:

```sh
nix shell nixpkgs#ffmpeg -c uv run --no-project --with soundfile --with numpy --with pillow \
    python record.py talk.html
```

It writes `talk.mp4` beside the page (h264 and aac, the captions as a subtitle track,
one chapter per slide) and `talk.srt`, with the voice the talk opens with; `--voice=NAME`
records with another, and a talk with no voice is refused. `--from=S --to=S` records a
stretch for a trial, `--theme=NAME` another theme, `--size=1280x720`, `--fps=25`,
`--crf=20`, `-o FILE`.
A 15-minute talk with 27 clips took 5.5 minutes on a 12-thread laptop.

The video is the page at every instant, not a screen capture: the same fades, pointers
and growing lines, the clips' frames taken from their files. What it loses against the
page: everything the viewer does (stepping, the outline, replaying a sentence, zoom,
selecting text), the theme switch (one theme per recording) and the viewer's own pace.
Look at a few frames and listen to a stretch before handing it over.

## Workflow

1. **Storyboard.** Sections, and for each its slides. Open on the title slide, state
   the question and the answer early, give each sub-question a section with a divider,
   and end on a summary and what is open. Write each slide's title as a claim.
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
- **Point rarely, and at data.** A pointer (`point=`) is for the few moments when the
  viewer would not find what the voice means: one curve among several, one point on
  it. A talk of fifteen minutes has ten to twenty, not one per sentence. Point at a
  point of a figure (`mark()` in `figures.py`), never at a text block, a box, a clip
  or a whole plot: what has just appeared needs no pointer.
- **Nothing is on the slide before its moment.** A curve, a marker or a label that the
  voice has not reached yet is not shown yet. Not every sentence has to bring
  something new; a sentence may simply talk about what is there.
- **When a video of the talk exists, reproduce it.** Same scenes, layouts, stages and
  pointers, in the same places. Do not redesign, add boxes or move the figure to the
  other side; improvements are proposed to the user, not slipped in.
- **Terse.** The voice carries the explanation, so the slide carries only the claim,
  the figure and a few short bullets.
- **Colours come from the theme.** `figures.py` draws with `C.blue`, `C.accent` and so
  on, and slides use the theme's classes and `var(--accent)`; a typed-in colour does
  not follow a change of theme. Each colour keeps one meaning for the whole talk. The
  voice and the slide text never name a colour ("the orange line"), because the viewer
  may be in another theme: say "the line", "the arrow".
- **Use the video's layouts** (`references/authoring.md`): the title card, the divider,
  a figure beside staged bullets, bullets only, the takeaway, the note. They put every
  block where the video engine would, at its sizes. Pin blocks by hand only for a slide
  no layout fits.
- **Every slide is numbered** in the footer (reveal.js's own slide number, in the
  format the front matter sets), so a question can name a slide; the address bar shows `#slide.sentence` and such a link opens there.
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

The path of `talk.html` and its size; length, slide and sentence count; the voices
beside it and the steps each lacks; what the check said; how the viewer steers it (P plays, space steps, so the same page can
be presented by hand or with a clicker; arrows, T for the outline, `,` for the settings,
which the browser remembers, `?` for the rest); and plainly whether anyone has listened to the audio. The check proves that the
talk runs, not that the voice is pleasant or a name sounds right.

Keep the talk's `README.md` and `build.sh` true (packages, anything the talk needs
besides the standard build), and follow the
project's own rules for where status and dated records go.

## Not built

Say so when asked, rather than improvising: speech engines other than Kokoro, except as
files imported per sentence (`--import-voice`); a free voice (one recording per slide,
spoken freely, with cues) and recording in the page, both planned (`TODO.md`); a
two-voice dialogue; background music.

## References

- `references/authoring.md`: the `say` block and its attributes, the title slide, silent
  steps, `figure()` and `values()`, themes, clips, front-matter settings, the player's keys and
  URL switches, voices (synthetic, an own reading, one file, the `voice.js` format), what is
  cached. Read before writing the first slide.
- `README.md`: what the pieces are and how they fit; read when something in the player
  or the build has to change.
