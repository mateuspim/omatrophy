# Settings and manifest

## `~/.config/omatrophy/config.json`

Optional; missing keys and invalid values fall back to the default.
`Service.qml` and `StylePicker.qml` watch the file, so edits apply to the
next card without a restart. Written by `omatrophy.py set` (and so by the
bar panel).

| Key | Values | Default |
| --- | --- | --- |
| `position` | `"top-center"`, `"top-left"`, `"top-right"` | `"top-center"` |
| `sound` | `true`, `false` | `true` |
| `chimes` | `"omatrophy"` (`assets/sounds/<tier>.wav`), `"classic"` (freedesktop sounds) | `"omatrophy"` |
| `icons` | `"omarchy"`, `"vector"`, `"painted"` | `"omarchy"` |
| `glass` | How much of the screen shows through a toast: `"clear"`, `"frosted"`, `"solid"` (the platinum card stays solid) | `"frosted"` |
| `games-sort` | The Games tab's last sort: `"recent"`, `"closest"`, `"name"`. Written when you pick one. | `"recent"` |
| `rarest` | The Now tab's last rarest-unlocks list: `"ever"`, `"month"`, `"platinum"`. Written when you pick one. | `"ever"` |
| `tracker-sort` | `"recent"`, `"rarity"`, `"name"`, `"game"` (the store's own order) | `"recent"` |
| `community` | `true`, `false`: fill in games that never ran here from your public Steam profile (ADR 11) | `false` |
| `now-metals`, `now-recent`, `now-rarest`, `now-shelf` | `true`, `false`: show the bar panel's Now-tab section (the metal tally, recently played, rarest unlocks, the platinum shelf). The game you're playing always shows. | `true` |
| `showcase` | Up to six trophies on the Profile tab's showcase, in the order pinned: `"store:game:api"` for one achievement, `"store:game"` for a game's platinum. Written by `omatrophy.py showcase` and the tracker's ☆; empty shows your rarest instead. | `[]` |
| `favorite` | The Profile tab's favorite game, `"store:game"`, or `""` for none. Written by `omatrophy.py favorite` and the Profile tab's Choose game. | `""` |
| `completionist` | Up to four finished games on the Profile's completionist tile, `"store:game"`, in the order pinned. Written by `omatrophy.py completionist` and the tracker's ☆ Completionist; empty shows your two newest platinums. | `[]` |
| `hidden` | Games left out of "closest to platinum" and, once finished, off the bar panel's platinum shelf (totals still count them), as `"store:game"` (`"steam:20920"`), sorted. Written by `omatrophy.py hide`/`unhide` and the Games tab. | `[]` |

```json
{ "position": "top-right", "sound": true, "chimes": "omatrophy", "icons": "omarchy",
  "hidden": ["steam:20920"] }
```

## Files OmaTrophy owns

| Path | Holds |
| --- | --- |
| `~/.config/omatrophy/config.json` | The settings above. |
| `~/.local/state/omatrophy/names.json` | Steam game names, so offline toasts keep them. |
| `~/.local/state/omatrophy/gog-clients.json` | Which GOG product each Comet client id belongs to, with its name, read from install folders, so an uninstalled game keeps both. |
| `~/.local/state/omatrophy/inbox.jsonl` | Events queued by `omatrophy.py test`. |
| `~/.cache/omatrophy/` | Achievement icons (`icons/<store>/<game>/`), art, the panel's and tracker's images (`images/<sha1 of URL>`, fetched in the background after the read that first names them), global rarity (`rarity/<game>.json`, refreshed daily), delisted games whose name lookup failed (`name-misses.json`, retried after a day) and, with `community` on, profile pages (`community/games/<app>.json`, refetched after you play, else weekly for games played in the last 60 days and every 60 days for the rest, 180 with nothing unlocked, never for a finished game; `community/none.json` for games without achievements, `community/status.json` for the latest run's line, which Settings shows, and `community/runs.json` for the last 50 runs' budget, pages fetched and whether Steam rate-limited them), and Load from Steam's `steam-load/checked.json` (every game a load tried, `{app: {time, found}}`, never tried again except by `steam-load all`), `steam-load/status.json` (the latest run) and `steam-load/stop` (a stop request, removed when the run sees it). Safe to delete. |

## `manifest.json`

Kinds `service` (`Service.qml`), `bar-widget` (`Panel.qml`) and `overlay`
(`Tracker.qml`), bar category Gaming, default section right, one instance.
The panel's IPC target is `pym.omatrophy` (`open`, `close`, `toggle`, from
Omarchy's `Panel`). `omarchy-shell shell summon pym.omatrophy '<json>'` opens
the tracker ([payload](cli.md#overlay), ADR 9).
