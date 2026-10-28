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

The README hero is [`preview.png`](../../preview.png) (3840 × 2160). Its
editable source is [`docs/brand/preview.svg`](../brand/preview.svg), which
places two offscreen captures from `docs/brand/captures/`: the tracker and
a gold toast. The captures come from the fake games in `dev/samples/`, never
from a desktop screenshot or `--live`. See [branding](../branding.md) for
colours and layout; `design/hero/` holds the brief it was drawn from.

1. Render the captures at 2×:

   ```sh
   for v in now tracker gold platinum games; do
     QT_SCALE_FACTOR=2 dev/render.sh "$v" "docs/brand/captures/$v.png"
   done
   ```

2. Render the hero from the repository root:

   ```sh
   rsvg-convert -o preview.png docs/brand/preview.svg
   ```

3. Open the PNG and check it before committing: no text over the cards,
   nothing clipped, the toast readable at README width.

## Release

1. Bump `version` in `manifest.json`.
2. Move the `CHANGELOG.md` Unreleased entries under `## X.Y.Z - YYYY-MM-DD`.
3. Check the README covers the change.
4. Run the tests and `omarchy plugin validate .`.
5. Commit `Release X.Y.Z`, tag `git tag -a vX.Y.Z -m "OmaTrophy X.Y.Z"`.
6. Ask the owner before pushing the commit, the tag or a GitHub release.
