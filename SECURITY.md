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
  10 s after it exits); `python3 omatrophy.py set|test` when you use the bar
  panel; `pw-play` for the chime (a bundled WAV, or a freedesktop sound with the classic set).
- Reads: Steam's local achievement cache
  (`<Steam>/appcache/stats/UserGameStats*_*.bin`) and library art
  (`<Steam>/appcache/librarycache/`), once a second for changed files; its own
  settings file.
- Writes: `~/.config/omatrophy/config.json` (settings),
  `~/.local/state/omatrophy/` (game-name cache, test inbox),
  `~/.cache/omatrophy/` (achievement icons and art).
- Root: never.
- Network: HTTPS to Steam's public, keyless endpoints only, when an unlock is
  shown: the store's app details (game name, cached), global achievement
  percentages, and Steam's CDN for icons and art. Your account id is not
  sent.
- Secrets: none. No API key, no login; a private Steam profile works.

The toast window takes no input or focus (an empty input mask). OmaTrophy
never changes configuration outside its own files.
