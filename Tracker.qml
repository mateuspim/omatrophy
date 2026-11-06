import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Commons as Commons

// The achievement tracker overlay: a dimmed screen with one game's full
// list on a card. The shell mounts this when summoned:
//   omarchy-shell shell summon pym.omatrophy '{"store":"steam","app":"1774580"}'
// An empty payload shows the game running now, or the one played last. The
// card itself is TrackerView.qml, built from its current text on each open
// (FreshObject.qml); this file only owns the window, so it is the part that
// needs a restart.
Item {
  id: root

  property var shell: null
  property var manifest: null

  property bool opened: false
  property var request: ({})

  // Builds the view once the shell has settled, so even the first Guide key
  // press after a start skips the compile (FreshObject's keep). Not live:
  // it reads nothing until opened.
  Timer {
    interval: 4000
    running: true
    onTriggered: {
      if (root.opened || view.item) return
      var item = view.load("TrackerView.qml")
      if (!item) return
      item.maxWidth = Qt.binding(function() { return panel.width - Commons.Style.gapsOut * 4 })
      item.maxHeight = Qt.binding(function() { return panel.height - Commons.Style.gapsOut * 4 })
      item.closeRequested.connect(root.dismiss)
    }
  }

  // Called by the shell's summon with the payload JSON.
  function open(payloadJson) {
    var r = {}
    try { r = JSON.parse(payloadJson || "{}") || {} } catch (e) {}
    root.request = r
    root.opened = true
    var item = view.load("TrackerView.qml")
    if (!item) return
    // A view kept from the last open (unchanged text) is already wired;
    // its load() resets it.
    if (!view.reused) {
      item.maxWidth = Qt.binding(function() { return panel.width - Commons.Style.gapsOut * 4 })
      item.maxHeight = Qt.binding(function() { return panel.height - Commons.Style.gapsOut * 4 })
      item.closeRequested.connect(root.dismiss)
    }
    item.load(root.request)
  }

  // Called by the shell's hide.
  // The view stays built for the next open (FreshObject's keep); `live`
  // off stops its polls while hidden.
  function close() {
    root.opened = false
    if (view.item) view.item.live = false
  }

  function dismiss() {
    root.close()
    if (root.shell && typeof root.shell.hide === "function")
      root.shell.hide((root.manifest && root.manifest.id) || "pym.omatrophy")
  }

  PanelWindow {
    id: panel
    visible: root.opened
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "omatrophy-tracker"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: root.opened ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      anchors.fill: parent
      color: Commons.Color.menu.scrim
    }

    MouseArea {
      anchors.fill: parent
      onClicked: root.dismiss()
    }

    FreshObject {
      id: view
      keep: true
      anchors.centerIn: parent
      width: item ? item.width : 0
      height: item ? item.height : 0
    }
  }
}
