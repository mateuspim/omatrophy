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
                                          │   ▲
                                 summon   │   └── omatrophy.py now
                                          ▼
                                     Tracker.qml ──▶ TrackerView.qml ◀── omatrophy.py game
```

## Components

| File | Role |
| --- | --- |
| `stores/base.py` | The `Store` contract and shared helpers (JSON files, HTTP, image cache). |
| `stores/steam.py` | Steam: binary and text KeyValues parsers, stats cache, rarity (cached a day), names, art, the running game (`/proc`) and last-played times (`localconfig.vdf`). |
| `stores/steam_community.py` | The opt-in backfill for games that never ran here: reads the JSON embedded in a public profile's achievement pages, cached under `~/.cache/omatrophy/community/` (ADR 11). |
| `stores/__init__.py` | The list of stores; `available()` keeps the installed ones. |
| `omatrophy.py` | Watch loop, diffing, tiers, event shapes, test inbox, settings, the panel's and tracker's JSON (`now`, `games`, `game`), CLI. |
| `Service.qml` | Runs the watcher, parses lines, queues events, plays the chime, shows one card at a time in an Overlay-layer window on the focused monitor. |
| `TrophyToast.qml` | One unlock: icon, trophy in the tier's metal, rarity, progress. |
| `PlatinumCard.qml` | 100% of a game: badge, ring, trophy, then a wide card over the hero art. |
| `Panel.qml` | Bar button; opens a `KeyboardPanel` that loads `StylePicker.qml`, and turns its `track` signal into a summon of the tracker. |
| `StylePicker.qml` | Three tabs. Now: totals, the running game (or the last three) and the platinum shelf, from `omatrophy.py now`. Games: every game, sortable, from `omatrophy.py games` on first open. Settings: trophy style, previews, position and sound, through `omatrophy.py set`. |
| `FreshObject.qml` | Builds a sibling QML file from its current text, so the cards, the panel content and the tracker pick up edits without a restart. |
| `Tracker.qml` | The `overlay` entry point: a dimmed full-screen window that takes the keyboard while open and loads `TrackerView.qml`. |
| `TrackerView.qml` | One game's every achievement with rarity and dates; filters, type-to-search and a keyboard-driven highlight. Read-only. |
| `assets/<set>/` | Trophy art: `omarchy` (pixel grid, theme-tinted inlay), `vector`, `painted`. |

## Data flow

1. On start, `watch` instantiates every installed store, records each game's
   change token and unlocked set, and prints a `ready` line.
2. Once a second it forwards new lines from the test inbox and asks each
   store for its tokens. For each game whose token changed it rereads the
   achievements, diffs the unlocked set and prints an `unlock` line per new,
   recent unlock (ADR 4), then a `platinum` line if that completed the game.
3. `Service.qml` queues `unlock` and `platinum` lines, plays a chime, and
   builds the matching card from its current text (ADR 10) into a click-through
   window on the Overlay layer (ADR 2). The card reports `finished`; the next
   event shows.
4. Settings live in `~/.config/omatrophy/config.json`; `Service.qml` and the
   picker watch it, so changes apply to the next card.
5. The panel runs `omatrophy.py now` each time it opens. Clicking a game
   summons the plugin's overlay with `{store, app}`; `Tracker.qml` passes it
   to `TrackerView.qml`, which runs `omatrophy.py game` (ADR 9).

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
