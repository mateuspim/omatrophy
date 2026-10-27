# 11. Backfill games this machine never ran from the public profile, opt-in

- Status: Accepted
- Date: 2026-10-27

## Context

Steam writes a game's `UserGameStats_<account>_<app>.bin` only once that
game has run on this machine (ADR 1). On a fresh install the panel showed 3
of the owner's games while localconfig listed 446 played, so the cabinet,
the Games tab and the tracker were nearly empty on any new machine.

A public Steam Community profile serves each game's achievement page,
`steamcommunity.com/profiles/<steamid64>/stats/<app>/achievements/`, without
a login or key. The old `?xml=1` view is gone; the page now embeds its data
as JSON (`<script id="valve-ssr-data">`, `renderContext.queryData`), with
the game's schema, the user's unlocks with unix times, and the game's name.
The owned-games list (`/games/`) needs a login, but localconfig already says
which games were played. A game without achievements redirects to the
profile page.

## Decision

- An opt-in setting, `community` (off by default; `omatrophy.py set
  community on`), lets the Steam store fill in games that have no local
  stats file from that page.
- It is a backfill, never the live path: the watcher fetches in a
  background thread after `ready`, one page about every 3 s, most
  recently played first. A 429 is waited out (1, 2, 4... minutes, five at
  most; Steam limited the first test run after about 20 pages); any other
  error ends the run and the next one resumes. Pages
  are cached in `~/.cache/omatrophy/community/games/<app>.json`, refetched
  after a week or when the game was played since; "no achievements" is
  kept for a month in one index, `community/none.json`, so `games()` stays
  a folder listing. `omatrophy.py sync` runs the same backfill in the
  foreground.
- Local data always wins: once a game has a local stats file, its
  community copy is ignored.
- Achievements read from the page carry `remote: true`, and the watcher
  never toasts them: an unlock that arrives through the page happened on
  another machine.
- Only the embedded JSON is read, never the page's markup. When its shape
  changes, the parser returns nothing for that game and the game drops back
  to "not on this machine yet"; toasts are unaffected.

## Consequences

- A new machine shows the whole library within minutes of enabling it,
  for a public profile with public game details.
- With `community` on, the owner's SteamID64 goes to steamcommunity.com in
  each page's URL. That is why it is opt-in; SECURITY.md says so.
- The page format is undocumented and Valve's to change; the parser's tests
  build the JSON shape seen on 2026-10-27.
- ADR 1 still holds for toasts and for every game that ran here; this adds
  a second, slower source and doesn't replace it.
