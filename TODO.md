# sci-narrated-talk: to do

The design is in [README.md § Voices](README.md#voices-the-slides-and-the-voice-as-separate-layers-planned-050-on).

## Phase 1 (0.5.0): voices as folders beside the slides

- [ ] The build makes the slides without speech synthesis; a talk with no voice opens
      as a deck to present by hand (no warning, no voice button, estimated lengths,
      P runs it silently).
- [ ] A synthetic voice is built into `media/voices/<name>/` (audio + `voice.js`)
      without rendering the slides again; only new or changed sentences are spoken.
- [ ] Your own reading of the script: one file per sentence (names from `--script`),
      imported into a voice folder; the import measures the files and binds each to
      its sentence's text.
- [ ] The page finds the voices beside it when it opens, offers "none" and each voice
      in the settings and in the address, remembers the choice, and recomputes the
      clock when the voice changes. A deleted voice folder is simply absent.
- [ ] Steps a voice lacks (narration edited later) run silently on their estimate; the
      settings and the build say how many.
- [ ] Single-file export with one voice inside (replaces `embed: true`).
- [ ] `record.py` takes the voice to record with and refuses "none".
- [ ] The `voice.js` format holds a step's start inside its file, so phase 1b fits
      without changing it.
- [ ] Talks written for 0.4.0 build unchanged; the speech already synthesised is reused.

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
