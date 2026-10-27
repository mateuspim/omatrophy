# Architecture Decision Records

Each record describes one durable decision in OmaTrophy's design: the
context that led to it, what was decided, and what follows from it. They use
Michael Nygard's format (Title, Status, Context, Decision, Consequences) and
are numbered in the order they were recorded. For how the parts fit together
today, see the [architecture overview](../architecture.md).

Records 1-8 were documented from the code on 2026-10-26, before the first
release; that date is when they were written down, not when each choice was
made.

| # | Decision | Status |
| --- | --- | --- |
| [1](0001-read-local-store-data.md) | Read the store's local data; need no account key | Accepted |
| [2](0002-overlay-layer-click-through.md) | Show cards on the Overlay layer, click-through and unfocusable | Accepted |
| [3](0003-rarity-picks-the-metal.md) | Rarity picks the metal; 100% is platinum | Accepted |
| [4](0004-skip-stale-unlocks.md) | Skip unlocks older than 15 minutes | Accepted |
| [5](0005-cards-load-by-fresh-url.md) | Load cards by a fresh URL; keep them standalone | Superseded by 10 |
| [6](0006-watcher-speaks-json-lines.md) | A Python watcher speaks JSON lines to the shell | Accepted |
| [7](0007-pluggable-stores.md) | Stores are pluggable; the watcher stays generic | Accepted |
| [8](0008-never-restart-the-shell-mid-game.md) | Develop without restarting the live shell | Accepted |
| [9](0009-tracker-is-an-overlay.md) | The achievement tracker is the plugin's overlay entry point | Accepted |
| [10](0010-build-views-from-their-text.md) | Build live-edited views from their text | Accepted |
| [11](0011-backfill-from-the-community-profile.md) | Backfill games this machine never ran from the public profile, opt-in | Accepted |

## Rules

- Add a record for a durable choice: a data source, a boundary, a safety
  rule, or something OmaTrophy deliberately refuses to do.
- Never rewrite an accepted record. To change a decision, add a new record,
  set the old one's status to "Superseded by N" with a link to the new
  record, and link back from the new one.
- Write "(unverified)" for anything you cannot confirm from the code or the
  history.
