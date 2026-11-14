import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import qs.Commons as Commons

// The missable reminder: shown when a game starts whose guide's current
// step has achievements still open that can be missed there, so the
// player knows before playing past them. Names the step and each
// missable with the guide's note on when it's lost; a hidden one comes
// as "Hidden achievement" unless the owner reveals hidden ones. Once per
// step, and again only for a missable it never named (the watcher keeps
// what it said). Slides in like the
// difficulty card, holds longer the more it names, slides out and
// reports finished.
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
  readonly property var missables: event && event.missables ? event.missables : []
  // Four rows fit the card; more are counted under them.
  readonly property int shownRows: Math.min(missables.length, 4)
  readonly property real outX: edge === "top-left" ? -(cardWidth + pad + 10) : (edge === "top-right" ? cardWidth + pad + 10 : 0)
  readonly property real outY: edge === "top-center" ? -(card.height + pad + 10) : 0

  width: cardWidth + pad * 2
  height: card.height + pad * 2
  clip: true

  onEventChanged: if (event) show.restart()

  function stepLine() {
    if (!event || !event.step) return ""
    return "Step " + event.step + (event.steps ? " of " + event.steps : "")
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
      }
    }
    ParallelAnimation {
      NumberAnimation { target: card; property: "slideX"; to: 0; duration: 420; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "slideY"; to: 0; duration: 420; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "opacity"; to: 1; duration: 300 }
    }
    // Read, not glanced at: a little longer per missable it names.
    PauseAnimation { duration: 7000 + 1500 * root.shownRows }
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
    height: body.y + body.height + 18

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

    // The game's banner across the top, fading into the card, inside the
    // card's mask so the stepped corners trim it.
    Item {
      id: surface
      anchors.fill: parent
      layer.enabled: true
      layer.effect: MultiEffect {
        maskEnabled: true
        maskSource: cardMask
      }

      Image {
        id: banner
        width: parent.width
        height: 84
        source: root.event && root.event.header ? root.event.header : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        opacity: 0.45
      }
      // Faded out before the text starts: a banner's own logo ran into
      // the label above it.
      Rectangle {
        width: parent.width
        height: banner.height
        visible: banner.status === Image.Ready
        gradient: Gradient {
          GradientStop { position: 0; color: Qt.alpha(Commons.Color.notifications.background, 0) }
          GradientStop { position: 0.7; color: Qt.alpha(Commons.Color.notifications.background, root.fillAlpha) }
        }
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

    Column {
      id: body
      x: 20
      // Where the banner has faded out.
      y: banner.status === Image.Ready ? 60 : 16
      width: card.width - 40
      spacing: 4

      Row {
        spacing: 8
        Text {
          textFormat: Text.PlainText
          text: "◆ MISSABLE"
          color: root.accent
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
          font.bold: true
          font.letterSpacing: 2
        }
        Text {
          textFormat: Text.PlainText
          text: root.stepLine()
          color: Qt.alpha(root.fg, 0.6)
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
        }
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: root.event && root.event.title ? root.event.title : ""
        color: root.fg
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.fontPx(1.5)
        font.bold: true
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: root.missables.length === 1 ? "Can be missed in this step:" : "These can be missed in this step:"
        color: Qt.alpha(root.fg, 0.7)
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
      }
      // One row per missable: a diamond in the accent, the name, and the
      // guide's note on when it is lost.
      Repeater {
        model: root.missables.slice(0, root.shownRows)
        delegate: Item {
          id: missRow
          required property var modelData
          width: body.width
          height: rowText.implicitHeight + 6
          Text {
            textFormat: Text.PlainText
            y: 3
            text: "◆"
            color: root.accent
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
          }
          Column {
            id: rowText
            x: 18
            y: 3
            width: parent.width - 18
            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: missRow.modelData.name || ""
              color: root.fg
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.body
              font.bold: true
              font.italic: missRow.modelData.hidden === true
              elide: Text.ElideRight
            }
            Text {
              textFormat: Text.PlainText
              width: parent.width
              visible: text !== ""
              text: missRow.modelData.note || ""
              color: Qt.alpha(root.fg, 0.65)
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
              wrapMode: Text.Wrap
              maximumLineCount: 2
              elide: Text.ElideRight
            }
          }
        }
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        visible: root.missables.length > root.shownRows
        text: "+" + (root.missables.length - root.shownRows) + " more in the tracker's guide"
        color: Qt.alpha(root.fg, 0.6)
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        topPadding: 4
        text: root.event ? root.event.game : ""
        color: Qt.alpha(root.fg, 0.5)
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
        elide: Text.ElideRight
      }
    }
  }
}
