# 8. Develop without restarting the live shell

- Status: Accepted
- Date: 2026-10-26 (documented from the code)

## Context

OmaTrophy is used while games run, and a shell restart under a running game
can disturb it.

## Decision

`dev/preview.sh` runs a throwaway Quickshell instance with the theme's
colours and `omatrophy.py demo` events, and never touches the live shell.
Cards reload by fresh URL (ADR 5). Agents check `pgrep -f SteamLaunch` and
ask before `omarchy restart shell`.

## Consequences

- Most visual work needs no restart; `Service.qml`, `Panel.qml` and the
  manifest still do.
