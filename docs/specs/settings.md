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
| `tracker-sort` | `"recent"`, `"rarity"`, `"name"`, `"game"` (the store's own order) | `"recent"` |
| `community` | `true`, `false`: fill in games that never ran here from your public Steam profile (ADR 11) | `false` |
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
| `~/.local/state/omatrophy/inbox.jsonl` | Events queued by `omatrophy.py test`. |
| `~/.cache/omatrophy/` | Achievement icons (`icons/<store>/<game>/`), art, the panel's and tracker's images (`images/<sha1 of URL>`, fetched in the background after the read that first names them), global rarity (`rarity/<game>.json`, refreshed daily), delisted games whose name lookup failed (`name-misses.json`, retried after a day) and, with `community` on, profile pages (`community/games/<app>.json`, refetched after you play, else weekly for games played in the last 60 days and every 60 days for the rest, 180 with nothing unlocked, never for a finished game; `community/none.json` for games without achievements). Safe to delete. |

## `manifest.json`

Kinds `service` (`Service.qml`), `bar-widget` (`Panel.qml`) and `overlay`
(`Tracker.qml`), bar category Gaming, default section right, one instance.
The panel's IPC target is `pym.omatrophy` (`open`, `close`, `toggle`, from
Omarchy's `Panel`). `omarchy-shell shell summon pym.omatrophy '<json>'` opens
the tracker ([payload](cli.md#overlay), ADR 9).
