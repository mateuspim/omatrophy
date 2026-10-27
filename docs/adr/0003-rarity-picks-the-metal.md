# 3. Rarity picks the metal; 100% is platinum

- Status: Accepted
- Date: 2026-10-26 (documented from the code)

## Context

Steam has no trophy grades, but the PlayStation idea of bronze, silver,
gold and platinum is what makes an unlock feel earned.

## Decision

`omatrophy.tier`: above 35% of players (or unknown) is bronze, above 10%
silver, 10% or fewer gold (`RARE_PERCENT`). Gold also gets the accent
border, glitter and a sweep of light, and a different chime. When an unlock
completes a game, a separate `platinum` event follows it and plays the
platinum card.

## Consequences

- Tiers depend on a network call; offline unlocks are bronze.
- The thresholds are tuning, not a contract; change them here and in
  `docs/specs/events.md`.
