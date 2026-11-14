# 22. Hold cards while Omarchy's Do Not Disturb is on

- Status: Accepted
- Date: 2026-11-14

## Context

Omarchy's bar has a Do Not Disturb toggle (the bell; also
`omarchy-toggle-notification-silencing`). It silences desktop
notifications, but OmaTrophy's cards are its own Overlay-layer window
([ADR 2](0002-overlay-layer-click-through.md)), not notifications, so they
kept showing. Someone who silenced the desktop for a meeting, a recording
or a stream still got a trophy, its chime and a platinum burst.

Omarchy 4's notification service (`shell/plugins/notifications/Service.qml`)
holds the state as `doNotDisturb`. The shell hands that service to other
plugins only through `firstPartyServiceFor`, and only to `bar` plugins
(`shell.qml`, `pluginHasBarCapabilities`); OmaTrophy is a `service`,
`bar-widget` and `overlay`. The service also answers
`omarchy-shell notifications isDnd` over IPC, which would need polling,
and saves the state to `~/.local/state/omarchy/notifications/quiet.json`
(`{"dnd": true}`, written atomically within 250 ms of a change; empty
before the first toggle).

## Decision

`Service.qml` watches `quiet.json` with a `FileView` (`watchChanges`
follows an atomic replace, a removal and a new file; checked in a
throwaway Quickshell). `dnd` is on only for `{"dnd": true}`; empty,
missing or unreadable reads as off.

A setting, `dnd`, picks what happens while it is on:

- `hold` (default): cards wait in the queue, in their usual order and
  ranks, under the same queue rule (ordinary cards are dropped when 20
  cards are pending; reminders and recaps are never dropped), and show,
  with their chimes, when Do Not Disturb ends. A card already showing
  finishes normally if Do Not Disturb turns on.
- `ignore`: cards show as before.

A card queued by `omatrophy.py test` (Settings' **Try**, the TRY IT tiles)
carries `"test": true` and shows even while held, bypassing the queue cap
like a kept card: a Try that shows nothing looks broken. It waits for any
current card to finish. `dev/preview.sh` sets `followsDnd: false`, so a throwaway
shell shows its cards whatever the live shell's state.

We considered dropping held cards to a count ("3 trophies while you were
away"). The session recap already sums up a session when the game stops,
and a held card loses nothing by waiting, so holding keeps each trophy's
own moment.

## Consequences

- `quiet.json` is Omarchy's private file, not a plugin contract. If its
  path or shape changes, OmaTrophy reads Do Not Disturb as off and shows
  cards as before; nothing breaks louder than that. Recheck it when
  Omarchy's notification service changes.
- With Do Not Disturb left on for hours, ordinary cards stop joining once
  20 cards wait, as in any burst. Kept cards and explicit tests can grow
  the queue beyond 20. This queue lives only in the shell's memory; a
  shell exit discards it.
- Changing `Service.qml` needs one `omarchy restart shell`.
