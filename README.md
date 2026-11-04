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
each). GOG needs no network at all. No root, no API key, no login. Details in
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
| Tab, Shift+Tab | All, Locked, Unlocked, Rare |
| Left, Right | Sort: recent, rarest, A–Z, the game's own order (remembered) |
| Any letter | Search; Backspace edits |
| Escape | Clear the search, then close |

From a script:

```bash
omarchy-shell shell summon pym.omatrophy '{}'   # the running or last game
```

## Settings

The panel's **Settings** tab holds the trophy style, then position, glass
and sound as rows of choices, and **Try it** tiles that show a toast of
each tier with your settings. Each choice applies to the next toast.
**Now tab** picks which sections the Now tab shows. Under
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
starts or Steam closes, and after 15 games in a row with no stats, which
usually means Steam is offline or still signing in; those 15 go first
next time. Everything stays on this machine
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
