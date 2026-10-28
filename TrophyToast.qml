import QtQuick
import QtQuick.Effects
import QtQuick.Particles
import QtQuick.Shapes
import qs.Commons as Commons

// One unlock: slides in from its edge (down from the top in the center, in
// from the side at a corner), flips a trophy in the unlock's metal into the
// tile that leads the card and runs a shine across it, pops the achievement
// art, rolls the count to the new number, holds, slides back out, then
// reports finished. A rail down the left edge carries the metal too.
//
// The metal comes from rarity (omatrophy.py `tier`): bronze, silver, or gold
// for 10% of players or fewer. The card's border and a soft halo behind the
// trophy tile carry the metal; gold gets them brighter, plus a glitter burst
// off the trophy and a sweep of light across the card.
//
// Built from its text per toast (FreshObject.qml), so it uses no other QML
// file from this folder; the Trophy component is repeated from
// PlatinumCard.qml for that reason.
Item {
  id: root
  property var event: null
  property string edge: "top-center"
  // Which trophy art: assets/omarchy (flat pixel grid, theme-tinted inlay),
  // assets/vector (SVG) or assets/painted (PNG).
  property string iconSet: "omarchy"
  // How much of the game shows through the card (config `glass`): clear,
  // frosted, or solid, the card before it went glass.
  property string glass: "frosted"
  readonly property real fillAlpha: ({ clear: 0.35, frosted: 0.8, solid: 1 })[glass] || 0.8
  signal finished()

  readonly property int pad: 40
  readonly property int cardWidth: 480
  readonly property string tier: event && event.tier ? event.tier : "bronze"
  readonly property bool gold: tier === "gold"
  readonly property color tierColor: ({ bronze: "#e9a46b", silver: "#dfe6ee", gold: "#f3cf4a" })[tier] || "#e9a46b"
  readonly property color fg: Commons.Color.notifications.text
  readonly property color accent: Commons.Color.accent
  readonly property real progress: event && event.total ? event.unlocked / event.total : 0
  readonly property real before: event && event.total ? Math.max(0, event.unlocked - 1) / event.total : 0
  // Off-screen start: above the window, or past the screen edge it hugs.
  readonly property real outX: edge === "top-left" ? -(cardWidth + pad + 10) : (edge === "top-right" ? cardWidth + pad + 10 : 0)
  readonly property real outY: edge === "top-center" ? -(card.height + pad + 10) : 0

  width: cardWidth + pad * 2
  height: card.height + pad * 2
  clip: true

  onEventChanged: if (event) show.restart()

  // The Omarchy logo's corners: cut in two grid steps, never rounded.
  function stepped(w, h, s, inset) {
    var x0 = inset, y0 = inset, x1 = w - inset, y1 = h - inset
    var pts = [[x0, y0 + 2 * s], [x0 + s, y0 + 2 * s], [x0 + s, y0 + s], [x0 + 2 * s, y0 + s], [x0 + 2 * s, y0],
               [x1 - 2 * s, y0], [x1 - 2 * s, y0 + s], [x1 - s, y0 + s], [x1 - s, y0 + 2 * s], [x1, y0 + 2 * s],
               [x1, y1 - 2 * s], [x1 - s, y1 - 2 * s], [x1 - s, y1 - s], [x1 - 2 * s, y1 - s], [x1 - 2 * s, y1],
               [x0 + 2 * s, y1], [x0 + 2 * s, y1 - s], [x0 + s, y1 - s], [x0 + s, y1 - 2 * s], [x0, y1 - 2 * s]]
    return "M" + pts.map(function(p) { return p[0] + " " + p[1] }).join(" L") + " Z"
  }

  component Trophy: Item {
    id: trophy
    property string metal: "bronze"
    property string set: "vector"
    property color accent: "white"
    property string engraving: ""
    // Where the shine band sits, in trophy widths: below 0 and above 1 are off the metal.
    property real shine: -1
    property real spin: 0
    transform: Rotation { origin.x: trophy.width / 2; origin.y: trophy.height / 2; axis { x: 0; y: 1; z: 0 } angle: trophy.spin }

    Image {
      id: cup
      anchors.fill: parent
      source: Qt.resolvedUrl("assets/" + trophy.set + "/trophy-" + trophy.metal + (trophy.set === "painted" ? ".png" : ".svg"))
      // The omarchy set is pixel art: keep its edges crisp.
      smooth: trophy.set !== "omarchy"
      sourceSize: Qt.size(256, 256)
    }
    // The omarchy set's inlay is a white layer of its own, painted here in
    // the theme accent so the trophy follows the theme.
    Item {
      anchors.fill: parent
      visible: trophy.set === "omarchy"
      Rectangle { id: inlayPaint; anchors.fill: parent; color: trophy.accent; visible: false; layer.enabled: true }
      Image {
        id: inlay
        anchors.fill: parent
        source: trophy.set === "omarchy" ? Qt.resolvedUrl("assets/omarchy/trophy-accent.svg") : ""
        sourceSize: Qt.size(256, 256)
        visible: false
      }
      MultiEffect { anchors.fill: parent; source: inlayPaint; maskEnabled: true; maskSource: inlay }
    }
    // Engraved into the plate (omarchy set: centred at 64,52 of 128).
    Text {
      textFormat: Text.PlainText
      visible: trophy.engraving !== "" && trophy.set === "omarchy"
      x: trophy.width * 0.5 - width / 2
      y: trophy.height * (52 / 128) - height / 2
      text: trophy.engraving
      color: trophy.accent
      font.family: Commons.Style.font.family
      font.pixelSize: Math.round(trophy.width * 0.12)
      font.bold: true
    }
    // The glint: a soft diagonal band on the painted metals, a hard
    // vertical scan line on the flat omarchy set.
    Item {
      id: band
      anchors.fill: parent
      visible: false
      layer.enabled: true
      readonly property bool flat: trophy.set === "omarchy"
      Rectangle {
        x: trophy.shine * trophy.width - width / 2
        y: -trophy.height * 0.3
        width: trophy.width * (band.flat ? 0.12 : 0.34)
        height: trophy.height * 1.6
        rotation: band.flat ? 0 : 20
        gradient: Gradient {
          orientation: Gradient.Horizontal
          GradientStop { position: 0; color: band.flat ? "#80ffffff" : "#00ffffff" }
          GradientStop { position: 0.5; color: band.flat ? "#80ffffff" : "#d8ffffff" }
          GradientStop { position: 1; color: band.flat ? "#80ffffff" : "#00ffffff" }
        }
      }
    }
    // The shine only lands on metal: the band, masked by the cup's own shape.
    MultiEffect {
      anchors.fill: parent
      source: band
      maskEnabled: true
      maskSource: cup
    }
  }

  SequentialAnimation {
    id: show
    ScriptAction { script: {
      card.slideX = root.outX; card.slideY = root.outY; card.opacity = 0
      iconBox.scale = 0.55; medal.scale = 0; medal.spin = 540; medal.shine = -1; halo.opacity = 0
      bar.shown = root.before; roll.offset = 0; sweep.x = -sweep.width
    } }
    ParallelAnimation {
      NumberAnimation { target: card; property: "slideX"; to: 0; duration: 420; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "slideY"; to: 0; duration: 420; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "opacity"; to: 1; duration: 260 }
      SequentialAnimation {
        PauseAnimation { duration: 140 }
        NumberAnimation { target: iconBox; property: "scale"; to: 1; duration: 520; easing.type: Easing.OutBack; easing.overshoot: 2.4 }
      }
    }
    // The trophy flips onto the icon's corner.
    ParallelAnimation {
      NumberAnimation { target: medal; property: "spin"; to: 0; duration: 700; easing.type: Easing.OutCubic }
      SequentialAnimation {
        NumberAnimation { target: medal; property: "scale"; to: 1.25; duration: 420; easing.type: Easing.OutCubic }
        NumberAnimation { target: medal; property: "scale"; to: 1; duration: 260; easing.type: Easing.InOutQuad }
      }
      SequentialAnimation {
        PauseAnimation { duration: 250 }
        NumberAnimation { target: roll; property: "offset"; to: 1; duration: 380; easing.type: Easing.OutBack }
      }
      NumberAnimation { target: bar; property: "shown"; to: root.progress; duration: 900; easing.type: Easing.InOutCubic }
      // The halo flares as the trophy lands, then settles to a glow.
      SequentialAnimation {
        PauseAnimation { duration: 200 }
        NumberAnimation { target: halo; property: "opacity"; to: root.gold ? 0.8 : 0.6; duration: 380; easing.type: Easing.OutCubic }
        NumberAnimation { target: halo; property: "opacity"; to: root.gold ? 0.45 : 0.3; duration: 900; easing.type: Easing.InOutQuad }
      }
    }
    ScriptAction { script: if (root.gold) glitter.burst(40) }
    ParallelAnimation {
      NumberAnimation { target: medal; property: "shine"; from: -0.4; to: 1.4; duration: 650; easing.type: Easing.InOutQuad }
      NumberAnimation { target: sweep; property: "x"; to: root.cardWidth; duration: root.gold ? 1200 : 0; easing.type: Easing.InOutQuad }
    }
    PauseAnimation { duration: 4600 }
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
    height: row.height + 32

    // A real soft shadow, cast by the card's own stepped shape.
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
      // Glass: the theme's background, a little see-through.
      ShapePath {
        fillColor: Qt.alpha(Commons.Color.notifications.background, root.fillAlpha)
        strokeColor: "transparent"
        PathSvg { path: root.stepped(card.width, card.height, 6, 0) }
      }
    }

    // The same shape, white, as the mask that keeps art and light inside it.
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

    Item {
      id: surface
      anchors.fill: parent
      layer.enabled: true
      layer.effect: MultiEffect {
        maskEnabled: true
        maskSource: cardMask
      }

      // Glass: light catching the top of the pane, and its lit top edge.
      Rectangle {
        visible: root.glass !== "solid"
        width: parent.width
        height: parent.height * 0.55
        gradient: Gradient {
          GradientStop { position: 0; color: Qt.rgba(1, 1, 1, 0.09) }
          GradientStop { position: 1; color: Qt.rgba(1, 1, 1, 0) }
        }
      }
      Rectangle {
        visible: root.glass !== "solid"
        y: 1
        width: parent.width
        height: 1
        color: Qt.rgba(1, 1, 1, 0.14)
      }

      // The gold sweep: a soft band of light crossing the card once.
      Rectangle {
        id: sweep
        width: 150
        height: parent.height
        x: -width
        visible: root.gold
        gradient: Gradient {
          orientation: Gradient.Horizontal
          GradientStop { position: 0; color: "transparent" }
          GradientStop { position: 0.5; color: Qt.alpha(root.tierColor, 0.16) }
          GradientStop { position: 1; color: "transparent" }
        }
      }
    }

    // The metal's rail down the left edge, inside the card's mask so the
    // stepped corners trim it.
    Rectangle {
      parent: surface
      width: 3
      height: card.height
      color: root.tierColor
    }

    Shape {
      anchors.fill: parent
      ShapePath {
        fillColor: "transparent"
        strokeColor: root.gold ? root.tierColor : Qt.alpha(root.tierColor, 0.45)
        strokeWidth: root.gold ? 2 : 1
        joinStyle: ShapePath.MiterJoin
        PathSvg { path: root.stepped(card.width, card.height, 6, root.gold ? 1 : 0.5) }
      }
    }

    // The achievement's own art, small, in the top-right corner.
    Rectangle {
      id: iconBox
      x: card.width - width - 16
      y: 16
      width: 44
      height: 44
      color: Qt.alpha(root.fg, 0.06)
      border.width: 1
      border.color: Qt.alpha(root.fg, 0.18)
      radius: Commons.Style.cornerRadius
      clip: true
      Image {
        anchors.fill: parent
        anchors.margins: 1
        source: root.event ? root.event.icon : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
      }
    }

    Row {
      id: row
      x: 20
      y: 16
      spacing: 16

      // The trophy leads: a tile washed in its metal.
      Item {
        width: 72
        height: 72

        ParticleSystem {
          anchors.centerIn: parent
          width: 2
          height: 2
          ImageParticle {
            source: "qrc:///particleresources/star.png"
            color: root.tierColor
            colorVariation: 0.15
            rotationVariation: 180
            rotationVelocityVariation: 220
            entryEffect: ImageParticle.Scale
          }
          Emitter {
            id: glitter
            x: -12; y: -12; width: 24; height: 24
            enabled: false
            lifeSpan: 1000; lifeSpanVariation: 300
            size: 14; sizeVariation: 6; endSize: 1
            velocity: AngleDirection { angleVariation: 180; magnitude: 130; magnitudeVariation: 60 }
            acceleration: PointDirection { y: 90 }
          }
        }

        // A soft halo in the metal behind the tile, kept square or rounded
        // like the tile itself.
        RectangularShadow {
          id: halo
          anchors.fill: parent
          scale: medal.scale
          radius: root.iconSet === "omarchy" ? 0 : Commons.Style.cornerRadius
          color: root.tierColor
          blur: 26
          spread: 2
          opacity: 0
        }

        // Square on the omarchy grid, theme-rounded for the other sets.
        Rectangle {
          anchors.fill: parent
          radius: root.iconSet === "omarchy" ? 0 : Commons.Style.cornerRadius
          scale: medal.scale
          border.width: 1
          border.color: Qt.alpha(root.tierColor, 0.6)
          gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(root.tierColor, 0.18) }
            GradientStop { position: 1; color: Qt.alpha(root.tierColor, 0.04) }
          }
        }
        Trophy {
          id: medal
          anchors.centerIn: parent
          width: 52
          height: 52
          metal: root.tier
          set: root.iconSet
          accent: root.accent
        }
      }

      Column {
        width: root.cardWidth - row.x - 72 - row.spacing - 16
        spacing: 2

        Row {
          spacing: 8
          Text {
            textFormat: Text.PlainText
            text: root.tier.toUpperCase() + " TROPHY"
            color: root.tierColor
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
            font.bold: true
            font.letterSpacing: 2
          }
          Text {
            textFormat: Text.PlainText
            text: root.event && root.event.percent !== null && root.event.percent !== undefined
                  ? root.event.percent.toFixed(1) + "% of players" : ""
            color: Qt.alpha(root.fg, 0.5)
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
          }
        }
        // The name and description stop short of the art in the corner.
        Text {
          textFormat: Text.PlainText
          width: parent.width - iconBox.width - 12
          text: root.event ? root.event.name : ""
          color: root.fg
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.fontPx(1.5)
          font.bold: true
          elide: Text.ElideRight
        }
        Text {
          textFormat: Text.PlainText
          width: parent.width - iconBox.width - 12
          text: root.event ? root.event.desc : ""
          color: Qt.alpha(root.fg, 0.7)
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
          wrapMode: Text.WordWrap
          maximumLineCount: 2
          elide: Text.ElideRight
        }
        Item { width: 1; height: 8 }
        Item {
          width: parent.width
          height: gameName.height
          Text {
            textFormat: Text.PlainText
            id: gameName
            width: parent.width - roll.width - 12
            text: root.event ? root.event.game : ""
            color: Qt.alpha(root.fg, 0.5)
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
            elide: Text.ElideRight
          }
          // The count rolls up from the number before this unlock.
          Item {
            id: roll
            property real offset: 0
            anchors.right: parent.right
            width: newCount.width
            height: newCount.height
            clip: true
            Text {
              textFormat: Text.PlainText
              y: -roll.offset * parent.height
              anchors.right: parent.right
              text: root.event ? Math.max(0, root.event.unlocked - 1) + " / " + root.event.total : ""
              color: Qt.alpha(root.fg, 0.5)
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
            }
            Text {
              textFormat: Text.PlainText
              id: newCount
              y: (1 - roll.offset) * parent.height
              anchors.right: parent.right
              text: root.event ? root.event.unlocked + " / " + root.event.total : ""
              color: root.fg
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
              font.bold: true
            }
          }
        }
        Item { width: 1; height: 5 }
        // Progress toward 100%, filling in from the count before this unlock.
        Rectangle {
          width: parent.width
          height: 4
          color: Qt.alpha(root.fg, 0.1)
          Rectangle {
            id: bar
            property real shown: 0
            width: parent.width * shown
            height: parent.height
            color: root.accent
          }
        }
      }
    }
  }
}
