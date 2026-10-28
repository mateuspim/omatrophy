#!/usr/bin/env bash
# Show OmaTrophy cards from a throwaway Quickshell instance, without touching
# the running Omarchy shell (restarting it can upset a running game).
#
#   dev/preview.sh                 unlock, rare, then platinum
#   dev/preview.sh platinum        just the platinum card
#   dev/preview.sh -t 30 rare      stop after 30 seconds (default 25)
#   dev/preview.sh --picker        the bar panel's style picker in a window
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
secs=25
if [[ ${1:-} == -t ]]; then secs=$2; shift 2; fi
picker=false
if [[ ${1:-} == --picker ]]; then picker=true; shift; fi
kinds=("$@")
[[ ${#kinds[@]} -gt 0 ]] || kinds=(unlock rare platinum)
# Arguments and paths are pasted into QML below, so only let through what
# can't end a QML string or add code to it.
[[ $secs =~ ^[0-9]+$ ]] || { echo "-t takes whole seconds, not '$secs'" >&2; exit 2; }
for kind in "${kinds[@]}"; do
  [[ $kind =~ ^(unlock|rare|bronze|silver|gold|platinum)$ ]] ||
    { echo "unknown card: $kind (unlock, rare, bronze, silver, gold or platinum)" >&2; exit 2; }
done
theme=$HOME/.local/state/omarchy/current/theme
for path in "$repo" "$theme"; do
  [[ $path != *[\"\\]* && $path != *$'\n'* ]] ||
    { echo "can't preview from a path with a quote, backslash or newline: $path" >&2; exit 2; }
done

dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
# The cards import qs.Commons for theme colors, which resolves against the
# config root, so link the shell's Commons in beside our entry point.
ln -s /usr/share/omarchy/shell/Commons "$dir/Commons"
ln -s /usr/share/omarchy/shell/Ui "$dir/Ui"
args=$(printf '"%s", ' "${kinds[@]}")
cat > "$dir/shell.qml" <<QML
import Quickshell
import Quickshell.Io
import qs.Commons as Commons
import "file:$repo" as Trophy

ShellRoot {
  // The real shell loads the current theme into Commons.Color at startup
  // (shell.qml, applyTheme); do the same so the preview shows true colors.
  FileView { path: "$theme/colors.toml"; onLoaded: Commons.Color.loadColors(text()) }
  FileView { path: "$theme/shell.toml"; printErrors: false; onLoaded: Commons.Color.loadShell(text()) }
$(if $picker; then cat <<PICK
  FloatingWindow {
    title: "omatrophy-picker"
    implicitWidth: 420
    implicitHeight: 700
    color: Commons.Color.background
    Trophy.StylePicker { x: 16; y: 16; width: 388 }
  }
PICK
else cat <<SERVICE
  Trophy.Service {
    watchCommand: ["python3", "$repo/omatrophy.py", "demo", ${args%, }]
  }
SERVICE
fi)
}
QML
timeout "$secs" quickshell -p "$dir" >"$dir/log" 2>&1 || true
grep -iE "error|warn" "$dir/log" | grep -v qmlscanner | sort -u | head -20 || true
