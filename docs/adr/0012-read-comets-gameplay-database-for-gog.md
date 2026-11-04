# 12. Read Comet's gameplay database for GOG

- Status: Accepted
- Date: 2026-11-03

## Context

GOG games on Omarchy run through Heroic Games Launcher
(`omarchy-install-gaming-heroic`). GOG Galaxy, which normally tracks GOG
achievements, is Windows-only. Since 2.x, Heroic starts **Comet**
(github.com/imLinguin/comet), an open-source stand-in for Galaxy's
service, beside every GOG game; it is on unless
`experimentalFeatures.cometSupport` is false. Games talk to it through the
Galaxy SDK, and Comet syncs unlocks to GOG.

Comet keeps one SQLite database per game and GOG user at
`$XDG_DATA_HOME/comet/gameplay/<client id>/<user id>/gameplay.db`. Its
`achievement` table holds each achievement's key, name, description,
whether it shows while locked, its icons, GOG's rarity percentage and,
once unlocked, an RFC 3339 `unlock_time`; `changed = 1` marks an unlock
not yet synced to GOG. Comet rewrites the file on each unlock while the
game runs (checked on 2026-11-03 with Heroic 2.22.4: an unlock in DOOM +
DOOM II showed in the file within a second). The database uses SQLite's
default rollback journal.

The database is keyed by the game's Galaxy client id. Heroic and GOG's
store know games by product id. Every install folder has
`goggame-<product id>.info`, a JSON file that names both.

GOG's own achievement API needs the user's OAuth token, which Heroic keeps
in `gog_store/auth.json`.

## Decision

- The GOG store (`stores/gog.py`) reads Comet's database: the same kind
  of source as Steam's stats cache (ADR 1), a file the launcher's own
  service keeps on this machine and updates the moment a game unlocks
  something.
- It opens the file read-only (`mode=ro`, a 0.5 s busy timeout), never
  with `immutable=1`, since Comet writes to it while the game runs. While
  Comet holds the lock it answers its last good copy and has the watcher
  try again next second; a first read that fails is "not readable yet".
- Games are named by product id. The client id → product id pair comes
  from each install's `goggame-*.info` and is remembered in
  `~/.local/state/omatrophy/gog-clients.json`, so a game uninstalled since
  keeps its name; a database that was never paired shows under its client
  id.
- Rarity, and so the metal (ADR 3), comes from the database's `rarity`
  column; 0, the column's default before Comet fetches it, is unknown.
- Titles and art come from Heroic's `store_cache/gog_library.json`,
  last-played times from `store/timestamp.json`, both read only. The game
  running now is the earliest process whose arguments point into a GOG
  install folder.
- No GOG API call, no account token. `gog_store/auth.json` is never read,
  and Comet's own command line (which carries a token) is matched against
  install paths only, never kept or printed.

## Consequences

- GOG unlocks toast as fast as Steam's, with GOG's rarity, without a login
  or a key, offline included.
- A GOG game shows only once it has run through Heroic with Comet on.
  Games played through Galaxy on Windows, or with Comet turned off, have
  no file here.
- The database layout is Comet's and may change between releases; the
  store's tests build the schema seen on 2026-11-03, and a missing table
  or column means no achievements for that game, never a crash.
- Comet's data folder inside the Heroic Flatpak, and a running game's
  Wine `Z:` path in `/proc`, are taken from how Flatpak and Wine work,
  not from a test on this machine (unverified).
