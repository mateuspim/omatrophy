# Command line

`python3 omatrophy.py <command>`, from anywhere (it finds its own folder).
Exits non-zero with a message when no store with achievement data is
installed.

| Command | Does |
| --- | --- |
| `watch` | The default. Prints [event lines](events.md) until killed. `Service.qml` runs this. |
| `test [kind]` | Queues one sample event for a running watcher, built from your most recently played game. `kind`: `bronze`, `silver`, `gold` (or `rare`), `platinum`; `unlock` (the default) keeps the achievement's real rarity. |
| `status` | Prints `[{store, app, unlocked, total}]` for every game with achievements, most complete first. |
| `cabinet` | Prints `{games, trophies, platinums, nearest}`: totals across every game, and `nearest`, the four started, unfinished games closest to 100%, each a `status` row plus `game` (name) and `header` (art URL). |
| `now` | Prints [what the bar panel's Now tab shows](#now), in one read of every store. |
| `games` | Prints [every game with achievements](#games) for the panel's Games tab. The first run looks up uncached names (eight at a time); later runs read the cache. |
| `game [store app]` | Prints [one game's every achievement](#game) for the tracker. Without arguments: the game running now, else the one played last. Exits non-zero, with what to do, when the game has no cached achievements. |
| `set position top-center\|top-left\|top-right` | Where cards appear. |
| `set sound on\|off\|omatrophy\|classic` | The chime: on, off, or which set (which also turns it on). |
| `set icons omarchy\|vector\|painted` | Trophy art set. |
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
  percent}`; `icon` is the greyed-out one and `desc` is `""` for hidden
  achievements.
- `recent`: the three games played last, minus the running one.
- `shelf`: every complete game, newest platinum first, with `latest` empty.

## games

`[{store, app, game, header, unlocked, total, platinum, played}]`, one per
game with achievements, in no set order: the panel sorts them (recent,
closest to platinum, name). `played` is `0` when the store doesn't say.

## game

```json
{"store": "steam", "app": "1774580", "game": "...", "unlocked": 4, "total": 53,
 "header": "...", "hero": "...", "platinum": 0, "playing": true,
 "achievements": [{"api": "...", "name": "...", "desc": "...", "icon": "...",
                   "icon_locked": "...", "hidden": false, "unlocked": true,
                   "time": 1793059700, "percent": 82.4, "tier": "bronze"}]}
```

Achievements come in the store's order; the tracker sorts them. `percent` is
`null` when the store doesn't say, and `tier` is the metal the unlock would
get ([ADR 3](../adr/0003-rarity-picks-the-metal.md)).

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
