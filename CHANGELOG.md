# Changelog

## Unreleased

100% guides (ADR 14). The tracker and panel changes show on their next
open; the watcher and `Tracker.qml` are unchanged, so no restart is needed.

- The tracker's **Guide** tab shows a game's path to 100%: up next, the
  route and notes, then every open achievement by phase, missables first,
  with time, difficulty, counters, tips, combos and "(unverified)" where
  no source backs a claim.
- **Make guide** writes one through your coding agent, run headless with
  no shell and no file tools (Claude Code; Codex and OpenCode adapters
  wait for a real lock check): OmaTrophy gathers sources, the agent
  researches, classifies and plans, and OmaTrophy verifies every quote.
  Live progress and Stop in the tracker; the last guide is kept as
  `.prev`.
- **Settings > Guides** picks the agent, its model (or any typed one), the
  effort, web search and, with ai-jail installed, a sandbox around the agent.
- Settings > Guides lists every installed agent with what it takes to use
  it; **Check** runs the lock check for Codex or OpenCode on your machine
  and turns the agent on when it passes (`guide check <agent>`).
- `guide bench` makes one game's guide with several agents and models and
  ranks them by verified quotes, coverage and filled fields, with time and
  cost; `--pick` makes the winner the default, local endpoints included.
- The Settings tab is split into sections (Toasts, Now tab, Guides,
  Stores) with an **Overview** of what each is set to.
- The Now tab's **Up next** follows the game's guide when it has one,
  with its time, missable warning and tip.
- `omatrophy.py guide [store app]`, `guide import <folder>`, `guide make`,
  `guide stop`, `guide status`, `guide agents`, `guide model`, and
  `set guide-agent` / `set guide-web`. `dev/check-lock.py <agent>` checks
  an agent's lock on a real run.
- OpenCode's research counts: the pages its webfetch read become sources
  and its token use is recorded (before, a local model's guide had no
  sources and every claim was unverified).
- Agents installed through mise run inside ai-jail (mise itself can't), and
  a lock check follows the agent's own binary, not mise's.
- A quote that only repeats the achievement's name, description or DLC no
  longer counts as verified, and search result pages are no source.
- First bench results on three games in the README and
  `docs/guide/guide-models.md`.

## 0.5.2 - 2026-11-04

Fixes left open from the Load from Steam review (PR #5). Toasts and the
loader run in the watcher and CLI: one `omarchy restart shell` for the
running watcher.

- Load from Steam stops when Steam isn't signed in (offline, or still
  signing in; read from Steam's own connection log), and after 15 games
  in a row give no stats, trying those games first next time, instead of
  filing them all as games without achievements.
- A game that first shows up while the watcher runs (just cached by a
  load, or first played) no longer toasts its old unlocks that Steam
  stored without a time.
- A Steam window that opened during a load (Friends, a sign-in dialog)
  comes back to your workspace; only the main window the load itself
  opened from the tray is closed again.
- Steam's window gets its own `focus_on_activate` rule dropped after a
  load, instead of a copy of the global value, so your Hyprland rules
  apply again.

## 0.5.1 - 2026-11-04

- The Steam profile backfill keeps the time of its next run on disk
  (`~/.local/state/omatrophy/backfill.json`). Before, every shell restart
  started the watcher's backfill at once, often straight into the same
  429 it had just been told to wait out. A `sync` that meets a 429 now
  pushes the watcher's next run back too. Needs one `omarchy restart
  shell` for the running watcher to pick it up.

## 0.5.0 - 2026-11-04

No shell restart needed: the panel picks the new parts up on its next
open.

- Load from Steam: `omatrophy.py steam-load` opens the library page of
  every game you played that OmaTrophy can't see yet, and the Steam
  client caches its achievements locally, about a second a game, with
  no key and no rate limit (ADR 13). On Hyprland Steam's window stays
  on a hidden workspace meanwhile. Tried games are remembered, so a
  load resumes where it stopped and later loads only take new games;
  `steam-load all` retries everything. `steam-load stop` (immediate) and
  `steam-load status` go with it. In the panel: Load from Steam and
  Check all again in Settings' Steam card, a Load button on the Games
  tab, and a progress strip under the tabs while it runs: the game being
  checked with its cover, found and empty counts on a split bar, time
  left, the latest results as covers, Stop, and a note that Steam is
  hidden only until the load ends, with Peek to look at it.

## 0.4.0 - 2026-11-04

After updating, restart the shell once (`omarchy restart shell`) so the
bar panel opens the tracker on an achievement.

- A Profile tab, after Steam's profile showcases, every tile yours to
  pick: a favorite game (+ Choose game searches your games; shows its
  hours, trophies and six rarest unlocks), a showcase of six trophies
  pinned with ☆ in the tracker (your rarest until you pin any; drag to
  reorder), a completionist tile of up to four finished games pinned
  with ☆ Completionist (your two newest until you pin any) over games
  completed, started and average completion, and hours played in two
  weeks and in all. New commands `favorite`, `showcase` and
  `completionist` (the pin lists also take `order`).
- Playtime from the launchers' own files: stores gain an optional
  `playtime()` (Steam's localconfig.vdf, Heroic's timestamp.json).
  Recently played games show their hours.
- The Now tab lists your rarest unlocks across every game, ever, this
  month or from platinumed games only; a click opens the tracker on that
  achievement, highlighted and revealed. Hidden games stay out. Rarity
  comes from the cache, so the panel makes no extra requests; the
  watcher fetches it once for games that have none.
- The Now tab's totals are split by metal in one bar with your average
  completion, recent games show "+N" after their latest icons, and the
  platinum shelf's empty slots tease the games closest to platinum
  ("2 left").
- Before any game has achievements, the Now tab says where they come
  from and points to the Steam profile switch.
- Settings is one list of choices: style, then position, glass and
  sound as chip rows, then Try it. A Now tab row shows or hides each of
  its sections (`set now-<section>`), and a Stores section has a card
  per store saying whether it was found and how many games it has.
- The panel remembers the Games sort and the rarest list you picked
  last (`games-sort`, `rarest`).
- Switching panel tabs no longer jumps, and the tracker no longer fills
  the shell log with "Cannot set a duration of < 0".
- The README hero names GOG.

## 0.3.0 - 2026-11-03

- GOG support: games played through Heroic Games Launcher toast, show
  in the panel and open in the tracker like Steam's, with GOG's own
  rarity picking the metal. OmaTrophy reads the database Heroic's Comet
  service keeps for each game; no GOG login or API (ADR 12).
- Settings has a Steam profile row: the community backfill's switch,
  what it sends, and how its latest run went, including when Steam has
  asked for a pause.
- The backfill's page budget adapts: halved after Steam's rate limit,
  five more after a run that used all of it (5 to 30 pages). Only a 429
  counts; being offline doesn't shrink it. Each run is kept in
  `~/.cache/omatrophy/community/runs.json`, so the limit can be measured
  from real runs.

## 0.2.1 - 2026-11-03

- Fixed duplicate `pym.omatrophy` IPC registrations on multiple monitors.
  Direct panel IPC belongs to the first screen; every bar button still
  opens its own panel.
- Bronze toasts keep a brighter, tighter halo around the trophy tile so
  its darker metal remains visible after the landing animation.

## 0.2.0 - 2026-10-29

- The panel and tracker keep their images: art and achievement icons are
  saved to `~/.cache/omatrophy/images/` after the first time they show,
  so later opens load them from disk instead of downloading every one
  again (80 of 127 Games headers did, on every open).
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
