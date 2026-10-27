# 5. Load cards by a fresh URL; keep them standalone

- Status: Accepted
- Date: 2026-10-26 (documented from the code)

## Context

The shell caches compiled QML until `omarchy restart shell`, and restarting
the shell can upset a running game, so iterating on the cards would need a
restart per edit.

## Decision

`Service.qml` loads `TrophyToast.qml` or `PlatinumCard.qml` with
`?v=<timestamp>` appended, and `Panel.qml` does the same for
`StylePicker.qml`. Types from the same folder don't resolve in such loads,
so the cards use no sibling QML file: the `Trophy` component is repeated
in both cards. They import `qs.Commons as Commons` and always write
`Commons.Color`, because a bare `Color` resolves to QtQuick's own type
(Qt 6.12). Tests enforce both.

## Consequences

- Card edits show on the next toast; no restart.
- Shared card code is duplicated; keep the two `Trophy` copies in step.
