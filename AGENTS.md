# OmaTrophy agent instructions

OmaTrophy is an Omarchy shell plugin (Quickshell/QML plus a Python watcher)
that shows game achievement unlocks as themed toasts over fullscreen games,
with a platinum card when a game reaches 100%. Plugin id `pym.omatrophy`;
public at https://github.com/mateuspim/omatrophy. The README is the user
manual; read its section before changing a feature. `docs/architecture.md`
says how the parts fit, `docs/adr/` why, `docs/specs/` what the contracts are
(event lines, CLI, settings).

## Project

- Layout: every `.qml` file at the root. `manifest.json` names two entry
  points: `Service.qml` (the watcher process and the toast window) and
  `Panel.qml` (the bar button). Don't add QML subfolders. `omatrophy.py` is
  the watcher and CLI; `stores/` holds one module per game store; trophy art
  in `assets/<set>/`; design sources in `design/`; dev tools in `dev/` and
  `tools/`; tests in `tests/`.
- Naming: plugin id, `moduleName` and IPC target `pym.omatrophy`; layer
  namespace `omatrophy`; settings `~/.config/omatrophy/config.json`; state
  `~/.local/state/omatrophy/`; cache `~/.cache/omatrophy/`; log prefix
  `omatrophy:`; store ids lowercase (`steam`).
- Qt 6.12: QtQuick exports its own `Color`. Write
  `import qs.Commons as Commons` and `Commons.Color.x`; never a bare `Color.`
  (`tests/` enforces it).
- `TrophyToast.qml`, `PlatinumCard.qml` and `StylePicker.qml` load by a fresh
  URL so edits show without a shell restart (ADR 5). They must not use other
  QML types from this folder; the `Trophy` component is repeated in both
  cards on purpose. `Service.qml`, `Panel.qml` and `manifest.json` need
  `omarchy restart shell`.
- Popup text uses `Commons.Color.popups.text`, never the bar's foreground:
  the bar's colour is meant for the bar's background.
- Stores read the launcher's local data and need no account keys (ADR 1,
  ADR 7). A store answers in plain dicts; diffing, tiers and events stay in
  `omatrophy.py`. New store: `docs/guide/stores.md`.
- The watcher only prints events; the shell decides what to show (ADR 6).
  Event and CLI shapes are public contracts: change `docs/specs/` with them.
- Never restart the user's shell while a game runs
  (`pgrep -f SteamLaunch`); a restart can upset the game (ADR 8). Ask first
  in any case.
- Target Omarchy 4.0+ and its Quickshell-based `omarchy-shell`. Treat
  `/usr/share/omarchy/` as read-only reference
  (`shell/plugins/README.md`, `shell/Ui/{Panel,KeyboardPanel}.qml`).
  Validate with `omarchy plugin validate .` after touching `manifest.json`
  or entry points.

## Code style

- Match the surrounding file: 2-space QML, 4-space Python, no semicolons in
  QML/JS, typed QML properties where the shape is known.
- Python stays standard-library only and runs on the system `python3`.
- Functions small and single-purpose; files focused, split by
  responsibility. Store-specific code lives in its `stores/` module only.
- Names specific and greppable; avoid `data`, `handler`, `Manager`.
- Early returns over nested ifs. Network calls time out (4 s) and fall back
  quietly: a toast with no rarity beats no toast.
- Error messages say what failed and what the user can do.

## Comments

- Keep existing comments; they carry intent and provenance.
- Write WHY, not WHAT. Name the upstream constraint or bug a line exists for.

## Tests

- `python3 -m unittest discover -s tests` runs everything; CI runs the same.
- Every new pure function gets a test; bug fixes get a regression test.
  Store tests build their launcher files in a temporary folder (see
  `SteamDir`); tests never touch a real launcher, the network or the user's
  config.
- Visual checks: `dev/preview.sh [bronze|silver|gold|platinum]` or
  `dev/preview.sh --picker` runs a throwaway Quickshell instance with sample
  events; it never touches the live shell. Hero captures for the README come
  from offscreen renders with fake data only.
- Live shell log (read-only):
  `quickshell log -p /usr/share/omarchy/shell -t 200 | grep -i omatrophy`.

## Dependencies

- Runtime: Omarchy's `qs.Ui`/`qs.Commons`, Quickshell, `python3` and
  `pw-play` (PipeWire) for the chime. No pip packages, no npm.
- Reuse Omarchy's public `qs.Ui` components (`Panel`, `KeyboardPanel`,
  `BarIconButton`, `PanelSectionHeader`, ...).

## Public-repo hygiene

- No `/home/...` paths, account ids, real desktop screenshots or LAN
  addresses in tracked files. Design-agent logs and in-game captures in
  `design/` stay gitignored.
- Never modify user config on load; settings change only through the panel
  or `omatrophy.py set`.
- `HANDOFF.md` is local-only and stays gitignored.

## Commits and releases

- Branch `master`. Commit subjects are plain imperative sentences with a body
  that says why. Ask the owner before pushing commits or tags, and before
  publishing a GitHub release.
- Release: bump `version` in `manifest.json`, add the `CHANGELOG.md` entry,
  check the README covers the change, run the tests,
  `omarchy plugin validate .`, commit `Release X.Y.Z`, annotated tag `vX.Y.Z`
  ("OmaTrophy X.Y.Z").
