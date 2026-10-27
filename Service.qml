import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons as Commons

// Runs omatrophy.py, which prints one JSON line per new Steam unlock, and
// shows each as a card on the focused monitor. The window sits on the
// Overlay layer like Omarchy's own notifications, so it lands above
// fullscreen games, and its mask is empty, so it never takes a click or focus.
//
// Settings live in ~/.config/omatrophy/config.json and apply live:
//   {"position": "top-center" | "top-left" | "top-right", "sound": true,
//    "icons": "omarchy" | "vector" | "painted"}
Scope {
  id: root

  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("omatrophy.py")).replace(/^file:\/\//, ""))
  readonly property string sounds: "/usr/share/sounds/freedesktop/stereo/"
  // dev/preview.sh swaps in `omatrophy.py demo` to show cards without Steam.
  property var watchCommand: ["python3", helperPath, "watch"]

  property var queue: []
  property var current: null
  property string position: "top-center"
  property bool sound: true
  property string iconSet: "omarchy"

  function enqueue(ev) {
    if (ev.type !== "unlock" && ev.type !== "platinum") return
    queue = queue.concat([ev])
    if (!current) next()
  }

  function next() {
    if (!queue.length) { current = null; return }
    current = queue[0]
    queue = queue.slice(1)
    if (sound && current.type !== "platinum")
      chime.play(current.rare ? "bell.oga" : "message-new-instant.oga")
  }

  // The focused monitor when the card starts; it stays there while shown.
  function focusedScreen() {
    var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
    var screens = Quickshell.screens
    for (var i = 0; i < screens.length; i++)
      if (screens[i].name === name) return screens[i]
    return screens[0]
  }

  FileView {
    path: Quickshell.env("HOME") + "/.config/omatrophy/config.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var c = {}
      try { c = JSON.parse(text()) } catch (e) { return }
      if (["top-center", "top-left", "top-right"].indexOf(c.position) >= 0) root.position = c.position
      if (typeof c.sound === "boolean") root.sound = c.sound
      if (["omarchy", "vector", "painted"].indexOf(c.icons) >= 0) root.iconSet = c.icons
    }
  }

  Process {
    id: watcher
    command: root.watchCommand
    running: true
    stdout: SplitParser {
      onRead: line => {
        try { root.enqueue(JSON.parse(line)) } catch (e) { console.warn("omatrophy: bad line", line) }
      }
    }
    // Steam folder missing, a parse error: try again rather than go quiet.
    onExited: restart.start()
  }

  Timer {
    id: restart
    interval: 10000
    onTriggered: watcher.running = true
  }

  Process {
    id: chime
    function play(file) {
      command = ["pw-play", "--volume", "0.6", root.sounds + file]
      running = true
    }
  }

  LazyLoader {
    active: root.current !== null

    PanelWindow {
      id: win
      screen: root.focusedScreen()
      readonly property bool left: root.position === "top-left"
      readonly property bool right: root.position === "top-right"

      WlrLayershell.namespace: "omatrophy"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      // Normal with a zero zone: reserves nothing, but Hyprland places it
      // inside everyone else's reserved zones, so it lands below the bar and
      // any OmaReach edge instead of on top of them.
      exclusionMode: ExclusionMode.Normal
      exclusiveZone: 0
      color: "transparent"
      mask: Region {}

      anchors.top: true
      anchors.left: left
      anchors.right: right
      // A card may draw into a transparent `pad` around itself (the platinum
      // burst); the margins take it back so the card itself keeps its spot.
      readonly property int pad: card.item && card.item.pad ? card.item.pad : 0
      margins.top: Commons.Style.gapsOut * 2 - pad
      margins.left: Commons.Style.gapsOut * 2 - pad
      margins.right: Commons.Style.gapsOut * 2 - pad
      implicitWidth: card.item ? card.item.width : 1
      implicitHeight: card.item ? card.item.height : 1

      // Loaded by a fresh URL each time so edits to the card files show on
      // the next toast; the shell otherwise keeps its compiled copy until
      // `omarchy restart shell`, which games don't always survive.
      Loader {
        id: card
        readonly property bool platinum: root.current && root.current.type === "platinum"
        // Re-evaluated on every event, so each card starts fresh.
        source: root.current ? Qt.resolvedUrl(platinum ? "PlatinumCard.qml" : "TrophyToast.qml") + "?v=" + Date.now() : ""
        onLoaded: {
          item.edge = root.position
          item.iconSet = root.iconSet
          item.finished.connect(root.next)
          if (item.chime) item.chime.connect(() => { if (root.sound) chime.play("complete.oga") })
          item.event = root.current
        }
      }
    }
  }
}
