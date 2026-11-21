# A narrated talk

One HTML page that tells the talk by itself. Everything in it is built from the files in this folder, so to change
the talk, change a source file and build again. Never edit `talk.html`: the next build overwrites it.

| file | what it is | edit? |
|---|---|---|
| `talk.qmd` | the slides and the narration (`::: say` blocks, one sentence each), voice and theme at the top | yes |
| `figures.py` | the drawings and every number the talk quotes | yes |
| `build.sh` | the build command | when `figures.py` needs another package |
| `narrate.py`, `record.py`, `_extensions/`, `theme/` | the builder, the recorder, the player and the look, copied from the skill | no: replace them together from a newer skill |
| `build/`, `media/`, `talk.html`, `talk_files/` | what the build writes | no |

## Build

```sh
sh build.sh            # figures, speech for new or changed sentences, the page, then a run-through check
sh build.sh --script   # only print the narration with its timing; builds nothing
sh build.sh --shots    # also a picture of every slide in build/shots/
```

Needs `uv`, `quarto` and `chromium` (the check; `--no-check` skips it). Only sentences whose wording, voice or
speed changed are spoken again, so a second build takes seconds. Open `talk.html` in a browser; `?` lists the keys.

## Record a video

```sh
nix shell nixpkgs#ffmpeg -c uv run --no-project --with soundfile --with numpy --with pillow python record.py talk.html
```

writes `talk.mp4` and `talk.srt` beside the page (`--from=S --to=S` for a trial stretch).
