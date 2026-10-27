# 6. A Python watcher speaks JSON lines to the shell

- Status: Accepted
- Date: 2026-10-26 (documented from the code)

## Context

Parsing binary caches, HTTP and file caching are awkward in QML, and the
shell should stay responsive whatever a store does.

## Decision

`omatrophy.py watch` is a long-running child of `Service.qml` that polls
once a second and prints one JSON object per line. The shell parses lines,
ignores unknown types and restarts the process 10 s after it exits. Test
events reach the same pipe through an inbox file, so `omatrophy.py test`
exercises the real path.

## Consequences

- Stores, diffing and tiers can be tested with plain `unittest`.
- The event shapes are a contract (`docs/specs/events.md`).
- Standard-library Python only, so the system `python3` is enough.
