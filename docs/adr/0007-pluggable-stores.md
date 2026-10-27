# 7. Stores are pluggable; the watcher stays generic

- Status: Accepted
- Date: 2026-10-26 (documented from the code)

## Context

Steam is the first store, but Epic, GOG, Battle.net and others run on the
same desktops. Threading a second launcher through Steam-shaped code would
make each new one harder.

## Decision

A store is a `stores.base.Store` subclass listed in `stores.STORES`: it
reports availability, games with a change token, achievements, name,
rarity and art, as plain dicts. `omatrophy.py` keeps the diffing,
freshness, tiers, events, inbox and settings, and watches every available
store. Events carry the store id; seen sets and icon caches are keyed by it.
Stores follow ADR 1: local data, no account keys.

## Consequences

- A new store is one module plus its tests (`docs/guide/stores.md`).
- Stores without rarity data produce only bronze until they find one.
