# By hand: ticks, counts and notes

Status: **Proposed** ([ADR 21](../adr/0021-tick-and-note-by-hand.md)).
Nothing here is built yet; the owner's answers to the ADR's open choices
may change it. Once built, this page describes the code, and the rows
marked *proposed* in [cli](cli.md), [guides](guides.md) and
[settings](settings.md) lose that mark.

## File

`~/.local/share/omatrophy/by-hand.json` (`$XDG_DATA_HOME` respected).
Written only by `omatrophy.py hand ...`; missing or broken reads as
empty (a broken one is kept as `by-hand.json.bad` on the next write).

```json
{"format": 1,
 "games": {
  "steam:418370": {
   "ticks":  {"ACH_SAFE": {"done": true,  "time": 1794000000},
              "ACH_OLD":  {"done": false, "time": 1794000100}},
   "counts": {"ACH_FEATHERS": {"value": 12, "time": 1794000200}},
   "notes":  {"ACH_SAFE": {"text": "Code 4521, office on floor 2", "time": 1794000300}},
   "note":   {"text": "Play Hard first; Madness unlocks after.", "time": 1794000400}}}}
```

| Key | Meaning |
| --- | --- |
| `ticks[api].done` | `true`: done by hand. `false`: not done, overruling a hand tick in the guide's `.md`. |
| `counts[api].value` | Count by hand, an integer from 0 to the guide's `counter.target`. Only for an achievement whose store gives no `progress`. |
| `notes[api].text` | The player's note on one achievement: plain text, newlines kept, other control characters dropped, at most 1000 characters. |
| `note.text` | The player's note on the game, at most 4000 characters. |
| `time` | Unix seconds of the last change. |

Keys OmaTrophy doesn't know are kept on a write. An entry for an `api`
the game no longer has is kept and ignored.

## Command line

All under `hand`, as `guide` groups its own. `<api>` is an achievement's
id from [`game`](cli.md#game). Writes print `{"hand": ..., "guide": ...}`:
the game's state as `game` gives it and its guide as `guide <store> <app>`
prints it (`{}` with none), so the tracker reads both at once, as after
`guide here`.

| Command | Does |
| --- | --- |
| `hand <store> <app>` | Prints the game's [`hand`](#in-game-and-guide) block. |
| `hand tick <store> <app> <api>` | Ticks it. Exits non-zero, with what to do, when the game has no such achievement or the store already says it is unlocked. |
| `hand untick <store> <app> <api>` | Unticks it; also overrules a hand tick in the guide's `.md` (`done: false`). |
| `hand count <store> <app> <api> <n\|+n\|-n\|clear>` | Sets, raises or lowers the count, clamped to `0..target`; `clear` removes it. Exits non-zero when the guide has no `counter` for it or the store tracks its progress. |
| `hand note <store> <app> <api\|game> <text>` | Saves a note on the achievement, or with `game` on the game; `""` removes it. Longer text exits non-zero, saying the limit. |
| `hand clear <store> <app>` | Removes everything the file holds for the game. |

## In `game` and `guide`

`game` gains one key; achievements, `unlocked` and `total` are unchanged
(by hand never counts as unlocked):

```json
"hand": {"ticks": ["ACH_SAFE"], "unticks": ["ACH_OLD"],
         "counts": {"ACH_FEATHERS": 12},
         "notes": {"ACH_SAFE": "Code 4521, office on floor 2"},
         "note": "Play Hard first; Madness unlocks after."}
```

`ticks` leaves out achievements the store has unlocked since. A note on
a hidden, locked achievement is in `notes` like any other; the tracker
keeps it secret with the name.

`guide`'s `ticks` widens: the `.md`'s hand ticks plus `hand.ticks`, minus
`hand.unticks`, in the store's order. Its shape doesn't change, so `next`,
`walkthrough` (`done`, `cleared`), `step`, `frontier`, `stacks` and the
`missable` event all follow by-hand ticks with no other change. Items
gain nothing: the tracker reads counts and notes from `game`'s `hand`.

## Tracker

Trophies tab (every game, with a guide or without):

- A locked row's right edge shows a round tick target on hover or
  highlight; a click (or **Ctrl+Enter** on the highlighted row) ticks
  or unticks it. A ticked row keeps its dim trophy (it isn't an
  unlock) and shows a ✓ and "by hand" where an unlock shows its date.
- **Ctrl+N** (or **Note** in the open row) opens a text box under the
  description: Enter saves, Shift+Enter is a new line, Escape cancels
  without closing the tracker. While it is open, typing goes to it,
  not to the search. A row with a note shows a small ✎ and the note
  under its description.
- A counter row whose store gives no count gets − and + beside its bar
  (**Ctrl+Up** / **Ctrl+Down** on the highlighted row).
- The header's progress reads "47 / 58 · 1 by hand" while any locked
  achievement is ticked. Filters are unchanged: a ticked one is still
  Locked, as the store says.

Guide tab: the steps' ✓, Do now, Up next and YOU ARE HERE already
follow `guide`'s `ticks`. Do now tiles and step names get the same tick
target. **Your notes** (the game's note) folds open under the guide's
overview, with **Edit**.

Every change shows at once and runs `hand ...` detached through one
queue (one process at a time), then takes its answer; a failed write
puts the row back and shows the command's message in the status line.

## Panel

No change. The Now tab's Up next already follows the guide's `next`, so a
by-hand tick leaves it as it leaves the tracker's.
