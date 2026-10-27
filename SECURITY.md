# Security

## Reporting a vulnerability

Please report privately through GitHub's
[security advisories](https://github.com/mateuspim/omatrophy/security/advisories/new)
rather than a public issue. Include the version (`manifest.json`), steps to
reproduce and impact. You can expect a reply within a week.

## Supported versions

Only the latest release on `master` receives fixes.

## Privilege model

Omarchy plugins run unsandboxed inside `omarchy-shell` as your user. This is
what OmaTrophy does with that access:

- Runs: `python3 omatrophy.py watch` for as long as the shell runs (restarted
  10 s after it exits); `python3 omatrophy.py now|games|set|hide|unhide|test` when you use
  the bar panel; `python3 omatrophy.py game` when the tracker opens; `pw-play` for the chime (a bundled WAV, or a freedesktop sound with the classic set).
- Reads: Steam's local achievement cache
  (`<Steam>/appcache/stats/UserGameStats*_*.bin`) and library art
  (`<Steam>/appcache/librarycache/`), once a second for changed files; when
  the panel or tracker opens, Steam's last-played times
  (`<Steam>/userdata/<account>/config/localconfig.vdf`) and the command lines
  of running processes (`/proc/*/cmdline`, to find `SteamLaunch AppId=N`);
  its own settings file.
- Writes: `~/.config/omatrophy/config.json` (settings and hidden games,
  only when you change them),
  `~/.local/state/omatrophy/` (game-name cache, test inbox),
  `~/.cache/omatrophy/` (achievement icons, art, global rarity per game,
  refreshed daily, and with the backfill on, profile pages per game in
  `community/`).
- Root: never.
- Network: HTTPS to Steam's public, keyless endpoints only, when an unlock is
  shown or the bar panel or tracker opens, plus one name lookup per uncached
  game when the watcher starts: the store's app details (game name, cached),
  global achievement percentages, and Steam's CDN for icons and art. Your account id is not
  sent, unless you turn on the community backfill (`omatrophy.py set
  community on`, off by default): then the watcher fetches your public
  profile's achievement page for each played game with no local data, one
  about every 3 s, and your SteamID64 is in those URLs (ADR 11).
- Secrets: none. No API key, no login; a private Steam profile works (the
  optional backfill needs a public one).

The toast window takes no input or focus (an empty input mask). The tracker
overlay takes the keyboard only while it is open, and closes on Escape or a
click outside it. OmaTrophy
never changes configuration outside its own files.
