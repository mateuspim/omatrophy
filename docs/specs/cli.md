# Command line

`python3 omatrophy.py <command>`, from anywhere (it finds its own folder).
Exits non-zero with a message when no store with achievement data is
installed.

| Command | Does |
| --- | --- |
| `watch` | The default. Prints [event lines](events.md) until killed. `Service.qml` runs this. |
| `test [kind]` | Queues one sample event for a running watcher, built from your most recently played game. `kind`: `bronze`, `silver`, `gold` (or `rare`), `platinum`; `unlock` (the default) keeps the achievement's real rarity. |
| `status` | Prints `[{store, app, unlocked, total}]` for every game with achievements, most complete first. |
| `set position top-center\|top-left\|top-right` | Where cards appear. |
| `set sound on\|off` | The chime. |
| `set icons omarchy\|vector\|painted` | Trophy art set. |
| `demo [kind...]` | Prints sample events straight to stdout, then idles. For `dev/preview.sh`. |

`set` writes [the settings file](settings.md); the shell applies it to the
next card.

## Environment

| Variable | Effect |
| --- | --- |
| `STEAM_DIR` | Steam folder, when it isn't in `~/.local/share/Steam`, `~/.steam/steam` or the Flatpak path. |
| `STEAM_ACCOUNT` | Steam account id (the number in `UserGameStats_<id>_<app>.bin`), when several accounts share the machine. Default: the one with the most games. |
