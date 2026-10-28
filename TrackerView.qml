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
  // The search the list is filtered by: `search` once typing pauses, so a
  // long list isn't filtered and rebuilt on every key. Clearing applies at
  // once.
  property string appliedSearch: ""
  // Remembered in config.json as `tracker-sort`, written only when the
  // viewer changes it.
  property string sortBy: "recent"
  readonly property var sorts: [
    { value: "recent", label: "Recent" },
    { value: "rarity", label: "Rarest" },
    { value: "name", label: "A–Z" },
    { value: "game", label: "Game order" }
  ]
  property string iconSet: "omarchy"
  property var rows: []
  // Hidden achievements revealed with Enter, by api name; hover reveals too.
  property var revealed: ({})

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
  onSearchChanged: {
    if (search === "") { searchPause.stop(); appliedSearch = "" }
    else searchPause.restart()
  }
  onAppliedSearchChanged: rebuild()
  onSortByChanged: rebuild()

  // Recent: unlocked newest first, then locked with the most common first:
  // what you did lately, then what you're likeliest to do next. Rarest:
  // fewest players first, unknown rarity last. A–Z by name. Game order:
  // as the store lists them, often the story's order.
  function order(a, b) {
    if (sortBy === "rarity") {
      if ((a.percent === null) !== (b.percent === null)) return a.percent === null ? 1 : -1
      return (a.percent || 0) - (b.percent || 0)
    }
    if (sortBy === "name") return a.name.localeCompare(b.name)
    if (a.unlocked !== b.unlocked) return a.unlocked ? -1 : 1
    if (a.unlocked) return b.time - a.time
    return (b.percent || 0) - (a.percent || 0)
  }

  function sorted(achs) {
    // filter() already copied the list, so sorting in place is safe; the
    // store's order is the copy as it came.
    return sortBy === "game" ? achs : achs.sort(order)
  }

  function cycleSort(step) {
    var i = 0
    while (i < sorts.length && sorts[i].value !== sortBy) i++
    sortBy = sorts[(i + step + sorts.length) % sorts.length].value
    saver.exec(["python3", helperPath, "set", "tracker-sort", sortBy])
  }

  function sortLabel() {
    for (var i = 0; i < sorts.length; i++) if (sorts[i].value === sortBy) return sorts[i].label
    return sortBy
  }

  function keep(a) {
    if (filter === "locked" && a.unlocked) return false
    if (filter === "unlocked" && !a.unlocked) return false
    if (filter === "rare" && !(a.percent !== null && a.percent <= rarePercent)) return false
    if (!appliedSearch) return true
    var q = appliedSearch.toLowerCase()
    var desc = a.hidden && !a.unlocked ? "" : a.desc
    return a.name.toLowerCase().indexOf(q) >= 0 || desc.toLowerCase().indexOf(q) >= 0
  }

  function rebuild() {
    if (!game) { rows = []; return }
    rows = sorted(game.achievements.filter(keep))
    list.currentIndex = -1
    list.positionViewAtBeginning()
  }

  // Move the highlighted row; the first key press lands on the first row.
  function moveTo(index) {
    if (list.count === 0) return
    list.currentIndex = Math.max(0, Math.min(list.count - 1, index))
    list.positionViewAtIndex(list.currentIndex, ListView.Contain)
  }

  function pageRows() {
    return Math.max(1, Math.floor(list.height / Commons.Style.space(58)))
  }

  function toggleReveal() {
    if (list.currentIndex < 0 || list.currentIndex >= rows.length) return
    var a = rows[list.currentIndex]
    if (!a.hidden || a.unlocked) return
    var next = Object.assign({}, revealed)
    if (next[a.api]) delete next[a.api]
    else next[a.api] = true
    revealed = next
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

  // Unlocked achievements per metal, for the header's tally.
  function tierCount(metal) {
    if (!game) return 0
    return game.achievements.filter(function(a) { return a.unlocked && a.tier === metal }).length
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
      if (c["tracker-sort"]) root.sortBy = c["tracker-sort"]
    }
  }

  Timer {
    id: searchPause
    interval: 180
    onTriggered: root.appliedSearch = root.search
  }

  Process { id: saver }

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

  // A filter or the sort as a soft pill; the chosen one takes the accent.
  component Chip: Rectangle {
    id: chip
    property string text: ""
    property bool chosen: false
    signal clicked(var mouse)
    width: chipText.implicitWidth + Commons.Style.space(18)
    height: chipText.implicitHeight + Commons.Style.space(10)
    radius: height / 2
    color: chosen ? Qt.alpha(Commons.Color.accent, 0.18) : (chipHit.containsMouse ? Commons.Style.hoverFill : Qt.alpha(root.foreground, 0.04))
    border.width: 1
    border.color: chosen ? Qt.alpha(Commons.Color.accent, 0.6) : Qt.alpha(root.foreground, 0.1)
    Accessible.role: Accessible.Button
    Accessible.name: text
    Behavior on color { ColorAnimation { duration: 120 } }
    Text {
      textFormat: Text.PlainText
      id: chipText
      anchors.centerIn: parent
      text: chip.text
      color: chip.chosen ? Commons.Color.accent : root.foreground
      opacity: chip.chosen ? 1 : 0.75
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      font.bold: chip.chosen
    }
    MouseArea {
      id: chipHit
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      onClicked: function(mouse) { chip.clicked(mouse) }
    }
  }

  // The game's completion as a ring that winds up when the game loads.
  component Ring: Canvas {
    id: ring
    property real fraction: 0
    property color fill: Commons.Color.accent
    property real shown: 0
    width: 76
    height: 76
    onFractionChanged: shown = fraction
    onShownChanged: requestPaint()
    onFillChanged: requestPaint()
    Behavior on shown { NumberAnimation { duration: 800; easing.type: Easing.OutCubic } }
    onPaint: {
      var c = getContext("2d")
      var r = width / 2 - 4
      c.reset()
      c.lineWidth = 5
      c.lineCap = "round"
      c.strokeStyle = Qt.alpha(root.foreground, 0.12)
      c.beginPath()
      c.arc(width / 2, height / 2, r, 0, 2 * Math.PI)
      c.stroke()
      if (shown <= 0) return
      c.strokeStyle = fill
      c.beginPath()
      c.arc(width / 2, height / 2, r, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * Math.min(1, shown))
      c.stroke()
    }
  }

  // A key cap and what it does, for the footer's legend.
  component Key: Row {
    property string cap: ""
    property string action: ""
    spacing: Commons.Style.space(5)
    Rectangle {
      anchors.verticalCenter: parent.verticalCenter
      width: Math.max(height, capText.implicitWidth + Commons.Style.space(8))
      height: capText.implicitHeight + Commons.Style.space(4)
      radius: 3
      color: Qt.alpha(root.foreground, 0.06)
      border.width: 1
      border.color: Qt.alpha(root.foreground, 0.16)
      Text {
        textFormat: Text.PlainText
        id: capText
        anchors.centerIn: parent
        text: parent.parent.cap
        color: root.foreground
        opacity: 0.75
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.caption
      }
    }
    Text {
      textFormat: Text.PlainText
      anchors.verticalCenter: parent.verticalCenter
      text: parent.action
      color: root.foreground
      opacity: 0.45
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.caption
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
        } else if (event.key === Qt.Key_Right) {
          root.cycleSort(1)
        } else if (event.key === Qt.Key_Left) {
          root.cycleSort(-1)
        } else if (event.key === Qt.Key_Backspace) {
          root.search = root.search.slice(0, -1)
        } else if (event.key === Qt.Key_Down) {
          root.moveTo(list.currentIndex + 1)
        } else if (event.key === Qt.Key_Up) {
          root.moveTo(list.currentIndex - 1)
        } else if (event.key === Qt.Key_PageDown) {
          root.moveTo(list.currentIndex + root.pageRows())
        } else if (event.key === Qt.Key_PageUp) {
          root.moveTo(list.currentIndex - root.pageRows())
        } else if (event.key === Qt.Key_Home) {
          root.moveTo(0)
        } else if (event.key === Qt.Key_End) {
          root.moveTo(list.count - 1)
        } else if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
          root.toggleReveal()
        } else if (event.key === Qt.Key_Space && !root.search && list.currentIndex >= 0) {
          // Space types into a search under way, so "first light" works.
          root.toggleReveal()
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
      height: Commons.Style.space(176)

      Image {
        id: hero
        anchors.fill: parent
        source: root.game ? (root.game.hero || root.game.header || "") : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: 1600
        opacity: status === Image.Ready ? 0.9 : 0
        Behavior on opacity { NumberAnimation { duration: 250 } }
      }
      // Fade the art into the card so the title reads on any image.
      Rectangle {
        anchors.fill: parent
        gradient: Gradient {
          GradientStop { position: 0.0; color: Qt.alpha(root.background, 0.05) }
          GradientStop { position: 0.55; color: Qt.alpha(root.background, 0.6) }
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
              textFormat: Text.PlainText
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
              textFormat: Text.PlainText
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
          textFormat: Text.PlainText
          width: parent.width
          text: root.game ? root.game.game : ""
          color: root.foreground
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.display
          font.bold: true
          elide: Text.ElideRight
        }
        // What you've earned, by metal, in your trophy style.
        Row {
          visible: root.game !== null
          spacing: Commons.Style.space(14)
          Repeater {
            model: ["gold", "silver", "bronze"]
            delegate: Row {
              required property string modelData
              spacing: Commons.Style.space(5)
              Trophy { anchors.verticalCenter: parent.verticalCenter; style: root.iconSet; metal: parent.modelData; width: 16; height: 16 }
              Text {
                textFormat: Text.PlainText
                anchors.verticalCenter: parent.verticalCenter
                text: root.tierCount(parent.modelData)
                color: root.metalColors[parent.modelData]
                font.family: Commons.Style.font.family
                font.pixelSize: Commons.Style.font.bodySmall
                font.bold: true
              }
            }
          }
        }
      }

      Row {
        id: progress
        visible: root.game !== null
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: Commons.Style.space(16)
        anchors.bottomMargin: Commons.Style.space(10)
        spacing: Commons.Style.space(12)
        Column {
          anchors.verticalCenter: parent.verticalCenter
          spacing: Commons.Style.space(1)
          Text {
            textFormat: Text.PlainText
            anchors.right: parent.right
            text: root.game ? root.game.unlocked + " / " + root.game.total : ""
            color: root.foreground
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.title
            font.bold: true
          }
          Caption {
            anchors.right: parent.right
            text: "unlocked"
          }
        }
        Item {
          width: ring.width
          height: ring.height
          Ring {
            id: ring
            fraction: root.game ? root.game.unlocked / root.game.total : 0
            fill: root.game && root.game.platinum ? root.metalColors.platinum : Commons.Color.accent
          }
          Text {
            textFormat: Text.PlainText
            anchors.centerIn: parent
            text: root.game ? Math.floor(100 * root.game.unlocked / root.game.total) + "%" : ""
            color: root.foreground
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.title
            font.bold: true
          }
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

      Row {
        id: filters
        spacing: Commons.Style.space(6)
        Repeater {
          model: [
            { value: "all", label: "All", kind: "all" },
            { value: "locked", label: "Locked", kind: "locked" },
            { value: "unlocked", label: "Unlocked", kind: "unlocked" },
            { value: "rare", label: "Rare", kind: "rare" }
          ]
          delegate: Chip {
            required property var modelData
            text: root.label(modelData.label, modelData.kind)
            chosen: root.filter === modelData.value
            onClicked: root.filter = modelData.value
          }
        }
      }

      // One chip that cycles the sort; Left and Right do the same.
      Chip {
        id: sortButton
        anchors.left: filters.right
        anchors.leftMargin: Commons.Style.space(14)
        anchors.verticalCenter: parent.verticalCenter
        text: "⇅ " + root.sortLabel()
        onClicked: function(mouse) { root.cycleSort(mouse.button === Qt.RightButton ? -1 : 1) }
      }

      // Typing anywhere searches; this box shows what's typed, with a caret.
      Rectangle {
        anchors.right: parent.right
        anchors.left: sortButton.right
        anchors.leftMargin: Commons.Style.space(16)
        anchors.verticalCenter: parent.verticalCenter
        height: filters.height
        radius: height / 2
        color: Qt.alpha(root.foreground, root.search ? 0.07 : 0.03)
        border.width: 1
        border.color: root.search ? Qt.alpha(Commons.Color.accent, 0.6) : Qt.alpha(root.foreground, 0.1)
        Text {
          textFormat: Text.PlainText
          id: searchGlyph
          anchors.left: parent.left
          anchors.leftMargin: Commons.Style.space(10)
          anchors.verticalCenter: parent.verticalCenter
          text: "⌕"
          color: root.foreground
          opacity: 0.5
          font.pixelSize: Commons.Style.font.body
        }
        Text {
          textFormat: Text.PlainText
          id: searchText
          anchors.left: searchGlyph.right
          anchors.leftMargin: Commons.Style.space(6)
          anchors.right: parent.right
          anchors.rightMargin: Commons.Style.space(12)
          anchors.verticalCenter: parent.verticalCenter
          text: root.search || "Type to search"
          color: root.foreground
          opacity: root.search ? 1 : 0.4
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
          elide: Text.ElideLeft
        }
        Rectangle {
          visible: root.search !== ""
          x: searchText.x + Math.min(searchText.contentWidth, searchText.width) + 1
          anchors.verticalCenter: parent.verticalCenter
          width: 1
          height: searchText.font.pixelSize + 2
          color: Commons.Color.accent
          SequentialAnimation on opacity {
            loops: Animation.Infinite
            running: root.search !== ""
            NumberAnimation { to: 0; duration: 530 }
            NumberAnimation { to: 1; duration: 530 }
          }
        }
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
      currentIndex: -1
      highlightFollowsCurrentItem: false

      // Qt's Flickable turns a wheel notch into a short flick that barely moves
      // a long list (dragging was far faster). A mouse notch now moves a fixed
      // distance; touchpads keep Qt's own smooth path.
      WheelHandler {
        target: null
        acceptedDevices: PointerDevice.Mouse
        onWheel: function(event) {
          var notch = Math.max(-120, Math.min(120, event.angleDelta.y)) / 120
          var top = list.originY
          var bottom = top + Math.max(0, list.contentHeight - list.height)
          list.contentY = Math.max(top, Math.min(bottom, list.contentY - notch * Commons.Style.space(120)))
        }
      }


      delegate: Rectangle {
        id: row
        required property var modelData
        required property int index
        readonly property var ach: modelData
        // Hidden achievements stay a secret until unlocked, or until you
        // hover or press Enter to reveal them.
        readonly property bool secret: ach.hidden && !ach.unlocked && !rowHover.containsMouse && !root.revealed[ach.api]
        width: list.width
        height: Commons.Style.space(56)
        radius: Commons.Style.cornerRadius
        color: ListView.isCurrentItem || rowHover.containsMouse ? Commons.Style.hoverFill
               : (ach.unlocked ? Qt.alpha(root.metalColors[ach.tier] || root.metalColors.bronze, 0.035) : "transparent")
        // The first screenful arrives in a short cascade; rows scrolled to
        // later just appear.
        opacity: 0
        Component.onCompleted: entry.start()
        SequentialAnimation {
          id: entry
          PauseAnimation { duration: Math.min(row.index, 12) * 22 }
          NumberAnimation { target: row; property: "opacity"; to: 1; duration: 180; easing.type: Easing.OutCubic }
        }

        // An unlocked row carries its metal as a rail, like the toast.
        Rectangle {
          visible: row.ach.unlocked
          anchors.verticalCenter: parent.verticalCenter
          width: 3
          height: parent.height - Commons.Style.space(16)
          radius: 1.5
          color: root.metalColors[row.ach.tier] || root.metalColors.bronze
        }

        // Hover moves the highlight too, so mouse and keys share one row.
        MouseArea {
          id: rowHover
          anchors.fill: parent
          hoverEnabled: true
          onEntered: list.currentIndex = row.index
        }

        Rectangle {
          id: iconFrame
          x: Commons.Style.space(12)
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
            textFormat: Text.PlainText
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
            text: row.secret ? "Hover or press Enter to reveal" : row.ach.desc
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
              textFormat: Text.PlainText
              anchors.verticalCenter: parent.verticalCenter
              text: row.ach.percent !== null ? row.ach.percent.toFixed(1) + "%" : "–"
              // In the metal it earns, dimmed while still locked.
              color: row.ach.percent !== null ? root.metalColors[row.ach.tier] || root.foreground : root.foreground
              opacity: row.ach.unlocked ? 1 : 0.7
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
          // A locked counter achievement shows how far along it is
          // instead of a bare "Locked".
          Row {
            anchors.right: parent.right
            spacing: Commons.Style.space(6)
            Rectangle {
              visible: !!row.ach.progress
              anchors.verticalCenter: parent.verticalCenter
              width: Commons.Style.space(48)
              height: 3
              radius: 1.5
              color: Qt.alpha(root.foreground, 0.15)
              Rectangle {
                width: row.ach.progress ? parent.width * row.ach.progress.value / row.ach.progress.max : 0
                height: parent.height
                radius: parent.radius
                color: Commons.Color.accent
              }
            }
            Caption {
              text: row.ach.unlocked ? (row.ach.time ? root.day(row.ach.time) : "Unlocked")
                : row.ach.progress ? row.ach.progress.value + " / " + row.ach.progress.max : "Locked"
            }
          }
        }
      }

      Caption {
        anchors.centerIn: parent
        visible: root.game !== null && list.count === 0
        text: root.appliedSearch ? "Nothing matches “" + root.appliedSearch + "”" : "Nothing here"
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
        y: header.y + header.height - height - Commons.Style.space(10)
        width: 76
        height: 76
        radius: 38
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
              x: Commons.Style.space(12)
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
      textFormat: Text.PlainText
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

    Column {
      id: footer
      anchors.bottom: parent.bottom
      anchors.bottomMargin: card.contentBottomInset + Commons.Style.space(8)
      anchors.horizontalCenter: parent.horizontalCenter
      spacing: Commons.Style.space(4)
      Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Commons.Style.space(14)
        Key { cap: "↑↓"; action: "move" }
        Key { cap: "Enter"; action: "reveal" }
        Key { cap: "Tab"; action: "filter" }
        Key { cap: "←→"; action: "sort" }
        Key { cap: "Esc"; action: "close" }
      }
      Caption {
        anchors.horizontalCenter: parent.horizontalCenter
        text: "Type to search · rarity is the share of all players"
        opacity: 0.35
      }
    }
  }
}
