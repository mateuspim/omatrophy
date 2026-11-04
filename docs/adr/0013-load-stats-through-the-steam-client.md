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
- Every game tried goes into `~/.cache/omatrophy/steam-load/checked.json`
  the moment it is done, with whether a stats file came: the checkpoint. A
  game in it is never tried again, so a stopped run resumes at the next
  game and a later load only takes games played since. A game whose page
  opened without a file has no achievements, as far as we can tell,
  except after 15 such games in a row: Steam offline or still signing in
  loads nothing, so the run stops there and keeps those games unsure
  (`found: null`), first in line for the next load. One that times out
  again then counts as none and starts no new streak, so a library with
  15 games without achievements in a row can't stop every load. Only
  `steam-load all` (Check all again in the panel) tries every played game
  without stats again: whole-library passes happen only when the owner
  asks.
- On Hyprland, Steam's window waits on a hidden special workspace
  (`special:omatrophy`) while a load runs, with `focus_on_activate` off
  for that window only, and goes back to its workspace afterwards with
  that override dropped (`value = "unset"`), so the user's own rules
  apply again. A main window the load itself opened (Steam was in the
  tray) is closed again; any other window that appeared meanwhile
  (Friends, a sign-in dialog) comes to the active workspace instead.
  This is set at runtime through `hyprctl`; Hyprland's config is never
  written. Elsewhere the window comes forward page by page.
- Only the owner starts it, from the CLI or the panel, never the watcher.
  It stops when Steam closes, when any store reports a running game (see
  ADR 8), or on `steam-load stop`, which also cuts short the wait on the
  current game. Progress, with the game being tried, goes to
  `steam-load/status.json`; the panel shows it as a bar on every tab.
- OmaTrophy writes nothing into Steam's files; the client writes its own
  cache, as it does when you click through the library yourself.

## Consequences

- A library fills in locally in minutes, out of sight: about a second
  per game with achievements and 8 s per game without, with no key, no
  public profile and no rate limit. The files are the same ones ADR 1 reads, so toasts,
  progress counters and the tracker work for those games as if they had
  run here.
- The steam:// page path is undocumented and Valve's to change. If it
  stops caching stats, every game times out and is marked tried
  (unverified how such a change would look); Check all again, or deleting
  the folder, retries them.
- Steam may drop those cache files later (unverified); since tried games
  aren't retried on their own, Check all again reloads them.
- The window hiding leans on Hyprland 0.56's Lua dispatch
  (`hl.dsp.window.move`, `hl.dsp.window.set_prop`). If those change, the
  calls fail quietly and the window comes forward again.
- The community backfill stays for what this can't reach: unlock times for
  games whose stats Steam won't load here, and machines where the owner
  won't let Steam's window move.
