# 19. Keep the tracker built between opens

- Status: Accepted
- Date: 2026-11-06
- Amends [ADR 10](0010-build-views-from-their-text.md) for the tracker

## Context

The owner found the Guide key (ADR 16) slow to show the guide. Measured
in a throwaway Quickshell with their MGSV data:

- the shell mounted the overlay only while open, so each press rebuilt
  `Tracker.qml` and its window;
- `FreshObject` compiled `TrackerView.qml` (about 100 KB) on every open:
  70 to 135 ms;
- the view then ran `game`, and only once it answered, `guide`: about
  75 ms each, one after the other.

## Decision

- `manifest.json` sets `keepLoaded`, so the shell keeps `Tracker.qml`
  mounted between summons, as Omarchy's image picker does.
- `FreshObject` gets `keep`: while the file's text hashes the same, `load()`
  returns the object it built and sets `reused`. An edit still builds anew,
  so ADR 10's live edits hold. The tracker uses it; toasts and the panel
  don't.
- `TrackerView.load()` resets what a fresh view starts with (tab, search,
  reveals, the game and its guide, job state, focus), and closing sets
  `live` off, which stops its polls.
- `Tracker.qml` builds the view a few seconds after the shell starts, so the
  first press skips the compile too.
- `omatrophy.py game [store app] --guide` answers the game and its guide in
  one process.

From a press to the guide on screen went from about 320 ms to about 150 ms
in the harness, before the window's own build, which `keepLoaded` removes.

## Consequences

- One tracker view stays in memory while the shell runs.
- `keepLoaded` also keeps the plugin's service through a plugin hot-reload;
  service changes already need `omarchy restart shell`.
- State a fresh view had for free has to be reset in `load()`; a new piece
  of tracker state must be added there.
