# OmaTrophy (PoC)

Steam achievement toasts on the Omarchy shell's Overlay layer, so they show
over fullscreen games even when Steam's own popup doesn't, plus a platinum
card when a game hits 100%.

- `omatrophy.py watch` diffs Steam's local cache
  (`<Steam>/appcache/stats/UserGameStats_<account>_<app>.bin`) once a second and
  prints one JSON line per new unlock. No API key; works with a private profile.
  Rarity comes from Steam's public global-percentages endpoint.
- `Service.qml` runs the watcher and shows `TrophyToast` / `PlatinumCard` on the
  focused monitor: click-through, no focus, themed from Omarchy colors, with a
  freedesktop chime via `pw-play`.

## Try it

```sh
ln -s ~/Projects/omarchy/omatrophy ~/.config/omarchy/plugins/pym.omatrophy
omarchy-shell shell rescanPlugins && omarchy plugin enable pym.omatrophy

python3 omatrophy.py test            # normal unlock (latest game you played)
python3 omatrophy.py test rare
python3 omatrophy.py test platinum
python3 omatrophy.py status          # per-game progress as JSON
```

After editing QML, run `omarchy restart shell`; disabling and re-enabling the
plugin keeps the cached components.
