# Troubleshooting

Start with the log:
`quickshell log -p /usr/share/omarchy/shell -t 200 | grep -i omatrophy`.

## No toast when I unlock something

- **Steam not found.** Run `python3 omatrophy.py status`. "No game store with
  achievement data found" means the Steam folder isn't in a usual place: set
  `STEAM_DIR` (see [specs/cli.md](../specs/cli.md)). The watcher retries
  every 10 s.
- **Wrong account.** Several Steam accounts on one machine: the watcher picks
  the one with the most cached games. Set `STEAM_ACCOUNT`.
- **The unlock is older than 15 minutes when Steam writes it.** That looks
  like a cache sync (a new machine, first launch) and is skipped on purpose
  (ADR 4).
- **Steam hasn't written the cache yet.** Some games sync stats late or on
  exit; the toast shows when the file changes.
- **The shell runs an old copy.** After updating, `omarchy restart shell`
  (not while a game runs).

Check the pipeline with `python3 omatrophy.py test silver`: a toast means the
shell side works and the problem is upstream.

## The toast is under the game

Fullscreen games on a different monitor than the focused one: the card goes
to the focused monitor. Exclusive-fullscreen games that bypass the
compositor's layers can hide it (unverified for specific games).

## No sound

`pw-play` (PipeWire) must be installed and sound on in the panel. The
classic set also needs the freedesktop sound theme
(`/usr/share/sounds/freedesktop/stereo/`).

## Rarity is missing (every trophy is bronze)

Rarity comes from Steam's public endpoint when the toast shows. Offline or
for games that don't publish percentages, the tier falls back to bronze.

## My edit doesn't show

Omarchy's Quickshell caches plugin files when it loads them, and ignores a
`?v=` query on the URL (ADR 10). What reloads without a restart:

- `TrophyToast.qml` and `PlatinumCard.qml`: the next card.
- `StylePicker.qml`: the next time the bar panel opens.
- `TrackerView.qml`: the next time the tracker opens.

These four are built from their current text by `FreshObject.qml`, so they
can't use other QML types from this folder; a new `Foo.qml` they reference
won't resolve. Everything else, `Service.qml`, `Panel.qml`, `Tracker.qml`,
`FreshObject.qml` and `manifest.json`, needs `omarchy restart shell` (not
while a game runs). `omatrophy.py` and `stores/` load when the watcher
restarts: `pkill -f 'omatrophy.py watch'` and the service starts it again
within 10 s. The full table is in
[development.md](development.md#what-reloads-when).

## The tracker doesn't open

- **Wrong command.** `omarchy-shell shell summon pym.omatrophy '{}'` opens the
  tracker (the plugin's overlay); add `{"store":"steam","app":"<id>"}` for a
  given game. The bar panel answers a different target:
  `omarchy-shell pym.omatrophy toggle`.
- **The shell predates the overlay.** The `overlay` kind and `Tracker.qml`
  load only on a shell start: run `omarchy plugin validate .`, then
  `omarchy restart shell` once. `omarchy plugin list` should show `overlay`
  among the plugin's kinds.
- **It opens empty.** With `'{}'` the tracker shows the running game or the
  last one played; with no game data at all it has nothing to list. Check
  `python3 omatrophy.py game` prints a game.

## The bar panel text is unreadable

Fixed in the panel by using the popup text colour; restart the shell once so
it loads the current `Panel.qml`.
