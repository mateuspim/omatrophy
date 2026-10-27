# OmaTrophy unlock sounds: brief

OmaTrophy shows game achievement unlocks as toasts on Omarchy, a Linux
desktop (Arch + Hyprland) with a calm, terminal-native look. The toast slides
in over a running game; the sound plays the moment it appears. The sound is
the reward: it should feel earned and a little precious, the way a
PlayStation trophy "ding" does, without copying it, and without ever being
annoying over game audio or the tenth time in an evening.

## Deliverables

Four mono WAV files, 48 kHz, 16-bit, one per tier, clearly one family (same
key, same instruments), each step up feeling bigger and rarer:

| file | when | length (to inaudible) | feel |
|---|---|---|---|
| `bronze.wav` | common unlock (most players have it) | 0.3–0.6 s | a small, satisfying tick-ding; never grating on repeat |
| `silver.wav` | uncommon (35% of players or fewer) | 0.6–1.0 s | brighter, a short rising figure |
| `gold.wav` | rare (10% or fewer) | 1.0–1.6 s | a flourish with sparkle; the card also bursts glitter |
| `platinum.wav` | the game is 100% complete | 2.0–3.5 s | the big one: it plays as a platinum trophy lands after spinning in, then a wide card opens; a struck chord into a shimmering bloom that rings out |

## Hard constraints

- Make them from code you write here (synthesis), standard-library Python
  only (`wave`, `math`, `struct`, `random`): no numpy, no downloaded
  samples, no network, nothing with a licence question. Put the generator in
  this folder as `generate.py`; running it must rebuild every file.
- Starts with the transient: the first audible energy within 5 ms, no
  silence lead-in, no click (ramp the attack over a few ms).
- Ends clean: fade the tail, trim below about -50 dB, no truncated ring.
- Peak around -3 dBFS, no clipping. The player plays them at 60% volume;
  they should sit about as loud as a desktop notification, not louder.
- Pleasant through cheap laptop speakers and headphones: avoid
  sub-150 Hz energy and harsh 2–5 kHz piercing tones; glassy highs are fine
  if they're soft.
- Musical: a major or lydian colour, consonant, tuned (equal temperament,
  A4 = 440). No speech, no fanfare brass parody, no 8-bit square waves
  unless they're very soft (the trophy art is pixel-grid, so a hint of that
  is welcome, but the sound should feel premium, not retro-cheap).

## Check your work

You can't listen, so measure: print each file's length, peak dBFS, the
RMS envelope in 50 ms steps, and the spectral centroid over time, and check
them against the table above. Write `NOTES.md`: the idea behind each sound,
the measurements, and what you'd change with more time.
