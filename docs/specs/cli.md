# Command line

`python3 omatrophy.py <command>`, from anywhere (it finds its own folder).
Exits non-zero with a message when no store with achievement data is
installed.

| Command | Does |
| --- | --- |
| `watch` | The default. Prints [event lines](events.md) until killed. `Service.qml` runs this. After `ready` it looks up uncached game names in the background (eight at a time, 4 s timeout each); events never wait on it. |
| `test [kind]` | Queues one sample event for a running watcher, built from your most recently played game. `kind`: `bronze`, `silver`, `gold` (or `rare`), `platinum`; `unlock` (the default) keeps the achievement's real rarity. |
| `status` | Prints `[{store, app, unlocked, total}]` for every game with achievements, most complete first. |
| `cabinet` | Prints `{games, trophies, platinums, nearest}`: totals across every game, and `nearest`, the four started, unfinished games closest to 100%, each a `status` row plus `game` (name) and `header` (art URL). |
| `now` | Prints [what the bar panel's Now tab shows](#now), in one read of every store, and keeps a copy in `~/.cache/omatrophy/panel/now.json` that the panel shows on its next open until a fresh read answers. |
| `games` | Prints [every game with achievements](#games) for the panel's Games tab. Uncached names are looked up eight at a time; the watcher warms that cache in the background after `ready`, so this is usually a file read. Keeps a copy in `~/.cache/omatrophy/panel/games.json`, like `now`. |
| `game [store app] [--guide]` | Prints [one game's every achievement](#game) for the tracker; with `--guide`, also `guide`: that game's guide as `guide [store app]` prints it (`{}` when none), in the same read ([ADR 19](../adr/0019-keep-the-tracker-built-between-opens.md)). Without a game: the game running now, else the one played last. Exits non-zero, with what to do, when the game has no cached achievements. |
| `guide [store app]`, `guide import <folder> [--replace]` | One game's 100% guide as JSON for the tracker, or copy guides in from another folder ([guides](guides.md#command-line)). |
| `guide here <store> <app> <step\|clear>` | Pins the walkthrough step you are at (1-based), or clears it; prints the guide ([guides](guides.md#command-line)). |
| `guide make <store> <app> [--no-web] [--agent a] [--model m] [--effort e]`, `guide stop [store app]`, `guide status [store app]`, `guide jobs` | Make a guide through your agent (ADR 14), up to 3 games at once; stop one (or all), or read their progress ([guides](guides.md#the-make-job)). |
| `guide agents`, `guide model <agent> <model> [effort] [@endpoint]\|default` | The agents, their models and your picks; set or clear one agent's pick. |
| `guide jail-options <agent> [options...]` | Extra ai-jail options for that agent, such as a local model's key file (`--map`); none clears. `guide jail` says whether ai-jail is installed and what each agent adds ([guides](guides.md#command-line)). |
| `guide bench <store> <app> <agent:model[:effort][@endpoint]>... [--pick] [--keep]` | Make one game's guide with each entry and rank them ([benchmark](guides.md#benchmark)). |
| `set guide-agent default\|<agent>`, `set guide-web on\|off`, `set guide-jail on\|off` | Which agent makes guides, whether it may search the web, and whether it runs inside ai-jail. |
| `set position top-center\|top-left\|top-right` | Where cards appear. |
| `set sound on\|off\|omatrophy\|classic` | The chime: on, off, or which set (which also turns it on). |
| `set icons omarchy\|vector\|painted` | Trophy art set. |
| `set glass clear\|frosted\|solid` | How see-through toasts are. |
| `set tracker-sort recent\|rarity\|name\|game` | The tracker's sort; the tracker writes it when you change it. |
| `guide-key <key>` | Binds the Guide key (`""` unbinds) through `hyprctl`, refusing a key in use; prints and saves `{key, bound, error}` to `~/.local/state/omatrophy/guide-key.json` ([ADR 18](../adr/0018-bind-the-guide-key-at-runtime.md)). `Service.qml` runs it with config.json's `guide-key`. |
| `guide-key free` | Up to six keys no Hyprland bind uses (ours counts as free), as a JSON list; the recorder offers them, as a bound key never reaches it. |
| `guide-key check <key>` | `{key, valid, taken}`: whether the key parses and what else uses it (`""` when free), without binding. Settings > Guides asks before Install. |
| `set guide-key <key>\|none` | Installs or removes the Guide key. |
| `set reveal-hidden on\|off` | The tracker's Reveal all; the tracker writes it when you change it. |
| `set games-sort recent\|closest\|name`, `set rarest ever\|month\|platinum`, `set settings-section overview\|toasts\|now\|guides\|stores` | The panel's last Games sort and rarest list; the panel writes them when you pick one, so the next open shows the same view. |
| `set now-metals\|now-recent\|now-rarest\|now-shelf on\|off` | Shows or hides that section of the panel's Now tab. |
| `set community on\|off` | The opt-in backfill of games that never ran on this machine from your public Steam profile ([ADR 11](../adr/0011-backfill-from-the-community-profile.md)). With it on, the watcher fetches in the background after `ready`. |
| `sync` | Runs that backfill now, one line per game (`steam: 3/444 1903340: 55 achievements`), at most the run's page budget (15 to start; halved after a 429, five more after a run that used it all, between 5 and 30), ending `paused: N fetched, M left for later runs` when more are due, `done: N fetched` when it got them all; `stopped at <app>: <error>` after any error (a 429 rate limit, offline, private profile), and the next run picks up where it stopped. Ends `next automatic run in N min` (`stopped early; ...` after an error): the watcher runs the same backfill every hour, after a failed run (here or in the watcher) 4 h then 8 h, and keeps that time across restarts. Exits non-zero while `community` is off. |
| `steam-load` | Opens the Steam library page of every played game with no local stats file that no load has tried yet, most played first, so the running client caches its stats ([ADR 13](../adr/0013-load-stats-through-the-steam-client.md)). On Hyprland, Steam's window stays on a hidden workspace meanwhile. One line per game (`steam: 3/336 433850: no stats`, or `loaded`), then `steam: done: N loaded, M without achievements`, or `steam: stopped: ...` with the reason (`stopped: Steam is not signed in ...` when Steam's `logs/connection_log.txt` last shows a state other than `Logged On`; `stopped: 15 games in a row gave no stats; Steam may be offline ...` after `TIMEOUT_STREAK` timeouts in a row; those games stay unsure and go first next load). Exits non-zero when Steam isn't installed or running, a game is running, or another load is running; a stop request exits 0. |
| `steam-load all` | The same over every played game without stats, tried before or not. |
| `steam-load stop` | Stops a running load within a quarter second; the game it was waiting on stays untried. |
| `steam-load status` | `{"missing": N, "unchecked": M, "status": {...}}`: played games without stats here, those no load has tried or left unsure, and `steam-load/status.json` (`time`, `line`, `done`, `total`, `loaded`, `none`, `app` (the game being tried, or `""`), `current` (`{app, name, art}` for it, or `null`), `recent` (the last six results, newest first, `{app, name, art, found}`), `started` (unix seconds), `hidden` (Steam's window waits on a hidden workspace), `everything` (an `all` run), `state`: `running`, `done`, `stopped` or `failed`; `{}` before any run). |
| `favorite <store> <game>`, `favorite clear` | Sets or clears the Profile tab's favorite game (config.json's `favorite`). Exits non-zero for an unknown store. |
| `completionist add\|remove <store> <game>` | Pins or unpins a finished game on the Profile's completionist tile (config.json's `completionist`). Exits non-zero for an unknown store, or when adding to a full tile (four). |
| `showcase order <key>...`, `completionist order <key>...` | Saves a new order for those pins; every pinned key exactly once, or it exits non-zero naming the current ones. The Profile tab's drag-to-reorder writes it. |
| `showcase add\|remove <store> <game> [api]` | Pins or unpins one achievement (with no `api`, the game's platinum) on the Profile showcase, in config.json's `showcase`. Exits non-zero for an unknown store, or when adding to a full showcase (six). |
| `hide <store> <game>` | Adds `"store:game"` to `hidden` in config.json: the game leaves `cabinet`'s `nearest`, the Games tab's Closest sort and the panel's platinum shelf (`now` still lists it in `shelf`; the panel filters). Exits non-zero for an unknown store. |
| `unhide <store> <game>` | Takes it back out. |
| `demo [kind...]` | Prints sample events straight to stdout, then idles. For `dev/preview.sh`. |

`set` writes [the settings file](settings.md); the shell applies it to the
next card.

Times are unix seconds; `0` means unknown or not yet. Art and icon fields
are URLs (`https://` or `file://`) or `""`. `now`, `games` and `game` give
the local copy (`file://`) of any image already in the cache; for the rest
they answer with the URL, then a detached child fetches those images, so
the next read names them locally. The command itself exits at once.

## now

```json
{"games": 126, "trophies": 1779, "platinums": 12,
 "playing": {...card, "hero": "...", "since": 1793065549, "session": [...], "next": [...]} | null,
 "recent": [card, ...], "shelf": [card, ...],
 "metals": {"bronze", "silver", "gold"}, "completion": 40, "started": 80,
 "playtime": {"total": 752100, "recent": 2343}, "favorite": {...card, "minutes", "rare", "rarest": [unlock, ...]} | null,
 "completionist": [card + {"key"}, ...],
 "showcase": [{"key", "store", "app", "api", "name", "icon", "time", "percent", "tier", "game"}, ...],
 "nearest": [card, ...], "stores": [{"id", "name", "found", "games"}, ...],
 "rarest": {"ever": [unlock, ...], "month": [unlock, ...], "platinum": [unlock, ...]}}
```

- A **card** is a `status` row plus `game`, `header`, `played` (last
  played), `platinum` (when the last achievement came, `0` while any is
  locked) and `latest`, the five newest unlocks as `{name, icon, time}`.
- `playing`: the game running now, or `null`. `hero` is its wide art (no
  logo), `since` when it started,
  `session` the unlocks since then (newest first, up to 12), `next` the three
  locked achievements most players have, as `{name, api, icon, time, desc,
  percent, progress, guide_time, missable, missable_note, tip}`; `icon` is the
  greyed-out one, `desc` is `""` for hidden achievements and `progress` is
  as in [game](#game). With a [guide](guides.md) for the game, `guide` is
  `true` and `next` is the guide's next three instead (its order,
  missables first, hand ticks counted done), with the plan's time as
  `guide_time` (text, like `"~20 min"`), `missable`, `missable_note` and
  `tip` (`""` for a hidden achievement); without one those are empty.
- `recent`: the three games played last, minus the running one.
- `shelf`: every complete game, newest platinum first, with `latest` empty.
- `metals`: every unlock counted by the metal its toast would have, from
  cached rarity (an unknown rarity counts as bronze, as its toast would);
  `completion`: the average share unlocked, in whole percent, over games
  with at least one unlock.
- `started`: games with at least one unlock. `playtime`: minutes played
  over every game a store keeps playtime for (achievements or not), in
  all and in the past two weeks (stores without a two-week figure add
  nothing to `recent`). `favorite`: the game set with `favorite`, with
  its `minutes`, `rare` (its gold-tier unlocks) and `rarest`, its six
  rarest unlocks, rarest first; `null` when none is set or it is gone.
  `completionist`: the pinned games still at 100%, in pin order. Cards in
  `recent` carry `minutes` too (`0` when unknown).
- `showcase`: the pinned trophies still earned, in pin order; a
  platinum pick has `api` `""`, `name` `"Platinum"`, tier `platinum` and
  the game's art as `icon`. Picks whose game or unlock is gone are left
  out.
- `stores`: every store OmaTrophy knows (`stores.STORES` order), whether
  it was found on this machine, and how many of its games have
  achievements; Settings shows one card per store.
- `nearest`: the six started, unfinished games closest to 100%, ties to
  the one with fewer left, with `latest` empty; the panel fills the
  platinum shelf's empty slots with them. Hidden games are left out.
- `rarest`: the eight unlocks fewest players have across the library,
  ever, since the first of this month (local time) and from finished
  games only (`platinum`), rarest first, ties to the newest; hidden
  games are left out. The Now tab shows three
  and the Profile showcase six; the spares let it drop a game hidden
  since the read. An **unlock** is
  `{name, icon, time, api, percent, tier, store, app, game}`. Rarity is read from the cache only, so `now` makes
  no request for it; unlocks of games with no cached rarity are left out.
  The watcher fetches the missing ones once after `ready`.

## games

`[{store, app, game, header, unlocked, total, platinum, played, hidden}]`,
one per game with achievements, in no set order: the panel sorts them
(recent, closest to platinum, name). `played` is `0` when the store doesn't
say; `hidden` is `true` for games set aside with `hide`.

## game

```json
{"store": "steam", "app": "1774580", "game": "...", "unlocked": 4, "total": 53,
 "header": "...", "hero": "...", "platinum": 0, "playing": true,
 "achievements": [{"api": "...", "name": "...", "desc": "...", "icon": "...",
                   "icon_locked": "...", "hidden": false, "unlocked": true,
                   "time": 1793059700, "percent": 82.4, "tier": "bronze",
                   "progress": null}]}
```

Achievements come in the store's order; the tracker sorts them. `percent` is
`null` when the store doesn't say, and `tier` is the metal the unlock would
get ([ADR 3](../adr/0003-rarity-picks-the-metal.md)). `progress` is
`{"value": 12, "max": 15}` on a locked counter achievement whose store
tracks the count (Steam: the schema's progress stat, once the game has
written it; an unwritten stat is unknown, not 0), else `null`; `value`
is already clamped to `0..max`, and `max` is at least 2 (a one-step
"counter" is a plain flag, so it gets `null`).

## Overlay

The tracker is the plugin's `overlay` entry point. Open it from a script
with the same JSON:

```sh
omarchy-shell shell summon pym.omatrophy '{"store":"steam","app":"1774580"}'
omarchy-shell shell summon pym.omatrophy '{}'   # the running or last game
```

An `api` key (an achievement's id from [game](#game)) opens the game with
that achievement highlighted in the middle of the list, revealed if it is
hidden, clearing a filter or search that would leave it out. The panel's
rarest unlocks open this way.

## Environment

| Variable | Effect |
| --- | --- |
| `STEAM_DIR` | Steam folder, when it isn't in `~/.local/share/Steam`, `~/.steam/steam` or the Flatpak path. |
| `STEAM_ACCOUNT` | Steam account id (the number in `UserGameStats_<id>_<app>.bin`), when several accounts share the machine. Default: the one with the most games. |
| `HEROIC_DIR` | Heroic's config folder, when it isn't in `$XDG_CONFIG_HOME/heroic` (`~/.config/heroic`) or the Flatpak path. |
| `COMET_DIR` | Comet's gameplay folder (the one holding `<client id>/<user id>/gameplay.db`), when it isn't in `$XDG_DATA_HOME/comet/gameplay` or the Flatpak path. |
