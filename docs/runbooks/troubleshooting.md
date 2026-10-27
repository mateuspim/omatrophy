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

## The bar panel text is unreadable

Fixed in the panel by using the popup text colour; restart the shell once so
it loads the current `Panel.qml`.
