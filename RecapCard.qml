import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import qs.Commons as Commons

// The session recap: shown when a game stops after a session that
// unlocked anything. How long it ran, how many trophies it brought, the
// rarest of them, and where the game stands now (a platinum earned in the
// session says so). Slides in like the difficulty card, holds, slides
// out and reports finished. Silent: the unlocks had their chimes.
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
  readonly property var rarest: event && event.rarest ? event.rarest : null
  readonly property real share: event && event.total ? event.unlocked / event.total : 0
  readonly property color tierColor: rarest ? (({ bronze: "#e9a46b", silver: "#dfe6ee", gold: "#f3cf4a" })[rarest.tier] || "#e9a46b") : accent
  readonly property real outX: edge === "top-left" ? -(cardWidth + pad + 10) : (edge === "top-right" ? cardWidth + pad + 10 : 0)
  readonly property real outY: edge === "top-center" ? -(card.height + pad + 10) : 0

  width: cardWidth + pad * 2
  height: card.height + pad * 2
  clip: true

  onEventChanged: if (event) show.restart()

  // "1 h 35 min", "40 min".
  function length(minutes) {
    if (!minutes) return ""
    var h = Math.floor(minutes / 60), m = minutes % 60
    return h ? h + " h" + (m ? " " + m + " min" : "") : m + " min"
  }

  function headline() {
    if (!event) return ""
    if (event.platinum) return "Platinum this session"
    return event.count + (event.count === 1 ? " trophy" : " trophies") + " this session"
  }

  function percentText(p) {
    if (p === null || p === undefined) return ""
    return (p < 1 ? p.toFixed(1) : Math.round(p * 10) / 10) + "% of players"
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
    PauseAnimation { duration: 7000 }
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
      spacing: 6

      Row {
        spacing: 8
        Text {
          textFormat: Text.PlainText
          text: "◆ SESSION"
          color: root.accent
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
          font.bold: true
          font.letterSpacing: 2
        }
        Text {
          textFormat: Text.PlainText
          text: root.length(root.event ? root.event.minutes : 0)
          color: Qt.alpha(root.fg, 0.6)
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
        }
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: root.headline()
        color: root.fg
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.fontPx(1.5)
        font.bold: true
        elide: Text.ElideRight
      }
      // Where the game stands now: the count and a bar in the accent.
      Item {
        width: parent.width
        height: progressText.implicitHeight
        Text {
          textFormat: Text.PlainText
          id: progressText
          text: root.event ? root.event.unlocked + " / " + root.event.total + " · " + Math.floor(root.share * 100) + "%" : ""
          color: Qt.alpha(root.fg, 0.75)
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
        }
        Rectangle {
          x: progressText.implicitWidth + 12
          anchors.verticalCenter: parent.verticalCenter
          width: parent.width - x
          height: 4
          color: Qt.alpha(root.fg, 0.12)
          Rectangle {
            width: parent.width * root.share
            height: parent.height
            color: root.accent
          }
        }
      }
      // The session's rarest unlock, its rarity in its metal.
      Row {
        visible: root.rarest !== null
        width: parent.width
        spacing: 10
        topPadding: 2
        Rectangle {
          width: 40
          height: 40
          color: Qt.alpha(root.fg, 0.06)
          border.width: 1
          border.color: Qt.alpha(root.tierColor, 0.6)
          radius: root.iconSet === "omarchy" ? 0 : Commons.Style.cornerRadius
          Image {
            anchors.fill: parent
            anchors.margins: 1
            source: root.rarest && root.rarest.icon ? root.rarest.icon : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
          }
        }
        Column {
          width: parent.width - 50
          anchors.verticalCenter: parent.verticalCenter
          Text {
            textFormat: Text.PlainText
            width: parent.width
            text: root.rarest ? "Rarest: " + root.rarest.name : ""
            color: root.fg
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.body
            font.bold: true
            elide: Text.ElideRight
          }
          Text {
            textFormat: Text.PlainText
            text: root.rarest ? root.percentText(root.rarest.percent) : ""
            color: root.tierColor
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
          }
        }
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        topPadding: 2
        text: root.event ? root.event.game : ""
        color: Qt.alpha(root.fg, 0.5)
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
        elide: Text.ElideRight
      }
    }
  }
}
