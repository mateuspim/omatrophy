import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import qs.Commons as Commons

// A counter milestone: a locked counter achievement ("52 / 80") passed
// half, three quarters or nine tenths of its goal. A small toast with the
// achievement's icon, its name and a bar that fills to the new count;
// slides in like the toast, holds briefly, slides out and reports
// finished. Silent: nothing unlocked yet.
//
// Built from its text per card (FreshObject.qml), so it uses no other QML
// file from this folder; stepped() is repeated from TrophyToast.qml.
Item {
  id: root
  property var event: null
  property string edge: "top-center"
  property string iconSet: "omarchy"
  property string glass: "frosted"
  readonly property real fillAlpha: ({ clear: 0.35, frosted: 0.8, solid: 1 })[glass] || 0.8
  signal finished()

  readonly property int pad: 40
  readonly property int cardWidth: 480
  readonly property color fg: Commons.Color.notifications.text
  readonly property color accent: Commons.Color.accent
  readonly property real share: event && event.max ? Math.min(1, event.value / event.max) : 0
  // The bar fills from where it was, the milestone before this one.
  property real fill: 0
  readonly property real outX: edge === "top-left" ? -(cardWidth + pad + 10) : (edge === "top-right" ? cardWidth + pad + 10 : 0)
  readonly property real outY: edge === "top-center" ? -(card.height + pad + 10) : 0

  width: cardWidth + pad * 2
  height: card.height + pad * 2
  clip: true

  onEventChanged: if (event) show.restart()

  // "52 / 80": whole counts as they are, others to one decimal.
  function count(v) {
    return v === Math.floor(v) ? String(v) : v.toFixed(1)
  }

  // The Omarchy logo's corners: cut in two grid steps, never rounded.
  function stepped(w, h, s, inset) {
    var x0 = inset, y0 = inset, x1 = w - inset, y1 = h - inset
    var pts = [[x0, y0 + 2 * s], [x0 + s, y0 + 2 * s], [x0 + s, y0 + s], [x0 + 2 * s, y0 + s], [x0 + 2 * s, y0],
               [x1 - 2 * s, y0], [x1 - 2 * s, y0 + s], [x1 - s, y0 + s], [x1 - s, y0 + 2 * s], [x1, y0 + 2 * s],
               [x1, y1 - 2 * s], [x1 - s, y1 - 2 * s], [x1 - s, y1 - s], [x1 - 2 * s, y1 - s], [x1 - 2 * s, y1],
               [x0 + 2 * s, y1], [x0 + 2 * s, y1 - s], [x0 + s, y1 - s], [x0 + s, y1 - 2 * s], [x0, y1 - 2 * s]]
    return "M" + pts.map(function(p) { return p[0] + " " + p[1] }).join(" L") + " Z"
  }

  SequentialAnimation {
    id: show
    ScriptAction {
      script: {
        card.slideX = root.outX
        card.slideY = root.outY
        card.opacity = 0
        root.fill = Math.max(0, ((root.event ? root.event.threshold : 50) - 25) / 100)
      }
    }
    ParallelAnimation {
      NumberAnimation { target: card; property: "slideX"; to: 0; duration: 420; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "slideY"; to: 0; duration: 420; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "opacity"; to: 1; duration: 300 }
    }
    NumberAnimation { target: root; property: "fill"; to: root.share; duration: 700; easing.type: Easing.OutCubic }
    PauseAnimation { duration: 3800 }
    ParallelAnimation {
      NumberAnimation { target: card; property: "slideX"; to: root.outX; duration: 340; easing.type: Easing.InCubic }
      NumberAnimation { target: card; property: "slideY"; to: root.outY; duration: 340; easing.type: Easing.InCubic }
      NumberAnimation { target: card; property: "opacity"; to: 0; duration: 340 }
    }
    ScriptAction { script: root.finished() }
  }

  Item {
    id: card
    property real slideX: 0
    property real slideY: 0
    x: root.pad + slideX
    y: root.pad + slideY
    width: root.cardWidth
    height: body.y + body.height + 14

    Shape {
      anchors.fill: parent
      layer.enabled: true
      layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: "#000000"
        shadowOpacity: 0.6
        shadowBlur: 1.0
        blurMax: 32
        shadowVerticalOffset: 6
      }
      ShapePath {
        fillColor: Qt.alpha(Commons.Color.notifications.background, root.fillAlpha)
        strokeColor: "transparent"
        PathSvg { path: root.stepped(card.width, card.height, 6, 0) }
      }
    }

    Shape {
      id: cardMask
      anchors.fill: parent
      visible: false
      layer.enabled: true
      ShapePath {
        fillColor: "white"
        strokeColor: "transparent"
        PathSvg { path: root.stepped(card.width, card.height, 6, 0) }
      }
    }

    // The glass edge and the accent rail, inside the card's mask so the
    // stepped corners trim them.
    Item {
      id: surface
      anchors.fill: parent
      layer.enabled: true
      layer.effect: MultiEffect {
        maskEnabled: true
        maskSource: cardMask
      }

      Rectangle {
        visible: root.glass !== "solid"
        y: 1
        width: parent.width
        height: 1
        color: Qt.rgba(1, 1, 1, 0.14)
      }
      // The accent's rail down the left edge, as the toast's metal.
      Rectangle {
        width: 3
        height: parent.height
        color: root.accent
      }
    }

    Shape {
      anchors.fill: parent
      ShapePath {
        fillColor: "transparent"
        strokeColor: Qt.alpha(root.accent, 0.5)
        strokeWidth: 1
        joinStyle: ShapePath.MiterJoin
        PathSvg { path: root.stepped(card.width, card.height, 6, 0.5) }
      }
    }

    Row {
      id: body
      x: 18
      y: 14
      width: card.width - 36
      spacing: 14

      Rectangle {
        id: iconBox
        width: 56
        height: 56
        anchors.verticalCenter: parent.verticalCenter
        color: Qt.alpha(root.fg, 0.06)
        border.width: 1
        border.color: Qt.alpha(root.accent, 0.5)
        radius: root.iconSet === "omarchy" ? 0 : Commons.Style.cornerRadius
        Image {
          anchors.fill: parent
          anchors.margins: 1
          source: root.event && root.event.icon ? root.event.icon : ""
          fillMode: Image.PreserveAspectCrop
          asynchronous: true
        }
      }
      Column {
        width: body.width - iconBox.width - body.spacing
        spacing: 4
        Row {
          spacing: 8
          Text {
            textFormat: Text.PlainText
            text: "◆ " + (root.event ? root.event.threshold : 0) + "%"
            color: root.accent
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
            font.bold: true
            font.letterSpacing: 2
          }
          Text {
            textFormat: Text.PlainText
            width: body.width - iconBox.width - body.spacing - 70
            text: root.event ? root.event.game : ""
            color: Qt.alpha(root.fg, 0.5)
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
            elide: Text.ElideRight
          }
        }
        Text {
          textFormat: Text.PlainText
          width: parent.width
          text: root.event ? root.event.name : ""
          color: root.fg
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
          font.bold: true
          elide: Text.ElideRight
        }
        Item {
          width: parent.width
          height: countText.implicitHeight
          Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - countText.implicitWidth - 10
            height: 4
            color: Qt.alpha(root.fg, 0.12)
            Rectangle {
              width: parent.width * root.fill
              height: parent.height
              color: root.accent
            }
          }
          Text {
            textFormat: Text.PlainText
            id: countText
            anchors.right: parent.right
            text: root.event ? root.count(root.event.value) + " / " + root.count(root.event.max) : ""
            color: Qt.alpha(root.fg, 0.75)
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
          }
        }
      }
    }
  }
}
