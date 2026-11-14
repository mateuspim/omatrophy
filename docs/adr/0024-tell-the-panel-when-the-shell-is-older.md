# 24. Tell the panel when the shell runs an older OmaTrophy

- Status: Accepted
- Date: 2026-11-14

## Context

Omarchy's Quickshell caches plugin files: `Service.qml` and the watcher it
starts keep the code they started with until `omarchy restart shell`. The
cards, the panel and the tracker are built fresh from their text
([ADR 10](0010-build-views-from-their-text.md)), and restarting the shell
mid-game can upset the game ([ADR 8](0008-never-restart-the-shell-mid-game.md)),
so after an update the two halves can be different versions for hours.

On 2026-11-14 the owner updated from 0.8.1 while a game ran. Settings >
Toasts, built fresh, offered Try for the missable, recap and milestone
cards; `omatrophy.py test` queued them in the inbox, and the 0.8.1 watcher
dropped every type it didn't know. Try did nothing, with no word why.

## Decision

The watcher records what it is in `~/.local/state/omatrophy/watcher.json`
when it starts: its pid, its version, the version of the `Service.qml`
that started it (passed as `watch --shell <version>`; `Service.qml` reads
its own `manifest.json` once at startup), its parent process and the card
types its inbox lets through. `omatrophy.py running` compares that with the
installed `manifest.json`:

- the same version: nothing to say;
- another version, or a running watcher with no record (older than
  1.0.0): stale, with the cards that watcher shows (for an unrecorded one,
  those every watcher since 0.8.0 shows);
- a watcher started from a terminal has no `Service.qml` of its own and
  counts by its version only.

Settings > Toasts reads it each time Settings opens and, when stale, shows a
banner ("Restart the shell to use the new cards", with both versions and
"when no game is running") and replaces Try with "Try after restart" for
the cards the running watcher lacks. `omatrophy.py test` says the same on
stderr. Nothing restarts the shell by itself.

## Consequences

- An update shows why a new card can't be tried yet, instead of a Try that
  silently does nothing.
- The check is by version: two commits with the same `manifest.json`
  version look the same. Releases bump it; a developer on a linked
  checkout knows to restart.
- The watcher writes one more small file; `running` scans `/proc` for
  `omatrophy.py watch` processes only when the record is missing or dead.
- The `ready` event gains `version` ([events](../specs/events.md#ready)), for
  logs; the shell doesn't need it.
