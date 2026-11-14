import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import qs.Commons as Commons

// Runs omatrophy.py, which prints one JSON line per new Steam unlock (and
// reminders when a game starts), and shows each as a card (cards.json) on the
// focused monitor, or the one named in `screen`. While Omarchy's Do Not
// Disturb is on, cards wait and show when it ends (`dnd`). The window sits on the
// Overlay layer like Omarchy's own notifications, so it lands above
// fullscreen games, and its mask is empty, so it never takes a click or focus.
//
// Settings live in ~/.config/omatrophy/config.json and apply live:
//   {"position": "top-center" | "top-left" | "top-right", "sound": true,
//    "chimes": "omatrophy" | "classic", "icons": "omarchy" | "vector" | "painted",
//    "glass": "clear" | "frosted" | "solid", "screen": "focused" | <monitor>,
//    "dnd": "hold" | "ignore"}
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
  property string glass: "frosted"
  // "focused", or a monitor's name (DP-1): a monitor that isn't connected
  // falls back to the focused one.
  property string screenName: "focused"
  // "hold": cards wait while Do Not Disturb is on; "ignore": they show anyway.
  property string dndMode: "hold"
  // Omarchy's Do Not Disturb, from its notification service's quiet.json.
  property bool dnd: false
  // dev/preview.sh turns it off: a throwaway shell shows its cards whatever
  // the live shell's Do Not Disturb says.
  property bool followsDnd: true
  property string quietPath: Quickshell.env("HOME") + "/.local/state/omarchy/notifications/quiet.json"
  readonly property bool holding: followsDnd && dndMode === "hold" && dnd
  // Do Not Disturb ended (or `dnd` went to ignore): what waited shows now.
  onHoldingChanged: if (!holding && !current) next()

  readonly property var tiers: ["bronze", "silver", "gold", "platinum"]

  // Every card the shell shows, from cards.json (omatrophy.py reads the
  // same table for what the test inbox lets through): type -> { file, the
  // QML built for it; chime, play the tier's chime as it shows; rank, go
  // ahead of queued cards of a lower rank (a launch reminder is about the
  // save being made now); keep, never dropped from a full queue }. Read
  // from its current text, so a new card needs a QML file and a row there,
  // no restart. Until it reads, the toast and the platinum card work.
  property var cards: ({ unlock: { file: "TrophyToast.qml", chime: true }, platinum: { file: "PlatinumCard.qml" } })

  FileView {
    path: decodeURIComponent(String(Qt.resolvedUrl("cards.json")).replace(/^(qs|file):\/\//, ""))
    // It still loads after the component completes (checked offscreen), but
    // long before the watcher's first card: the watcher reads every store
    // before it prints `ready`, and a launch reminder waits a poll on top.
    blockLoading: true
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try {
        var table = JSON.parse(text())
        if (table && typeof table === "object" && !Array.isArray(table)) root.cards = table
      } catch (e) { console.warn("omatrophy: cards.json does not parse:", e) }
    }
  }

  function cardOf(ev) {
    var card = ev && Object.prototype.hasOwnProperty.call(cards, ev.type) ? cards[ev.type] : null
    return card && typeof card.file === "string" ? card : null
  }

  function rankOf(ev) {
    var card = cardOf(ev)
    return card && typeof card.rank === "number" ? card.rank : 0
  }

  function enqueue(ev) {
    var card = cardOf(ev)
    if (!card) return
    // `tier` names the chime file; anything else falls back to bronze.
    if (tiers.indexOf(ev.tier) < 0) ev.tier = "bronze"
    // A burst (a backfilled library, a flood in the inbox) shows the first
    // few cards, not a queue that runs for an hour. A card kept (a launch
    // reminder: shown once, the watcher records it as sent) is never
    // dropped.
    if (!card.keep && queue.length >= 20) return
    // A ranked card goes ahead of every queued card of a lower rank and
    // after those of its own: the difficulty reminder first, then the
    // missable one, then toasts in the order they came.
    var rank = rankOf(ev)
    var at = queue.length
    if (rank > 0) {
      at = 0
      while (at < queue.length && rankOf(queue[at]) >= rank) at++
    }
    queue = queue.slice(0, at).concat([ev], queue.slice(at))
    if (!current) next()
  }

  function next() {
    // While held, only a card asked for (`test`: Settings' Try, `omatrophy.py
    // test`) shows; Try showing nothing would look broken. The rest wait in
    // order, ranks kept, the same 20-card limit applying.
    var at = 0
    if (holding) {
      at = -1
      for (var i = 0; i < queue.length && at < 0; i++)
        if (queue[i].test === true) at = i
    }
    if (!queue.length || at < 0) { current = null; return }
    current = queue[at]
    queue = queue.slice(0, at).concat(queue.slice(at + 1))
    // The platinum card asks for its chime when the trophy lands; a
    // reminder is no unlock, so it comes silent.
    var card = cardOf(current)
    if (card && card.chime) chime.play(current.tier || "bronze")
  }

  // The monitor named in `screen` when it is connected, else the focused one.
  function toastScreen() {
    var screens = Quickshell.screens
    if (screenName !== "focused")
      for (var i = 0; i < screens.length; i++)
        if (screens[i].name === screenName) return screens[i]
    return focusedScreen()
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
      if (["clear", "frosted", "solid"].indexOf(c.glass) >= 0) root.glass = c.glass
      root.guideKey = typeof c["guide-key"] === "string" ? c["guide-key"] : ""
      // Not kept as the last good value like the rest: a monitor removed
      // from the setting must go back to the focused one.
      root.screenName = typeof c.screen === "string" && c.screen !== "" ? c.screen : "focused"
      root.dndMode = c.dnd === "ignore" ? "ignore" : "hold"
    }
  }

  // Do Not Disturb (ADR 22): Omarchy's notification service keeps it in quiet.json
  // ({"dnd": true}, written within a quarter second of the bar's toggle or
  // omarchy-toggle-notification-silencing). A third-party plugin can't reach
  // the service itself (the shell hands it only to `bar` plugins), so read
  // the file; it is replaced atomically, which FileView follows. Empty,
  // missing or unreadable: notifications aren't silenced.
  FileView {
    path: root.followsDnd ? root.quietPath : ""
    // Read before the first card: a held card must not slip out first.
    blockLoading: true
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: root.dnd = root.quietOn(text())
    onLoadFailed: root.dnd = false
  }

  function quietOn(text) {
    try {
      var quiet = JSON.parse(text)
      return !!quiet && quiet.dnd === true
    } catch (e) { return false }
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
      if (root.tiers.indexOf(tier) < 0) tier = "bronze"
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
      screen: root.toastScreen()
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
          var kind = root.cardOf(root.current)
          var item = kind ? load(kind.file) : null
          // A card that doesn't build would stall the queue; skip to the next.
          if (!item) { Qt.callLater(root.next); return }
          item.edge = root.position
          item.iconSet = root.iconSet
          // Only the toast is glass; the platinum card keeps its own look.
          if ("glass" in item) item.glass = root.glass
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

  // ---- The Guide key (ADR 18): config.json's `guide-key`, which the owner
  // installs from Settings > Guides ("" until then: nothing is bound
  // unasked), bound at runtime by `omatrophy.py guide-key`, which refuses a
  // key another bind uses. Hyprland drops runtime binds on a config
  // reload, so it binds again then.
  // dev/preview.sh turns it off: a throwaway shell must neither bind the
  // key nor, closing, unbind the live shell's.
  property bool bindsGuideKey: true
  property string guideKey: ""
  property string guideKeyError: ""
  property string notifiedKeyError: ""

  onGuideKeyChanged: keySync.restart()
  Component.onCompleted: if (bindsGuideKey) keySync.restart()
  // Unbinds ours, so a disabled plugin leaves no key behind.
  Component.onDestruction: if (bindsGuideKey) Quickshell.execDetached(["python3", helperPath, "guide-key", ""])

  onGuideKeyErrorChanged: {
    if (guideKeyError === "" || guideKeyError === notifiedKeyError) return
    notifiedKeyError = guideKeyError
    Quickshell.execDetached(["notify-send", "--app-name=OmaTrophy", "OmaTrophy", guideKeyError])
  }

  // Coalesces typing in the setting, and lets a previous service's unbind
  // land first on a plugin reload.
  Timer {
    id: keySync
    interval: 600
    onTriggered: {
      if (!root.bindsGuideKey) return
      if (keyBinder.running) return keySync.restart()
      keyBinder.command = ["python3", root.helperPath, "guide-key", root.guideKey]
      keyBinder.running = true
    }
  }

  Process {
    id: keyBinder
    stdout: StdioCollector {
      onStreamFinished: {
        var r = {}
        try { r = JSON.parse(text) } catch (e) { return }
        root.guideKeyError = r.error || ""
      }
    }
  }

  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (event.name === "configreloaded") keySync.restart()
    }
  }
}
