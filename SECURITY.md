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
  the bar panel; `python3 omatrophy.py sync` only when you run it; `python3 omatrophy.py game` when the tracker opens; `pw-play` for the chime (a bundled WAV, or a freedesktop sound with the classic set).
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
  game when the watcher starts: the store's app details
  (`store.steampowered.com`, game name, cached), global achievement
  percentages (`api.steampowered.com`), and Steam's CDN
  (`*.steamstatic.com`) for icons and art. The watcher refuses any other
  host, plain HTTP, and redirects off those hosts, and reads at most 8 MB
  per response with a 4 s socket timeout. The panel and tracker load
  header art and achievement icons straight from the CDN as images. Your account id is not
  sent, unless you turn on the community backfill (`omatrophy.py set
  community on`, off by default): then the watcher fetches your public
  profile's achievement page for each played game with no local data, one
  about every 3 s, and your SteamID64 is in those URLs (ADR 11).
- Secrets: none. No API key, no login; a private Steam profile works (the
  optional backfill needs a public one).

## Untrusted input

Steam's files, its web pages and the shell's IPC are treated as untrusted:

- Binary stats files are read up to 64 MB and parsed with bounded nesting;
  a truncated or malformed file means no achievements for that game, never
  a hang.
- App and account ids must be ASCII digits before they reach a file path,
  a URL or a command; anything else is ignored.
- Every piece of text the views show (game names, achievement names and
  descriptions) is drawn as plain text, never rich text.
- Icon URLs from profile pages are kept only when they are HTTPS on
  Steam's hosts.
- Files are written to a temporary file in the same folder, then renamed
  over the old one, so a crash never leaves half a file and a symlink in
  OmaTrophy's folders is replaced, not followed.
- Commands run as argument lists, never through a shell.

Local processes running as you can already do anything you can; within
that, the IPC target `pym.omatrophy` (`omarchy-shell shell summon
pym.omatrophy '{...}'`) opens the tracker for a game, and the test inbox
(`~/.local/state/omatrophy/inbox.jsonl`) forwards only `unlock` and
`platinum` events, at most 64 KB a line; the shell plays only the four
bundled tier chimes and queues at most 20 cards.

## Windows and input

The toast window takes no input or focus (an empty input mask). The tracker
overlay takes the keyboard only while it is open, and closes on Escape or a
click outside it. OmaTrophy
never changes configuration outside its own files.
