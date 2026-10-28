import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons as Commons

// The bar panel's content, in three tabs. Now: your totals, the game you're
// playing (or the last few you played) and the shelf of platinums. Games:
// every game with its count, sorted by recent, closest to platinum or name.
// Settings: trophy style, preview tiles that fire real toasts through the
// running service, position and sound. Any game opens the achievement
// tracker. Settings read and write the same ~/.config/omatrophy/config.json
// the service watches, through `omatrophy.py set`, so a choice applies to the
// next toast. Bones shimmer in place of what's still loading.
Column {
  id: root
  property color foreground: Commons.Color.popups.text

  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("omatrophy.py")).replace(/^file:\/\//, ""))
  readonly property var styles: [
    { id: "omarchy", name: "Omarchy" },
    { id: "vector", name: "Faceted" },
    { id: "painted", name: "Painted" }
  ]
  readonly property var metals: ["bronze", "silver", "gold", "platinum"]
  readonly property var metalColors: ({ bronze: "#e9a46b", silver: "#dfe6ee", gold: "#f3cf4a", platinum: "#e2eaff" })

  property string tab: "now"
  property string iconSet: "omarchy"
  property string position: "top-center"
  property bool sound: true
  property string chimes: "omatrophy"

  // From `omatrophy.py now`; null until it answers. dev/render.sh turns
  // `live` off and sets `cabinet` to sample data.
  property var cabinet: null
  property bool live: true
  // From `omatrophy.py games`, read the first time the Games tab opens.
  property var games: null
  property string sort: "recent"
  // Typed into the Games tab's filter field; matches game names.
  property string gameFilter: ""
  // "store:app" keys from config.json's `hidden`, kept live so a toggle
  // shows at once; hidden games leave Closest and dim elsewhere.
  property var hiddenKeys: ({})
  readonly property var sortedGames: games ? games.filter(showGame).sort(gameOrder) : []
  readonly property int hiddenCount: games ? games.filter(function(g) { return isHidden(g) }).length : 0
  // With the community backfill a library runs to hundreds of games, and a
  // row each made the panel slow to open: the list shows a page at a time
  // and "Show more" adds the next. Filter and sort see every game first.
  readonly property int gamesPage: 25
  property int gamesShown: gamesPage
  readonly property var shownGames: sortedGames.slice(0, gamesShown)
  onSortChanged: gamesShown = gamesPage
  onGameFilterChanged: gamesShown = gamesPage
  // True while the filter field has the keyboard; Panel.qml then lets keys
  // through to it instead of its own shortcuts.
  readonly property bool typing: filterField.activeFocus

  onTabChanged: if (tab === "games" && games === null && live) gamesReader.running = true

  // Asks Panel.qml to open the tracker on one game; the panel owns the
  // shell handle, this file only knows the game.
  signal track(string store, string app)

  function set(key, value) {
    if (key === "icons") iconSet = value
    if (key === "position") position = value
    if (key === "sound") {
      sound = value !== "off"
      if (value !== "on" && value !== "off") chimes = value
    }
    runner.exec(["python3", helperPath, "set", key, value])
  }

  function isHidden(g) {
    return !!hiddenKeys[g.store + ":" + g.app]
  }

  function showGame(g) {
    if (sort === "closest" && isHidden(g)) return false
    return !gameFilter || g.game.toLowerCase().indexOf(gameFilter.toLowerCase()) >= 0
  }

  function toggleHidden(g) {
    var hide = !isHidden(g)
    var next = Object.assign({}, hiddenKeys)
    if (hide) next[g.store + ":" + g.app] = true
    else delete next[g.store + ":" + g.app]
    hiddenKeys = next
    runner.exec(["python3", helperPath, hide ? "hide" : "unhide", g.store, g.app])
  }

  // Keys the panel's key catcher passes on (it keeps h/j/k/l/x/Space for
  // itself): on the Games tab, "/" or any other character starts the filter.
  function textKey(t) {
    if (tab !== "games" || !t || t.charCodeAt(0) < 32) return
    filterField.forceActiveFocus()
    if (t !== "/") filterField.text += t
  }

  // The metal a rarity earns, as omatrophy.py's tier() picks it, so the
  // panel colours a percentage the way its toast would.
  function tierOf(pct) {
    if (pct === null || pct === undefined || pct > 35) return "bronze"
    return pct > 10 ? "silver" : "gold"
  }

  function preview(kind) {
    runner.exec(["python3", helperPath, "test", kind])
  }

  function day(t) {
    return t ? Qt.formatDate(new Date(t * 1000), "d MMM yyyy") : ""
  }

  // "12 min ago", "3 h ago", "yesterday", then the date.
  function ago(t) {
    if (!t) return ""
    var s = Date.now() / 1000 - t
    if (s < 3600) return Math.max(1, Math.round(s / 60)) + " min ago"
    if (s < 86400) return Math.round(s / 3600) + " h ago"
    if (s < 172800) return "yesterday"
    return day(t)
  }

  // Recent: last played first. Closest: unfinished games nearest 100%, then
  // the finished ones, then the untouched. Name: alphabetical.
  function gameOrder(a, b) {
    if (sort === "name") return a.game.localeCompare(b.game)
    if (sort === "recent") return (b.played - a.played) || a.game.localeCompare(b.game)
    var ra = a.unlocked === a.total ? 1 : (a.unlocked === 0 ? 2 : 0)
    var rb = b.unlocked === b.total ? 1 : (b.unlocked === 0 ? 2 : 0)
    if (ra !== rb) return ra - rb
    return (b.unlocked / b.total - a.unlocked / a.total) || ((a.total - a.unlocked) - (b.total - b.unlocked))
  }

  // "12 min", "1 h 05": how long the running game has been up.
  function duration(since) {
    var m = Math.max(0, Math.floor((Date.now() / 1000 - since) / 60))
    if (m < 60) return m + " min"
    var rest = m % 60
    return Math.floor(m / 60) + " h " + (rest < 10 ? "0" : "") + rest
  }

  spacing: Commons.Style.space(8)

  FileView {
    path: Quickshell.env("HOME") + "/.config/omatrophy/config.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var c = {}
      try { c = JSON.parse(text()) } catch (e) { return }
      if (c.icons) root.iconSet = c.icons
      if (c.position) root.position = c.position
      if (typeof c.sound === "boolean") root.sound = c.sound
      if (c.chimes) root.chimes = c.chimes
      var keys = {}
      if (Array.isArray(c.hidden)) c.hidden.forEach(function(k) { keys[k] = true })
      root.hiddenKeys = keys
    }
  }

  Process { id: runner }

  Process {
    id: gamesReader
    command: ["python3", root.helperPath, "games"]
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.games = JSON.parse(text) } catch (e) { root.games = [] }
      }
    }
  }

  Process {
    running: root.live
    command: ["python3", root.helperPath, "now"]
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.cabinet = JSON.parse(text) } catch (e) {}
      }
    }
  }

  // One trophy, drawn the way the cards draw it (the omarchy set's inlay
  // painted in the theme accent).
  component Thumb: Item {
    id: thumb
    property string style: "omarchy"
    property string metal: "bronze"
    width: 28
    height: 28
    Image {
      anchors.fill: parent
      source: Qt.resolvedUrl("assets/" + thumb.style + "/trophy-" + thumb.metal + (thumb.style === "painted" ? ".png" : ".svg"))
      sourceSize: Qt.size(128, 128)
      smooth: thumb.style !== "omarchy"
      mipmap: thumb.style === "painted"
    }
    Item {
      anchors.fill: parent
      visible: thumb.style === "omarchy"
      Rectangle { id: paint; anchors.fill: parent; color: Commons.Color.accent; visible: false; layer.enabled: true }
      Image {
        id: inlay
        anchors.fill: parent
        source: thumb.style === "omarchy" ? Qt.resolvedUrl("assets/omarchy/trophy-accent.svg") : ""
        sourceSize: Qt.size(128, 128)
        visible: false
      }
      MultiEffect { anchors.fill: parent; source: paint; maskEnabled: true; maskSource: inlay }
    }
  }

  // A big number over its label.
  component Stat: Column {
    property string value: ""
    property string label: ""
    property color tint: root.foreground
    spacing: Commons.Style.space(1)
    Text {
      textFormat: Text.PlainText
      text: parent.value
      color: parent.tint
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.display
      font.bold: true
    }
    MiniLabel { text: parent.label }
  }

  // Store art, cropped into a rounded frame. Steam's header art is 460 × 215;
  // delisted games can lack it, so the name stands in until it loads.
  component Art: Rectangle {
    id: art
    property string source: ""
    property string label: ""
    color: Qt.alpha(root.foreground, 0.06)
    radius: Commons.Style.cornerRadius
    clip: true
    Text {
      textFormat: Text.PlainText
      anchors.fill: parent
      anchors.margins: 4
      visible: artImage.status !== Image.Ready
      text: art.label
      color: root.foreground
      opacity: 0.5
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.caption
      horizontalAlignment: Text.AlignHCenter
      verticalAlignment: Text.AlignVCenter
      wrapMode: Text.Wrap
      elide: Text.ElideRight
    }
    Image {
      id: artImage
      anchors.fill: parent
      source: art.source
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      sourceSize.width: 460
    }
  }

  // An achievement icon; `locked` dims it the way the store greys it out.
  component AchIcon: Rectangle {
    property string source: ""
    property bool locked: false
    width: 22
    height: 22
    radius: 3
    color: Qt.alpha(root.foreground, 0.08)
    clip: true
    Image {
      anchors.fill: parent
      source: parent.source
      asynchronous: true
      sourceSize: Qt.size(64, 64)
      opacity: parent.locked ? 0.45 : 1
    }
  }

  // A progress bar that fills from empty when it first shows, so a tab's
  // bars read as progress rather than as static rules.
  component Bar: Rectangle {
    id: bar
    property real fraction: 0
    property color fill: Commons.Color.accent
    property bool grown: false
    height: 4
    radius: height / 2
    color: Qt.alpha(root.foreground, 0.1)
    Component.onCompleted: grown = true
    Rectangle {
      width: bar.grown ? bar.width * Math.max(0, Math.min(1, bar.fraction)) : 0
      height: parent.height
      radius: parent.radius
      color: bar.fill
      Behavior on width { NumberAnimation { duration: 650; easing.type: Easing.OutCubic } }
    }
  }

  // A tab's content, faded in and risen a few pixels each time it shows.
  component TabPage: Column {
    id: page
    property real rise: 0
    width: root.width
    transform: Translate { y: page.rise }
    onVisibleChanged: if (visible) enter.restart()
    ParallelAnimation {
      id: enter
      NumberAnimation { target: page; property: "opacity"; from: 0; to: 1; duration: 220; easing.type: Easing.OutCubic }
      NumberAnimation { target: page; property: "rise"; from: 8; to: 0; duration: 260; easing.type: Easing.OutCubic }
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
      width: Math.max(40, bone.width * 0.5)
      height: bone.height
      gradient: Gradient {
        orientation: Gradient.Horizontal
        GradientStop { position: 0; color: "transparent" }
        GradientStop { position: 0.5; color: Qt.alpha(root.foreground, 0.08) }
        GradientStop { position: 1; color: "transparent" }
      }
      NumberAnimation on x {
        from: -Math.max(40, bone.width * 0.5)
        to: bone.width
        duration: 1300
        loops: Animation.Infinite
        running: bone.visible
      }
    }
  }

  // The small spaced label used across the panel (stats, sections inside a
  // card, setting names).
  component MiniLabel: Text {
    color: root.foreground
    opacity: 0.55
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.caption
    font.letterSpacing: 1.5
  }

  component Caption: Text {
    color: root.foreground
    opacity: 0.6
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.caption
    elide: Text.ElideRight
  }

  // A row you can click to open the tracker on its game.
  component Hit: MouseArea {
    property var game: null
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: if (game) root.track(game.store, game.app)
  }

  // A quiet choice of a few options (the Games sort): plain words, the
  // chosen one on a soft accent pill. Lighter than ButtonGroup, so it
  // doesn't compete with the tabs above it.
  component Chips: Row {
    id: chips
    property var options: []
    property string value: ""
    signal picked(string value)
    spacing: Commons.Style.space(2)
    Repeater {
      model: chips.options
      delegate: Rectangle {
        id: chip
        required property var modelData
        readonly property bool chosen: chips.value === modelData.value
        width: chipText.implicitWidth + Commons.Style.space(16)
        height: chipText.implicitHeight + Commons.Style.space(8)
        radius: height / 2
        color: chosen ? Qt.alpha(Commons.Color.accent, 0.18) : (chipHit.containsMouse ? Commons.Style.hoverFill : "transparent")
        Accessible.role: Accessible.RadioButton
        Accessible.name: modelData.label
        Accessible.checked: chosen
        Behavior on color { ColorAnimation { duration: 120 } }
        Text {
          textFormat: Text.PlainText
          id: chipText
          anchors.centerIn: parent
          text: chip.modelData.label
          color: chip.chosen ? Commons.Color.accent : root.foreground
          opacity: chip.chosen ? 1 : 0.6
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.caption
          font.bold: chip.chosen
        }
        MouseArea {
          id: chipHit
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: chips.picked(chip.modelData.value)
        }
      }
    }
  }

  // Settings as label + control rows, so they read as one compact block.
  component SettingRow: Item {
    property string label: ""
    default property alias control: slot.data
    width: root.width
    height: Math.max(labelText.height, slot.childrenRect.height)
    MiniLabel {
      id: labelText
      anchors.verticalCenter: parent.verticalCenter
      text: parent.label
    }
    Item {
      id: slot
      anchors.right: parent.right
      anchors.verticalCenter: parent.verticalCenter
      width: childrenRect.width
      height: childrenRect.height
    }
  }

  // The tabs as an underlined strip, so they read as places in the panel
  // and the Games tab's sort buttons below them as controls.
  Item {
    id: tabStrip
    readonly property var tabs: [{ value: "now", label: "Now" }, { value: "games", label: "Games" }, { value: "settings", label: "Settings" }]
    readonly property real tabWidth: width / tabs.length
    readonly property int current: Math.max(0, tabs.findIndex(function(t) { return t.value === root.tab }))
    width: root.width
    height: Commons.Style.space(30)

    Rectangle {
      anchors.bottom: parent.bottom
      width: parent.width
      height: 1
      color: Qt.alpha(root.foreground, 0.12)
    }
    Rectangle {
      anchors.bottom: parent.bottom
      x: tabStrip.current * tabStrip.tabWidth + Commons.Style.space(14)
      width: tabStrip.tabWidth - Commons.Style.space(28)
      height: 2
      radius: 1
      color: Commons.Color.accent
      Behavior on x { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    }
    Row {
      anchors.fill: parent
      Repeater {
        model: tabStrip.tabs
        delegate: Item {
          id: tabItem
          required property var modelData
          required property int index
          readonly property bool active: root.tab === modelData.value
          width: tabStrip.tabWidth
          height: tabStrip.height
          Accessible.role: Accessible.PageTab
          Accessible.name: modelData.label
          Text {
            textFormat: Text.PlainText
            anchors.centerIn: parent
            anchors.verticalCenterOffset: -1
            text: tabItem.modelData.label
            color: root.foreground
            opacity: tabItem.active ? 1 : (tabHit.containsMouse ? 0.8 : 0.5)
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.body
            font.bold: tabItem.active
            Behavior on opacity { NumberAnimation { duration: 120 } }
          }
          MouseArea {
            id: tabHit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.tab = tabItem.modelData.value
          }
        }
      }
    }
  }

  // ---------------------------------------------------------------- Now

  TabPage {
    id: nowTab
    visible: root.tab === "now"
    width: root.width
    spacing: root.spacing

    // The totals, led by a platinum trophy in your style.
    Item {
      width: root.width
      height: Commons.Style.space(60)

      Thumb {
        id: heroTrophy
        anchors.verticalCenter: parent.verticalCenter
        style: root.iconSet
        metal: "platinum"
        width: 52
        height: 52
      }
      Row {
        anchors.left: heroTrophy.right
        anchors.leftMargin: Commons.Style.space(18)
        anchors.verticalCenter: parent.verticalCenter
        spacing: Commons.Style.space(22)
        Stat {
          value: root.cabinet ? root.cabinet.trophies.toLocaleString(Qt.locale(), "f", 0) : "–"
          label: "TROPHIES"
        }
        Stat {
          value: root.cabinet ? root.cabinet.platinums : "–"
          label: "PLATINUM"
          tint: root.metalColors.platinum
        }
        Stat {
          value: root.cabinet ? root.cabinet.games : "–"
          label: "GAMES"
        }
      }
    }

    // ------------------------------------------------ now playing

    // No section header: the banner's PLAYING chip says it.
    // The game you're playing: its hero art as a banner with the name on it,
    // then this session's unlocks and the likeliest next ones.
    Rectangle {
      id: playing
      readonly property var game: root.cabinet ? root.cabinet.playing : null
      visible: game !== null
      width: root.width
      height: visible ? playingBody.height + Commons.Style.space(10) : 0
      radius: Commons.Style.cornerRadius
      color: playHit.containsMouse ? Commons.Style.hoverFill : Qt.alpha(root.foreground, 0.04)
      clip: true
      Accessible.role: Accessible.Button
      Accessible.name: game ? "All achievements for " + game.game : ""

      Hit { id: playHit; game: playing.game }

      Column {
        id: playingBody
        width: parent.width
        spacing: Commons.Style.space(10)

        Item {
          id: banner
          width: parent.width
          height: Math.round(width * 0.42)

          // Library hero art carries no logo, so the name can sit on it;
          // the header (which has one) only stands in when there's no hero.
          Image {
            id: bannerArt
            anchors.fill: parent
            source: playing.game ? (playing.game.hero || playing.game.header || "") : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize.width: 900
            onStatusChanged: if (status === Image.Error && playing.game && source !== playing.game.header) source = playing.game.header
          }
          Rectangle {
            anchors.fill: parent
            gradient: Gradient {
              GradientStop { position: 0.35; color: "transparent" }
              GradientStop { position: 1.0; color: Qt.alpha(Commons.Color.popups.background, 0.92) }
            }
          }

          Rectangle {
            x: Commons.Style.space(10)
            y: Commons.Style.space(10)
            width: liveRow.width + Commons.Style.space(14)
            height: liveRow.height + Commons.Style.space(6)
            radius: height / 2
            color: Qt.alpha(Commons.Color.popups.background, 0.8)
            Row {
              id: liveRow
              anchors.centerIn: parent
              spacing: Commons.Style.space(6)
              Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 6
                height: 6
                radius: 3
                color: Commons.Color.accent
                SequentialAnimation on opacity {
                  loops: Animation.Infinite
                  NumberAnimation { to: 0.3; duration: 900; easing.type: Easing.InOutQuad }
                  NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutQuad }
                }
              }
              Text {
                textFormat: Text.PlainText
                text: playing.game ? "PLAYING · " + root.duration(playing.game.since) : ""
                color: root.foreground
                font.family: Commons.Style.font.family
                font.pixelSize: Commons.Style.font.caption
                font.letterSpacing: 1.2
                font.bold: true
              }
            }
          }

          // Name and count on the art, the percentage large beside them,
          // and the game's progress as the banner's bottom edge.
          Item {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: playBar.top
            anchors.margins: Commons.Style.space(12)
            height: Math.max(playNames.height, playPct.height)
            Column {
              id: playNames
              anchors.left: parent.left
              anchors.right: playPct.left
              anchors.rightMargin: Commons.Style.space(12)
              anchors.bottom: parent.bottom
              spacing: Commons.Style.space(2)
              Text {
                textFormat: Text.PlainText
                width: parent.width
                text: playing.game ? playing.game.game : ""
                color: root.foreground
                font.family: Commons.Style.font.family
                font.pixelSize: Commons.Style.font.heading
                font.bold: true
                elide: Text.ElideRight
              }
              Caption {
                width: parent.width
                opacity: 0.75
                text: playing.game ? playing.game.unlocked + " of " + playing.game.total + " unlocked" : ""
              }
            }
            Text {
              textFormat: Text.PlainText
              id: playPct
              anchors.right: parent.right
              anchors.bottom: parent.bottom
              anchors.bottomMargin: -3
              text: playing.game ? Math.floor(100 * playing.game.unlocked / playing.game.total) + "%" : ""
              color: root.foreground
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.display
              font.bold: true
            }
          }
          Bar {
            id: playBar
            anchors.bottom: parent.bottom
            width: parent.width
            height: 3
            radius: 0
            fraction: playing.game ? playing.game.unlocked / playing.game.total : 0
          }
        }

        // This session's unlocks, on the label's line.
        Item {
          x: Commons.Style.space(10)
          width: parent.width - Commons.Style.space(20)
          height: Math.max(sessionLabel.height, sessionIcons.height)
          MiniLabel {
            id: sessionLabel
            anchors.verticalCenter: parent.verticalCenter
            text: playing.game && playing.game.session.length ? "THIS SESSION · " + playing.game.session.length : "THIS SESSION"
          }
          Row {
            id: sessionIcons
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            spacing: Commons.Style.space(4)
            Caption {
              visible: playing.game !== null && playing.game.session.length === 0
              text: "nothing yet"
            }
            Repeater {
              // As many as fit beside the label, newest first.
              model: playing.game ? playing.game.session.slice(0, 9) : []
              delegate: AchIcon {
                required property var modelData
                source: modelData.icon
                width: 26
                height: 26
              }
            }
          }
        }

        MiniLabel {
          x: Commons.Style.space(10)
          visible: playing.game !== null && playing.game.next.length > 0
          text: "UP NEXT"
        }
        Column {
          x: Commons.Style.space(10)
          width: parent.width - Commons.Style.space(20)
          spacing: Commons.Style.space(6)
          Repeater {
            model: playing.game ? playing.game.next : []
            delegate: Item {
              id: nextRow
              required property var modelData
              width: parent.width
              height: Math.max(32, nextText.height)
              AchIcon { id: nextIcon; anchors.verticalCenter: parent.verticalCenter; source: nextRow.modelData.icon; locked: true; width: 32; height: 32 }
              Column {
                id: nextText
                anchors.left: nextIcon.right
                anchors.leftMargin: Commons.Style.space(10)
                anchors.right: pctText.left
                anchors.rightMargin: Commons.Style.space(10)
                anchors.verticalCenter: parent.verticalCenter
                spacing: Commons.Style.space(2)
                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  text: nextRow.modelData.name
                  color: root.foreground
                  font.family: Commons.Style.font.family
                  font.pixelSize: Commons.Style.font.bodySmall
                  elide: Text.ElideRight
                }
                Caption {
                  width: parent.width
                  visible: text !== ""
                  text: nextRow.modelData.desc
                }
                // A counter achievement shows how far along it is: a thin
                // bar under its text and the count beside the rarity.
                Bar {
                  visible: !!nextRow.modelData.progress
                  width: parent.width
                  height: 2
                  fraction: nextRow.modelData.progress ? nextRow.modelData.progress.value / nextRow.modelData.progress.max : 0
                }
              }
              // The rarity in the metal it would earn, the count under it.
              Column {
                id: pctText
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                spacing: Commons.Style.space(1)
                Text {
                  textFormat: Text.PlainText
                  anchors.right: parent.right
                  readonly property var pct: nextRow.modelData.percent
                  visible: pct !== null && pct !== undefined
                  text: visible ? pct.toFixed(1) + "%" : ""
                  color: root.metalColors[root.tierOf(pct)]
                  font.family: Commons.Style.font.family
                  font.pixelSize: Commons.Style.font.bodySmall
                  font.bold: true
                }
                Caption {
                  anchors.right: parent.right
                  visible: !!nextRow.modelData.progress
                  text: visible ? nextRow.modelData.progress.value + " / " + nextRow.modelData.progress.max : ""
                }
              }
            }
          }
        }

        Caption {
          anchors.right: parent.right
          anchors.rightMargin: Commons.Style.space(10)
          text: "All achievements →"
          color: Commons.Color.accent
          opacity: playHit.containsMouse ? 1 : 0.8
        }
      }
    }

    // ------------------------------------------------ recent games

    PanelSectionHeader {
      visible: recent.count > 0
      text: "RECENTLY PLAYED"
      foreground: root.foreground
    }

    Repeater {
      id: recent
      // The game you're playing takes this space; the rest wait for it to end.
      model: root.cabinet && !root.cabinet.playing ? root.cabinet.recent : []
      // A recent game: art, its latest unlocks, progress. A finished game
      // gets the platinum edge and date instead of a count.
      delegate: Rectangle {
        id: recentCard
        required property var modelData
        readonly property bool platinum: modelData.platinum > 0
        width: root.width
        height: Commons.Style.space(64)
        radius: Commons.Style.cornerRadius
        color: recentHit.containsMouse ? Commons.Style.hoverFill
               : (platinum ? Qt.alpha(root.metalColors.platinum, 0.05) : "transparent")
        Accessible.role: Accessible.Button
        Accessible.name: "All achievements for " + modelData.game

        Hit { id: recentHit; game: recentCard.modelData }

        // The toast's metal rail marks a finished game.
        Rectangle {
          visible: recentCard.platinum
          width: 3
          height: parent.height
          color: root.metalColors.platinum
        }

        Art {
          id: recentArt
          x: Commons.Style.space(8)
          anchors.verticalCenter: parent.verticalCenter
          height: parent.height - Commons.Style.space(8)
          width: Math.round(height * 460 / 215)
          source: recentCard.modelData.header || ""
          label: recentCard.modelData.game
        }
        Thumb {
          visible: recentCard.platinum
          anchors.right: recentArt.right
          anchors.bottom: recentArt.bottom
          anchors.margins: 2
          style: root.iconSet
          metal: "platinum"
          width: 20
          height: 20
        }

        Column {
          anchors.left: recentArt.right
          anchors.leftMargin: Commons.Style.space(10)
          anchors.right: parent.right
          anchors.rightMargin: Commons.Style.space(6)
          anchors.verticalCenter: parent.verticalCenter
          spacing: Commons.Style.space(4)

          Text {
            textFormat: Text.PlainText
            width: parent.width
            text: recentCard.modelData.game
            color: root.foreground
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.body
            font.bold: true
            elide: Text.ElideRight
          }
          Row {
            spacing: Commons.Style.space(3)
            Repeater {
              model: recentCard.modelData.latest
              delegate: AchIcon {
                required property var modelData
                source: modelData.icon
                width: 18
                height: 18
              }
            }
          }
          Bar {
            width: parent.width
            visible: !recentCard.platinum
            fraction: recentCard.modelData.unlocked / recentCard.modelData.total
          }
          Item {
            width: parent.width
            height: recentCount.height
            Caption {
              id: recentCount
              text: recentCard.platinum ? "Platinum · " + root.day(recentCard.modelData.platinum)
                    : recentCard.modelData.unlocked + " / " + recentCard.modelData.total
              color: recentCard.platinum ? root.metalColors.platinum : root.foreground
            }
            Caption {
              anchors.right: parent.right
              visible: !recentCard.platinum
              text: root.ago(recentCard.modelData.played)
            }
          }
        }
      }
    }

    // ------------------------------------------------ platinum shelf

    PanelSectionHeader {
      visible: shelf.count > 0
      text: "PLATINUM SHELF · " + shelf.count
      foreground: root.foreground
    }

    // Every platinum, in a grid whose tiles fit the width exactly.
    Grid {
      id: shelfGrid
      visible: shelf.count > 0
      columns: 4
      spacing: Commons.Style.space(6)
      readonly property real tileWidth: (root.width - spacing * (columns - 1)) / columns
      Repeater {
        id: shelf
        model: root.cabinet ? root.cabinet.shelf : []
        // Each platinum game's art with a metal edge; the date on hover.
        delegate: Rectangle {
          id: shelfCard
          required property var modelData
          width: shelfGrid.tileWidth
          height: Math.round(width * 215 / 460)
          radius: Commons.Style.cornerRadius
          color: "transparent"
          border.width: 1
          border.color: Qt.alpha(root.metalColors.platinum, shelfHit.containsMouse ? 1 : 0.45)
          z: shelfHit.containsMouse ? 1 : 0
          scale: shelfHit.containsMouse ? 1.06 : 1
          Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
          Accessible.role: Accessible.Button
          Accessible.name: modelData.game + ", platinum " + root.day(modelData.platinum)

          Art {
            anchors.fill: parent
            anchors.margins: 1
            source: shelfCard.modelData.header || ""
            label: shelfCard.modelData.game
          }
          Thumb {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 3
            style: root.iconSet
            metal: "platinum"
            width: 16
            height: 16
          }
          Hit { id: shelfHit; game: shelfCard.modelData }
          PanelToolTip {
            visible: shelfHit.containsMouse
            text: shelfCard.modelData.game + " · " + root.day(shelfCard.modelData.platinum)
          }
        }
      }
    }

    // Placeholders in the shape of what's coming while `now` reads the stores.
    Column {
      visible: root.cabinet === null
      width: root.width
      spacing: Commons.Style.space(10)
      Bone { width: parent.width; height: Math.round(parent.width * 0.36) }
      Bone { width: parent.width * 0.6; height: 10 }
      Bone { width: parent.width; height: 4 }
      Repeater {
        model: 3
        delegate: Row {
          spacing: Commons.Style.space(10)
          Bone { width: 28; height: 28 }
          Bone { width: root.width * 0.5; height: 10; anchors.verticalCenter: parent.verticalCenter }
        }
      }
      Bone { width: parent.width * 0.4; height: 10 }
      Row {
        spacing: Commons.Style.space(6)
        Repeater {
          model: 4
          delegate: Bone { width: shelfGrid.tileWidth; height: Math.round(width * 215 / 460) }
        }
      }
    }
  }

  // ---------------------------------------------------------------- Games

  TabPage {
    id: gamesTab
    visible: root.tab === "games"
    width: root.width
    spacing: Commons.Style.space(6)

    Item {
      width: root.width
      height: sortGroup.height
      MiniLabel {
        anchors.verticalCenter: parent.verticalCenter
        text: !root.games ? "GAMES"
              : root.sortedGames.length === root.games.length ? root.games.length + " GAMES"
              : root.sortedGames.length + " OF " + root.games.length + " GAMES"
      }
      Chips {
        id: sortGroup
        anchors.right: parent.right
        options: [
          { value: "recent", label: "Recent" },
          { value: "closest", label: "Closest" },
          { value: "name", label: "Name" }
        ]
        value: root.sort
        onPicked: value => root.sort = value
      }
    }

    TextField {
      id: filterField
      width: root.width
      visible: root.games !== null && root.games.length > 0
      placeholderText: "Filter by name ( / )"
      foreground: root.foreground
      font.pixelSize: Commons.Style.font.bodySmall
      verticalPadding: Commons.Style.space(4)
      onTextChanged: root.gameFilter = text
      // Enter opens the first match; Escape clears, then hands the keys
      // back to the panel; Tab leaves the field with the filter kept.
      Keys.onReturnPressed: if (root.sortedGames.length) root.track(root.sortedGames[0].store, root.sortedGames[0].app)
      Keys.onEnterPressed: if (root.sortedGames.length) root.track(root.sortedGames[0].store, root.sortedGames[0].app)
      Keys.onEscapePressed: {
        if (text) text = ""
        else focus = false
      }
      Keys.onTabPressed: focus = false
    }

    Repeater {
      model: root.shownGames
      // One game: art, name, count and a thin bar; a finished game carries
      // the platinum rail and date instead.
      delegate: Item {
        id: gameRow
        required property var modelData
        readonly property bool platinum: modelData.platinum > 0
        readonly property bool hiddenGame: root.isHidden(modelData)
        width: root.width
        height: Commons.Style.space(46)
        // A hidden game dims its art, name and bar, but not its Show link.
        readonly property real dim: hiddenGame ? 0.45 : 1
        Accessible.role: Accessible.Button
        Accessible.name: "All achievements for " + modelData.game

        Rectangle {
          anchors.fill: parent
          radius: Commons.Style.cornerRadius
          color: gameHit.containsMouse ? Commons.Style.hoverFill
                 : (gameRow.platinum ? Qt.alpha(root.metalColors.platinum, 0.05) : "transparent")
        }
        Rectangle {
          visible: gameRow.platinum
          width: 3
          height: parent.height
          color: root.metalColors.platinum
        }
        Hit { id: gameHit; game: gameRow.modelData }

        Art {
          id: gameArt
          x: Commons.Style.space(8)
          anchors.verticalCenter: parent.verticalCenter
          height: parent.height - Commons.Style.space(8)
          width: Math.round(height * 460 / 215)
          source: gameRow.modelData.header || ""
          opacity: gameRow.dim
        }
        Thumb {
          visible: gameRow.platinum
          anchors.right: gameArt.right
          anchors.bottom: gameArt.bottom
          anchors.margins: 2
          style: root.iconSet
          metal: "platinum"
          width: 16
          height: 16
        }
        Column {
          anchors.left: gameArt.right
          anchors.leftMargin: Commons.Style.space(10)
          anchors.right: parent.right
          anchors.rightMargin: Commons.Style.space(6)
          anchors.verticalCenter: parent.verticalCenter
          spacing: Commons.Style.space(3)
          Item {
            width: parent.width
            height: gameName.height
            Text {
              textFormat: Text.PlainText
              id: gameName
              width: parent.width - gameCount.width - Commons.Style.space(8)
                     - (hideToggle.visible ? hideToggle.width + Commons.Style.space(8) : 0)
              text: gameRow.modelData.game
              color: root.foreground
              opacity: gameRow.dim
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
              font.bold: true
              elide: Text.ElideRight
            }
            // Hide or show this game; only on hover, or always for a
            // hidden one so it can come back.
            Text {
              textFormat: Text.PlainText
              id: hideToggle
              anchors.right: gameCount.left
              anchors.rightMargin: Commons.Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
              visible: !gameRow.platinum && (gameHit.containsMouse || hideHit.containsMouse || gameRow.hiddenGame)
              text: gameRow.hiddenGame ? "Show" : "Hide"
              color: Commons.Color.accent
              opacity: hideHit.containsMouse ? 1 : 0.75
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.caption
              MouseArea {
                id: hideHit
                anchors.fill: parent
                anchors.margins: -4
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.toggleHidden(gameRow.modelData)
              }
            }
            // The percentage leads; a platinum says so in its metal.
            Text {
              textFormat: Text.PlainText
              id: gameCount
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              text: gameRow.platinum ? "PLATINUM" : Math.floor(100 * gameRow.modelData.unlocked / gameRow.modelData.total) + "%"
              color: gameRow.platinum ? root.metalColors.platinum : root.foreground
              opacity: (gameRow.platinum ? 1 : 0.85) * gameRow.dim
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.caption
              font.letterSpacing: gameRow.platinum ? 1.5 : 0
              font.bold: true
            }
          }
          Bar {
            width: parent.width
            height: 3
            opacity: gameRow.dim
            fraction: gameRow.modelData.unlocked / gameRow.modelData.total
            fill: gameRow.platinum ? root.metalColors.platinum : Commons.Color.accent
          }
          Item {
            width: parent.width
            height: gameMeta.height
            Caption {
              id: gameMeta
              opacity: 0.5 * gameRow.dim
              text: gameRow.modelData.unlocked + " / " + gameRow.modelData.total
            }
            Caption {
              anchors.right: parent.right
              opacity: 0.5 * gameRow.dim
              text: gameRow.platinum ? root.day(gameRow.modelData.platinum) : root.ago(gameRow.modelData.played)
            }
          }
        }
      }
    }

    Item {
      width: root.width
      height: moreLink.height + Commons.Style.space(8)
      visible: root.sortedGames.length > root.gamesShown
      Accessible.role: Accessible.Button
      Accessible.name: moreLink.text
      Text {
        textFormat: Text.PlainText
        id: moreLink
        anchors.centerIn: parent
        text: "Show " + Math.min(root.gamesPage, root.sortedGames.length - root.gamesShown)
              + " more · " + (root.sortedGames.length - root.gamesShown) + " left"
        color: Commons.Color.accent
        opacity: moreHit.containsMouse ? 1 : 0.75
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.caption
      }
      MouseArea {
        id: moreHit
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.gamesShown += root.gamesPage
      }
    }

    Caption {
      width: root.width
      horizontalAlignment: Text.AlignHCenter
      visible: root.games !== null && root.games.length > 0 && root.sortedGames.length === 0
      text: root.gameFilter ? "No game matches “" + root.gameFilter + "”" : "Every game here is hidden"
    }

    Caption {
      width: root.width
      horizontalAlignment: Text.AlignHCenter
      visible: root.sort === "closest" && root.hiddenCount > 0
      text: root.hiddenCount + (root.hiddenCount === 1 ? " hidden game" : " hidden games")
            + " left out; Recent and Name still list them"
      opacity: 0.45
    }

    Repeater {
      model: root.games === null ? 8 : 0
      delegate: Row {
        spacing: Commons.Style.space(10)
        height: Commons.Style.space(46)
        Bone { width: Math.round(height * 460 / 215); height: Commons.Style.space(38); anchors.verticalCenter: parent.verticalCenter }
        Column {
          anchors.verticalCenter: parent.verticalCenter
          spacing: Commons.Style.space(6)
          Bone { width: root.width * 0.45; height: 10 }
          Bone { width: root.width * 0.7; height: 3 }
        }
      }
    }
  }

  // ---------------------------------------------------------- Settings

  TabPage {
    id: settingsTab
    visible: root.tab === "settings"
    width: root.width
    spacing: root.spacing

    PanelSectionHeader { text: "TROPHY STYLE"; foreground: root.foreground }

    Row {
      id: styleCards
      spacing: Commons.Style.space(6)
      readonly property real cardWidth: (root.width - spacing * (root.styles.length - 1)) / root.styles.length
      Repeater {
        model: root.styles
        // A card per style: its gold trophy and name. The chosen one carries
        // the accent edge.
        delegate: Rectangle {
          id: styleCard
          required property var modelData
          readonly property bool chosen: root.iconSet === modelData.id
          width: styleCards.cardWidth
          height: Commons.Style.space(70)
          radius: Commons.Style.cornerRadius
          color: chosen ? Commons.Style.selectedFill : (pick.containsMouse ? Commons.Style.hoverFill : Qt.alpha(root.foreground, 0.04))
          border.width: 1
          border.color: chosen ? Commons.Color.accent : Qt.alpha(root.foreground, 0.12)
          Accessible.role: Accessible.Button
          Accessible.name: modelData.name + " trophies" + (chosen ? ", in use" : "")

          MouseArea {
            id: pick
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.set("icons", styleCard.modelData.id)
          }
          Column {
            anchors.centerIn: parent
            spacing: Commons.Style.space(5)
            Thumb {
              anchors.horizontalCenter: parent.horizontalCenter
              style: styleCard.modelData.id
              metal: "gold"
              width: 34
              height: 34
            }
            Text {
              textFormat: Text.PlainText
              anchors.horizontalCenter: parent.horizontalCenter
              text: styleCard.modelData.name
              color: root.foreground
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.caption
              font.bold: styleCard.chosen
            }
          }
        }
      }
    }

    Item { width: 1; height: Commons.Style.space(2) }

    SettingRow {
      label: "PREVIEW"
      Row {
        spacing: Commons.Style.space(6)
        Repeater {
          model: root.metals
          // A tile per metal that fires a real toast; its edge is the metal.
          delegate: Rectangle {
            id: tile
            required property string modelData
            width: Commons.Style.space(40)
            height: Commons.Style.space(34)
            radius: Commons.Style.cornerRadius
            color: fire.pressed ? Qt.alpha(root.metalColors[modelData], 0.22)
                   : (fire.containsMouse ? Qt.alpha(root.metalColors[modelData], 0.12) : Qt.alpha(root.foreground, 0.04))
            border.width: 1
            border.color: Qt.alpha(root.metalColors[modelData], fire.containsMouse ? 0.8 : 0.35)
            Accessible.role: Accessible.Button
            Accessible.name: "Show a " + modelData + " toast now"

            MouseArea {
              id: fire
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.preview(tile.modelData)
            }
            Thumb {
              anchors.centerIn: parent
              style: root.iconSet
              metal: tile.modelData
              width: 22
              height: 22
            }
          }
        }
      }
    }

    SettingRow {
      label: "POSITION"
      ButtonGroup {
        options: [
          { value: "top-left", label: "Left" },
          { value: "top-center", label: "Center" },
          { value: "top-right", label: "Right" }
        ]
        value: root.position
        foreground: root.foreground
        fontSize: Commons.Style.font.bodySmall
        onChanged: value => root.set("position", value)
      }
    }

    SettingRow {
      label: "SOUND"
      ButtonGroup {
        options: [
          { value: "omatrophy", label: "OmaTrophy" },
          { value: "classic", label: "Classic" },
          { value: "off", label: "Silent" }
        ]
        value: root.sound ? root.chimes : "off"
        foreground: root.foreground
        fontSize: Commons.Style.font.bodySmall
        onChanged: value => root.set("sound", value)
      }
    }
  }
}
