import QtQuick
import Quickshell
import qs.Ui
import qs.Commons

// The bar button: a trophy that opens the style picker.
Panel {
  id: root
  moduleName: "pym.omatrophy"
  ipcTarget: "pym.omatrophy"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  BarIconButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    tooltipText: "OmaTrophy: trophy style and previews"
    Accessible.role: Accessible.Button
    Accessible.name: "OmaTrophy settings"
    onPressed: function(b) { root.toggle() }
  }

  KeyboardPanel {
    id: popup
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: fittedContentWidth(Style.space(380))
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

        // Loaded by a fresh URL on each open, like the toast cards, so edits
        // to the picker show without restarting the shell. Text uses the
        // popup colours: the bar's own foreground is meant for the bar's
        // background and can vanish on the panel's (a light bar, a dark panel).
        Loader {
          id: picker
          width: scroller.width
          active: root.opened
          source: root.opened ? Qt.resolvedUrl("StylePicker.qml") + "?v=" + Date.now() : ""
          onLoaded: item.width = Qt.binding(function() { return scroller.width })
        }
      }
    }
  }
}
