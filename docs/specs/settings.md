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
| `icons` | `"omarchy"`, `"vector"`, `"painted"` | `"omarchy"` |

```json
{ "position": "top-right", "sound": true, "icons": "omarchy" }
```

## Files OmaTrophy owns

| Path | Holds |
| --- | --- |
| `~/.config/omatrophy/config.json` | The settings above. |
| `~/.local/state/omatrophy/names.json` | Steam game names, so offline toasts keep them. |
| `~/.local/state/omatrophy/inbox.jsonl` | Events queued by `omatrophy.py test`. |
| `~/.cache/omatrophy/` | Achievement icons (`icons/<store>/<game>/`) and art. Safe to delete. |

## `manifest.json`

Kinds `service` (`Service.qml`) and `bar-widget` (`Panel.qml`), bar category
Gaming, default section right, one instance. The panel's IPC target is
`pym.omatrophy` (`open`, `close`, `toggle`, from Omarchy's `Panel`).
