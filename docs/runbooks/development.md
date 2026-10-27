# Development runbook

## Set up

You need Omarchy 4.0+ (with `omarchy-shell`), `python3`, and a Steam install
with some achievement progress for real data. `rsvg-convert` (librsvg) only
to re-render the README hero.

Link a checkout into the user plugin directory (never into
`/usr/share/omarchy`), then rescan and enable it:

```sh
git clone https://github.com/mateuspim/omatrophy.git
ln -s "$PWD/omatrophy" ~/.config/omarchy/plugins/pym.omatrophy
cd omatrophy
omarchy plugin validate .
omarchy-shell shell rescanPlugins
omarchy plugin enable pym.omatrophy
```

If the plugin was already listed in `shell.json` before it had a bar widget,
`omarchy plugin enable --section` does nothing: disable it, then enable it
again to place the button.

Watch the live log (read-only):

```sh
quickshell log -p /usr/share/omarchy/shell -t 200 | grep -i omatrophy
```

## What reloads when

| You changed | It shows |
| --- | --- |
| `TrophyToast.qml`, `PlatinumCard.qml` | On the next card (built from the file's text). |
| `StylePicker.qml` | The next time the bar panel opens. |
| `TrackerView.qml` | The next time the tracker opens. |
| `omatrophy.py`, `stores/` | When the watcher restarts: after `omarchy restart shell`, or kill it (`pkill -f 'omatrophy.py watch'`) and the service starts it again in 10 s. |
| `Service.qml`, `Panel.qml`, `Tracker.qml`, `FreshObject.qml`, `manifest.json` | After `omarchy restart shell`. |

Don't restart the shell while a game runs (`pgrep -f SteamLaunch`): games
don't always survive it.

## Test

```sh
python3 -m unittest discover -s tests
omarchy plugin validate .
```

Fire real toasts through the running shell:

```sh
python3 omatrophy.py test bronze      # also silver, gold, platinum
python3 omatrophy.py status
```

## Preview without the live shell

`dev/preview.sh` starts a throwaway Quickshell instance with the current
theme and sample events from your latest game, then quits:

```sh
dev/preview.sh                   # unlock, rare, then platinum
dev/preview.sh -t 30 platinum    # stop after 30 s (default 25)
dev/preview.sh --picker          # the bar panel in a window
```

## Render to a PNG

`dev/render.sh` draws one view offscreen and saves it: no window, no live
shell. It uses the fake games in `dev/samples/`, so its output is safe for
the README; `--live` reads your own stores instead and stays out of git.

```sh
dev/render.sh now /tmp/now.png          # the panel mid-game; also idle, games, settings, loading
dev/render.sh tracker /tmp/tracker.png  # the achievement tracker; tracker-loading for its skeleton
dev/render.sh gold /tmp/gold.png        # a toast: bronze, silver, gold, platinum
dev/render.sh --live tracker /tmp/t.png # your running or last game
```

The software renderer drops `MultiEffect` layers (the omarchy set's accent
inlay, card masks and shadows); check those with `dev/preview.sh`.

## Refresh the preview

The README hero is `docs/brand/preview.svg` rendered to `preview.png`
(3840 × 2160). It isn't made yet: it waits for the default trophy style.
Its card captures must come from offscreen renders with sample data, never a
desktop screenshot:

```sh
rsvg-convert -o preview.png docs/brand/preview.svg
```

Open the PNG and check it before committing.

## Release

1. Bump `version` in `manifest.json`.
2. Move the `CHANGELOG.md` Unreleased entries under `## X.Y.Z - YYYY-MM-DD`.
3. Check the README covers the change.
4. Run the tests and `omarchy plugin validate .`.
5. Commit `Release X.Y.Z`, tag `git tag -a vX.Y.Z -m "OmaTrophy X.Y.Z"`.
6. Ask the owner before pushing the commit, the tag or a GitHub release.
