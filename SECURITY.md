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
  10 s after it exits); `python3 omatrophy.py guide-key` when the shell starts, Hyprland reloads or you change the Guide key, which runs `hyprctl` to bind or unbind that one key at runtime (ADR 18); `python3 omatrophy.py now|games|set|hide|unhide|test|running` when you use
  the bar panel; `python3 omatrophy.py hand` when you tick, count or note by hand in the tracker; `python3 omatrophy.py steam-load` when you press Load from Steam, which opens `steam://` links and moves Steam's window to a hidden workspace and back through `hyprctl` (ADR 13); `python3 omatrophy.py sync` only when you run it; `python3 omatrophy.py game` when the tracker opens; `python3 omatrophy.py share` when you press Save image, which runs a throwaway `quickshell` offscreen (its own temporary config folder, gone when it exits) to draw the image, and `notify-send` to say where it went (also when a guide make ends or the Guide key can't be bound); `pw-play` for the chime (a bundled WAV, or a freedesktop sound with the classic set).
- Reads: Steam's local achievement cache
  (`<Steam>/appcache/stats/UserGameStats*_*.bin`) and library art
  (`<Steam>/appcache/librarycache/`), once a second for changed files; when
  the panel or tracker opens, Steam's last-played times
  (`<Steam>/userdata/<account>/config/localconfig.vdf`) and the command lines
  of running processes (`/proc/*/cmdline`, to find `SteamLaunch AppId=N`);
  its own settings file; to tell whether the shell runs an older OmaTrophy after an update, its own `watcher.json` and, when that is missing, the command lines of running processes (`/proc/*/cmdline`, looking for `omatrophy.py watch`) (ADR 24); Omarchy's Do Not Disturb state
  (`~/.local/state/omarchy/notifications/quiet.json`, watched, never
  written). For GOG: Comet's per-game databases
  (`$XDG_DATA_HOME/comet/gameplay/*/*/gameplay.db`, opened read-only), once
  a second for changed files; Heroic's `gog_store/installed.json`, each
  install folder's `goggame-<product>.info`, `store_cache/gog_library.json`
  and `store/timestamp.json`; and process command lines, matched against
  GOG install folders only. Heroic's GOG login (`gog_store/auth.json`) is
  never read.
- Writes: `~/.config/omatrophy/config.json` (settings and hidden games,
  only when you change them),
  `~/.local/state/omatrophy/` (game-name cache, GOG client-to-product
  pairs, test inbox, which games the launch reminders spoke for, pinned
  walkthrough steps, the Guide key's last bind, the backfill's schedule,
  the running watcher's version in `watcher.json`),
  `~/.local/share/omatrophy/` (your guides and your ticks, counts and notes
  by hand in `by-hand.json`, written only by `omatrophy.py hand`),
  `~/.cache/omatrophy/` (achievement icons, art, global rarity per game,
  refreshed daily, and with the backfill on, profile pages per game in
  `community/`); and, only when you press Save image or run
  `omatrophy.py share`, one PNG per game in your pictures folder
  (`~/Pictures/omatrophy/`, or `--out`). The game's art is fetched
  once into the cache when there is no copy yet (as for the platinum
  toast); the drawing itself reads local files only, and the image is
  never uploaded.
- 100% guides, only when you press Make guide or run `omatrophy.py guide
  make`: runs your coding agent (`claude`, the one checked so far) headless
  in a fresh empty temporary folder, with its built-in tools limited to
  none, or to WebSearch and WebFetch for the research stage; no MCP servers,
  no user or project settings (so no hooks or plugins), and anything else
  refused without a prompt (ADR 14). It uses the agent's own login; a cloud
  agent bills your account. OmaTrophy itself fetches at most 10 HTTPS pages
  a job (Steam community guides and pages the agent cites), as
  `omatrophy-guide/<version>`, with an 8 s timeout and 4 MB cap, skips any
  page behind a bot check rather than retrying it another way, and reads
  pages you saved in `guides/sources/`. It writes only in
  `~/.local/share/omatrophy/guides/`. An agent whose lock isn't checked on a
  real run (`dev/check-lock.py`) never runs, and no adapter ever passes an
  auto-approve flag. With `guide-jail` on, the agent also runs inside
  ai-jail (bubblewrap, Landlock, seccomp): only the job's folder is
  writable and only the variables it needs are passed in.
- Root: never.
- Network: HTTPS to the stores' public, keyless hosts only, when an unlock is
  shown or the bar panel or tracker opens, plus one name lookup per uncached
  game when the watcher starts: the store's app details
  (`store.steampowered.com`, game name, cached), global achievement
  percentages (`api.steampowered.com`), and Steam's CDN
  (`*.steamstatic.com`) for icons and art; for GOG, only icons and art from
  `images.gog.com` and `images.gog-statics.com`, whose URLs Heroic and
  Comet already hold (GOG rarity is in Comet's database, so no lookup). The
  watcher refuses any other
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

The review before 1.0.0, with what it found and fixed, is in
[docs/security-review-1.0.md](docs/security-review-1.0.md).


Steam's files, its web pages and the shell's IPC are treated as untrusted:

- Binary stats files are read up to 64 MB and parsed with bounded nesting;
  a truncated or malformed file means no achievements for that game, never
  a hang.
- Comet's databases are opened read-only and never written; a file that
  isn't Comet's layout means no achievements for that game.
- App, account and GOG product and client ids must be ASCII digits before
  they reach a file path,
  a URL or a command; anything else is ignored.
- Icon URLs from profile pages are kept only when they are HTTPS on
  Steam's hosts.
- Files are written to a temporary file in the same folder, then renamed
  over the old one, so a crash never leaves half a file and a symlink in
  OmaTrophy's folders is replaced, not followed.
- Commands run as argument lists, never through a shell. A note you
  write in the tracker goes to `omatrophy.py hand note` on stdin, never as
  an argument: other local users can read a process's command line.
- `by-hand.json`'s data folder is created private (`0700`); a hand edit
  refuses a folder that isn't yours or that others can write in, and opens
  its lock file without following a link or truncating.
- Every `omatrophy.py` command first checks OmaTrophy's config, state,
  cache and data folders and every folder in them: one that isn't yours or
  that others can write in, or that sits where another user could swap
  it (any folder above it, as written or through a link, that isn't
  yours or root's, or that others can write in without the sticky bit),
  stops the
  command with the `chmod go-w` fix, so nobody else can plant settings, a
  card for the inbox, art or a link for it to act on. The shell's own
  QML reads of those files rely on this check too: with an unsafe folder
  the watcher stops and logs why. OmaTrophy never chmods your folders.
- Files written in place (locks, the test inbox, stop and "looked, none"
  markers) are opened without following a link or truncating, and only
  when they are plain files of yours. Files read for content open
  non-blocking and must be plain files, so a FIFO can't hang the watcher;
  sources and imported guides are read only when the name itself is a
  plain file, checked on the open file, not before. Cached art is used
  only when it is a plain file of yours, never a link, and Save image
  copies the art into its private temporary folder through the open file
  and draws that copy.
- `--env NAME=value` is refused in the jail options: ai-jail would show
  the value in its command line. `--env NAME` or `--env-from-file` keep it
  out.
- A guide is the agent's text: its answers are parsed only as JSON between
  stage tags and checked field by field; achievement names it gives must
  be the game's own; prose is shown as Markdown whose links open only when
  they are `https`. Images in it become plain links before it shows (Qt's
  Markdown view would fetch them, plain http included), both in
  `guides.py` and in the tracker. The prompts tell the agent that pages
  and excerpts are material to quote, never instructions; a page can
  still steer what the agent writes, which is why every claim must quote
  a source OmaTrophy fetched itself.
- Pages the agent cites are fetched by OmaTrophy only over `https` and
  only from the public internet: `localhost`, loopback, LAN, link-local
  (cloud metadata), CGNAT and reserved addresses are refused, checked on
  the address the connection reached, so DNS tricks and redirects are
  covered.
- `guide import` reads only plain files from the folder you give (no
  links, at most 16 MB each), and every file OmaTrophy writes in its own
  folders goes through a temporary file and a rename.
- Every view draws text as plain text except the guide prose (Markdown,
  above): a game or achievement name that looks like HTML is shown as
  written, never rendered (`tests/test_qml.py` checks every `Text`).
- Image URLs reach the shell only when they are local files or `https` on
  the stores' hosts; one from another program's files (Comet, Heroic) on
  any other host is dropped, since the shell's images load what they are
  given.

Local processes running as you can already do anything you can; within
that, the IPC target `pym.omatrophy` (`omarchy-shell shell summon
pym.omatrophy '{...}'`) opens the tracker for a game, and the test inbox
(`~/.local/state/omatrophy/inbox.jsonl`) forwards only events whose
type has a card in `cards.json`, at most 64 KB a line; the shell plays only the four
bundled tier chimes and queues at most 20 cards.

## Windows and input

The toast window takes no input or focus (an empty input mask). The tracker
overlay takes the keyboard only while it is open, and closes on Escape or a
click outside it. OmaTrophy
never changes configuration outside its own files: the Guide key, once you
install it, is a runtime Hyprland bind (`hyprctl`) that a Hyprland reload
drops and the shell binds again, never a line in your Hyprland config.
