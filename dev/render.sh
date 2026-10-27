#!/usr/bin/env bash
# Render one OmaTrophy view to a PNG offscreen, from a throwaway Quickshell
# instance: no window shows and the live shell is never touched.
#
#   dev/render.sh now out.png            the bar panel's Now tab, mid-game
#   dev/render.sh idle out.png           the Now tab with nothing running
#   dev/render.sh games out.png          the Games tab
#   dev/render.sh loading out.png        the Now tab's skeleton, before data
#   dev/render.sh tracker-loading out.png
#   dev/render.sh settings out.png       its Settings tab
#   dev/render.sh tracker out.png        the achievement tracker
#   dev/render.sh gold out.png           a toast: bronze, silver, gold, platinum
#   dev/render.sh --live tracker out.png the views read your real stores
#
# Sample data is fake (dev/samples/) so captures are safe for the README;
# --live output shows your own games and stays out of git. The software
# renderer drops MultiEffect layers, so the omarchy set's accent inlay is
# missing here; check it with dev/preview.sh.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
live=false
if [[ ${1:-} == --live ]]; then live=true; shift; fi
[[ $# -eq 2 ]] || { sed -n '5,14p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
target=$1
out=$(realpath -m "$2")

dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT
ln -s /usr/share/omarchy/shell/Commons "$dir/Commons"
ln -s /usr/share/omarchy/shell/Ui "$dir/Ui"
theme=$HOME/.local/state/omarchy/current/theme

case $target in
  now|idle|settings|games|loading)
    w=460 h=900 at=2500
    tab=now; [[ $target == settings || $target == games ]] && tab=$target
    data=now.json; [[ $target == idle ]] && data=idle.json; [[ $target == games ]] && data=games.json
    feed="item.cabinet = JSON.parse(sample.text())"
    [[ $target == games ]] && feed="item.games = JSON.parse(sample.text())"
    [[ $target == loading ]] && feed=""
    view="Loader {
        x: 20; y: 20; width: 420
        source: \"file:$repo/StylePicker.qml\"
        onLoaded: {
          item.width = 420
          item.live = $live
          if (!$live) { $feed }
          item.tab = \"$tab\"
        }
      }" ;;
  tracker|tracker-loading)
    w=1000 h=900 at=3000
    [[ $target == tracker-loading ]] && live=skeleton
    view="Loader {
        anchors.centerIn: parent
        source: \"file:$repo/TrackerView.qml\"
        onLoaded: {
          item.maxWidth = 960; item.maxHeight = 860
          if (\"$live\" === \"true\") item.load({})
          else if (\"$live\" === \"false\") item.game = JSON.parse(sample.text())
        }
      }"
    data=game.json ;;
  bronze|silver|gold|platinum)
    # The platinum card takes about six seconds to open fully.
    w=1000 h=$([[ $target == platinum ]] && echo 400 || echo 260) at=$([[ $target == platinum ]] && echo 6500 || echo 3500)
    card=$([[ $target == platinum ]] && echo PlatinumCard || echo TrophyToast)
    view="Loader {
        anchors.horizontalCenter: parent.horizontalCenter
        source: \"file:$repo/$card.qml\"
        onLoaded: item.event = JSON.parse(sample.text())[\"$target\"]
      }"
    data=events.json ;;
  *) echo "unknown view: $target" >&2; exit 2 ;;
esac

cat > "$dir/shell.qml" <<QML
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons

ShellRoot {
  // The real shell loads the current theme into Commons.Color at startup.
  FileView { path: "$theme/colors.toml"; blockLoading: true; onLoaded: Commons.Color.loadColors(text()) }
  FileView { path: "$theme/shell.toml"; blockLoading: true; printErrors: false; onLoaded: Commons.Color.loadShell(text()) }
  FileView { id: sample; path: "$repo/dev/samples/$data"; blockLoading: true }
  FloatingWindow {
    implicitWidth: $w
    implicitHeight: $h
    color: Commons.Color.popups.background
    Item {
      id: frame
      anchors.fill: parent
      Rectangle { anchors.fill: parent; color: Commons.Color.popups.background }
      $view
    }
    Timer {
      interval: $at
      running: true
      onTriggered: frame.grabToImage(function(r) { r.saveToFile("$out"); Qt.quit() })
    }
  }
}
QML
QT_QPA_PLATFORM=offscreen timeout 30 quickshell -p "$dir" >"$dir/log" 2>&1 || true
grep -iE "error|warn" "$dir/log" | grep -v qmlscanner | sort -u | head -20 || true
[[ -f $out ]] && echo "$out" || { echo "no image; log:" >&2; tail -20 "$dir/log" >&2; exit 1; }
