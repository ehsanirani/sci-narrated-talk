# A narrated talk

An HTML page that tells the talk by itself, or that you present by hand. Everything in it is built from the files in
this folder, so to change the talk, change a source file and build again. Never edit `talk.html`: the next build
overwrites it.

The slides and the voice are separate. `talk.html` is the slides; each voice is a folder beside it in
`media/voices/`. The page finds the voices when it opens and offers them in its settings (`,`), with "none" for
presenting by hand. Send the page together with `media/`, or a one-file copy: `--bundle=voice`, `--bundle=clips` or `--bundle=both`, by what goes inside.

| file | what it is | edit? |
|---|---|---|
| `talk.qmd` | the slides and the narration (`::: say` blocks, one sentence each), voice and theme at the top | yes |
| `figures.py` | the drawings and every number the talk quotes | yes |
| `build.sh` | the build command | when `figures.py` needs another package |
| `narrate.py`, `record.py`, `_extensions/`, `theme/` | the builder, the recorder, the player and the look, copied from the skill | no: replace them together from a newer skill |
| `media/voices/<name>/` | a voice: its audio and `voice.js`. A synthetic voice is made again by the build; a recorded one is yours | delete a folder to remove that voice |
| `build/`, `media/manifest.js`, `media/voices/index.js`, `talk.html`, `talk_files/` | what the build writes | no |

## Build

```sh
sh build.sh                     # figures, the voice of talk.qmd (only new or changed sentences), the page, a check
sh build.sh --no-voice          # the slides only, nothing spoken
sh build.sh --script            # only print the narration with its timing and recording names; builds nothing
sh build.sh --shots             # also a picture of every slide in build/shots/
sh build.sh --voice=bm_george   # add another synthetic voice (--speed=1.2 for another pace); the slides stay as they are
sh build.sh --bundle=both       # talk-af_heart.html: one file with the voice and the clips inside (voice: the voice only; clips: the clips, no voice)
```

Needs `uv`, `quarto` and `chromium` (the check; `--no-check` skips it). Only sentences whose wording, voice or
speed changed are spoken again, so a second build takes seconds. Open `talk.html` in a browser; `?` lists the keys.

## Your own voice

1. `sh build.sh --script` lists every sentence with a name such as `03.2` (slide 3, step 2; `talk.html#3.2` shows it).
2. Record each sentence as `media/voices/me/03.2.wav` (or `.mp3`, `.ogg`, `.flac`).
3. `sh build.sh --import-voice=me` binds each file to its sentence and says which sentences have none yet.

After you change a sentence, build, then import again: the other recordings stay bound to their sentences, and the
import names the ones to record again. A step without a recording runs silently on its estimated length.

## Record a video

```sh
nix shell nixpkgs#ffmpeg -c uv run --no-project --with soundfile --with numpy --with pillow python record.py talk.html
```

writes `talk.mp4` and `talk.srt` beside the page, with the voice the talk opens with (`--voice=NAME` for another,
`--from=S --to=S` for a trial stretch).
