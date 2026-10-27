# Changelog

## Unreleased

- First version: Steam achievement unlocks as toasts on the Overlay layer,
  over fullscreen games, with no API key and private profiles supported.
  Rarity picks the metal (bronze, silver, gold at 10% of players or fewer);
  100% of a game plays the platinum card over the game's hero art.
- Bar button with a trophy cabinet (totals, the games closest to platinum
  with their header art) and a style picker: three trophy art sets (Omarchy pixel grid
  with a theme-tinted inlay, faceted vector, painted), previews of every
  tier, position (top centre, left or right) and sound.
- A chime per tier, synthesised for OmaTrophy (`tools/sounds.py`, from
  the brief in `design/sounds/`), with the
  freedesktop sounds kept as the classic set.
- Stores are pluggable (`stores/`); Steam is the first.
- The bar panel in three tabs. Now: the game you're playing (hero art,
  progress, this session's unlocks, the likeliest next ones) or the last
  three you played, and a shelf of platinums. Games: every game with its
  count, sorted by recent, closest to platinum or name. Settings: the style,
  previews, position and sound. Shimmering placeholders while data loads,
  in the panel and the tracker.
- An achievement tracker overlay: every achievement of a game with rarity
  and unlock date, filters (all, locked, unlocked, rare) and type-to-search;
  opened from any game in the panel or with `omarchy-shell shell summon`.
  Arrow keys, Page Up/Down, Home and End move a highlighted row; Enter
  reveals a hidden achievement. A sort (recent, rarest, A–Z, game order)
  that the tracker remembers in config.json.
- Locked counter achievements show their progress ("52 / 80" and a thin
  bar) in the tracker and under Up next, from the stat Steam's schema ties
  them to.
- The Games tab filters by name as you type, and a game you won't finish
  can be hidden from Closest (`omatrophy.py hide`/`unhide`, config
  `hidden`).
- The platinum card in the toast's language: a metal rail, the trophy on a
  platinum tile, a spaced label, then the count and a filling bar.
- Global rarity is cached a day per game and kept when offline.
- The watcher fills the game-name cache in the background after it starts,
  so the Games tab's first open doesn't wait on the network.
- `omatrophy.py` CLI: `watch`, `test`, `status`, `cabinet`, `now`, `games`,
  `game`, `set`.
- `dev/render.sh`: any view offscreen to a PNG, from fake sample data.
