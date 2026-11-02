#!/usr/bin/env bash
# Regression check for per-monitor IPC ownership, without loading the live shell.
# Needs two connected monitors. Both throwaway windows close automatically.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
[[ $repo != *[\"\\]* && $repo != *$'\n'* ]] || { echo "unsupported checkout path" >&2; exit 2; }
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
ln -s /usr/share/omarchy/shell/Commons "$dir/Commons"
ln -s /usr/share/omarchy/shell/Ui "$dir/Ui"
cat > "$dir/shell.qml" <<QML
import QtQuick
import Quickshell
import "file://$repo" as Trophy
ShellRoot {
  PanelWindow {
    id: firstWindow
    screen: Quickshell.screens[0]
    implicitWidth: 1
    implicitHeight: 1
    exclusionMode: ExclusionMode.Ignore
    Trophy.Panel { id: first }
  }
  PanelWindow {
    id: secondWindow
    screen: Quickshell.screens[1] || Quickshell.screens[0]
    implicitWidth: 1
    implicitHeight: 1
    exclusionMode: ExclusionMode.Ignore
    Trophy.Panel { id: second }
  }
  Timer {
    interval: 400
    running: true
    onTriggered: {
      if (Quickshell.screens.length < 2) {
        console.log("IPC SKIP: connect two monitors")
        Qt.quit()
        return
      }
      if (!first.manageIpc || second.manageIpc) {
        console.log("IPC FAIL: initial ownership")
        Qt.quit()
        return
      }
      firstWindow.screen = Quickshell.screens[1]
      secondWindow.screen = Quickshell.screens[0]
      verifyMoved.start()
    }
  }
  Timer {
    id: verifyMoved
    interval: 400
    onTriggered: {
      console.log(!first.manageIpc && second.manageIpc ? "IPC PASS" : "IPC FAIL: screen reassignment")
      Qt.quit()
    }
  }
}
QML
timeout 8 quickshell -p "$dir" >"$dir/log" 2>&1 || { cat "$dir/log"; exit 1; }
cat "$dir/log"
# A second registration was the original bug, even if the final owner is right.
if grep -q 'another handler is registered for target pym.omatrophy' "$dir/log"; then exit 1; fi
grep -q 'IPC PASS' "$dir/log"
