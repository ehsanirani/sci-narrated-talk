# sci-narrated-talk: to do

The design is in [README.md § Voices](README.md#voices-the-slides-and-the-voice-as-separate-layers);
the format and the commands in `references/authoring.md`, Voices.

## Phase 1 (0.5.0): voices as folders beside the slides — done 2026-11-22

- [x] The build makes the slides without speech synthesis (`--no-voice`, or
      `voice: false`); a talk with no voice opens as a deck to present by hand (no
      warning, no voice button, estimated lengths, P runs it silently).
- [x] A synthetic voice is built into `media/voices/<name>/` (audio + `voice.js`)
      without rendering the slides again (`--voice=NAME --speed=X --lang=L`; folder
      `NAME-X-L` where speed and language are not the voice's own); only new or changed
      sentences are spoken.
- [x] Your own reading of the script: one file per sentence (names from `--script`,
      `03.2.wav`; wav, mp3, ogg, flac), imported with `--import-voice=NAME`, which
      measures the files, binds each to its sentence's text and renames it
      `03.2-<hash>.wav` so that no later recording overwrites it.
- [x] The page finds the voices beside it when it opens (`media/voices/index.js`, each
      `voice.js` loaded as a script), offers "none" and each voice in the settings and in
      the address (`?narrator=NAME`), remembers the choice, and recomputes the clock when
      the voice changes. A deleted voice folder is simply absent.
- [x] Steps a voice lacks (narration edited later) run silently on their estimate; the
      settings and the build say how many.
- [x] Single-file export with one voice inside: `--bundle=NAME` (and `embed: true`).
- [x] `record.py` takes the voice to record with (`--voice=NAME`) and refuses "none".
- [x] The `voice.js` format holds a step's start inside its file (`at`), so phase 1b
      fits without changing it.
- [x] Talks written for 0.4.0 build unchanged; the speech already synthesised is reused
      (moved from `media/audio/`).

Found on the way, not done:

- [ ] `plain()` keeps a Markdown link's URL (`[a](url)`): the sentence is spoken with
      the URL and its text key differs from the page's, so the check fails (as 0.4.0's
      "Narration out of date" did).
- [ ] `record.py` stops on recordings at different sample rates; an imported voice could
      be resampled instead.
- [ ] `--import-voice` takes no label; the settings show the folder's name.
- [ ] `record.py`'s frames differ slightly from run to run (pointer regions), in 0.4.0 too:
      find what is not deterministic in `?rec` (a pointer's animation time?).

## Phase 1b: free voice

- [ ] One recording per slide plus a cue per step; the page plays it continuously and
      the steps follow its time (no added pauses).
- [ ] Cues imported from a file of times (Audacity labels, or a plain list).
- [ ] Captions off for a free voice; phrased pointers all on for the step.
- [ ] A slide whose steps changed after its recording is reported, to record or cue
      again.

## Phase 2: recording in the page

- [ ] A record mode: present by hand, speaking freely; the page records the microphone
      per slide and takes each Space press as a cue; saves the voice to import.
- [ ] Tapping cues along an existing recording, and correcting them.
- [ ] Check first: microphone access from a page opened as `file://` in Firefox and
      Chromium.

## Smaller items

- [ ] Presenting by hand from reveal.js's speaker-view window: its keys are reveal's
      (P steps back there, nothing plays the voice).
