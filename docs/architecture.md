# Architecture

OmaTrophy has two halves: a Python watcher that turns game stores' local
achievement data into JSON event lines, and QML in the Omarchy shell that
turns those lines into cards on screen.

```text
 launcher files ──▶ stores/<id>.py ──▶ omatrophy.py watch ──stdout──▶ Service.qml ──▶ TrophyToast.qml
 (Steam, Comet)      read + describe     diff, tier, events   JSON lines   queue, window      PlatinumCard.qml
                                              ▲                               ▲
           omatrophy.py test ──▶ inbox.jsonl ─┘        config.json ───────────┤ (watched live)
                                                                    Omarchy's quiet.json ┘ (Do Not Disturb)
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
| `stores/gog.py` | GOG through Heroic: reads Comet's per-game SQLite database read-only (achievements, unlock times, GOG's rarity), pairs Comet's client ids with product ids from install folders, and takes titles, art and last-played times from Heroic's files (ADR 12). |
| `stores/steam_community.py` | The opt-in backfill for games that never ran here: reads the JSON embedded in a public profile's achievement pages, cached under `~/.cache/omatrophy/community/` (ADR 11). |
| `stores/steam_loader.py` | Load from Steam: opens played games' library pages through `steam://` links so the client caches their stats, on request only (`omatrophy.py steam-load`, ADR 13). |
| `guides.py` | Reads 100% guides: finds a game's `.md` by its trailing id, parses notes, checklist and `.plan.json`, matches items to achievements (`omatrophy.py guide`), and imports guide files. |
| `by_hand.py` | The player's ticks, counts and notes by hand in `~/.local/share/omatrophy/by-hand.json` (ADR 21): reads them for `game` and `guide`, writes them for `omatrophy.py hand` only, under a lock. A tick is done for the guide, never an unlock. |
| `guide_maker.py` | Makes a guide on request (ADR 14): gather sources, research, classify, route, verify quotes, write the files; status and stop like Load from Steam. Prompts in `prompts/guide/`. |
| `guide_bench.py` | `guide bench`: makes one game's guide with several agents and models side by side and ranks them by what can be checked ([guides](specs/guides.md#benchmark)). |
| `guide_key.py` | The Guide key (ADR 18): parses a key, checks it against Hyprland's binds and binds or unbinds it at runtime through `hyprctl`; never edits Hyprland's config. |
| `guide_agents.py` | One adapter per coding agent: its locked headless command, model list and answer parsing; only adapters whose lock was checked run. |
| `stores/__init__.py` | The list of stores; `available()` keeps the installed ones. |
| `difficulty.py` | Reads from an achievement's own text the difficulty setting it needs ("on Nightmare", "Normal or higher"), for the `difficulty` fields of `game` and `games`. Pure, no store or network. |
| `omatrophy.py` | Watch loop (unlocks and counter milestones), launch watch (the difficulty and missable reminders, the session recap when a game stops), diffing, tiers, event shapes, test inbox, settings, the panel's and tracker's JSON (`now`, `games`, `game`), CLI. |
| `Service.qml` | Runs the watcher, parses lines, queues events, plays the chime, shows one card at a time in an Overlay-layer window on the focused monitor (or the one in `screen`), holding cards while Omarchy's Do Not Disturb is on (ADR 22). |
| `TrophyToast.qml` | One unlock: icon, trophy in the tier's metal, rarity, progress. |
| `DifficultyCard.qml` | The difficulty reminder at a game's launch: the settings its achievements left need, and whether the guide says they stack. |
| `MissableCard.qml` | The missable reminder at a game's launch: the guide's current step and what can be missed in it. |
| `RecapCard.qml` | The session recap when a game stops: its length, trophies, rarest unlock and the game's progress. |
| `MilestoneCard.qml` | A small toast when a counter achievement passes 50, 75 or 90% of its goal. |
| `cards.json` | The one table of cards: each event type's QML file, chime, rank in the queue and whether a full queue may drop it. `Service.qml` reads it live; `omatrophy.py` lets only its types through the test inbox. |
| `PlatinumCard.qml` | 100% of a game: badge, ring, trophy, then a wide card over the hero art. With `still`, straight to the opened card, for the saved image. |
| `PlatinumShare.qml` | The saved platinum image: `PlatinumCard.qml` held open over the game's blurred art, with the date and store along the bottom. Loaded only by `share.py`'s throwaway Quickshell, never the live shell. |
| `share.py` | `omatrophy.py share`: draws `PlatinumShare.qml` in an offscreen Quickshell on the GPU and saves the PNG to the pictures folder (ADR 23). |
| `Panel.qml` | Bar button; opens a `KeyboardPanel` that loads `StylePicker.qml`, and turns its `track` signal into a summon of the tracker. |
| `StylePicker.qml` | Four tabs. Now: guides being made, totals, the running game (or the last three), rarest unlocks and the platinum shelf, from `omatrophy.py now`. Profile: favorite game, showcase, completionist and playtime. Games: every game, sortable, from `omatrophy.py games` on first open. Settings: toasts (style, position, glass, monitor, Do Not Disturb, sound, reminders, Try), the Now tab's sections, guides and stores, through `omatrophy.py set`; it asks `omatrophy.py running` whether the shell needs a restart. |
| `FreshObject.qml` | Builds a sibling QML file from its current text, so the cards, the panel content and the tracker pick up edits without a restart. |
| `Tracker.qml` | The `overlay` entry point (kept loaded): a dimmed full-screen window that takes the keyboard while open and loads `TrackerView.qml`, kept built between opens while its text is unchanged (ADR 19). |
| `TrackerView.qml` | One game's every achievement with rarity and dates; filters, type-to-search and a keyboard-driven highlight. Its Guide tab shows the game's 100% guide and starts or stops a make (`omatrophy.py guide make`, detached). |
| `assets/<set>/` | Trophy art: `omarchy` (pixel grid, theme-tinted inlay), `vector`, `painted`. |

## Data flow

1. On start, `watch` instantiates every installed store, records each game's
   change token and unlocked set, writes `watcher.json` (its version, the
   `Service.qml` version it was started with, the cards it lets through)
   and prints a `ready` line.
2. Once a second it forwards new lines from the test inbox and asks each
   store for its tokens. For each game whose token changed it rereads the
   achievements, diffs the unlocked set and prints an `unlock` line per new,
   recent unlock (ADR 4), then a `platinum` line if that completed the game,
   and a `milestone` line per counter that passed 50, 75 or 90% since the
   last read.
3. `Service.qml` queues the lines `cards.json` has a card for (the launch
   reminders ahead of toasts), plays a chime for unlocks, and
   builds the matching card from its current text (ADR 10) into a click-through
   window on the Overlay layer (ADR 2). The card reports `finished`; the next
   event shows. While Omarchy's Do Not Disturb is on (its notification
   service's `quiet.json`) and `dnd` is `hold`, cards wait in the queue
   until it ends, except one queued by `test` (ADR 22).
4. Settings live in `~/.config/omatrophy/config.json`; `Service.qml` and the
   picker watch it, so changes apply to the next card.
5. The panel runs `omatrophy.py now` each time it opens. Clicking a game
   summons the plugin's overlay with `{store, app}`; `Tracker.qml` passes it
   to `TrackerView.qml`, which runs `omatrophy.py game --guide` (ADR 9, ADR 19).
6. The shell keeps its startup `Service.qml` and watcher until a restart,
   while the panel is built fresh: Settings asks `omatrophy.py running`,
   which compares `watcher.json` with the installed version, and offers a
   restart instead of a Try the old watcher would drop.
7. Save image (the tracker of a finished game, or a shelf tile) runs
   `omatrophy.py share --notify`, which starts its own offscreen Quickshell
   to draw `PlatinumShare.qml`, writes the PNG and exits; the live shell
   draws nothing for it (ADR 23).

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
- Nothing runs as root and nothing outside OmaTrophy's own files is written,
  except the platinum images you ask for in `~/Pictures/omatrophy/`
  ([SECURITY.md](../SECURITY.md)).
