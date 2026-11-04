# 13. Load played games' stats through the Steam client, on request

- Status: Accepted
- Date: 2026-11-04

## Context

Steam writes `appcache/stats/UserGameStats_<account>_<app>.bin` (and the
game's schema) only once its client has loaded that game's stats. ADR 1 and
ADR 11 assumed that meant the game had to run on this machine. On
2026-11-03 the owner opened Batman: Arkham Asylum's library page without
playing it, and both files appeared within a second. On 2026-11-04,
`steam steam://nav/games/details/377160` did the same for Fallout 4. On the
owner's machine localconfig.vdf listed about 446 played games and 136 had
a stats file, so about 340 were missing only because Steam had never
loaded them here.

The community backfill (ADR 11) fills that gap from the network, needs a
public profile, and runs into Steam's rate limit after a few pages. The
client's own cache needs none of that.

## Decision

- `omatrophy.py steam-load` opens the library page of each played game
  (localconfig.vdf `Playtime` > 0) that has no local stats file, most
  played first, through a `steam://nav/games/details/<app>` link handed to
  the running client (`steam`, else `xdg-open`). It waits up to 8 s for the
  stats file, then moves on.
- Played games are the whole queue: you can't earn achievements in a game
  you never played, so owned-but-unplayed games (Steam's binary
  packageinfo/appinfo) aren't read.
- A game whose page opened without a stats file has no achievements, as
  far as we can tell, and goes into `~/.cache/omatrophy/steam-load/none.json`.
  It is tried again after 30 days.
- Only the owner starts it, from the CLI or the panel, never the watcher:
  Steam's window comes forward and changes page for every game. It stops
  when Steam closes, when any store reports a running game (the window
  must not jump over a game, see ADR 8), or on `steam-load stop`. Progress
  goes to `steam-load/status.json`. A rerun picks up where the last one
  stopped, since loaded games have their file now.
- OmaTrophy writes nothing into Steam's files; the client writes its own
  cache, as it does when you click through the library yourself.

## Consequences

- A library fills in locally in minutes: about a second per game with
  achievements and 8 s per game without, with no key, no public profile
  and no rate limit. The files are the same ones ADR 1 reads, so toasts,
  progress counters and the tracker work for those games as if they had
  run here.
- The steam:// page path is undocumented and Valve's to change. If it
  stops caching stats, every game times out and lands in none.json for a
  month (unverified how such a change would look); deleting the folder
  resets it.
- Steam may drop those cache files later (unverified); a rerun reloads
  them.
- The community backfill stays for what this can't reach: unlock times for
  games whose stats Steam won't load here, and machines where the owner
  won't let Steam's window move.
