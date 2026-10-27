# 2. Show cards on the Overlay layer, click-through and unfocusable

- Status: Accepted
- Date: 2026-10-26 (documented from the code)

## Context

Toasts must appear over fullscreen games without stealing input or focus:
a stolen click or keypress mid-fight is worse than no toast.

## Decision

`Service.qml` shows each card in a `PanelWindow` on `WlrLayer.Overlay`
(namespace `omatrophy`), like Omarchy's notifications, with
`keyboardFocus: None` and an empty input mask (`mask: Region {}`). It
reserves no space (`exclusiveZone: 0`) but uses `ExclusionMode.Normal` so
it sits below the bar and other reserved edges. The window goes to the
monitor focused when the card starts and stays there.

## Consequences

- Cards can't be clicked or dismissed; they leave on their own.
- One card at a time; events queue.
