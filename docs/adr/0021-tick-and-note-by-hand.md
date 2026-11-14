# 21. Tick, count and take notes by hand, in a file of the player's own

- Status: Proposed
- Date: 2026-11-14
- Answers the open question of [ADR 9](0009-tracker-is-an-overlay.md)
  and [ADR 14](0014-generate-guides-through-the-users-agent.md) ("slice f")

## Context

OmaTrophy only sees what a store records. The player sometimes knows
more:

- an achievement that is done but the store missed (stats that never
  synced, a broken trigger, one got on another copy of the game);
- a counter the store doesn't track (every GOG counter, and Steam ones
  whose schema names no progress stat), where the guide gives a target
  (`counter: {target, label}`) but the tracker can only show 0;
- things to remember: "the safe code is 4521", "skip the boss on the
  first visit".

Guides already have one kind of hand tick: a `[x]` line without
`_(unlocked ...)_` in a guide's `.md` (the owner's earlier games app
wrote them). `guides.py` reads them into `guide`'s `ticks`, they count
as done for Up next, the steps, Do now and the missable reminder, and
the maker carries them over when it rewrites the checklist. Nothing in
OmaTrophy can make one: the tracker is read-only (ADR 9), and the
reader never writes a guide (ADR 14). The "I'm here" pin (ADR 17's
`guide here`) set the pattern for the player's own state: a small JSON
file keyed `store:app`, written only through a CLI command the tracker
runs, never inside the guide files.

## Decision (proposed; see Open choices below)

- **One file, the player's own.** Ticks, counts and notes live in
  `~/.local/share/omatrophy/by-hand.json` (`$XDG_DATA_HOME` respected),
  keyed `"store:app"`, then by achievement `api`. It sits beside the
  guides, not in the state folder: a note is writing the player can't
  get back, which state (like the `guide here` pin) is not. It works
  for every game, with a guide or without.
- **Written only by `omatrophy.py hand ...`.** The tracker runs the
  command as it runs `guide here` or `showcase` (no shell, arguments as
  an argv list); QML never writes a file. Each write reads, changes one
  entry and replaces the file atomically under an `fcntl` lock, so two
  quick clicks can't lose one. Reads never write; a broken file reads
  as empty and the next write keeps a `.bad` copy before starting anew.
- **The store stays the truth for progress.** A tick, or a count at
  its target, is not an unlock: no toast, no chime, no platinum card,
  no change to `unlocked`, `total`, percentages, the cabinet, the
  panel's shelves or "closest to platinum". It counts as *done* where
  a guide plans play: `guide`'s `ticks` (so Up next, the steps, YOU ARE
  HERE, Do now and the missable reminder skip it), and the tracker
  marks it "by hand".
- **Guide `.md` ticks still count; the file can overrule them.**
  `ticks` = hand ticks in the guide's `.md` plus the file's ticks,
  minus the ones the file unticks (`done: false`). OmaTrophy still
  never writes a guide to tick; the maker keeps carrying `.md` hand
  ticks over as today. Nothing is migrated.
- **A store unlock wins.** Ticking an unlocked achievement is refused
  ("already unlocked in Steam"); a tick the store later confirms stays
  in the file, unused.
- **Counts by hand** only where the store gives none: an item whose
  guide has a `counter` target and whose `progress` is `null`. The
  tracker's bar shows the store's count when there is one, else the
  hand count. A count reaching its target does not tick by itself.
- **Notes are plain text**: one per achievement and one per game,
  shown as `Text.PlainText` (never Markdown or rich text), control
  characters other than newline dropped, at most 1000 characters per
  achievement and 4000 per game. A note on a hidden, locked
  achievement stays hidden with its name until revealed.
- No new event, no new setting, no network. Only `omatrophy.py`,
  `guides.py` and `TrackerView.qml` change, so no shell restart.

Shapes: [by hand](../specs/by-hand.md).

## Consequences

- The tracker writes state for the first time; ADR 9's "read-only"
  now means it never writes a file itself, only through the CLI.
- Two "by hand" sources must agree: the `.md` checklist (read-only to
  OmaTrophy) and `by-hand.json`. A tick made in the tracker never
  reaches the `.md`, so the owner's other app doesn't see it.
- Progress numbers can say 47/58 while the guide says one more is
  done; the tracker's header shows both ("47 / 58 · 1 by hand") so it
  doesn't look like a bug.
- `by-hand.json` is the player's data, like the guides: the README and
  settings spec list it as not safe to delete.
- Notes are text the player typed, shown back in the overlay; showing
  them as plain text keeps a pasted link or tag inert.

## Open choices (the owner's; recommendation first)

1. Where the file lives: `~/.local/share/omatrophy/by-hand.json`
   (recommended: notes are the player's writing, kept with the guides),
   or `~/.local/state/omatrophy/` beside the `guide here` pin.
2. Whether a tick counts as an unlock: no (recommended; the store stays
   the truth for toasts, platinum, percentages and the panel), or yes
   for progress too.
3. `.md` hand ticks: read both and let the file overrule (recommended),
   migrate them into the file once, or let the tracker write the `.md`.
4. Ticks for games without a guide: yes (recommended), or only on the
   Guide tab.
5. Counts by hand in F2: yes, only where a guide gives a target and the
   store no count (recommended); or leave counts for later.
6. Notes: one per achievement and one per game, plain text, 1000 / 4000
   characters (recommended); or per game only.
7. Keys: Ctrl+Enter tick, Ctrl+N note, Ctrl+Up/Down count, plus click
   targets (recommended); plain letters stay type-to-search.
8. Ticking an achievement the store already unlocked: refused
   (recommended), or allowed and ignored.
9. The panel: no change in F2 (recommended); a game note on the Now
   tab's playing card could come later.
10. Release: 0.13.0, no shell restart (recommended; only
    `omatrophy.py`, `guides.py` and `TrackerView.qml` change).
