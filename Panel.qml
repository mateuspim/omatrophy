import QtQuick
import Quickshell
import qs.Ui
import qs.Commons

// The bar button: a trophy that opens the cabinet (StylePicker.qml), whose
// games open the achievement tracker overlay (Tracker.qml).
Panel {
  id: root
  moduleName: "pym.omatrophy"
  ipcTarget: "pym.omatrophy"
  // Omarchy creates one widget per monitor, but IPC targets are process-wide.
  // Only the first screen owns direct IPC; mouse access stays on every bar.
  manageIpc: !!root.QsWindow.window && root.QsWindow.window.screen === Quickshell.screens[0]

  // The tracker is this plugin's overlay entry point; the shell hands its
  // summon to Tracker.qml.
  // `api`, when given, is one achievement for the tracker to highlight.
  function openTracker(store, app, api) {
    root.close()
    var request = { store: store, app: app }
    if (api) request.api = api
    if (root.bar && root.bar.shell)
      root.bar.shell.summon("pym.omatrophy", JSON.stringify(request))
  }

  // The Guide key setting (manifest schema, Omarchy's plugin settings
  // page), handed to the service, which binds it (ADR 18).
  readonly property string guideKey: String(setting("guideKey", "SUPER + CTRL + G"))
  property QtObject service: null

  function findService() {
    if (service) return
    var shell = bar ? bar.shell : null
    service = shell && typeof shell.serviceFor === "function" ? shell.serviceFor(moduleName) : null
  }

  // The service may load after the widget.
  Timer {
    interval: 1000
    repeat: true
    running: root.service === null && root.manageIpc
    onTriggered: root.findService()
  }

  Binding {
    target: root.service
    property: "guideKey"
    value: root.guideKey
    when: root.service !== null && root.manageIpc
  }

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    tooltipText: "OmaTrophy: trophies, games and settings"
    Accessible.role: Accessible.Button
    Accessible.name: "OmaTrophy"
    onPressed: function(b) { root.toggle() }
  }

  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: fittedContentWidth(Style.space(420))
    contentHeight: fittedContentHeight(picker.item ? picker.item.implicitHeight : Style.space(300))

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      // The Games tab's filter field takes every key while it has focus;
      // other characters reach the picker, which may start the filter.
      blocked: picker.item ? !!picker.item.typing : false
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        if (picker.item && typeof picker.item.textKey === "function") picker.item.textKey(t)
      }

      Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: picker.item ? picker.item.implicitHeight : 0
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        // Qt's Flickable turns a wheel notch into a short flick that barely moves
        // a long list (dragging was far faster). A mouse notch now moves a fixed
        // distance; touchpads keep Qt's own smooth path.
        WheelHandler {
          target: null
          acceptedDevices: PointerDevice.Mouse
          onWheel: function(event) {
            var notch = Math.max(-120, Math.min(120, event.angleDelta.y)) / 120
            var top = scroller.originY
            var bottom = top + Math.max(0, scroller.contentHeight - scroller.height)
            scroller.contentY = Math.max(top, Math.min(bottom, scroller.contentY - notch * Style.space(120)))
          }
        }


        // Built from the file's current text on each open (FreshObject.qml),
        // so edits to the picker show without restarting the shell. Text uses
        // the popup colours: the bar's own foreground is meant for the bar's
        // background and can vanish on the panel's (a light bar, a dark panel).
        FreshObject {
          id: picker
          width: scroller.width
          height: item ? item.implicitHeight : 0
        }
        // When the filter field lets go, the keys come back here, so Escape
        // still closes the panel.
        Connections {
          target: picker.item
          ignoreUnknownSignals: true
          function onTypingChanged() {
            if (picker.item && !picker.item.typing) keyCatcher.forceActiveFocus()
          }
        }
        Connections {
          target: root
          function onOpenedChanged() {
            if (!root.opened) { picker.clear(); return }
            var item = picker.load("StylePicker.qml")
            if (!item) return
            item.width = Qt.binding(function() { return scroller.width })
            item.track.connect(root.openTracker)
          }
        }
      }
    }
  }
}
