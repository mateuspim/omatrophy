import QtQuick
import QtQuick.Effects
import qs.Commons as Commons

// The saved image of a platinum (`omatrophy.py share`): the platinum card,
// held open, over the game's own art blurred into the theme, with the date
// and the plugin's name along the bottom. 1200 x 630, the shape link
// previews use; share.py grabs it at twice that.
//
// Only a throwaway offscreen Quickshell loads this (share.py, dev/render.sh
// share), never the live shell, so it loads PlatinumCard.qml from this
// folder by file like the shell does and needs no restart to change.
Item {
  id: root
  // The platinum event (docs/specs/events.md) plus `platinum` (unix time of
  // the last unlock) and `store_name`.
  property var event: null
  property string iconSet: "omarchy"
  // The card is scaled up so it carries the image; the grab renders it
  // at full resolution, so text and shapes stay sharp.
  readonly property real cardScale: 1.36
  readonly property color bg: Commons.Color.notifications.background
  readonly property color fg: Commons.Color.notifications.text
  readonly property color metal: "#e2eaff"
  // Darker on a light theme, as on the card.
  readonly property color ink: bg.hslLightness > 0.5 ? Qt.darker(metal, 1.9) : metal
  readonly property string art: event ? (event.hero || event.header || "") : ""

  width: 1200
  height: 630

  // The card loads with the scene, before the event arrives.
  onEventChanged: if (card.item) card.item.event = event
  onIconSetChanged: if (card.item) card.item.iconSet = iconSet

  function day(t) {
    return t > 0 ? Qt.formatDate(new Date(t * 1000), "d MMM yyyy").toUpperCase() : ""
  }

  Rectangle { anchors.fill: parent; color: root.bg }

  // The game's art, blurred and pushed back, so the card reads first.
  Image {
    id: backdrop
    anchors.fill: parent
    source: root.art
    fillMode: Image.PreserveAspectCrop
    asynchronous: false
    visible: false
    onStatusChanged: if (status === Image.Error && root.event && source !== root.event.header) source = root.event.header || ""
  }
  MultiEffect {
    anchors.fill: parent
    source: backdrop
    visible: backdrop.status === Image.Ready
    blurEnabled: true
    blur: 1
    blurMax: 48
    saturation: -0.15
    opacity: 0.5
  }
  // Darker toward the edges and the bottom, where the footer sits.
  Rectangle {
    anchors.fill: parent
    gradient: Gradient {
      GradientStop { position: 0; color: Qt.alpha(root.bg, 0.55) }
      GradientStop { position: 0.55; color: Qt.alpha(root.bg, 0.25) }
      GradientStop { position: 1; color: Qt.alpha(root.bg, 0.92) }
    }
  }
  Rectangle {
    anchors.fill: parent
    gradient: Gradient {
      orientation: Gradient.Horizontal
      GradientStop { position: 0; color: Qt.alpha(root.bg, 0.6) }
      GradientStop { position: 0.3; color: "transparent" }
      GradientStop { position: 0.7; color: "transparent" }
      GradientStop { position: 1; color: Qt.alpha(root.bg, 0.6) }
    }
  }

  Loader {
    id: card
    // The card's own pad (its light and glitter) stays in, so the rays
    // fan out over the backdrop.
    x: (root.width - width) / 2
    y: (root.height - 70 - height) / 2
    scale: root.cardScale
    transformOrigin: Item.Center
    source: Qt.resolvedUrl("PlatinumCard.qml")
    onLoaded: {
      item.still = true
      item.iconSet = root.iconSet
      item.event = root.event
    }
  }

  // The footer: a hairline, the plugin's mark and name, the store, and the
  // day the platinum landed.
  Item {
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.bottom: parent.bottom
    anchors.leftMargin: 56
    anchors.rightMargin: 56
    height: 70

    Rectangle {
      anchors.left: parent.left
      anchors.right: parent.right
      height: 1
      gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: Qt.alpha(Commons.Color.accent, 0.7) }
        GradientStop { position: 0.5; color: Qt.alpha(root.metal, 0.25) }
        GradientStop { position: 1; color: Qt.alpha(Commons.Color.accent, 0.7) }
      }
    }

    Row {
      anchors.left: parent.left
      anchors.verticalCenter: parent.verticalCenter
      anchors.verticalCenterOffset: 2
      spacing: 10
      Image {
        anchors.verticalCenter: parent.verticalCenter
        width: 22
        height: 22
        source: Qt.resolvedUrl("icon.svg")
        sourceSize: Qt.size(128, 128)
        smooth: false
      }
      Text {
        textFormat: Text.PlainText
        anchors.verticalCenter: parent.verticalCenter
        text: "OmaTrophy"
        color: root.fg
        font.family: Commons.Style.font.family
        font.pixelSize: 17
        font.bold: true
      }
      Text {
        textFormat: Text.PlainText
        anchors.verticalCenter: parent.verticalCenter
        visible: text !== ""
        text: root.event && root.event.store_name ? "·  " + root.event.store_name : ""
        color: Qt.alpha(root.fg, 0.6)
        font.family: Commons.Style.font.family
        font.pixelSize: 15
      }
    }

    Text {
      textFormat: Text.PlainText
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      anchors.verticalCenterOffset: 2
      text: root.event && root.event.platinum ? "PLATINUM  ·  " + root.day(root.event.platinum) : "PLATINUM"
      color: root.ink
      font.family: Commons.Style.font.family
      font.pixelSize: 14
      font.bold: true
      font.letterSpacing: 2.5
    }
  }
}
