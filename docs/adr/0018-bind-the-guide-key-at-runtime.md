# 18. Bind the Guide key at runtime, once the owner installs it

- Status: Accepted
- Date: 2026-11-06
- Supersedes the bind part of [ADR 16](0016-in-game-guide-is-the-tracker-on-a-key.md)

## Context

ADR 16 left the in-game guide's key to a bind the owner pastes into
`bindings.lua`. The owner asked for a default key they can change when
it's taken, and for nothing to be bound until they say so. OmaMosaic's
Swap key (its ADR 14) binds a setting at runtime with `hyprctl eval`, as
Omarchy has no plugin key-binding API.

A first try put the key in the manifest's bar-widget `schema`, like
OmaMosaic. Omarchy 4's shell keeps that schema but draws no page for it,
so the owner could not change the key, and the default was bound unasked.

## Decision

The key lives in `config.json` as `guide-key`, `""` (nothing bound) until
the owner installs one in **Settings > Guides**:

- With the default (`SUPER + CTRL + G`) free, **Install Super+Ctrl+G**.
- With it taken, a warning names the bind that has it, and **Pick a key**
  opens a field; **Install** checks the typed key first
  (`omatrophy.py guide-key check <key>`) and says what holds it, if
  anything.
- Installed, the key shows with **Change** and **Remove**.

`Service.qml` reads `guide-key` and runs `omatrophy.py guide-key <key>`
after a change, at start and on Hyprland's `configreloaded` (a reload
drops runtime binds). `guide_key.py`:

- parses the key (modifier names and a plain key only: it goes into Lua);
- reads `hyprctl -j binds`, unbinds ours (found by its description) from
  any other key, and refuses a key another bind uses, saying which;
- binds `omarchy-shell shell toggle pym.omatrophy '{"view":"guide"}'` with
  `hl.bind`, reusing a bind it left before a shell restart;
- writes `{key, bound, error}` to `~/.local/state/omatrophy/guide-key.json`
  for Settings > Guides, and the service sends an error as a notification.

The service unbinds ours when it goes away.

## Consequences

- Nothing is bound unasked, nothing is written to the owner's Hyprland
  config, and the key never takes one in use.
- Python, so the tests cover the parsing, conflicts and Lua.
- Test shells (`dev/preview.sh`) set `bindsGuideKey: false`, or they would
  bind the key and, on closing, unbind the live shell's.
