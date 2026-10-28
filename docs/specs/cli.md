# Command line

`python3 omatrophy.py <command>`, from anywhere (it finds its own folder).
Exits non-zero with a message when no store with achievement data is
installed.

| Command | Does |
| --- | --- |
| `watch` | The default. Prints [event lines](events.md) until killed. `Service.qml` runs this. After `ready` it looks up uncached game names in the background (eight at a time, 4 s timeout each); events never wait on it. |
| `test [kind]` | Queues one sample event for a running watcher, built from your most recently played game. `kind`: `bronze`, `silver`, `gold` (or `rare`), `platinum`; `unlock` (the default) keeps the achievement's real rarity. |
| `status` | Prints `[{store, app, unlocked, total}]` for every game with achievements, most complete first. |
| `cabinet` | Prints `{games, trophies, platinums, nearest}`: totals across every game, and `nearest`, the four started, unfinished games closest to 100%, each a `status` row plus `game` (name) and `header` (art URL). |
| `now` | Prints [what the bar panel's Now tab shows](#now), in one read of every store, and keeps a copy in `~/.cache/omatrophy/panel/now.json` that the panel shows on its next open until a fresh read answers. |
| `games` | Prints [every game with achievements](#games) for the panel's Games tab. Uncached names are looked up eight at a time; the watcher warms that cache in the background after `ready`, so this is usually a file read. Keeps a copy in `~/.cache/omatrophy/panel/games.json`, like `now`. |
| `game [store app]` | Prints [one game's every achievement](#game) for the tracker. Without arguments: the game running now, else the one played last. Exits non-zero, with what to do, when the game has no cached achievements. |
| `set position top-center\|top-left\|top-right` | Where cards appear. |
| `set sound on\|off\|omatrophy\|classic` | The chime: on, off, or which set (which also turns it on). |
| `set icons omarchy\|vector\|painted` | Trophy art set. |
| `set glass clear\|frosted\|solid` | How see-through toasts are. |
| `set tracker-sort recent\|rarity\|name\|game` | The tracker's sort; the tracker writes it when you change it. |
| `set community on\|off` | The opt-in backfill of games that never ran on this machine from your public Steam profile ([ADR 11](../adr/0011-backfill-from-the-community-profile.md)). With it on, the watcher fetches in the background after `ready`. |
| `sync` | Runs that backfill now, one line per game (`steam: 3/444 1903340: 55 achievements`), at most 15 pages a run, ending `paused: N fetched, M left for later runs` when more are due, then `fetched N`; "stopped early" after any error (a 429 rate limit, offline, private profile), and the next run picks up where it stopped. The watcher runs the same backfill every hour. Exits non-zero while `community` is off. |
| `hide <store> <game>` | Adds `"store:game"` to `hidden` in config.json: the game leaves `cabinet`'s `nearest`, the Games tab's Closest sort and the panel's platinum shelf (`now` still lists it in `shelf`; the panel filters). Exits non-zero for an unknown store. |
| `unhide <store> <game>` | Takes it back out. |
| `demo [kind...]` | Prints sample events straight to stdout, then idles. For `dev/preview.sh`. |

`set` writes [the settings file](settings.md); the shell applies it to the
next card.

Times are unix seconds; `0` means unknown or not yet. Art and icon fields
are URLs (`https://` or `file://`) or `""`.

## now

```json
{"games": 126, "trophies": 1779, "platinums": 12,
 "playing": {...card, "hero": "...", "since": 1793065549, "session": [...], "next": [...]} | null,
 "recent": [card, ...], "shelf": [card, ...]}
```

- A **card** is a `status` row plus `game`, `header`, `played` (last
  played), `platinum` (when the last achievement came, `0` while any is
  locked) and `latest`, the five newest unlocks as `{name, icon, time}`.
- `playing`: the game running now, or `null`. `hero` is its wide art (no
  logo), `since` when it started,
  `session` the unlocks since then (newest first, up to 12), `next` the three
  locked achievements most players have, as `{name, icon, time, desc,
  percent, progress}`; `icon` is the greyed-out one, `desc` is `""` for
  hidden achievements and `progress` is as in [game](#game).
- `recent`: the three games played last, minus the running one.
- `shelf`: every complete game, newest platinum first, with `latest` empty.

## games

`[{store, app, game, header, unlocked, total, platinum, played, hidden}]`,
one per game with achievements, in no set order: the panel sorts them
(recent, closest to platinum, name). `played` is `0` when the store doesn't
say; `hidden` is `true` for games set aside with `hide`.

## game

```json
{"store": "steam", "app": "1774580", "game": "...", "unlocked": 4, "total": 53,
 "header": "...", "hero": "...", "platinum": 0, "playing": true,
 "achievements": [{"api": "...", "name": "...", "desc": "...", "icon": "...",
                   "icon_locked": "...", "hidden": false, "unlocked": true,
                   "time": 1793059700, "percent": 82.4, "tier": "bronze",
                   "progress": null}]}
```

Achievements come in the store's order; the tracker sorts them. `percent` is
`null` when the store doesn't say, and `tier` is the metal the unlock would
get ([ADR 3](../adr/0003-rarity-picks-the-metal.md)). `progress` is
`{"value": 12, "max": 15}` on a locked counter achievement whose store
tracks the count (Steam: the schema's progress stat, once the game has
written it; an unwritten stat is unknown, not 0), else `null`; `value`
is already clamped to `0..max`, and `max` is at least 2 (a one-step
"counter" is a plain flag, so it gets `null`).

## Overlay

The tracker is the plugin's `overlay` entry point. Open it from a script
with the same JSON:

```sh
omarchy-shell shell summon pym.omatrophy '{"store":"steam","app":"1774580"}'
omarchy-shell shell summon pym.omatrophy '{}'   # the running or last game
```

## Environment

| Variable | Effect |
| --- | --- |
| `STEAM_DIR` | Steam folder, when it isn't in `~/.local/share/Steam`, `~/.steam/steam` or the Flatpak path. |
| `STEAM_ACCOUNT` | Steam account id (the number in `UserGameStats_<id>_<app>.bin`), when several accounts share the machine. Default: the one with the most games. |
