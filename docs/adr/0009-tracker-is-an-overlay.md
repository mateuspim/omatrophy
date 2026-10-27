# 9. The achievement tracker is the plugin's overlay entry point

- Status: Accepted
- Date: 2026-10-27

## Context

A game's full achievement list (often 50 to 100 rows, with search and
filters) doesn't fit the bar panel, which is a narrow popup sized to its
content. Omarchy's shell already hosts full-screen, keyboard-driven surfaces
as `overlay` plugins (the image picker, emojis): it mounts them on
`shell.summon(id, payload)`, calls `open(payload)` and `close()`, and gives
them `shell.hide()` to dismiss themselves.

## Decision

`manifest.json` adds the `overlay` kind with `Tracker.qml` as its entry
point. The panel's game rows emit `track(store, app)`; `Panel.qml` closes the
panel and calls `bar.shell.summon("pym.omatrophy", {store, app})`.
`Tracker.qml` owns only the window (Overlay layer, exclusive keyboard focus
while open, a scrim that closes on click) and loads `TrackerView.qml` by a
fresh URL (ADR 5, now ADR 10), which runs `omatrophy.py game` for its data. The tracker
is read-only.

## Consequences

- Scripts and keybindings can open the tracker:
  `omarchy-shell shell summon pym.omatrophy '{}'`.
- With an overlay kind, the shell routes `summon pym.omatrophy` to the
  tracker, not the bar panel (the shell treats a plugin with both kinds like
  `omarchy.menu`). The panel still opens from its button and from its own
  IPC target (`omarchy-shell pym.omatrophy toggle`).
- Adding the entry point needs one `omarchy restart shell`; edits to
  `TrackerView.qml` after that need none.
- Marking achievements done by hand, or notes, would make the tracker write
  state; that is a separate decision if it comes.
