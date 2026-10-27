# Architecture

OmaTrophy has two halves: a Python watcher that turns game stores' local
achievement data into JSON event lines, and QML in the Omarchy shell that
turns those lines into cards on screen.

```
 launcher files ──▶ stores/<id>.py ──▶ omatrophy.py watch ──stdout──▶ Service.qml ──▶ TrophyToast.qml
 (Steam cache)       read + describe     diff, tier, events   JSON lines   queue, window      PlatinumCard.qml
                                              ▲                               ▲
           omatrophy.py test ──▶ inbox.jsonl ─┘        config.json ───────────┘ (watched live)
                                                           ▲
                         Panel.qml ──▶ StylePicker.qml ──▶ omatrophy.py set
```

## Components

| File | Role |
| --- | --- |
| `stores/base.py` | The `Store` contract and shared helpers (JSON files, HTTP, image cache). |
| `stores/steam.py` | Steam: binary KeyValues parser, stats cache, rarity, names, art. |
| `stores/__init__.py` | The list of stores; `available()` keeps the installed ones. |
| `omatrophy.py` | Watch loop, diffing, tiers, event shapes, test inbox, settings, CLI. |
| `Service.qml` | Runs the watcher, parses lines, queues events, plays the chime, shows one card at a time in an Overlay-layer window on the focused monitor. |
| `TrophyToast.qml` | One unlock: icon, trophy in the tier's metal, rarity, progress. |
| `PlatinumCard.qml` | 100% of a game: badge, ring, trophy, then a wide card over the hero art. |
| `Panel.qml` | Bar button; opens a `KeyboardPanel` that loads `StylePicker.qml`. |
| `StylePicker.qml` | Trophy style, previews, position and sound; writes through `omatrophy.py set`. |
| `assets/<set>/` | Trophy art: `omarchy` (pixel grid, theme-tinted inlay), `vector`, `painted`. |

## Data flow

1. On start, `watch` instantiates every installed store, records each game's
   change token and unlocked set, and prints a `ready` line.
2. Once a second it forwards new lines from the test inbox and asks each
   store for its tokens. For each game whose token changed it rereads the
   achievements, diffs the unlocked set and prints an `unlock` line per new,
   recent unlock (ADR 4), then a `platinum` line if that completed the game.
3. `Service.qml` queues `unlock` and `platinum` lines, plays a chime, and
   loads the matching card by a fresh URL (ADR 5) into a click-through
   window on the Overlay layer (ADR 2). The card reports `finished`; the next
   event shows.
4. Settings live in `~/.config/omatrophy/config.json`; `Service.qml` and the
   picker watch it, so changes apply to the next card.

Line shapes are in [specs/events.md](specs/events.md), the CLI in
[specs/cli.md](specs/cli.md), the settings file in
[specs/settings.md](specs/settings.md).

## Boundaries

- The watcher knows nothing about the screen; the shell knows nothing about
  stores. The JSON line is the only coupling (ADR 6).
- A store only reads and describes; it never decides what is new or what
  tier it gets (ADR 7).
- If the watcher exits (no store found, a crash), `Service.qml` restarts it
  after 10 s.
- Nothing runs as root and nothing outside OmaTrophy's own files is written
  ([SECURITY.md](../SECURITY.md)).
