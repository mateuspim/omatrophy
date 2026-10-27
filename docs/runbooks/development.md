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
| `TrophyToast.qml`, `PlatinumCard.qml` | On the next card (loaded by fresh URL). |
| `StylePicker.qml` | The next time the bar panel opens. |
| `omatrophy.py`, `stores/` | When the watcher restarts: after `omarchy restart shell`, or kill it (`pkill -f 'omatrophy.py watch'`) and the service starts it again in 10 s. |
| `Service.qml`, `Panel.qml`, `manifest.json` | After `omarchy restart shell`. |

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
