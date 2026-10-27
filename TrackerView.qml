import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons as Commons

// The tracker's card: one game's every achievement, with rarity, the date
// you got it, and filters (all, locked, unlocked, rare) plus type-to-search.
// Read-only. Built from its text by Tracker.qml (FreshObject.qml), so it must not use
// other QML types from this folder. Tracker.qml calls load(); dev/render.sh
// sets `game` to sample data instead.
Item {
  id: root

  property real maxWidth: 900
  property real maxHeight: 900
  // From `omatrophy.py game`; null until it answers.
  property var game: null
  property string error: ""

  property string filter: "all"
  property string search: ""
  property string iconSet: "omarchy"
  property var rows: []

  readonly property color foreground: Commons.Color.menu.text
  readonly property color background: Commons.Color.menu.background
  readonly property var metalColors: ({ bronze: "#e9a46b", silver: "#dfe6ee", gold: "#f3cf4a", platinum: "#e2eaff" })
  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("omatrophy.py")).replace(/^file:\/\//, ""))
  readonly property real rarePercent: 10

  signal closeRequested()

  width: Math.min(maxWidth, Commons.Style.space(760))
  height: Math.min(maxHeight, Commons.Style.space(820))

  // Called by Tracker.qml with the summon payload: {store, app}, or empty
  // for the game running now (or played last).
  function load(request) {
    var args = ["python3", helperPath, "game"]
    if (request && request.store && request.app) args = args.concat([String(request.store), String(request.app)])
    loader.command = args
    loader.running = true
  }

  onGameChanged: rebuild()
  onFilterChanged: rebuild()
  onSearchChanged: rebuild()

  // Unlocked newest first, then locked with the most common first: what you
  // did lately, then what you're likeliest to do next.
  function order(a, b) {
    if (a.unlocked !== b.unlocked) return a.unlocked ? -1 : 1
    if (a.unlocked) return b.time - a.time
    return (b.percent || 0) - (a.percent || 0)
  }

  function keep(a) {
    if (filter === "locked" && a.unlocked) return false
    if (filter === "unlocked" && !a.unlocked) return false
    if (filter === "rare" && !(a.percent !== null && a.percent <= rarePercent)) return false
    if (!search) return true
    var q = search.toLowerCase()
    var desc = a.hidden && !a.unlocked ? "" : a.desc
    return a.name.toLowerCase().indexOf(q) >= 0 || desc.toLowerCase().indexOf(q) >= 0
  }

  function rebuild() {
    if (!game) { rows = []; return }
    rows = game.achievements.filter(keep).sort(order)
    list.positionViewAtBeginning()
  }

  // A filter's label with its count, once there is one to count.
  function label(name, kind) {
    return game ? name + " " + count(kind) : name
  }

  function count(kind) {
    if (!game) return 0
    var n = 0
    for (var i = 0; i < game.achievements.length; i++) {
      var a = game.achievements[i]
      if (kind === "all" || (kind === "locked" && !a.unlocked) || (kind === "unlocked" && a.unlocked)
          || (kind === "rare" && a.percent !== null && a.percent <= rarePercent)) n++
    }
    return n
  }

  function day(t) {
    return t ? Qt.formatDate(new Date(t * 1000), "d MMM yyyy") : ""
  }

  function cycleFilter(step) {
    var all = ["all", "locked", "unlocked", "rare"]
    filter = all[(all.indexOf(filter) + step + all.length) % all.length]
  }

  Component.onCompleted: Qt.callLater(function() { keys.forceActiveFocus() })

  FileView {
    path: Quickshell.env("HOME") + "/.config/omatrophy/config.json"
    printErrors: false
    onLoaded: {
      var c = {}
      try { c = JSON.parse(text()) } catch (e) { return }
      if (c.icons) root.iconSet = c.icons
    }
  }

  Process {
    id: loader
    stdout: StdioCollector {
      onStreamFinished: {
        if (!text) return
        try { root.game = JSON.parse(text) } catch (e) { root.error = "Couldn't read the game's achievements." }
      }
    }
    stderr: StdioCollector {
      onStreamFinished: if (text && !root.game) root.error = text.trim()
    }
  }

  // One trophy, drawn the way the cards draw it (the omarchy set's inlay
  // painted in the theme accent).
  component Trophy: Item {
    id: trophy
    property string style: "omarchy"
    property string metal: "bronze"
    width: 18
    height: 18
    Image {
      anchors.fill: parent
      source: Qt.resolvedUrl("assets/" + trophy.style + "/trophy-" + trophy.metal + (trophy.style === "painted" ? ".png" : ".svg"))
      sourceSize: Qt.size(64, 64)
      smooth: trophy.style !== "omarchy"
      mipmap: trophy.style === "painted"
    }
    Item {
      anchors.fill: parent
      visible: trophy.style === "omarchy"
      Rectangle { id: paint; anchors.fill: parent; color: Commons.Color.accent; visible: false; layer.enabled: true }
      Image {
        id: inlay
        anchors.fill: parent
        source: trophy.style === "omarchy" ? Qt.resolvedUrl("assets/omarchy/trophy-accent.svg") : ""
        sourceSize: Qt.size(64, 64)
        visible: false
      }
      MultiEffect { anchors.fill: parent; source: paint; maskEnabled: true; maskSource: inlay }
    }
  }

  // A loading placeholder, like a web skeleton: a dim block with a band of
  // light sweeping across it.
  component Bone: Rectangle {
    id: bone
    color: Qt.alpha(root.foreground, 0.07)
    radius: 3
    clip: true
    Rectangle {
      width: Math.max(60, bone.width * 0.4)
      height: bone.height
      gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: "transparent" }
        GradientStop { position: 0.5; color: Qt.alpha(root.foreground, 0.08) }
        GradientStop { position: 1; color: "transparent" }
      }
      NumberAnimation on x {
        from: -Math.max(60, bone.width * 0.4)
        to: bone.width
        duration: 1300
        loops: Animation.Infinite
        running: bone.visible
      }
    }
  }

  component Caption: Text {
    color: root.foreground
    opacity: 0.6
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.caption
    elide: Text.ElideRight
  }

  BorderSurface {
    id: card
    anchors.fill: parent
    radius: Commons.Style.cornerRadius
    color: root.background
    borderSpec: Commons.Border.surfaceSpec("menu", "border", Commons.Color.menu.border, Math.max(1, Commons.Style.space(2)))
    clip: true

    // Swallow clicks so only the scrim around the card closes it.
    MouseArea { anchors.fill: parent }

    Item {
      id: keys
      anchors.fill: parent
      focus: true

      Keys.onPressed: function(event) {
        if (event.key === Qt.Key_Escape) {
          if (root.search) root.search = ""
          else root.closeRequested()
        } else if (event.key === Qt.Key_Tab) {
          root.cycleFilter(1)
        } else if (event.key === Qt.Key_Backtab) {
          root.cycleFilter(-1)
        } else if (event.key === Qt.Key_Backspace) {
          root.search = root.search.slice(0, -1)
        } else if (event.key === Qt.Key_Down) {
          list.flick(0, -1200)
        } else if (event.key === Qt.Key_Up) {
          list.flick(0, 1200)
        } else if (event.key === Qt.Key_PageDown) {
          list.contentY = Math.min(list.contentY + list.height, Math.max(0, list.contentHeight - list.height))
        } else if (event.key === Qt.Key_PageUp) {
          list.contentY = Math.max(0, list.contentY - list.height)
        } else if (event.text && event.text.length === 1 && event.text.charCodeAt(0) >= 32 && event.text.charCodeAt(0) !== 127) {
          root.search += event.text
        } else {
          return
        }
        event.accepted = true
      }
    }

    // ------------------------------------------------------------ header

    Item {
      id: header
      x: card.contentLeftInset
      y: card.contentTopInset
      width: parent.width - card.contentLeftInset - card.contentRightInset
      height: Commons.Style.space(150)

      Image {
        id: hero
        anchors.fill: parent
        source: root.game ? (root.game.hero || root.game.header || "") : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 1600
        opacity: status === Image.Ready ? 0.8 : 0
        Behavior on opacity { NumberAnimation { duration: 250 } }
      }
      // Fade the art into the card so the title reads on any image.
      Rectangle {
        anchors.fill: parent
        gradient: Gradient {
          GradientStop { position: 0.0; color: Qt.alpha(root.background, 0.1) }
          GradientStop { position: 0.6; color: Qt.alpha(root.background, 0.7) }
          GradientStop { position: 1.0; color: root.background }
        }
      }

      Column {
        anchors.left: parent.left
        anchors.right: progress.left
        anchors.bottom: parent.bottom
        anchors.margins: Commons.Style.space(16)
        anchors.bottomMargin: Commons.Style.space(10)
        spacing: Commons.Style.space(4)

        Row {
          spacing: Commons.Style.space(8)
          visible: root.game !== null && (root.game.playing || root.game.platinum > 0)
          Rectangle {
            visible: root.game !== null && root.game.playing
            width: playingText.width + Commons.Style.space(12)
            height: playingText.height + Commons.Style.space(4)
            radius: height / 2
            color: Qt.alpha(Commons.Color.accent, 0.25)
            border.width: 1
            border.color: Commons.Color.accent
            Text {
              id: playingText
              anchors.centerIn: parent
              text: "PLAYING NOW"
              color: root.foreground
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.caption
              font.letterSpacing: 1.5
              font.bold: true
            }
          }
          Row {
            visible: root.game !== null && root.game.platinum > 0
            spacing: Commons.Style.space(6)
            Trophy { style: root.iconSet; metal: "platinum"; width: 20; height: 20 }
            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: root.game ? "Platinum · " + root.day(root.game.platinum) : ""
              color: root.metalColors.platinum
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
              font.bold: true
            }
          }
        }
        Text {
          width: parent.width
          text: root.game ? root.game.game : ""
          color: root.foreground
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.display
          font.bold: true
          elide: Text.ElideRight
        }
      }

      Column {
        id: progress
        visible: root.game !== null
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Commons.Style.space(16)
        anchors.bottomMargin: Commons.Style.space(12)
        width: Commons.Style.space(150)
        spacing: Commons.Style.space(4)
        Text {
          anchors.right: parent.right
          text: root.game ? Math.floor(100 * root.game.unlocked / root.game.total) + "%" : ""
          color: root.foreground
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.display
          font.bold: true
        }
        Rectangle {
          width: parent.width
          height: 4
          color: Qt.alpha(root.foreground, 0.15)
          Rectangle {
            width: root.game ? parent.width * root.game.unlocked / root.game.total : 0
            height: parent.height
            color: root.game && root.game.platinum ? root.metalColors.platinum : Commons.Color.accent
          }
        }
        Caption {
          anchors.right: parent.right
          text: root.game ? root.game.unlocked + " of " + root.game.total + " unlocked" : ""
        }
      }
    }

    // ------------------------------------------------------------ toolbar

    Item {
      id: toolbar
      anchors.top: header.bottom
      anchors.topMargin: Commons.Style.space(6)
      x: header.x + Commons.Style.space(12)
      width: header.width - Commons.Style.space(24)
      height: filters.height

      ButtonGroup {
        id: filters
        options: [
          { value: "all", label: root.label("All", "all") },
          { value: "locked", label: root.label("Locked", "locked") },
          { value: "unlocked", label: root.label("Unlocked", "unlocked") },
          { value: "rare", label: root.label("Rare", "rare") }
        ]
        value: root.filter
        focusable: false
        foreground: root.foreground
        fontSize: Commons.Style.font.bodySmall
        onChanged: value => root.filter = value
      }

      Text {
        anchors.right: parent.right
        anchors.left: filters.right
        anchors.leftMargin: Commons.Style.space(16)
        anchors.verticalCenter: parent.verticalCenter
        horizontalAlignment: Text.AlignRight
        text: root.search ? "“" + root.search + "”" : "Type to search"
        color: root.foreground
        opacity: root.search ? 1 : 0.45
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        elide: Text.ElideLeft
      }
    }

    // ------------------------------------------------------------ list

    ListView {
      id: list
      anchors.top: toolbar.bottom
      anchors.topMargin: Commons.Style.space(10)
      anchors.bottom: footer.top
      anchors.bottomMargin: Commons.Style.space(6)
      x: toolbar.x
      width: toolbar.width
      clip: true
      model: root.rows
      spacing: Commons.Style.space(2)
      boundsBehavior: Flickable.StopAtBounds

      delegate: Rectangle {
        id: row
        required property var modelData
        readonly property var ach: modelData
        // Hidden achievements stay a secret until unlocked, or until you
        // hover to reveal them.
        readonly property bool secret: ach.hidden && !ach.unlocked && !rowHover.containsMouse
        width: list.width
        height: Commons.Style.space(56)
        radius: Commons.Style.cornerRadius
        color: rowHover.containsMouse ? Commons.Style.hoverFill : "transparent"

        MouseArea { id: rowHover; anchors.fill: parent; hoverEnabled: true }

        Rectangle {
          id: iconFrame
          x: Commons.Style.space(6)
          anchors.verticalCenter: parent.verticalCenter
          width: Commons.Style.space(42)
          height: width
          radius: 4
          color: Qt.alpha(root.foreground, 0.08)
          border.width: row.ach.unlocked ? 1 : 0
          border.color: Qt.alpha(root.metalColors[row.ach.tier] || root.metalColors.bronze, 0.7)
          clip: true
          Image {
            anchors.fill: parent
            anchors.margins: parent.border.width
            source: row.ach.unlocked ? row.ach.icon : (row.ach.icon_locked || row.ach.icon)
            asynchronous: true
            sourceSize: Qt.size(96, 96)
            opacity: row.ach.unlocked ? 1 : 0.55
          }
        }

        Column {
          anchors.left: iconFrame.right
          anchors.leftMargin: Commons.Style.space(12)
          anchors.right: side.left
          anchors.rightMargin: Commons.Style.space(12)
          anchors.verticalCenter: parent.verticalCenter
          spacing: Commons.Style.space(3)
          Text {
            width: parent.width
            text: row.secret ? "Hidden achievement" : row.ach.name
            color: root.foreground
            opacity: row.ach.unlocked ? 1 : 0.8
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.body
            font.bold: row.ach.unlocked
            font.italic: row.secret
            elide: Text.ElideRight
          }
          Caption {
            width: parent.width
            text: row.secret ? "Hover to reveal" : row.ach.desc
            visible: text !== ""
          }
        }

        Column {
          id: side
          anchors.right: parent.right
          anchors.rightMargin: Commons.Style.space(8)
          anchors.verticalCenter: parent.verticalCenter
          width: Commons.Style.space(130)
          spacing: Commons.Style.space(3)
          Row {
            anchors.right: parent.right
            spacing: Commons.Style.space(6)
            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: row.ach.percent !== null ? row.ach.percent.toFixed(1) + "%" : "–"
              color: row.ach.percent !== null && row.ach.percent <= root.rarePercent ? root.metalColors.gold : root.foreground
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
              font.bold: true
            }
            Trophy {
              anchors.verticalCenter: parent.verticalCenter
              style: root.iconSet
              metal: row.ach.tier
              opacity: row.ach.unlocked ? 1 : 0.35
            }
          }
          Caption {
            anchors.right: parent.right
            text: row.ach.unlocked ? (row.ach.time ? root.day(row.ach.time) : "Unlocked") : "Locked"
          }
        }
      }

      Caption {
        anchors.centerIn: parent
        visible: root.game !== null && list.count === 0
        text: root.search ? "Nothing matches “" + root.search + "”" : "Nothing here"
        font.pixelSize: Commons.Style.font.title
      }
    }

    // Bones in the shape of the header and rows while `game` reads the store.
    Item {
      anchors.fill: parent
      visible: root.game === null && root.error === ""
      Bone {
        x: header.x + Commons.Style.space(16)
        y: header.y + header.height - Commons.Style.space(46)
        width: header.width * 0.45
        height: 24
      }
      Bone {
        x: header.x + header.width - width - Commons.Style.space(16)
        y: header.y + header.height - Commons.Style.space(20)
        width: Commons.Style.space(150)
        height: 4
      }
      Column {
        x: list.x
        y: list.y
        width: list.width
        spacing: Commons.Style.space(2)
        Repeater {
          model: Math.max(1, Math.floor(list.height / Commons.Style.space(58)))
          delegate: Item {
            width: parent.width
            height: Commons.Style.space(56)
            Bone {
              id: boneIcon
              x: Commons.Style.space(6)
              anchors.verticalCenter: parent.verticalCenter
              width: Commons.Style.space(42)
              height: width
              radius: 4
            }
            Column {
              anchors.left: boneIcon.right
              anchors.leftMargin: Commons.Style.space(12)
              anchors.verticalCenter: parent.verticalCenter
              spacing: Commons.Style.space(7)
              Bone { width: list.width * (0.25 + (index % 3) * 0.08); height: 11 }
              Bone { width: list.width * (0.4 + (index % 2) * 0.12); height: 8 }
            }
            Bone {
              anchors.right: parent.right
              anchors.rightMargin: Commons.Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
              width: Commons.Style.space(70)
              height: 10
            }
          }
        }
      }
    }

    Text {
      anchors.centerIn: parent
      width: parent.width * 0.7
      visible: root.error !== "" && root.game === null
      text: root.error
      color: root.foreground
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.Wrap
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.title
    }

    Caption {
      id: footer
      anchors.bottom: parent.bottom
      anchors.bottomMargin: card.contentBottomInset + Commons.Style.space(8)
      anchors.horizontalCenter: parent.horizontalCenter
      text: "Tab filters · type to search · Esc closes · rarity is the share of all players"
      opacity: 0.4
    }
  }
}
