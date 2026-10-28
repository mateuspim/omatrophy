# Changelog

## Unreleased

- Settings has a Steam popups row: a button that opens Steam's settings,
  where you can turn off Steam's own achievement popup so only
  OmaTrophy's shows. OmaTrophy doesn't change Steam's settings itself.
- Toasts are glass: the card shows a little of the game through it, with
  light along its top. A Glass slider in Settings (and `set glass`) goes
  from Clear through Frosted (the default) to Solid, the old card.
- The toast's border is its metal instead of the theme accent, and a soft
  halo in the metal flares behind the trophy as it lands.
- A redesigned bar panel: the tabs as an underlined strip, the playing
  game's percentage and progress on its art, Up next rarities in the metal
  they'd earn, quieter sort chips, and Games rows with bigger art, the
  percentage first and when you last played. Bars fill and tabs fade in
  as they show.
- The Games tab shows eight games a page with a pager (previous, page
  numbers, next) instead of 25 and "Show more", so it takes half the
  panel instead of all of it.
- Platinums can come off the shelf: an × on a shelf tile, or Hide on a
  platinum in the Games tab (Show brings it back). It uses the same
  `hidden` list as Closest; totals still count the game.
- The panel opens filled: `now` and `games` keep their last answer in
  `~/.cache/omatrophy/panel/`, the panel shows it at once and a fresh
  read replaces it a moment later, instead of bones on every open.
- The tracker's search waits for a pause in typing (180 ms) before it
  filters, so long lists don't rebuild on every key; the box shows each
  key at once.
- The tracker's list animates a filter, search or sort instead of
  swapping: rows that no longer match slide out, the rest close the gap,
  rows coming back fade in where they belong, and a new sort moves rows
  to their places.
- Fixed: achievements whose stat the game never wrote showed "0 / 15"
  (Jedi: Survivor had it on every locked one); they now show no counter.
- More motion while things load: art and icons fade in as they arrive,
  recent cards, shelf tiles, Up next and Games rows come in one after
  another (Games again on each page), this session's unlocks pop in and
  the totals count up. Hovered art zooms inside its frame, so shelf tiles
  at the panel's edge no longer get cut off.
- Settings redesigned: each trophy style card shows its whole set, preview
  tiles name their metal, the toast position is picked on a small drawing
  of the screen, and the sound is a row of chips.
- A redesigned tracker: a completion ring and your unlocks by metal in the
  header, filters and sort as chips, a search box with a caret, unlocked
  rows marked with their metal and every rarity in its metal's colour,
  rows that cascade in, and a key-cap legend.

## 0.1.0 - 2026-10-27

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
  count, 25 at a time with "Show more", sorted by recent, closest to
  platinum or name. Settings: the style,
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
- An opt-in backfill (`set community on`, `sync`) fills in games that
  never ran on this machine from the public Steam profile's achievement
  pages, cached, 15 pages an hour to stay under Steam's rate limit, and
  finished games never refetched unless played; their unlocks never toast
  (ADR 11).
- The watcher fills the game-name cache in the background after it starts,
  so the Games tab's first open doesn't wait on the network.
- `omatrophy.py` CLI: `watch`, `test`, `status`, `cabinet`, `now`, `games`,
  `game`, `set`.
- `dev/render.sh`: any view offscreen to a PNG, from fake sample data.
