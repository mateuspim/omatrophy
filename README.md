# <img src="icon.svg" alt="" width="32" height="32" align="top"> OmaTrophy

![OmaTrophy: a gold trophy toast over the achievement tracker, beside the wordmark, its feature chips and the install command](preview.png)

**Achievement unlocks as trophies over your games, on the Omarchy shell:
bronze, silver and gold by rarity, and a platinum moment when you finish a
game. Steam and GOG (through Heroic); no API key, works with a private
Steam profile.**

## Quick start

```bash
omarchy plugin add https://github.com/mateuspim/omatrophy.git --enable
python3 ~/.config/omarchy/plugins/pym.omatrophy/omatrophy.py test gold
```

Unlock something in a game, or click the trophy in the bar: it shows the
game you're playing and what's left in it, and opens any game's full
achievement list.

## Features

- Toasts on the shell's Overlay layer, so they land over fullscreen games
  even when Steam's own popup doesn't. Click-through; never takes focus.
- About two seconds from unlock to toast: OmaTrophy reads the launcher's
  local achievement data (Steam's cache, the GOG database Heroic keeps),
  so no Web API key, no login and no public profile.
- Rarity picks the metal: bronze, silver at 35% of players or fewer, gold at
  10% or fewer, with glitter and a sweep of light for gold.
- A platinum card at 100%: the trophy spins in over the game's hero art and
  the count rolls up.
- The achievement icon, its description, the share of players, and your
  progress through the game, filling in as you watch.
- A trophy cabinet in the bar: the game you're playing with this session's
  unlocks and the likeliest next ones, or the last three games you played,
  your rarest unlocks ever or this month, and a shelf of your platinums; every game, eight to a page, filtered as you
  type and sorted by recent, closest to platinum or name, with games you
  won't finish set aside, and platinums you'd rather not show taken off
  the shelf.
- An achievement tracker over the screen: every achievement of a game with
  its rarity, the day you got it, and how far along a counter is ("52 /
  80"); filtered to locked, unlocked or rare, sorted, and searched as you
  type, by mouse or keyboard. Hidden ones stay hidden until you hover or
  press Enter.
- A 100% guide per game, made on request by your own coding agent (Claude
  Code today): the route, missables first, time and difficulty per
  achievement, combos and tips, with every claim checked against the page
  it quotes. The Now tab's Up next follows it.
- Three trophy styles: Omarchy (a pixel grid with an inlay in your theme
  accent), Faceted and Painted.
- Theme-native: cards draw from your Omarchy theme colours.
- A chime per tier, from a short tick for bronze to a ringing bloom for
  platinum, made for OmaTrophy; or the classic desktop sounds, or silence.
- Top centre, top left or top right.
- Steam and GOG today, and built for more: each store is a small module
  ([adding a store](docs/guide/stores.md)).

## Install

```bash
omarchy plugin add https://github.com/mateuspim/omatrophy.git --enable
```

This places a trophy button in the bar. If it doesn't show, run
`omarchy restart shell` once (not while a game runs).

## Remove

```bash
omarchy plugin remove pym.omatrophy
rm -rf ~/.config/omatrophy ~/.local/state/omatrophy ~/.cache/omatrophy
```

## Security and privileges

OmaTrophy runs inside `omarchy-shell` as your user. It reads Steam's local
achievement cache and, for GOG, the database Heroic's Comet service keeps, keeps its settings and a small cache in its own folders,
and calls Steam's public endpoints for rarity, game names and art when a
toast shows, the bar panel opens or the watcher starts (game names, once
each). GOG needs no network at all. No root, no API key, no login. Making a 100%
guide is the one exception, and only when you ask: it runs your own coding
agent, locked to web search and fetch, through its own login. Details in
[SECURITY.md](SECURITY.md).

## Trophy cabinet and tracker

Click the trophy in the bar. The **Now** tab shows your totals, split by
metal with your average completion, then the game
you're playing: its art and progress, what you've unlocked this session and
the three locked achievements most players have. With nothing running it
shows the last three games you played instead (a finished one carries its
platinum date). Below them come your three rarest unlocks across every game,
ever, this month or from your platinums only (click one to open it in the
tracker), and your platinum shelf,
whose empty slots tease the games you're closest to finishing ("2 left"). Before any game has
achievements, the tab says where they come from and points to the Steam
profile switch. The **Games** tab lists every
game with its count, sorted by last played, closest to platinum or name.
Type (or press `/`) to filter by name; Enter opens the first match. Hover a
game and click **Hide** to set aside one you won't finish: it leaves
Closest and dims in the other sorts until you click **Show**.

The **Profile** tab shows your library at a glance, in tiles after Steam's
profile showcases, each one yours to pick from the tracker:

- **Favorite game**: **+ Choose game** on the tile opens a search of your
  games. Shows its art, hours, trophies and your six rarest unlocks from
  it.
- **Showcase**: click ☆ on up to six earned trophies. Until you do, your
  rarest stand in.
- **Completionist**: click **☆ Completionist** beside a finished game's
  Platinum in the tracker, for up to four games. Until you do, your two newest platinums stand in. Below it:
  games completed, started and average completion.
- **Playtime**: hours in the past two weeks and in all, from the
  launchers' own files.

Hover a pinned tile for **×** to take it off; drag a showcase trophy
sideways to move it.

On multiple monitors, each trophy button opens its own panel. Direct IPC
(`omarchy-shell pym.omatrophy toggle`, also `open` or `close`) controls the
panel on the first screen in Quickshell's screen list.

Click any game for the **tracker**, a card over the screen with every
achievement: rarity, the trophy it would earn, and the date you got it.
Locked counter achievements show how far along you are ("52 / 80") when
the game tracks the count. Its keys:

| Key | Does |
| --- | --- |
| Up, Down, Page Up/Down, Home, End | Move the highlight |
| Enter (or Space, when not searching) | Reveal a hidden achievement |
| Shift+Enter | Reveal all hidden achievements, or hide them again (remembered) |
| Tab, Shift+Tab | All, Locked, Unlocked, Rare, Guide |
| Left, Right | Sort: recent, rarest, A–Z, the game's own order (remembered) |
| Any letter | Search; Backspace edits |
| Escape | Clear the search, then close |

From a script:

```bash
omarchy-shell shell summon pym.omatrophy '{}'   # the running or last game
```

## 100% guides

![The tracker's Guide tab for a sample game: up next and the walkthrough on the left, every open achievement by phase on the right](docs/brand/captures/guide.png)

The tracker's **Guide** tab shows a game's path to 100%: what to do next,
an overview and the recommended route, then every open achievement by
phase (missable first, then story, quick, challenge, grind, collectibles,
online), each with its time, difficulty, counter, where the point of no
return is, a tip and what it combines with. A hidden achievement keeps its
name and tip secret until you hover it, or **Reveal all** (next to Up
next and the trophy list, or Shift+Enter) shows every one, in every game,
until you hide them again.
Anything no source backs says
"(unverified)". With a guide, the Now tab's **Up next** follows its route.

A guide with a **walkthrough** leads with it, under a short overview: the
game's chapters or missions in play order, each with its progress
("1 / 3") and its trophies in full, done ones ticked, a ⚠ on the ones you
lose by moving on. The step you're on (the first with a trophy left, at
or after your latest unlock) is open; click a step's title to open or
fold it. Trophies no step holds follow under **Not in a step**. Without
a walkthrough, Up next and the route show as before
([ADR 17](docs/adr/0017-walkthrough-is-a-maker-stage.md)). A guide made
before 0.7.0 has none: the tracker says "older maker", and **Make again**
adds one.

### The guide over your game

Like Steam's Shift+Tab overlay: **Super+Ctrl+G** opens the guide of the
game you're playing over it, and the same key (or Escape) closes it. No
guide yet? **Make guide** is right there. Change the key under **Guide
key** in Omarchy's plugin settings for OmaTrophy; a key another binding
already uses is refused, with a notification and a note in
**Settings > Guides**. Leave it empty to bind none and keep your own bind
to `omarchy-shell shell toggle pym.omatrophy '{"view":"guide"}'`.
OmaTrophy binds the key at runtime and never edits your Hyprland config
([ADR 18](docs/adr/0018-bind-the-guide-key-at-runtime.md)).

While the guide is open it takes the keyboard, like the Steam overlay; a
game that pauses when it loses focus pauses
([ADR 16](docs/adr/0016-in-game-guide-is-the-tracker-on-a-key.md)).

### Making a guide

No guide yet? **Make guide** asks your coding agent to write one. OmaTrophy
gathers what it can fetch itself (Steam community guides, pages you saved
by hand in `~/.local/share/omatrophy/guides/sources/<guide name>/`), the
agent searches the web if you let it, classifies the achievements in small
batches and plans the route, and OmaTrophy checks each quote against the
page it came from. It takes a few minutes and keeps going if you close the
tracker; **Stop** leaves the old guide as it was. A cloud agent bills your
account (the guide records the cost it reports). A game you already have at
100% gets no **Make guide**: there is nothing left to plan.

The agent runs headless in an empty folder with no shell and no file
tools, only web search and fetch when it researches
([ADR 14](docs/adr/0014-generate-guides-through-the-users-agent.md)). Claude
Code is checked to stay locked down that way. Codex and OpenCode stay off
until their lock is checked on your machine: **Check** in
**Settings > Guides** asks the agent to write a file and run a command, and
turns it on if it can't (again after the agent updates). Pick the agent (or follow
`omarchy default agent`), its model (any the agent lists, or type another)
and effort in the tracker or in **Settings > Guides**. The model list marks
the [guide bench](docs/guide/guide-models.md)'s best pick for the agent
with ★ (Opus for Claude Code, GPT-6.1 Terra for Codex); the agent's own
default stays until you pick. With
[ai-jail](https://github.com/akitaonrails/ai-jail) installed, **Sandbox**
runs the agent inside it as well. A local model needs its server let in:
**Jail options** under Sandbox (or `guide jail-options`) adds ai-jail
options for the picked agent, such as `--map ~/path/to/key` for a key file
it reads. The jail keeps the network on (the agent searches the web), so a
server on `127.0.0.1` is reachable without `--forward-port`, which ai-jail
refuses next to it. **Check in ai-jail** runs the lock check there to see
that the agent still answers, and `guide jail` says what is installed.
ai-jail 2.x and 3.x both work, with nothing to approve in
`ai-jail configure`: on 3.x OmaTrophy passes the access itself (the
network and the agent's login), and the job's folder is a new one each
run, so no saved ai-jail policy applies to it.
[ai-jail](https://github.com/akitaonrails/ai-jail) is
[Akita](https://github.com/akitaonrails)'s work; OmaTrophy only calls it.

Guides from another folder of `<slug>-<appid>.md` files (with their
`.plan.json`) come in with `guide import`; the folder is only read.

```bash
omatrophy.py guide import ~/path/to/guides     # copy guides in (--replace overwrites)
omatrophy.py set guide-agent claude            # or default: follow omarchy default agent
omatrophy.py guide model claude sonnet medium  # that agent's model and effort; `default` clears
omatrophy.py guide jail                        # is ai-jail installed, the sandbox on, each agent's options
omatrophy.py guide jail-options opencode --map ~/path/to/key  # extra ai-jail options; none clears
omatrophy.py guide make steam 620              # make one; --no-web, --model, --effort for this run
omatrophy.py guide jobs                        # every guide being made, as JSON (up to 3 at once)
omatrophy.py guide stop steam 1774580          # stop one game's; guide stop alone stops them all
omatrophy.py guide steam 620                   # the guide, as JSON
```

Which model writes the best guide? `guide bench` makes one game's guide
with each, side by side, and ranks them by what OmaTrophy can check
(quotes verified, achievements covered, fields filled), with time and
cost. `--pick` makes the winner your default; `--keep` keeps its guide.
A model on your own machine takes part through OpenCode (`opencode:<provider/model>`,
once its **Check** passes) or through Claude Code pointed at a local
Anthropic-compatible server:

```bash
omatrophy.py guide bench steam 620 claude:haiku claude:sonnet:medium \
  claude:my-local-model@http://127.0.0.1:8080 --pick
```

One bench on three games (2026-11-06, unreleased guides build, web
research on). Results vary per game, per run and per machine; full numbers
and caveats in [docs/guide/guide-models.md](docs/guide/guide-models.md).

| Agent · model | Where it runs | Score (small / DLC / big game) | Verified quotes | Coverage | Time (3 games) | Cost (3 games) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Claude Code · Opus 5.5, medium | cloud | 95.0 / 88.6 / 88.6 | 90% | 100% | 14 min | $3.15 | best average and verified share |
| Codex · GPT-6.1 Terra, medium | cloud | 88.8 / 91.4 / 85.0 | 77% | 100% | 6 min | plan | fastest; best on the DLC game |
| OpenCode · Qwen3.8 Flash Next, Q2 | local | 86.9 / 82.3 / 87.0 | 75% | 100% | 32 min | $0 | needs working web search |
| Claude Code · Sonnet, medium | cloud | 89.8 / 67.1 / 78.7 | 61% | 100% | 8 min | $1.27 | left one section empty each time |
| Claude Code · Haiku | cloud | 86.9 / 58.6 / 88.4 | 76% | 100% | 14 min | $0.28 | cheapest per-use; uneven |
| Codex · GPT-6 Luna | cloud | 89.6 / 60.0 / 76.1 | 46% | 100% | 8 min | plan | |
| Codex · GPT-6.1 Sol, medium | cloud | 88.8 / 52.5 / 81.5 | 60% | 100% | 12 min | plan | missed every DLC tag on RE7 |

Games: METAL GEAR SOLID V: GROUND ZEROES (13 open), Resident Evil 7
Biohazard (11 open, all DLC), Rise of the Tomb Raider (81 open). "plan":
Codex reports no cost; it bills your ChatGPT plan.

Format and stages: [docs/specs/guides.md](docs/specs/guides.md).

## Settings

The panel's **Settings** tab opens on an **Overview**: one line per
section saying what it is set to; click one, or pick a section above it.
**Toasts** holds the trophy style, then position, glass
and sound as rows of choices, and **Try it** tiles that show a toast of
each tier with your settings. Each choice applies to the next toast.
**Now tab** picks which sections the Now tab shows. **Guides** picks the
agent that makes 100% guides and its model, each from a list that unfolds
in place (every installed agent with its state; every model the agent
lists, searchable, or any model id you type) and its effort, then whether
it may search the web. In
**Stores**, a card per store says whether OmaTrophy found it and how many
games it has, or what to do when it didn't. In Steam's card, **Profile**
fills in games this machine never ran from your public Steam profile (off
by default), and **Load from Steam** has the Steam client save the
achievements of played games OmaTrophy can't see yet (it shows how many;
the Games tab has the same button), with **Check all again** to retry the
whole library. While a load runs, a bar under the tabs shows it. GOG has nothing to set. Steam also shows its own popup for each unlock; **Turn off in Steam** opens
Steam's Notifications settings: untick Show Toast (and Play Sound) on
"When I unlock an achievement".

From a terminal:

```bash
omatrophy.py set position top-right     # top-center, top-left, top-right
omatrophy.py set sound off              # on, off, omatrophy, classic
omatrophy.py set icons vector           # omarchy, vector, painted
omatrophy.py set glass clear            # clear, frosted, solid
omatrophy.py hide steam 20920           # out of "closest to platinum" and the shelf; unhide brings it back
omatrophy.py test platinum              # bronze, silver, gold, platinum
omatrophy.py status                     # progress of every game
omatrophy.py now                        # the panel's Now tab, as JSON
omatrophy.py game                       # every achievement of the running game
```

The full command list is in [docs/specs/cli.md](docs/specs/cli.md), the
settings file in [docs/specs/settings.md](docs/specs/settings.md).

## Game stores

Steam and GOG are supported today.

### Steam

Native or Flatpak; set `STEAM_DIR` if yours lives elsewhere.

Steam keeps a game's achievements on disk only once its client has
loaded them here: by playing the game, or just by opening its library
page. So a fresh install shows just a few games. With Steam running and no
game open, let OmaTrophy open those pages for you:

```bash
omatrophy.py steam-load          # every played game not tried yet, most played first
omatrophy.py steam-load stop     # from another terminal: stop now
omatrophy.py steam-load all      # try every played game without stats again
```

On Hyprland, Steam's window waits on a hidden workspace while it runs, and
comes back where it was afterwards (Peek shows it meanwhile); the panel
shows the progress on every tab: the game being checked, what was found,
and time left. It takes about a second per game with achievements and 8 s for
one without. Each game is remembered once tried, so a stopped load picks
up where it ended and later loads only take games you played since; only
`all` goes over the whole library again. It stops by itself when a game
starts, Steam closes or Steam isn't signed in (offline, or still signing
in), and after 15 games in a row with no stats, which usually means the
same; those 15 go first next time. Everything stays on this machine
([ADR 13](docs/adr/0013-load-stats-through-the-steam-client.md)).

If your profile and game details are public, you can also fill in games
from your Steam Community profile:

```bash
omatrophy.py set community on   # off by default; sends your SteamID64 to steamcommunity.com
omatrophy.py sync               # optional: fetch now with progress (the watcher also does it)
```

Steam limits how fast a profile can be read, so the watcher fetches a few
pages an hour (15 to start, fewer after Steam says to slow down, more while
it doesn't) and a large library fills in over a day or two. After a rate
limit it waits a few hours, shell restarts included. Settings has
the same switch, and shows how the latest run went. Toasts still
come only from this machine's own data.

### GOG

GOG games played through [Heroic Games Launcher](https://heroicgameslauncher.com)
(`omarchy-install-gaming-heroic`), native or Flatpak. Heroic runs Comet, an
open-source stand-in for GOG Galaxy, beside every GOG game, and Comet keeps
each game's achievements, unlock times and GOG's rarity in a small database
OmaTrophy reads ([ADR 12](docs/adr/0012-read-comets-gameplay-database-for-gog.md)).
Nothing goes online and Heroic's GOG login is never read.

- A game shows once it has run through Heroic. Comet is on by default;
  with it turned off among Heroic's experimental features, nothing is
  recorded.
- Names and art come from Heroic's library, so a game you've
  uninstalled keeps them.
- Set `HEROIC_DIR` or `COMET_DIR` if Heroic or Comet keep their files
  somewhere unusual.

Other launchers plug in as one module each:
[adding a store](docs/guide/stores.md).

## Requirements

- Omarchy 4.0+ with the Quickshell-based `omarchy-shell`
- Python 3 (standard library only)
- Steam, or Heroic Games Launcher for GOG (Heroic 2.x with Comet, its
  default), with games that have achievements
- PipeWire (`pw-play`) for the chime

## Documentation

- [Documentation index](docs/README.md): architecture, decisions, specs and
  runbooks.
- [Troubleshooting](docs/runbooks/troubleshooting.md).
- [Contributing](CONTRIBUTING.md) and [Security](SECURITY.md).

## Development

Link a checkout to `~/.config/omarchy/plugins/pym.omatrophy`, then run
`python3 -m unittest discover -s tests` and `omarchy plugin validate .`.
Preview cards without touching the live shell with `dev/preview.sh`, or
render any view to a PNG with `dev/render.sh`.
Everything is in the [development runbook](docs/runbooks/development.md).

## License

MIT. See [LICENSE](LICENSE).
