import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import qs.Commons as Commons

// The difficulty reminder: shown once when a game with difficulty
// achievements left starts, so the new save is made on the right setting.
// Names the settings those achievements need and, when the game's guide
// says, whether a run on a harder setting also counts for the easier ones.
// Slides in like the toast, holds a little longer (it's read, not glanced
// at), slides out and reports finished.
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
  readonly property var settings: event && event.settings ? event.settings : []
  readonly property real outX: edge === "top-left" ? -(cardWidth + pad + 10) : (edge === "top-right" ? cardWidth + pad + 10 : 0)
  readonly property real outY: edge === "top-center" ? -(card.height + pad + 10) : 0

  width: cardWidth + pad * 2
  height: card.height + pad * 2
  clip: true

  onEventChanged: if (event) show.restart()

  // "Start on Nightmare" when one setting decides: the only one, or the
  // only exact one beside floors ("Veteran+"), which a Nightmare run
  // usually meets too. Several exact ones can't be ranked from their
  // names, so the chips list them and the line asks to pick.
  function headline() {
    if (settings.indexOf("All") >= 0) return "Every setting has an achievement"
    if (settings.indexOf("Hardest") >= 0) return "Start on the hardest setting"
    var exact = settings.filter(function(s) { return s.slice(-1) !== "+" })
    if (exact.length === 1) return "Start on " + exact[0]
    if (exact.length === 0 && settings.length === 1) return "Start on " + settings[0].slice(0, -1) + " or higher"
    return "Pick the setting before a new save"
  }

  function stackLine() {
    if (!event || event.stacks === null || event.stacks === undefined) return ""
    var line = event.stacks ? "The guide says a harder run also counts for the easier settings"
                            : "The guide says each setting needs a run of its own"
    return line + (event.stacks_verified ? "" : " (unverified)")
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
    PauseAnimation { duration: 8000 }
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
          id: label
          text: "◆ DIFFICULTY"
          color: root.accent
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
          font.bold: true
          font.letterSpacing: 2
        }
        Text {
          textFormat: Text.PlainText
          text: root.event && root.event.count ? root.event.count + (root.event.count === 1 ? " achievement" : " achievements") : ""
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
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
      }
      // One chip per setting, exact ones first as `games` lists them.
      Flow {
        width: parent.width
        spacing: 6
        topPadding: 2
        bottomPadding: 2
        Repeater {
          model: root.settings.slice(0, 6)
          delegate: Rectangle {
            required property string modelData
            width: chipText.implicitWidth + 16
            height: chipText.implicitHeight + 6
            radius: root.iconSet === "omarchy" ? 0 : Commons.Style.cornerRadius
            color: Qt.alpha(root.accent, 0.14)
            border.width: 1
            border.color: Qt.alpha(root.accent, 0.5)
            Text {
              textFormat: Text.PlainText
              id: chipText
              anchors.centerIn: parent
              text: modelData
              color: root.fg
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.body
              font.bold: true
            }
          }
        }
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        visible: text !== ""
        text: root.stackLine()
        color: Qt.alpha(root.fg, 0.7)
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
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
