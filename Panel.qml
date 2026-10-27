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

  // The tracker is this plugin's overlay entry point; the shell hands its
  // summon to Tracker.qml.
  function openTracker(store, app) {
    root.close()
    if (root.bar && root.bar.shell)
      root.bar.shell.summon("pym.omatrophy", JSON.stringify({ store: store, app: app }))
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
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }

      Flickable {
        id: scroller
        anchors.fill: parent
        contentWidth: width
        contentHeight: picker.item ? picker.item.implicitHeight : 0
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height

        // Built from the file's current text on each open (FreshObject.qml),
        // so edits to the picker show without restarting the shell. Text uses
        // the popup colours: the bar's own foreground is meant for the bar's
        // background and can vanish on the panel's (a light bar, a dark panel).
        FreshObject {
          id: picker
          width: scroller.width
          height: item ? item.implicitHeight : 0
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
