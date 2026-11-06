# 16. The in-game guide is the tracker's Guide tab on a key

- Status: Accepted; how the key is bound superseded by [ADR 18](0018-bind-the-guide-key-at-runtime.md)
- Date: 2026-11-06

## Context

The owner wants a guide over the game they're playing, the way the Steam
overlay opens on Shift+Tab: one key while the game runs, the game's guide
(or Make guide when there is none), the walkthrough, and the same key to
put it away.

The tracker (ADR 9) already is that surface. It opens on the Overlay
layer, above fullscreen games; with an empty payload it shows the game
running now; `{"view": "guide"}` opens it on the Guide tab, which has
Make guide when the game has no guide. The shell's
`omarchy-shell shell toggle <id> <payload>` summons a closed overlay with
the payload and hides an open one.

## Decision

The in-game guide is the tracker summoned on the Guide tab by a
Hyprland bind the owner adds:

```
omarchy-shell shell toggle pym.omatrophy '{"view":"guide"}'
```

No new window, entry point or IPC target. The tracker keeps its
exclusive keyboard focus while open: the guide is read with the keyboard
(Tab, arrows, Enter, Shift+Enter), and a passive panel over a game that
grabs the mouse could not be scrolled at all. Hyprland handles binds
before the focused surface, so the same key closes it; so do Escape and a
click on the scrim.

OmaTrophy doesn't add the bind itself: the owner's Hyprland config is
theirs (AGENTS.md: never modify user config). The README and Settings >
Guides show the line to copy. Shift+Tab is not suggested: a global bind on
it would take Shift+Tab from every app and game.

## Consequences

- Nothing to restart: the payload and the toggle exist in Omarchy 4.0's
  shell and in `TrackerView.qml`.
- The game keeps running under the overlay and loses keyboard input while
  the guide is open, like the Steam overlay. A game that pauses on focus
  loss pauses.
- A walkthrough (ADR 17) shows in the same Guide tab, so it comes with the
  key at no extra cost.
