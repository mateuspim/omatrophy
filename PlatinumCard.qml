import QtQuick
import QtQuick.Effects
import QtQuick.Particles
import QtQuick.Shapes
import qs.Commons as Commons

// 100% of a game, told in beats:
//   1. a badge slides in, its ring one trophy short of full
//   2. the ring fills to 100%
//   3. the platinum trophy spins in like a flipped coin and lands
//   4. on landing: a bloom of light, a glitter burst, a flash ring, slow
//      rays, a shine across the metal, and the chime (`chime` signal)
//   5. the badge opens into a wide card over the game's hero art
//   6. PLATINUM TROPHY writes itself letter by letter, the name rises in,
//      the count rolls up from zero and the bar fills with it
// then it holds, glinting now and then, folds back into the badge and leaves.
//
// It speaks the toast's language (TrophyToast.qml): a metal rail down the
// left edge, the trophy on a tile washed in its metal, a spaced label over
// the name, then a count and a progress bar.
//
// The badge stays against the screen edge it came from: at top-right the
// card opens leftward with the badge on its right. Light and particles draw
// outside the card, into `pad` of transparent margin, which Service.qml
// takes back out of the window margins.
//
// Built from its text per card (FreshObject.qml), so it uses no other QML
// file from this folder; the Trophy component below is repeated in
// TrophyToast.qml for that reason.
Item {
  id: root
  property var event: null
  property string edge: "top-center"
  // Which trophy art: assets/omarchy (flat pixel grid, theme-tinted inlay),
  // assets/vector (SVG) or assets/painted (PNG).
  property string iconSet: "omarchy"
  signal finished()
  signal chime()

  readonly property int pad: 90
  readonly property int full: 660
  readonly property int badge: 140
  readonly property bool mirror: edge === "top-right"
  readonly property color fg: Commons.Color.notifications.text
  readonly property color accent: Commons.Color.accent
  readonly property color bg: Commons.Color.notifications.background
  readonly property color metal: "#e2eaff"
  readonly property real startFill: event && event.total ? Math.max(0, event.total - 1) / event.total : 0.9
  readonly property real outX: edge === "top-left" ? -(badge + pad + 20) : (edge === "top-right" ? badge + pad + 20 : 0)
  readonly property real outY: edge === "top-center" ? -(card.height + pad) : 0

  // Driven by the timeline below.
  property real reveal: 0
  property real counted: 0

  width: full + pad * 2
  height: card.height + pad * 2
  clip: true

  onEventChanged: if (event) show.restart()

  // The Omarchy logo's corners: cut in two grid steps, never rounded. With
  // `broken`, an open outline with the two breaks of the Omarchy mark (left
  // middle, bottom right), for the border; otherwise a closed shape to fill.
  function stepped(w, h, s, inset, broken) {
    var x0 = inset, y0 = inset, x1 = w - inset, y1 = h - inset, m = (y0 + y1) / 2, g = 20
    var pts = [[x0, m - g / 2], [x0, y0 + 2 * s], [x0 + s, y0 + 2 * s], [x0 + s, y0 + s], [x0 + 2 * s, y0 + s], [x0 + 2 * s, y0],
               [x1 - 2 * s, y0], [x1 - 2 * s, y0 + s], [x1 - s, y0 + s], [x1 - s, y0 + 2 * s], [x1, y0 + 2 * s],
               [x1, y1 - 2 * s], [x1 - s, y1 - 2 * s], [x1 - s, y1 - s], [x1 - 2 * s, y1 - s], [x1 - 2 * s, y1]]
    var path = "M" + pts.map(function(p) { return p[0] + " " + p[1] }).join(" L")
    // The bottom-right break sits a little in from the corner.
    if (broken) path += " L" + (x1 - 2 * s - 22) + " " + y1 + " M" + (x1 - 2 * s - 46) + " " + y1
    path += " L" + (x0 + 2 * s) + " " + y1 + " L" + (x0 + 2 * s) + " " + (y1 - s) + " L" + (x0 + s) + " " + (y1 - s)
          + " L" + (x0 + s) + " " + (y1 - 2 * s) + " L" + x0 + " " + (y1 - 2 * s) + " L" + x0 + " " + (m + g / 2)
    return broken ? path : path + " Z"
  }

  function span(ev) {
    if (!ev || !ev.first || !ev.last) return ""
    var s = Math.max(0, ev.last - ev.first)
    var d = Math.floor(s / 86400)
    if (d >= 1) return d + (d === 1 ? " day" : " days")
    var h = Math.max(1, Math.round(s / 3600))
    return h + (h === 1 ? " hour" : " hours")
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
      card.width = root.badge; card.opacity = 0; card.slideX = root.outX; card.slideY = root.outY
      ring.fill = root.startFill; trophy.spin = 900; trophy.scale = 0.15; trophy.opacity = 0; trophy.shine = -1
      flash.scale = 0.6; flash.opacity = 0; glow.opacity = 0; glow.scale = 0.4; rays.opacity = 0
      art.opacity = 0; root.reveal = 0; root.counted = 0; title.opacity = 0; title.y = 12; stats.opacity = 0
      sweep.x = -sweep.width; twinkle.enabled = false; frame.opacity = 0; frame.scale = 1.25; ring.opacity = 1
    } }
    // 1. badge in
    ParallelAnimation {
      NumberAnimation { target: card; property: "slideX"; to: 0; duration: 460; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "slideY"; to: 0; duration: 460; easing.type: Easing.OutCubic }
      NumberAnimation { target: card; property: "opacity"; to: 1; duration: 300 }
    }
    // 2. the last stretch of the ring
    NumberAnimation { target: ring; property: "fill"; to: 1; duration: 650; easing.type: Easing.InOutCubic }
    // 3. the trophy spins in
    ParallelAnimation {
      NumberAnimation { target: trophy; property: "spin"; to: 0; duration: 950; easing.type: Easing.OutCubic }
      NumberAnimation { target: trophy; property: "opacity"; to: 1; duration: 200 }
      SequentialAnimation {
        NumberAnimation { target: trophy; property: "scale"; to: 1.18; duration: 700; easing.type: Easing.OutCubic }
        NumberAnimation { target: trophy; property: "scale"; to: 1; duration: 250; easing.type: Easing.InOutQuad }
      }
      NumberAnimation { target: glow; property: "opacity"; to: 0.5; duration: 900 }
    }
    // 4. landing
    ScriptAction { script: { root.chime(); glitter.burst(90); dust.burst(40) } }
    ParallelAnimation {
      SequentialAnimation {
        NumberAnimation { target: glow; property: "opacity"; to: 1; duration: 120 }
        NumberAnimation { target: glow; property: "opacity"; to: 0.55; duration: 1400; easing.type: Easing.OutCubic }
      }
      NumberAnimation { target: glow; property: "scale"; to: 1; duration: 700; easing.type: Easing.OutBack }
      NumberAnimation { target: flash; property: "scale"; to: 2.4; duration: 900; easing.type: Easing.OutCubic }
      SequentialAnimation {
        NumberAnimation { target: flash; property: "opacity"; to: 1; duration: 80 }
        NumberAnimation { target: flash; property: "opacity"; to: 0; duration: 820 }
      }
      NumberAnimation { target: rays; property: "opacity"; to: 1; duration: 700 }
      NumberAnimation { target: ring; property: "opacity"; to: 0; duration: 200 }
      NumberAnimation { target: frame; property: "opacity"; to: 1; duration: 160 }
      NumberAnimation { target: frame; property: "scale"; to: 1; duration: 420; easing.type: Easing.OutBack; easing.overshoot: 2 }
      SequentialAnimation {
        PauseAnimation { duration: 120 }
        NumberAnimation { target: trophy; property: "shine"; from: -0.4; to: 1.4; duration: 700; easing.type: Easing.InOutQuad }
      }
      // 5. open into the full card
      SequentialAnimation {
        PauseAnimation { duration: 450 }
        ParallelAnimation {
          NumberAnimation { target: card; property: "width"; to: root.full; duration: 650; easing.type: Easing.OutCubic }
          NumberAnimation { target: art; property: "opacity"; to: 1; duration: 900 }
        }
      }
    }
    // 6. text
    ScriptAction { script: twinkle.enabled = true }
    ParallelAnimation {
      NumberAnimation { target: root; property: "reveal"; to: 16; duration: 800 }
      SequentialAnimation {
        PauseAnimation { duration: 200 }
        ParallelAnimation {
          NumberAnimation { target: title; property: "opacity"; to: 1; duration: 450 }
          NumberAnimation { target: title; property: "y"; to: 0; duration: 550; easing.type: Easing.OutCubic }
        }
      }
      SequentialAnimation {
        PauseAnimation { duration: 400 }
        ParallelAnimation {
          NumberAnimation { target: stats; property: "opacity"; to: 1; duration: 350 }
          NumberAnimation { target: root; property: "counted"; to: root.event ? root.event.total : 0; duration: 1100; easing.type: Easing.OutCubic }
        }
      }
      SequentialAnimation {
        PauseAnimation { duration: 300 }
        NumberAnimation { target: sweep; property: "x"; to: root.full; duration: 1400; easing.type: Easing.InOutQuad }
      }
    }
    // hold, with a glint across the trophy every couple of seconds
    SequentialAnimation {
      loops: 3
      PauseAnimation { duration: 2000 }
      NumberAnimation { target: trophy; property: "shine"; from: -0.4; to: 1.4; duration: 650; easing.type: Easing.InOutQuad }
    }
    ScriptAction { script: twinkle.enabled = false }
    // fold back and leave
    ParallelAnimation {
      NumberAnimation { targets: [title, stats, art]; property: "opacity"; to: 0; duration: 260 }
      NumberAnimation { target: root; property: "reveal"; to: 0; duration: 260 }
      NumberAnimation { targets: [rays, glow]; property: "opacity"; to: 0; duration: 400 }
    }
    NumberAnimation { target: card; property: "width"; to: root.badge; duration: 420; easing.type: Easing.InOutCubic }
    ParallelAnimation {
      NumberAnimation { target: card; property: "slideX"; to: root.outX; duration: 380; easing.type: Easing.InCubic }
      NumberAnimation { target: card; property: "slideY"; to: root.outY; duration: 380; easing.type: Easing.InCubic }
      NumberAnimation { target: card; property: "opacity"; to: 0; duration: 380 }
    }
    ScriptAction { script: root.finished() }
  }

  Item {
    id: card
    property real slideX: 0
    property real slideY: 0
    // Grows away from the edge it hugs.
    x: root.pad + (root.edge === "top-left" ? 0 : root.mirror ? root.full - width : (root.full - width) / 2) + slideX
    y: root.pad + slideY
    width: root.badge
    height: 176

    // Rays turn behind the card, so they read as light from behind it
    // rather than a sticker on top of the art.
    Item {
      id: rays
      x: badgeSlot.x + badgeSlot.width / 2
      y: card.height / 2
      opacity: 0
      RotationAnimation on rotation { from: 0; to: 360; duration: 30000; loops: Animation.Infinite; running: rays.opacity > 0 }
      Repeater {
        model: 14
        Shape {
          required property int index
          rotation: index * (360 / 14)
          transformOrigin: Item.TopLeft
          preferredRendererType: Shape.CurveRenderer
          ShapePath {
            strokeColor: "transparent"
            fillGradient: LinearGradient {
              x1: 0; y1: 0; x2: 0; y2: -175
              GradientStop { position: 0.3; color: Qt.alpha(root.metal, 0.38) }
              GradientStop { position: 1; color: "transparent" }
            }
            startX: 0; startY: 0
            PathLine { x: -12; y: -175 }
            PathLine { x: 12; y: -175 }
            PathLine { x: 0; y: 0 }
          }
        }
      }
    }

    // A real soft shadow, cast by the card's own stepped shape.
    Shape {
      anchors.fill: parent
      layer.enabled: true
      layer.effect: MultiEffect {
        shadowEnabled: true
        shadowColor: "#000000"
        shadowOpacity: 0.7
        shadowBlur: 1.0
        blurMax: 40
        shadowVerticalOffset: 8
      }
      ShapePath {
        fillColor: root.bg
        strokeColor: "transparent"
        PathSvg { path: root.stepped(card.width, card.height, 6, 0, false) }
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
        PathSvg { path: root.stepped(card.width, card.height, 6, 0, false) }
      }
    }

    Item {
      id: surface
      anchors.fill: parent
      // The card background itself.
      Rectangle { anchors.fill: parent; color: root.bg }
      layer.enabled: true
      layer.effect: MultiEffect {
        maskEnabled: true
        maskSource: cardMask
      }

      // Hero art, laid out at full width from the start so opening the card
      // reveals it rather than stretching it, and faded into the theme
      // background on the badge side.
      Item {
        id: art
        x: root.mirror ? card.width - root.full : (root.edge === "top-left" ? 0 : (card.width - root.full) / 2)
        width: root.full
        height: card.height
        Image {
          id: hero
          anchors.fill: parent
          source: root.event ? root.event.hero : ""
          fillMode: Image.PreserveAspectCrop
          asynchronous: true
          opacity: 0.65
          onStatusChanged: if (status === Image.Error && root.event && source !== root.event.header) source = root.event.header
        }
        Rectangle {
          anchors.fill: hero
          gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: root.mirror ? Qt.alpha(root.bg, 0.1) : root.bg }
            GradientStop { position: root.mirror ? 0.6 : 0.4; color: Qt.alpha(root.bg, 0.85) }
            GradientStop { position: 1; color: root.mirror ? root.bg : Qt.alpha(root.bg, 0.1) }
          }
        }
      }

      Rectangle {
        id: sweep
        width: 220
        height: parent.height
        x: -width
        gradient: Gradient {
          orientation: Gradient.Horizontal
          GradientStop { position: 0; color: "transparent" }
          GradientStop { position: 0.5; color: Qt.alpha(root.metal, 0.16) }
          GradientStop { position: 1; color: "transparent" }
        }
      }

      // The metal's rail down the left edge, as on every toast.
      Rectangle {
        width: 3
        height: card.height
        color: root.metal
      }
    }


    // The border, broken like the Omarchy mark.
    Shape {
      anchors.fill: parent
      ShapePath {
        fillColor: "transparent"
        strokeColor: root.accent
        strokeWidth: 2
        joinStyle: ShapePath.MiterJoin
        capStyle: ShapePath.FlatCap
        PathSvg { path: root.stepped(card.width, card.height, 6, 2 / 2, true) }
      }
    }

    // The badge. Light and particles are not clipped, so they spill past
    // the card into the pad.
    Item {
      id: badgeSlot
      x: root.mirror ? card.width - 18 - width : 18
      width: 104
      height: 104
      anchors.verticalCenter: parent.verticalCenter

      Shape {
        id: glow
        anchors.centerIn: parent
        width: 300
        height: 300
        opacity: 0
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
          strokeColor: "transparent"
          fillGradient: RadialGradient {
            centerX: 150; centerY: 150; centerRadius: 150; focalX: 150; focalY: 150
            GradientStop { position: 0; color: Qt.alpha(root.metal, 0.5) }
            GradientStop { position: 0.3; color: Qt.alpha(root.accent, 0.22) }
            GradientStop { position: 1; color: "transparent" }
          }
          PathAngleArc { centerX: 150; centerY: 150; radiusX: 150; radiusY: 150; startAngle: 0; sweepAngle: 360 }
        }
      }

      Rectangle {
        id: flash
        anchors.centerIn: parent
        width: parent.width
        height: parent.height
        color: "transparent"
        border.width: 3
        border.color: root.metal
        opacity: 0
      }

      ParticleSystem {
        id: particles
        anchors.centerIn: parent
        width: 2
        height: 2

        ImageParticle {
          groups: ["glitter"]
          source: "qrc:///particleresources/star.png"
          color: root.metal
          colorVariation: 0.15
          rotationVariation: 180
          rotationVelocityVariation: 260
          entryEffect: ImageParticle.Scale
        }
        ImageParticle {
          groups: ["dust"]
          source: "qrc:///particleresources/glowdot.png"
          color: root.accent
          colorVariation: 0.25
        }
        Emitter {
          id: glitter
          group: "glitter"
          x: -12; y: -12; width: 24; height: 24
          enabled: false
          lifeSpan: 1500; lifeSpanVariation: 500
          size: 20; sizeVariation: 10; endSize: 2
          velocity: AngleDirection { angleVariation: 180; magnitude: 210; magnitudeVariation: 120 }
          acceleration: PointDirection { y: 150 }
        }
        Emitter {
          id: dust
          group: "dust"
          x: -20; y: -20; width: 40; height: 40
          enabled: false
          lifeSpan: 1100; lifeSpanVariation: 400
          size: 12; sizeVariation: 6; endSize: 0
          velocity: AngleDirection { angleVariation: 180; magnitude: 120; magnitudeVariation: 70 }
        }
        // Slow sparkle around the trophy while the card holds.
        Emitter {
          id: twinkle
          group: "glitter"
          x: -52; y: -52; width: 104; height: 104
          shape: EllipseShape {}
          enabled: false
          emitRate: 7
          lifeSpan: 1100; lifeSpanVariation: 300
          size: 11; sizeVariation: 6; endSize: 0
          velocity: PointDirection { y: -16; xVariation: 10; yVariation: 8 }
        }
      }

      // The toast's trophy tile, washed in platinum, over a dark base so it
      // reads on any hero art.
      Rectangle {
        anchors.centerIn: parent
        width: 92
        height: 92
        color: Qt.alpha(root.bg, 0.6)
        Rectangle {
          anchors.fill: parent
          border.width: 1
          border.color: Qt.alpha(root.metal, 0.6)
          gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(root.metal, 0.18) }
            GradientStop { position: 1; color: Qt.alpha(root.metal, 0.04) }
          }
        }
      }

      // Progress as a square with stepped corners, walked clockwise from the
      // top centre; at 100% it hands over to the broken frame below.
      Canvas {
        id: ring
        property real fill: 0
        anchors.fill: parent
        onFillChanged: requestPaint()
        function corners(a, b, s) {
          var m = (a + b) / 2
          return [[m, a], [b - 2 * s, a], [b - 2 * s, a + s], [b - s, a + s], [b - s, a + 2 * s], [b, a + 2 * s],
                  [b, b - 2 * s], [b - s, b - 2 * s], [b - s, b - s], [b - 2 * s, b - s], [b - 2 * s, b],
                  [a + 2 * s, b], [a + 2 * s, b - s], [a + s, b - s], [a + s, b - 2 * s], [a, b - 2 * s],
                  [a, a + 2 * s], [a + s, a + 2 * s], [a + s, a + s], [a + 2 * s, a + s], [a + 2 * s, a], [m, a]]
        }
        function trace(ctx, pts, upto) {
          var total = 0, i
          for (i = 1; i < pts.length; i++) total += Math.abs(pts[i][0] - pts[i - 1][0]) + Math.abs(pts[i][1] - pts[i - 1][1])
          var left = total * upto
          ctx.beginPath(); ctx.moveTo(pts[0][0], pts[0][1])
          for (i = 1; i < pts.length && left > 0; i++) {
            var dx = pts[i][0] - pts[i - 1][0], dy = pts[i][1] - pts[i - 1][1], d = Math.abs(dx) + Math.abs(dy)
            var t = Math.min(1, left / d)
            ctx.lineTo(pts[i - 1][0] + dx * t, pts[i - 1][1] + dy * t)
            left -= d
          }
          ctx.stroke()
        }
        onPaint: {
          var ctx = getContext("2d")
          ctx.reset()
          ctx.lineWidth = 4
          ctx.lineJoin = "miter"
          var pts = corners(2, width - 2, 5)
          ctx.strokeStyle = Qt.alpha(root.fg, 0.12)
          trace(ctx, pts, 1)
          ctx.strokeStyle = root.accent
          trace(ctx, pts, fill)
        }
      }

      // The frame the trophy earns: broken like the Omarchy mark, in the
      // theme accent. Revealed on the burst, replacing the progress square.
      Item {
        id: frame
        anchors.centerIn: parent
        width: parent.width + 8
        height: parent.height + 8
        opacity: 0
        Rectangle { id: framePaint; anchors.fill: parent; color: root.accent; visible: false; layer.enabled: true }
        Image {
          id: frameShape
          anchors.fill: parent
          source: Qt.resolvedUrl("assets/omarchy/trophy-frame.svg")
          sourceSize: Qt.size(256, 256)
          smooth: false
          visible: false
        }
        MultiEffect { anchors.fill: parent; source: framePaint; maskEnabled: true; maskSource: frameShape }
      }

      Trophy {
        id: trophy
        anchors.centerIn: parent
        width: 76
        height: 76
        metal: "platinum"
        set: root.iconSet
        accent: root.accent
        engraving: "#"
      }
    }

    Column {
      id: textCol
      width: root.full - root.badge - 30 - 26
      x: root.mirror ? badgeSlot.x - 30 - width : badgeSlot.x + badgeSlot.width + 30
      anchors.verticalCenter: parent.verticalCenter
      spacing: 2

      // PLATINUM TROPHY, one letter at a time, set like the toast's label.
      Row {
        anchors.right: root.mirror ? parent.right : undefined
        spacing: 2
        Repeater {
          model: "PLATINUM TROPHY".split("")
          Text {
            textFormat: Text.PlainText
            required property string modelData
            required property int index
            readonly property real shown: Math.max(0, Math.min(1, root.reveal - index))
            text: modelData
            color: root.metal
            opacity: shown
            transform: Translate { y: (1 - shown) * 10 }
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
            font.bold: true
          }
        }
      }
      Item {
        width: parent.width
        height: title.height + 2
        Text {
          textFormat: Text.PlainText
          id: title
          width: parent.width
          horizontalAlignment: root.mirror ? Text.AlignRight : Text.AlignLeft
          text: root.event ? root.event.game : ""
          color: root.fg
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.display
          font.bold: true
          elide: Text.ElideRight
          opacity: 0
        }
      }
      Column {
        id: stats
        width: parent.width
        spacing: 2
        opacity: 0
        Text {
          textFormat: Text.PlainText
          width: parent.width
          horizontalAlignment: root.mirror ? Text.AlignRight : Text.AlignLeft
          text: root.span(root.event) ? "Every achievement, in " + root.span(root.event) : "Every achievement"
          color: Qt.alpha(root.fg, 0.7)
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
        }
        Item { width: 1; height: 8 }
        Item {
          width: parent.width
          height: count.height
          // A clean exit: the game has nothing left to give.
          Text {
            textFormat: Text.PlainText
            text: "exit 0"
            color: Qt.alpha(root.fg, 0.5)
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
          }
          Text {
            textFormat: Text.PlainText
            id: count
            anchors.right: parent.right
            text: root.event ? Math.round(root.counted) + " / " + root.event.total : ""
            color: root.fg
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
            font.bold: true
          }
        }
        Item { width: 1; height: 5 }
        // Fills with the count, in the metal rather than the accent: this
        // bar only ever ends full.
        Rectangle {
          width: parent.width
          height: 4
          color: Qt.alpha(root.fg, 0.1)
          Rectangle {
            width: root.event && root.event.total ? parent.width * root.counted / root.event.total : 0
            height: parent.height
            color: root.metal
          }
        }
      }
    }
  }
}
