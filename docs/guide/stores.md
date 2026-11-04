# Adding a game store

Steam and GOG are the stores today, but the watcher doesn't know that: it
asks every class in `stores.STORES` that reports itself available. Adding
Epic, Battle.net, Lutris or anything else is one module. `stores/steam.py`
parses binary files; `stores/gog.py` reads a SQLite database a launcher
service keeps, and is the shorter one to copy.

## What a store does

Subclass `stores.base.Store` in `stores/<id>.py`:

| Member | Return |
| --- | --- |
| `id` | Short lowercase identifier (`epic`). Namespaces game ids and cached icons; never change it once released. |
| `name` | Name shown to people (`Epic Games`). |
| `available()` | True when the launcher is installed and there is achievement data to read. Called once at start; keep it cheap. |
| `games()` | `{game id: change token}`. Called once a second, so read directory metadata, not file contents. The token (mtime, size, hash) must change whenever unlocks may have. |
| `achievements(game)` | `[{api, name, desc, icon, unlocked, time}]`: `api` stable per achievement, `icon` an image URL or `""` (only fetched when that unlock is shown), `time` unix seconds or 0. Optional: `hidden` (secret until unlocked), `icon_locked` (the greyed-out icon) on locked counter achievements, `progress: {value, max}` with `value` clamped to `0..max`, and `remote: true` for data from an online backfill (the watcher never toasts those). Raising is fine: the watcher treats it as "not readable yet" and retries on the next change. |
| `game_name(game)` | Display name. Cache it if it costs a request. |
| `percents(game)` | `{api: share of players}`, or `{}`. Cache it: the panel and tracker ask often. `{}` makes every unlock bronze. `percent(game, api)` reads from it. |
| `art(game)` | `{'hero', 'header'}` image URLs for the platinum card, panel and tracker, or `""`. |
| `running()` | `{'game': id, 'since': unix seconds}` for the game being played now, or `None`. Optional; the panel's now-playing card needs it. |
| `recent()` | `[(unix seconds, game id)]` last played, newest first. Optional; the panel's recent games need it. |
| `backfill(say=None)` | Slowly fill in games with no local data from an online source, if the user opted in; `say(line)` reports progress. Optional; the watcher runs it in a background thread and `omatrophy.py sync` in the foreground. Steam's reads the public profile (ADR 11). |

Then add the class to `STORES` in `stores/__init__.py`.

The base module also gives you `read_json`, `write_json`, `http_json` (4 s
timeout), `cached(url, name)` for local image copies, and `started_at` /
`boot_time` for a process's start time in `/proc`. Image hosts must be in
`TRUSTED_HOSTS` there, or the watcher and the panel won't fetch them.

## Rules

- Read what the launcher already keeps on disk. No account keys, no login
  flows, no scraping a signed-in web session (ADR 1, ADR 7). If a store only
  offers achievements through an authenticated API, open an issue first.
- Diffing, tiers, events and timing stay in `omatrophy.py`; a store only
  reads and describes.
- Network calls time out and fall back quietly.
- List every new path or host the store touches in
  [SECURITY.md](../../SECURITY.md).

## Test it

Add a test class in `tests/` that builds the launcher's files in a temporary
folder (see `SteamDir` in `tests/test_omatrophy.py`, or `HeroicDir` in
`tests/test_gog.py`) and checks
`available()`, `games()` and `achievements()`. The contract test there
already covers every class in `STORES`. Then:

```sh
python3 -m unittest discover -s tests
python3 omatrophy.py status          # your games from every store
python3 omatrophy.py test silver     # a toast from your latest game
```

## Stores we checked

Read this before starting a store, and update the row with what you find
(date, evidence) so nobody digs the same hole twice. "Local" means files the
launcher keeps on this machine that change when you unlock something; that
is what live toasts need (ADR 1). Omarchy's own gaming installers
(`omarchy-install-gaming-*`) set the order we checked them in.

| Store | Verdict | Why | What would change it |
| --- | --- | --- | --- |
| Steam | Done | Local stats and schema files per game; opt-in profile backfill for games never run here (ADR 11) | |
| GOG through Heroic | Done (0.3.0) | Comet, which Heroic starts beside every GOG game, keeps a SQLite `gameplay.db` per game with unlock times and GOG's rarity (ADR 12) | |
| Epic through Heroic (Legendary) | No | Legendary has no achievement support and keeps no unlocks on disk; Epic's achievements come from its online services (EOS) behind your login. Checked 2026-11-03: no achievement file in Heroic's `legendaryConfig/` or `store_cache/` | A local file the game or EOS writes on unlock; or a public, login-free profile page that could feed an opt-in backfill like ADR 11 (no live toasts; not checked) |
| Amazon through Heroic (Nile) | No | No local achievement data found (unverified) | Same as Epic |
| Heroic's `gog_achievements.json` | Don't use | A copy of GOG's online list, saved when you open a game's page in Heroic and never refreshed: not live, often stale | Use Comet's database instead (already done) |
| Lutris | No store of its own | Lutris runs Windows games under Wine; it keeps no achievements. A GOG game run there without Comet writes nothing | GOG games launched with Comet should already work through the GOG store's database fallback (unverified) |
| Battle.net | No | Blizzard keeps achievements inside each game's online service | A local file per game (none known) |
| RetroArch | No | RetroAchievements needs an account and API key (ADR 1) | Revisiting ADR 1 for an opt-in, key-based store |
| RPCS3 (PS3 emulator) | Possible, deferred | Per-game trophy files on disk: `TROPCONF.SFM` lists trophies, `TROPUSR.DAT` holds unlock flags and timestamps as plain big-endian records (per RPCS3's `Loader/TROPUSR.h`). The owner put it off on 2026-11-03 | A real trophy folder to build tests from |
| Minecraft | Possible, not planned | Advancements are JSON per world on disk | Someone wanting it |
| GeForce Now, Xbox Cloud | No | Cloud streaming: nothing runs or is stored here | |
| GOG Galaxy under Wine | Unchecked | Its local database may hold achievements (unverified) | A real install to read |
