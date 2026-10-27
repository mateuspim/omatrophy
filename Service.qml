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
//    "chimes": "omatrophy" | "classic", "icons": "omarchy" | "vector" | "painted"}
Scope {
  id: root

  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("omatrophy.py")).replace(/^file:\/\//, ""))
  readonly property string sounds: "/usr/share/sounds/freedesktop/stereo/"
  // The classic set: freedesktop sounds, before OmaTrophy had its own.
  readonly property var classic: ({ bronze: "message-new-instant.oga", silver: "message-new-instant.oga",
                                    gold: "bell.oga", platinum: "complete.oga" })
  // dev/preview.sh swaps in `omatrophy.py demo` to show cards without Steam.
  property var watchCommand: ["python3", helperPath, "watch"]

  property var queue: []
  property var current: null
  property string position: "top-center"
  property bool sound: true
  property string chimes: "omatrophy"
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
    // The platinum card asks for its chime when the trophy lands.
    if (current.type !== "platinum") chime.play(current.tier || "bronze")
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
      if (["omatrophy", "classic"].indexOf(c.chimes) >= 0) root.chimes = c.chimes
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
    // The watcher's own messages (a missing Steam folder, backfill
    // progress) go to the shell log. Read them even if nobody looks: an
    // unread pipe fills and would stall the watcher's background thread.
    // console.warn because the shell's log file drops QML info lines.
    stderr: SplitParser {
      onRead: line => console.warn(line)
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
    // One sound per tier: assets/sounds/<tier>.wav, or the classic set.
    function play(tier) {
      if (!root.sound) return
      var file = root.chimes === "classic" ? root.sounds + (root.classic[tier] || root.classic.bronze)
                 : decodeURIComponent(String(Qt.resolvedUrl("assets/sounds/" + tier + ".wav")).replace(/^file:\/\//, ""))
      command = ["pw-play", "--volume", "0.6", file]
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

      // Built from the card file's current text for every event
      // (FreshObject.qml), so edits show on the next toast; the shell
      // otherwise keeps its startup copy until `omarchy restart shell`,
      // which games don't always survive.
      FreshObject {
        id: card
        width: item ? item.width : 0
        height: item ? item.height : 0

        function show() {
          if (!root.current) return
          var item = load(root.current.type === "platinum" ? "PlatinumCard.qml" : "TrophyToast.qml")
          // A card that doesn't build would stall the queue; skip to the next.
          if (!item) { Qt.callLater(root.next); return }
          item.edge = root.position
          item.iconSet = root.iconSet
          item.finished.connect(root.next)
          if (item.chime) item.chime.connect(() => chime.play("platinum"))
          item.event = root.current
        }

        Component.onCompleted: show()
        Connections {
          target: root
          function onCurrentChanged() { card.show() }
        }
      }
    }
  }
}
