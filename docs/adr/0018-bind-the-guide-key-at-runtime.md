# 18. Bind the Guide key at runtime from a plugin setting

- Status: Accepted
- Date: 2026-11-06
- Supersedes the bind part of [ADR 16](0016-in-game-guide-is-the-tracker-on-a-key.md)

## Context

ADR 16 left the in-game guide's key to a bind the owner pastes into
`bindings.lua`. The owner asked for it the way their other plugins do it:
a setting on Omarchy's plugin settings page with a default key, changed
there when the key is taken. OmaMosaic's Swap key (its ADR 14) does this:
Omarchy has no plugin key-binding API, so the service binds the setting at
runtime with `hyprctl eval`.

## Decision

`manifest.json` declares `guideKey` (default `SUPER + CTRL + G`) in the
bar widget's schema. `Panel.qml` hands it to `Service.qml`, which runs
`omatrophy.py guide-key <key>` after a change, at start and on Hyprland's
`configreloaded` (a reload drops runtime binds). `guide_key.py`:

- parses the key (modifier names and a plain key only: it goes into Lua);
- reads `hyprctl -j binds`, unbinds ours (found by its description) from
  any other key, and refuses a key another bind uses, saying which;
- binds `omarchy-shell shell toggle pym.omatrophy '{"view":"guide"}'` with
  `hl.bind`, reusing a bind it left before a shell restart;
- writes `{key, bound, error}` to `~/.local/state/omatrophy/guide-key.json`
  for Settings > Guides, and the service sends an error as a notification.

An empty setting binds nothing, for an owner who keeps the bind in their
own config. The service unbinds ours when it goes away.

## Consequences

- Still nothing written to the owner's config, and the key never takes one
  in use.
- Python, so the tests cover the parsing, conflicts and Lua.
- Test shells (`dev/preview.sh`) set `bindsGuideKey: false`, or they would
  bind the key and, on closing, unbind the live shell's.
- The setting needs the bar widget placed: without it no Panel hands the
  key over and the default is bound from the service alone.
