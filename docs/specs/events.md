# Event lines

`omatrophy.py watch` prints one JSON object per line on stdout.
`Service.qml` reads them; `omatrophy.py test` queues the same shapes through
the inbox (`~/.local/state/omatrophy/inbox.jsonl`), and `demo` prints them
directly. Unknown `type`s are ignored by the shell, so new types are safe to
add; changing a field is a breaking change. `cards.json` lists the types
the shell has a card for: each type's QML file, whether it plays the tier's
chime (`chime`), whether it goes ahead of queued cards of a lower `rank`,
and whether a full queue (20) may drop it (`keep`). The test inbox lets
through these types only.

## `ready`

Printed once, when the watcher has its baseline.

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"ready"` | |
| `stores` | string[] | Ids of the stores being watched, e.g. `["steam"]`. |
| `games` | number | Games with achievement data across those stores. |

## `unlock`

One achievement, newly unlocked.

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"unlock"` | |
| `store` | string | Store id. |
| `app` | string | The store's game id. |
| `game` | string | Game name (`"App <id>"` when offline and uncached). |
| `name`, `desc` | string | Achievement title and description. |
| `icon` | string | `file://` path to a cached icon, the remote URL when offline, or `""`. |
| `percent` | number or null | Share of players with it; null when the store doesn't say. |
| `rare` | bool | `percent` ≤ 10. |
| `tier` | `"bronze"`, `"silver"`, `"gold"` | Above 35% or unknown: bronze; above 10%: silver; else gold. |
| `unlocked`, `total` | number | Unlocked count after this one, and the game's total. |
| `time` | number | Unix seconds of the unlock (now, when the store has no time). |

## `platinum`

The game's last achievement just unlocked. Always follows its `unlock` line.

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"platinum"` | |
| `store`, `app`, `game` | string | As above. |
| `total` | number | Achievements in the game. |
| `first`, `last` | number | Unix seconds of the first and last unlock (0 when unknown). |
| `hero` | string | Wide art (`file://` or URL) behind the card, or `""`. |
| `header` | string | Banner URL, or `""`. |

## `difficulty`

A game other than the one running at the last check (every 5 s) started,
and has locked achievements that need a difficulty setting. Tried at each
check for two minutes while the game runs, as a first launch's achievement
files appear only once the game is up. Once per game: the watcher keeps
the games it reminded of in `~/.local/state/omatrophy/reminded.json`. Not
sent with `difficulty-reminder` off or for a game already running when the
watcher started; a hidden achievement's setting is left out unless
`reveal-hidden` is on. The shell shows it before any queued toast, never
drops it, and plays no chime.

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"difficulty"` | |
| `store`, `app`, `game` | string | As above. |
| `settings` | string[] | As `games` gives `difficulty`: each setting once, exact ones first, floors marked `+`. |
| `count` | number | Locked achievements that need one. |
| `header` | string | Banner URL, or `""`. |
| `stacks` | bool or null | The guide's word, as `guide` gives it: `true` when a harder run also counts for the easier settings, `false` when a setting needs its own run, `null` with no guide or no word. |
| `stacks_verified` | bool | A quote backs `stacks`. |

## `missable`

A game started (as for `difficulty`) whose guide's current step (`guide`'s
`step`: the pinned one, else the guess) has achievements still open that
can be missed there: the step's `missables` and the items marked
`missable` it places, the ones the tracker's Do now puts first. Tried at
each check for two minutes, each launch reminder on its own. Once per
step and set: the watcher keeps `{"store:app": "<step>:<title>:<apis>"}`
in `~/.local/state/omatrophy/missable-reminded.json` and stays quiet while
the next launch would say the same; a new step, a missable got or a new
one placed sends it again. Not sent with `missable-reminder` off, for a
game without a guide, or for a game already running when the watcher
started. The shell shows it right after any `difficulty` card, before
queued toasts, never drops it, and plays no chime.

| Field | Type | Meaning |
| --- | --- | --- |
| `type` | `"missable"` | |
| `store`, `app`, `game` | string | As above. |
| `header` | string | Banner URL, or `""`. |
| `step`, `steps` | number | The step, 1-based, and how many the walkthrough has. |
| `title` | string | The step's title. |
| `missables` | object[] | `{api, name, hidden, note}` per open missable, the step's `missables` first. `name` is `"Hidden achievement"` and `hidden` `true` for a hidden achievement unless `reveal-hidden` is on; `note` is the guide's `missable_note` (when it is lost), or `""`. |
