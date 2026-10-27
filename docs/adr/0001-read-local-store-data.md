# 1. Read the store's local data; need no account key

- Status: Accepted
- Date: 2026-10-26 (documented from the code)

## Context

Steam's Web API reports achievements only with a personal API key and a
public profile, and it lags behind the game. Steam's own unlock popup often
doesn't show over fullscreen Proton games, which is the problem OmaTrophy
exists to solve, so the data has to arrive within a second or two.

## Decision

The Steam store reads `<Steam>/appcache/stats/UserGameStats_<account>_<app>.bin`
and the matching schema file, parsing Steam's binary KeyValues itself. Steam
rewrites the user file on unlock. Network is used only for public, keyless
extras: global percentages, game names and art.

## Consequences

- No key, no login, private profiles work; a toast lands about 2 s after the
  unlock.
- The cache format is undocumented and can change with a Steam update; the
  parser and tests in `tests/` are where that breaks first.
- Other stores follow the same rule (ADR 7).
