# 10. Build live-edited views from their text

- Status: Accepted
- Date: 2026-10-27
- Supersedes [5](0005-cards-load-by-fresh-url.md)

## Context

ADR 5 loaded the cards and the panel content with `?v=<timestamp>` appended
so each load compiled the file afresh. Omarchy's Quickshell build (the
`OmarchyLoadPatch` pragma in the shell's `shell.qml`) serves plugin files as
`qs://` URLs from a cache filled on first load and ignores the query, so
every load got the copy from shell start: edits showed only after
`omarchy restart shell`. Reproduced in a throwaway Quickshell with the same
pragma. A `file://` URL does reload, but makes Quickshell watch the file and
reload the whole shell when it changes, which ADR 8 rules out.

## Decision

`FreshObject.qml` reads a sibling file's text with `FileView` and builds it
with `Qt.createQmlObject`, under a sibling URL that is never a file
(`<name>.live.qml`) so the engine compiles that text rather than reuse a
cached type. `Service.qml` uses it per toast, `Panel.qml` per open of the
panel, `Tracker.qml` per open of the tracker. The built files stay
standalone (no sibling QML types), as ADR 5 required; tests still enforce it.

## Consequences

- Edits to `TrophyToast.qml`, `PlatinumCard.qml`, `StylePicker.qml` and
  `TrackerView.qml` show on the next toast or open, with no restart and no
  file watch.
- A file that fails to compile logs `omatrophy: <name> failed to build` and
  shows nothing; for toasts the queue moves on.
- Compile errors name `<name>.live.qml`, not the real file.
- `FreshObject.qml` itself, like the entry points, needs a restart.
