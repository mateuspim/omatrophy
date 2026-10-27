# 4. Skip unlocks older than 15 minutes

- Status: Accepted
- Date: 2026-10-26 (documented from the code)

## Context

Steam rewrites a game's stats file on first launch, on a new machine, or
after syncing progress made elsewhere. Diffing alone would toast every past
achievement at once.

## Decision

The watcher records a baseline at start, and a newly unlocked achievement
becomes an event only if its unlock time is within `FRESH_SECONDS` (15 min)
or unknown. A platinum fires only when a fresh unlock completed the game.

## Consequences

- No toast storms after a sync.
- A game that writes its stats more than 15 minutes late loses its toasts.
