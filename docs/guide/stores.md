# Adding a game store

Steam is the only store today, but the watcher doesn't know that: it asks
every class in `stores.STORES` that reports itself available. Adding Epic,
GOG, Battle.net, Heroic, Lutris or anything else is one module.

## What a store does

Subclass `stores.base.Store` in `stores/<id>.py`:

| Member | Return |
| --- | --- |
| `id` | Short lowercase identifier (`epic`). Namespaces game ids and cached icons; never change it once released. |
| `name` | Name shown to people (`Epic Games`). |
| `available()` | True when the launcher is installed and there is achievement data to read. Called once at start; keep it cheap. |
| `games()` | `{game id: change token}`. Called once a second, so read directory metadata, not file contents. The token (mtime, size, hash) must change whenever unlocks may have. |
| `achievements(game)` | `[{api, name, desc, icon, unlocked, time}]`: `api` stable per achievement, `icon` an image URL or `""` (only fetched when that unlock is shown), `time` unix seconds or 0. Optional: `hidden` (secret until unlocked) and `icon_locked` (the greyed-out icon). Raising is fine: the watcher treats it as "not readable yet" and retries on the next change. |
| `game_name(game)` | Display name. Cache it if it costs a request. |
| `percents(game)` | `{api: share of players}`, or `{}`. Cache it: the panel and tracker ask often. `{}` makes every unlock bronze. `percent(game, api)` reads from it. |
| `art(game)` | `{'hero', 'header'}` image URLs for the platinum card, panel and tracker, or `""`. |
| `running()` | `{'game': id, 'since': unix seconds}` for the game being played now, or `None`. Optional; the panel's now-playing card needs it. |
| `recent()` | `[(unix seconds, game id)]` last played, newest first. Optional; the panel's recent games need it. |

Then add the class to `STORES` in `stores/__init__.py`.

The base module also gives you `read_json`, `write_json`, `http_json` (4 s
timeout) and `cached(url, name)` for local image copies.

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
folder (see `SteamDir` in `tests/test_omatrophy.py`) and checks
`available()`, `games()` and `achievements()`. The contract test there
already covers every class in `STORES`. Then:

```sh
python3 -m unittest discover -s tests
python3 omatrophy.py status          # your games from every store
python3 omatrophy.py test silver     # a toast from your latest game
```

## Where other launchers keep achievements

Unconfirmed starting points; check them on a real install before relying on
them.

- Heroic / Legendary (Epic, GOG): no local achievement cache known
  (unverified).
- Battle.net under Wine/Proton: achievements live server-side per game
  (unverified).
- GOG Galaxy is Windows-only; under Wine its local database may hold them
  (unverified).
