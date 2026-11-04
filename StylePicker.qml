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
//
// Sections, in order, each under a "// ---- Name" banner: State, Helpers,
// Files and processes, Building blocks, Tab strip, Now, Profile, Games,
// Settings.
Column {
  id: root
  spacing: Commons.Style.space(8)

  // ------------------------------------------------------------------ State

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
  property string glass: "frosted"
  property bool community: false
  // The Steam profile backfill's latest line, from its status.json
  // (stores/steam_community.py); {} before the first run.
  property var backfill: ({})

  // From `omatrophy.py now`; null until it answers. dev/render.sh turns
  // `live` off and sets `cabinet` to sample data.
  property var cabinet: null
  property bool live: true
  // The JSON text behind `cabinet` and `games`: a fresh read that matches
  // the cached copy is dropped, so the rows don't rebuild and animate in a
  // second time a moment after the panel opens.
  property string cabinetText: ""
  property string gamesText: ""
  // From `omatrophy.py games`, read the first time the Games tab opens.
  property var games: null
  property string sort: "recent"
  // The Now tab's sections, from config.json's now-* switches (all on
  // unless switched off in Settings).
  readonly property var nowSections: [
    { value: "metals", label: "Metals" },
    { value: "recent", label: "Recent" },
    { value: "rarest", label: "Rarest" },
    { value: "shelf", label: "Shelf" }
  ]
  property var nowShows: ({ metals: true, recent: true, rarest: true, shelf: true })
  // Which rarest unlocks the Now tab lists: "ever", "month" or "platinum"
  // (from finished games only).
  property string rarestRange: "ever"
  // Typed into the Games tab's filter field; matches game names.
  property string gameFilter: ""
  // "store:app" keys from config.json's `hidden`, kept live so a toggle
  // shows at once; hidden games leave Closest and dim elsewhere.
  property var hiddenKeys: ({})
  readonly property var sortedGames: games ? games.filter(showGame).sort(gameOrder) : []
  readonly property int hiddenCount: games ? games.filter(function(g) { return isHidden(g) }).length : 0
  // With the community backfill a library runs to hundreds of games, and a
  // row each made the panel slow to open: the list shows a short page, about
  // half the panel, with a pager under it. Filter and sort see every game
  // first; changing either goes back to the first page.
  readonly property int gamesPage: 8
  property int gamesPageIndex: 0
  readonly property int gamesPageCount: Math.max(1, Math.ceil(sortedGames.length / gamesPage))
  readonly property var shownGames: sortedGames.slice(gamesPageIndex * gamesPage, (gamesPageIndex + 1) * gamesPage)
  onSortChanged: gamesPageIndex = 0
  onGameFilterChanged: gamesPageIndex = 0
  onGamesPageCountChanged: gamesPageIndex = Math.min(gamesPageIndex, gamesPageCount - 1)
  // True while the filter field has the keyboard; Panel.qml then lets keys
  // through to it instead of its own shortcuts.
  readonly property bool typing: filterField.activeFocus

  // The Games tab reads once per open; a copy from the last read (below)
  // shows until it answers.
  property bool gamesRead: false
  onTabChanged: if (tab === "games" && !gamesRead && live) { gamesRead = true; gamesReader.running = true }

  // Asks Panel.qml to open the tracker on one game; the panel owns the
  // shell handle, this file only knows the game.
  signal track(string store, string app, string api)

  // ---------------------------------------------------------------- Helpers

  function set(key, value) {
    if (key === "icons") iconSet = value
    if (key === "position") position = value
    if (key === "glass") glass = value
    if (key === "community") community = value === "on"
    if (key.indexOf("now-") === 0) {
      var shows = Object.assign({}, nowShows)
      shows[key.slice(4)] = value === "on"
      nowShows = shows
    }
    if (key === "sound") {
      sound = value !== "off"
      if (value !== "on" && value !== "off") chimes = value
    }
    runner.exec(["python3", helperPath, "set", key, value])
  }

  function isHidden(g) {
    return !!hiddenKeys[g.store + ":" + g.app]
  }

  // One store's row from `now` ({id, name, found, games}), or null before
  // the first read.
  function storeInfo(id) {
    if (!cabinet || !cabinet.stores) return null
    return cabinet.stores.find(function(s) { return s.id === id }) || null
  }

  // A view choice (a sort, the rarest list) shows at once and is kept in
  // config.json, written only when it changes, so the next open shows the
  // same view.
  function remember(key, property, value) {
    if (root[property] === value) return
    root[property] = value
    runner.exec(["python3", helperPath, "set", key, value])
  }

  // Minutes as whole hours, "552 h"; under an hour, "42 min".
  function hours(minutes) {
    if (minutes < 60) return minutes + " min"
    return Math.round(minutes / 60).toLocaleString(Qt.locale(), "f", 0) + " h"
  }

  // Showcase picks taken off since the last read: gone at once, without
  // rebuilding the whole tab.
  property var unpinned: ({})

  function unpin(pick) {
    var gone = Object.assign({}, unpinned)
    gone[pick.key] = true
    unpinned = gone
    var args = ["python3", helperPath, "showcase", "remove", String(pick.store), String(pick.app)]
    runner.exec(pick.api ? args.concat([pick.api]) : args)
  }

  // The rows of a list whose game isn't hidden.
  function unhidden(rows) {
    return rows.filter(function(g) { return !isHidden(g) })
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

  // The pager's buttons: every page when there are few, otherwise the
  // first, the last and the current one with its neighbours, with -1
  // standing for a gap ("1 … 4 5 6 … 16").
  function pageButtons(current, count) {
    if (count <= 7) return Array.from({ length: count }, function(_, i) { return i })
    var pages = [0]
    var from = Math.max(1, Math.min(current - 1, count - 4))
    var to = Math.min(count - 2, Math.max(current + 1, 3))
    if (from > 1) pages.push(-1)
    for (var i = from; i <= to; i++) pages.push(i)
    if (to < count - 2) pages.push(-1)
    pages.push(count - 1)
    return pages
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

  // What the backfill row says under its switch: what turning it on sends
  // while off, then the latest run, so a slow fill or Steam's rate limit
  // is visible without the shell log.
  function backfillText() {
    if (!community)
      return "Fills in games this machine never ran from your public Steam profile. On sends your SteamID64 to steamcommunity.com."
    var b = backfill
    if (!b || !b.time) return "On. The first pages come within the hour, then more every hour."
    var at = Qt.formatTime(new Date(b.time * 1000), "hh:mm")
    if (b.limited)
      return "Steam asked for a pause at " + at + ". The next run waits a few hours and fetches fewer pages."
    return "Last run " + at + " · " + b.line
  }

  // ---------------------------------------------------- Files and processes
  // What the panel reads (settings, the last answers, the backfill's
  // status) and the omatrophy.py calls that fill it.

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
      if (c.glass) root.glass = c.glass
      root.community = c.community === true
      if (c["games-sort"]) root.sort = c["games-sort"]
      if (c.rarest) root.rarestRange = c.rarest
      var shows = {}
      root.nowSections.forEach(function(n) { shows[n.value] = c["now-" + n.value] !== false })
      root.nowShows = shows
      var keys = {}
      if (Array.isArray(c.hidden)) c.hidden.forEach(function(k) { keys[k] = true })
      root.hiddenKeys = keys
    }
  }

  // The last `now` and `games` answers, kept by omatrophy.py. This file is
  // rebuilt on every open, so without them each open showed bones while
  // Python read the stores again; with them the panel opens filled and the
  // fresh read replaces the copy a moment later.
  FileView {
    path: root.live ? Quickshell.env("HOME") + "/.cache/omatrophy/panel/now.json" : ""
    blockLoading: true
    printErrors: false
    onLoaded: {
      if (root.cabinet !== null) return
      try { root.cabinet = JSON.parse(text()); root.cabinetText = text().trim() } catch (e) {}
    }
  }
  FileView {
    path: root.live ? Quickshell.env("HOME") + "/.cache/omatrophy/panel/games.json" : ""
    blockLoading: true
    printErrors: false
    onLoaded: {
      if (root.games !== null) return
      try { root.games = JSON.parse(text()); root.gamesText = text().trim() } catch (e) {}
    }
  }

  FileView {
    path: root.live ? Quickshell.env("HOME") + "/.cache/omatrophy/community/status.json" : ""
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try { root.backfill = JSON.parse(text()) } catch (e) {}
    }
  }

  Process { id: runner }

  Process {
    id: gamesReader
    command: ["python3", root.helperPath, "games"]
    stdout: StdioCollector {
      onStreamFinished: {
        // A failed read keeps the last copy rather than emptying the list.
        if (text.trim() === root.gamesText) return
        try { root.games = JSON.parse(text); root.gamesText = text.trim() } catch (e) { if (root.games === null) root.games = [] }
      }
    }
  }

  Process {
    running: root.live
    command: ["python3", root.helperPath, "now"]
    stdout: StdioCollector {
      onStreamFinished: {
        if (text.trim() === root.cabinetText) return
        try { root.cabinet = JSON.parse(text); root.cabinetText = text.trim() } catch (e) {}
      }
    }
  }

  // -------------------------------------------------------- Building blocks
  // Inline components, kept in this file because FreshObject builds it
  // from its text alone (ADR 10): it can't load sibling QML types.

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
  // A big number over its label; it counts up to a new value, so totals
  // arriving read as a tally rather than a jump. -1 shows a dash.
  component Stat: Column {
    id: stat
    property real value: -1
    property string label: ""
    property color tint: root.foreground
    // Put after the number ("%").
    property string suffix: ""
    property real shown: 0
    onValueChanged: if (value >= 0) shown = value
    Component.onCompleted: if (value >= 0) shown = value
    Behavior on shown { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
    spacing: Commons.Style.space(1)
    Text {
      textFormat: Text.PlainText
      text: stat.value < 0 ? "–" : Math.round(stat.shown).toLocaleString(Qt.locale(), "f", 0) + stat.suffix
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
    // `zoom` scales the art inside its frame (a hover), so it can never
    // grow past the panel's edge the way scaling the whole tile did.
    property real zoom: 1
    Image {
      id: artImage
      anchors.fill: parent
      source: art.source
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      sourceSize.width: 460
      opacity: status === Image.Ready ? 1 : 0
      scale: art.zoom
      Behavior on opacity { NumberAnimation { duration: 260 } }
      Behavior on scale { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
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
      opacity: status !== Image.Ready ? 0 : (parent.locked ? 0.45 : 1)
      Behavior on opacity { NumberAnimation { duration: 220 } }
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

  // Brings a freshly built row or card in: a short wait by its place in
  // the list (capped, so long lists don't drag), then a fade and a small
  // rise. The item starts at opacity 0.
  component FadeIn: SequentialAnimation {
    id: fade
    property Item item
    property int order: 0
    running: true
    PauseAnimation { duration: Math.min(fade.order, 10) * 35 }
    ParallelAnimation {
      NumberAnimation { target: fade.item; property: "opacity"; to: 1; duration: 240; easing.type: Easing.OutCubic }
      NumberAnimation { target: fade.item; property: "rise"; from: 6; to: 0; duration: 280; easing.type: Easing.OutCubic }
    }
  }

  // A tab's content, faded in each time it shows. It goes to opacity 0 as
  // it hides, so it never shows a frame at full opacity before the fade
  // starts; that frame, plus a rise on top of the panel snapping to the new
  // tab's height, read as a jump.
  component TabPage: Column {
    id: page
    width: root.width
    // Tabs that start hidden fade in on their first show too.
    Component.onCompleted: if (!visible) opacity = 0
    onVisibleChanged: {
      if (visible) {
        enter.restart()
        return
      }
      enter.stop()
      opacity = 0
    }
    NumberAnimation { id: enter; target: page; property: "opacity"; to: 1; duration: 160; easing.type: Easing.OutCubic }
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
    // A row naming one achievement (a rarest unlock) opens on it.
    onClicked: if (game) root.track(game.store, game.app, game.api || "")
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
    width: parent ? parent.width : root.width
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

  // A store in Settings: a card with its name and what OmaTrophy found
  // there, then that store's own rows, shown only once it is found.
  component StoreCard: Rectangle {
    id: card
    property string storeId: ""
    // What to do when the store isn't found, and a line once it is.
    property string missing: ""
    property string note: ""
    default property alias rows: storeRows.data
    readonly property var info: root.storeInfo(storeId)
    readonly property bool found: info !== null && info.found
    width: root.width
    height: storeBody.height + Commons.Style.space(24)
    radius: Commons.Style.cornerRadius
    color: Qt.alpha(root.foreground, 0.04)
    border.width: 1
    border.color: Qt.alpha(root.foreground, 0.12)
    Column {
      id: storeBody
      x: Commons.Style.space(12)
      y: Commons.Style.space(12)
      width: parent.width - Commons.Style.space(24)
      spacing: Commons.Style.space(8)
      Item {
        width: parent.width
        height: storeName.height
        Text {
          textFormat: Text.PlainText
          id: storeName
          text: card.info ? card.info.name : ""
          color: root.foreground
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
          font.bold: true
        }
        Row {
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          spacing: Commons.Style.space(6)
          Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: 6
            height: 6
            radius: 3
            color: card.found ? Commons.Color.accent : Qt.alpha(root.foreground, 0.3)
          }
          Caption {
            text: card.info === null ? "…" : card.found
              ? card.info.games + (card.info.games === 1 ? " game" : " games")
              : "Not found"
          }
        }
      }
      Caption {
        width: parent.width
        visible: text !== ""
        wrapMode: Text.WordWrap
        elide: Text.ElideNone
        opacity: 0.45
        text: card.info === null ? "" : card.found ? card.note : card.missing
      }
      Column {
        id: storeRows
        visible: card.found
        width: parent.width
        spacing: Commons.Style.space(8)
      }
    }
  }

  // -------------------------------------------------------------- Tab strip

  // The tabs as an underlined strip, so they read as places in the panel
  // and the Games tab's sort buttons below them as controls.
  Item {
    id: tabStrip
    readonly property var tabs: [{ value: "now", label: "Now" }, { value: "profile", label: "Profile" }, { value: "games", label: "Games" }, { value: "settings", label: "Settings" }]
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

  // -------------------------------------------------------------------- Now

  TabPage {
    id: nowTab
    visible: root.tab === "now"
    width: root.width
    spacing: root.spacing

    // The totals, led by a platinum trophy in your style.
    Item {
      width: root.width
      height: Commons.Style.space(76)

      // A soft platinum halo behind the trophy, in rings, since the
      // offscreen renderer and older GPUs drop blur effects.
      Repeater {
        model: 3
        delegate: Rectangle {
          required property int index
          readonly property real size: heroTrophy.width + 6 + index * 10
          x: heroTrophy.x + (heroTrophy.width - size) / 2
          y: heroTrophy.y + (heroTrophy.height - size) / 2
          width: size
          height: size
          radius: size / 2
          color: Qt.alpha(root.metalColors.platinum, 0.025)
        }
      }
      Thumb {
        id: heroTrophy
        x: Commons.Style.space(10)
        anchors.verticalCenter: parent.verticalCenter
        style: root.iconSet
        metal: "platinum"
        width: 48
        height: 48
      }
      Row {
        anchors.left: heroTrophy.right
        anchors.leftMargin: Commons.Style.space(30)
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        spacing: Commons.Style.space(16)
        Stat {
          value: root.cabinet ? root.cabinet.trophies : -1
          label: "TROPHIES"
        }
        Rectangle { width: 1; height: Commons.Style.space(34); anchors.verticalCenter: parent.verticalCenter; color: Qt.alpha(root.foreground, 0.12) }
        Stat {
          value: root.cabinet ? root.cabinet.platinums : -1
          label: "PLATINUM"
          tint: root.metalColors.platinum
        }
        Rectangle { width: 1; height: Commons.Style.space(34); anchors.verticalCenter: parent.verticalCenter; color: Qt.alpha(root.foreground, 0.12) }
        Stat {
          value: root.cabinet ? root.cabinet.games : -1
          label: "GAMES"
        }
      }
    }

    // Every trophy by the metal its toast would have, as one bar, with the
    // average completion of the games you've started beside it.
    Column {
      id: metalTally
      readonly property var metals: root.cabinet && root.cabinet.metals ? root.cabinet.metals : null
      readonly property int total: metals ? metals.bronze + metals.silver + metals.gold : 0
      property bool grown: false
      visible: total > 0 && root.nowShows.metals
      width: root.width
      spacing: Commons.Style.space(6)
      Component.onCompleted: grown = true
      Row {
        width: parent.width
        height: 4
        spacing: 2
        Repeater {
          model: ["gold", "silver", "bronze"]
          delegate: Rectangle {
            required property string modelData
            readonly property int count: metalTally.metals ? metalTally.metals[modelData] : 0
            visible: count > 0
            height: 4
            radius: 2
            width: metalTally.grown && metalTally.total > 0 ? Math.max(4, (metalTally.width - 4) * count / metalTally.total) : 0
            color: root.metalColors[modelData]
            Behavior on width { NumberAnimation { duration: 650; easing.type: Easing.OutCubic } }
          }
        }
      }
      Item {
        width: parent.width
        height: metalLegend.height
        Row {
          id: metalLegend
          spacing: Commons.Style.space(12)
          Repeater {
            model: ["gold", "silver", "bronze"]
            delegate: Row {
              required property string modelData
              spacing: Commons.Style.space(5)
              Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 6
                height: 6
                radius: 3
                color: root.metalColors[modelData]
              }
              Caption {
                text: (metalTally.metals ? metalTally.metals[modelData].toLocaleString(Qt.locale(), "f", 0) : "") + " " + modelData
              }
            }
          }
        }
        Caption {
          anchors.right: parent.right
          text: (root.cabinet ? root.cabinet.completion : 0) + "% avg completion"
        }
      }
    }

    // ------------------------------------------------ first run

    // No game with achievements yet: say where they come from instead of
    // an empty tab, and point at the Steam profile switch, which fills in
    // games this machine never ran.
    Rectangle {
      id: firstRun
      visible: root.cabinet !== null && root.cabinet.games === 0
      width: root.width
      height: firstRunBody.height + Commons.Style.space(28)
      radius: Commons.Style.cornerRadius
      color: Qt.alpha(root.foreground, 0.04)
      border.width: 1
      border.color: Qt.alpha(root.foreground, 0.12)
      Column {
        id: firstRunBody
        x: Commons.Style.space(14)
        y: Commons.Style.space(14)
        width: parent.width - Commons.Style.space(28)
        spacing: Commons.Style.space(8)
        Text {
          textFormat: Text.PlainText
          text: "No achievements yet"
          color: root.foreground
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.body
          font.bold: true
        }
        Caption {
          width: parent.width
          wrapMode: Text.WordWrap
          elide: Text.ElideNone
          text: "Play a game with achievements on Steam, or on GOG through Heroic, and it shows up here. Your first unlock brings a toast."
        }
        Caption {
          width: parent.width
          wrapMode: Text.WordWrap
          elide: Text.ElideNone
          text: root.community
            ? "Steam profile fill-in is on: games you played on other machines arrive over the next hours."
            : "Played on another machine? Turn on Steam profile in Settings to fill in those games."
        }
        Caption {
          visible: !root.community
          text: "Open Settings →"
          color: Commons.Color.accent
          opacity: firstRunHit.containsMouse ? 1 : 0.8
          Accessible.role: Accessible.Button
          Accessible.name: "Open Settings"
          MouseArea {
            id: firstRunHit
            anchors.fill: parent
            anchors.margins: -4
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: root.tab = "settings"
          }
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
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 350 } }
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
              // Each unlock pops in, newest first.
              delegate: AchIcon {
                id: sessionIcon
                required property var modelData
                required property int index
                source: modelData.icon
                width: 26
                height: 26
                scale: 0
                SequentialAnimation {
                  running: true
                  PauseAnimation { duration: 120 + Math.min(sessionIcon.index, 8) * 50 }
                  NumberAnimation { target: sessionIcon; property: "scale"; to: 1; duration: 320; easing.type: Easing.OutBack }
                }
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
              required property int index
              property real rise: 0
              opacity: 0
              transform: Translate { y: nextRow.rise }
              FadeIn { item: nextRow; order: nextRow.index + 1 }
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
      model: root.cabinet && !root.cabinet.playing && root.nowShows.recent ? root.cabinet.recent : []
      // A recent game: art, its latest unlocks, progress. A finished game
      // gets the platinum edge and date instead of a count.
      delegate: Rectangle {
        id: recentCard
        required property var modelData
        required property int index
        readonly property bool platinum: modelData.platinum > 0
        property real rise: 0
        opacity: 0
        transform: Translate { y: recentCard.rise }
        FadeIn { item: recentCard; order: recentCard.index }
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
          zoom: recentHit.containsMouse ? 1.06 : 1
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
            // How many more unlocks than the icons show, like Steam's "+8".
            Rectangle {
              readonly property int more: recentCard.modelData.unlocked - recentCard.modelData.latest.length
              visible: more > 0
              width: moreText.implicitWidth + 8
              height: 18
              radius: 3
              color: Qt.alpha(root.foreground, 0.08)
              Text {
                textFormat: Text.PlainText
                id: moreText
                anchors.centerIn: parent
                text: "+" + parent.more
                color: root.foreground
                opacity: 0.7
                font.family: Commons.Style.font.family
                font.pixelSize: 10
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
              // Hours on record first, when the store keeps them.
              text: (recentCard.modelData.minutes > 0 ? root.hours(recentCard.modelData.minutes) + " · " : "")
                    + root.ago(recentCard.modelData.played)
            }
          }
        }
      }
    }

    // ------------------------------------------------ rarest unlocks

    // The rarest trophies across the whole library, ever or this month.
    // Rarity comes from the watcher's cache, so this costs no request.
    Item {
      id: rarestHeader
      readonly property var lists: root.cabinet && root.cabinet.rarest ? root.cabinet.rarest : null
      // A game hidden since the last read leaves at once; `now` sends a
      // couple spare unlocks so three still show.
      readonly property var ever: lists ? root.unhidden(lists.ever).slice(0, 3) : []
      readonly property var month: lists ? root.unhidden(lists.month).slice(0, 3) : []
      readonly property var platinum: lists && lists.platinum ? root.unhidden(lists.platinum).slice(0, 3) : []
      visible: ever.length > 0 && root.nowShows.rarest
      width: root.width
      height: rarestChips.height
      PanelSectionHeader {
        anchors.left: parent.left
        anchors.verticalCenter: parent.verticalCenter
        text: "RAREST UNLOCKS"
        foreground: root.foreground
      }
      Chips {
        id: rarestChips
        anchors.right: parent.right
        options: [
          { value: "ever", label: "Ever" },
          { value: "month", label: "This month" },
          { value: "platinum", label: "Platinums" }
        ]
        value: root.rarestRange
        onPicked: value => root.remember("rarest", "rarestRange", value)
      }
    }

    Column {
      visible: rarestHeader.visible
      width: root.width
      spacing: Commons.Style.space(6)
      Repeater {
        model: rarestHeader[root.rarestRange]
        delegate: Item {
          id: rareRow
          required property var modelData
          required property int index
          property real rise: 0
          opacity: 0
          transform: Translate { y: rareRow.rise }
          FadeIn { item: rareRow; order: rareRow.index }
          width: parent.width
          height: Math.max(32, rareText.height)
          Accessible.role: Accessible.Button
          Accessible.name: modelData.name + ", " + modelData.game + ", " + modelData.percent.toFixed(1) + " percent"
          AchIcon { id: rareIcon; anchors.verticalCenter: parent.verticalCenter; source: rareRow.modelData.icon; width: 32; height: 32 }
          Column {
            id: rareText
            anchors.left: rareIcon.right
            anchors.leftMargin: Commons.Style.space(10)
            anchors.right: rarePct.left
            anchors.rightMargin: Commons.Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Commons.Style.space(2)
            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: rareRow.modelData.name
              color: root.foreground
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
              elide: Text.ElideRight
            }
            Caption {
              width: parent.width
              elide: Text.ElideRight
              text: rareRow.modelData.game + " · " + root.day(rareRow.modelData.time)
            }
          }
          Text {
            textFormat: Text.PlainText
            id: rarePct
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: rareRow.modelData.percent.toFixed(1) + "%"
            color: root.metalColors[rareRow.modelData.tier]
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.bodySmall
            font.bold: true
          }
          Hit { game: rareRow.modelData }
        }
      }
      Caption {
        visible: rarestHeader[root.rarestRange].length === 0
        width: parent.width
        opacity: 0.5
        text: root.rarestRange === "platinum" ? "No platinum yet." : "Nothing unlocked yet this month."
      }
    }

    // ------------------------------------------------ platinum shelf

    PanelSectionHeader {
      readonly property int hiddenPlatinums: root.cabinet ? root.cabinet.shelf.length - shelf.count : 0
      visible: root.nowShows.shelf && (shelf.count > 0 || hiddenPlatinums > 0 || almost.count > 0)
      text: "PLATINUM SHELF · " + shelf.count + (hiddenPlatinums > 0 ? " · " + hiddenPlatinums + " HIDDEN" : "")
      foreground: root.foreground
    }

    // Every platinum, in a grid whose tiles fit the width exactly.
    Grid {
      id: shelfGrid
      visible: root.nowShows.shelf && (shelf.count > 0 || almost.count > 0)
      columns: 4
      spacing: Commons.Style.space(6)
      readonly property real tileWidth: (root.width - spacing * (columns - 1)) / columns
      Repeater {
        id: shelf
        // A hidden game leaves the shelf (and Closest); the Games tab's
        // Show brings it back.
        model: root.cabinet ? root.cabinet.shelf.filter(function(g) { return !root.isHidden(g) }) : []
        // Each platinum game's art with a metal edge; the date on hover.
        delegate: Rectangle {
          id: shelfCard
          required property var modelData
          required property int index
          width: shelfGrid.tileWidth
          height: Math.round(width * 215 / 460)
          radius: Commons.Style.cornerRadius
          color: "transparent"
          border.width: 1
          border.color: Qt.alpha(root.metalColors.platinum, shelfHit.containsMouse ? 1 : 0.45)
          property real rise: 0
          opacity: 0
          transform: Translate { y: shelfCard.rise }
          FadeIn { item: shelfCard; order: shelfCard.index }
          Accessible.role: Accessible.Button
          Accessible.name: modelData.game + ", platinum " + root.day(modelData.platinum)

          Art {
            anchors.fill: parent
            anchors.margins: 1
            source: shelfCard.modelData.header || ""
            label: shelfCard.modelData.game
            zoom: shelfHit.containsMouse || removeHit.containsMouse ? 1.08 : 1
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
            visible: shelfHit.containsMouse && !removeHit.containsMouse
            text: shelfCard.modelData.game + " · " + root.day(shelfCard.modelData.platinum)
          }
          // Takes the game off the shelf; shown on hover only.
          Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.margins: 3
            width: 16
            height: 16
            radius: 8
            visible: shelfHit.containsMouse || removeHit.containsMouse
            color: removeHit.containsMouse ? Commons.Color.accent : Qt.alpha(Commons.Color.popups.background, 0.85)
            Accessible.role: Accessible.Button
            Accessible.name: "Take " + shelfCard.modelData.game + " off the shelf"
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "×"
              color: removeHit.containsMouse ? Commons.Color.popups.background : root.foreground
              font.pixelSize: 12
              font.bold: true
            }
            MouseArea {
              id: removeHit
              anchors.fill: parent
              anchors.margins: -2
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.toggleHidden(shelfCard.modelData)
            }
            PanelToolTip {
              visible: removeHit.containsMouse
              text: "Off the shelf · Games tab › Show brings it back"
            }
          }
        }
      }
      // The shelf's empty slots, or a fresh row when it is full, go to
      // the games nearest platinum: dimmed art, how many are left, and a
      // bar, so the shelf shows what's next to finish.
      Repeater {
        id: almost
        readonly property int slots: (shelfGrid.columns - shelf.count % shelfGrid.columns) % shelfGrid.columns || shelfGrid.columns
        model: root.cabinet && root.cabinet.nearest ? root.unhidden(root.cabinet.nearest).slice(0, slots) : []
        delegate: Rectangle {
          id: almostCard
          required property var modelData
          required property int index
          readonly property int toGo: modelData.total - modelData.unlocked
          width: shelfGrid.tileWidth
          height: Math.round(width * 215 / 460)
          radius: Commons.Style.cornerRadius
          color: "transparent"
          border.width: 1
          border.color: Qt.alpha(root.foreground, almostHit.containsMouse ? 0.45 : 0.14)
          property real rise: 0
          opacity: 0
          transform: Translate { y: almostCard.rise }
          FadeIn { item: almostCard; order: shelf.count + almostCard.index }
          Accessible.role: Accessible.Button
          Accessible.name: modelData.game + ", " + toGo + " to platinum"

          Art {
            anchors.fill: parent
            anchors.margins: 1
            source: almostCard.modelData.header || ""
            label: almostCard.modelData.game
            zoom: almostHit.containsMouse ? 1.08 : 1
            opacity: almostHit.containsMouse ? 0.75 : 0.4
            Behavior on opacity { NumberAnimation { duration: 160 } }
          }
          Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 3
            width: leftText.implicitWidth + 8
            height: leftText.implicitHeight + 2
            radius: height / 2
            color: Qt.alpha(Commons.Color.popups.background, 0.85)
            Text {
              textFormat: Text.PlainText
              id: leftText
              anchors.centerIn: parent
              text: almostCard.toGo + " left"
              color: root.foreground
              font.family: Commons.Style.font.family
              font.pixelSize: 9
              font.bold: true
            }
          }
          Bar {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            // Flush with the frame, under the art's name label.
            anchors.margins: 1
            height: 2
            radius: 0
            fraction: almostCard.modelData.unlocked / almostCard.modelData.total
          }
          Hit { id: almostHit; game: almostCard.modelData }
          PanelToolTip {
            visible: almostHit.containsMouse
            text: almostCard.modelData.game + " · " + almostCard.modelData.unlocked + " / " + almostCard.modelData.total + " · " + almostCard.toGo + " to platinum"
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

  // ---------------------------------------------------------------- Profile

  // The library at a glance, in tiles taken from Steam's profile
  // showcases: the game you play most, your rarest trophies, what you've
  // finished, and how long you've played. Every number is local data.
  TabPage {
    id: profileTab
    visible: root.tab === "profile"
    width: root.width
    spacing: root.spacing

    // ------------------------------------------------ favorite game

    PanelSectionHeader {
      visible: favorite.game !== null
      text: "MOST PLAYED"
      foreground: root.foreground
    }

    Rectangle {
      id: favorite
      readonly property var game: root.cabinet && root.cabinet.favorite ? root.cabinet.favorite : null
      visible: game !== null
      width: root.width
      height: favoriteBody.height + Commons.Style.space(20)
      radius: Commons.Style.cornerRadius
      color: favoriteHit.containsMouse ? Commons.Style.hoverFill : Qt.alpha(root.foreground, 0.04)
      border.width: 1
      border.color: Qt.alpha(root.foreground, 0.12)
      Behavior on color { ColorAnimation { duration: 120 } }
      Hit { id: favoriteHit; game: favorite.game }
      Column {
        id: favoriteBody
        x: Commons.Style.space(10)
        y: Commons.Style.space(10)
        width: parent.width - Commons.Style.space(20)
        spacing: Commons.Style.space(10)
        Row {
          spacing: Commons.Style.space(12)
          Art {
            id: favoriteArt
            width: Math.round(favoriteBody.width * 0.45)
            height: Math.round(width * 215 / 460)
            source: favorite.game ? favorite.game.header || "" : ""
            label: favorite.game ? favorite.game.game : ""
            zoom: favoriteHit.containsMouse ? 1.05 : 1
          }
          Column {
            anchors.verticalCenter: parent.verticalCenter
            width: favoriteBody.width - favoriteArt.width - Commons.Style.space(12)
            spacing: Commons.Style.space(6)
            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: favorite.game ? favorite.game.game : ""
              color: root.foreground
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.body
              font.bold: true
              elide: Text.ElideRight
            }
            Row {
              spacing: Commons.Style.space(16)
              Stat { value: favorite.game ? Math.round(favorite.game.minutes / 60) : -1; label: "HOURS" }
              Stat { value: favorite.game ? favorite.game.rare : -1; label: "RARE"; tint: root.metalColors.gold }
            }
          }
        }
        Item {
          width: parent.width
          height: favoriteCount.height
          Caption {
            id: favoriteCount
            text: favorite.game ? favorite.game.unlocked + " / " + favorite.game.total + " trophies" : ""
          }
          Caption {
            anchors.right: parent.right
            visible: favorite.game !== null && favorite.game.platinum > 0
            text: "Platinum"
            color: root.metalColors.platinum
          }
        }
        Bar {
          width: parent.width
          fraction: favorite.game ? favorite.game.unlocked / favorite.game.total : 0
          fill: favorite.game && favorite.game.platinum > 0 ? root.metalColors.platinum : Commons.Color.accent
        }
      }
    }

    // ------------------------------------------------ showcase

    // Up to six trophies you pin with ☆ in the tracker (a game's platinum
    // too), like Steam's achievement showcase. Until you pin one, your
    // rarest ever stand in, so the tile is never empty.
    Item {
      id: showcaseHeader
      readonly property var picks: root.cabinet && root.cabinet.showcase
        ? root.cabinet.showcase.filter(function(p) { return !root.unpinned[p.key] }) : []
      readonly property bool picked: picks.length > 0
      readonly property var tiles: picked ? picks
        : (root.cabinet && root.cabinet.rarest ? root.unhidden(root.cabinet.rarest.ever).slice(0, 6) : [])
      visible: tiles.length > 0
      width: root.width
      height: showcaseTitle.height
      PanelSectionHeader {
        id: showcaseTitle
        text: showcaseHeader.picked ? "SHOWCASE · " + showcaseHeader.picks.length + " / 6" : "SHOWCASE · RAREST EVER"
        foreground: root.foreground
      }
      Caption {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        opacity: 0.45
        text: "☆ a trophy in the tracker to pin it"
      }
    }

    // Each pick framed in its metal; a click opens it in the tracker, the
    // × takes it off. Empty slots say how to fill them.
    Row {
      id: showcaseRow
      visible: showcaseHeader.visible
      spacing: Commons.Style.space(6)
      readonly property real tile: (root.width - spacing * 5) / 6
      Repeater {
        id: showcase
        model: showcaseHeader.tiles
        delegate: Rectangle {
          id: showTile
          required property var modelData
          required property int index
          readonly property bool platinum: modelData.tier === "platinum"
          width: showcaseRow.tile
          height: width
          radius: Commons.Style.cornerRadius
          color: Qt.alpha(root.metalColors[modelData.tier], showHit.containsMouse ? 0.22 : 0.1)
          border.width: 1
          border.color: Qt.alpha(root.metalColors[modelData.tier], showHit.containsMouse ? 1 : 0.55)
          clip: true
          property real rise: 0
          opacity: 0
          transform: Translate { y: showTile.rise }
          FadeIn { item: showTile; order: showTile.index }
          Accessible.role: Accessible.Button
          Accessible.name: modelData.name + ", " + modelData.game
          AchIcon {
            visible: !showTile.platinum
            anchors.fill: parent
            anchors.margins: 4
            source: showTile.modelData.icon
            scale: showHit.containsMouse ? 1.06 : 1
            Behavior on scale { NumberAnimation { duration: 140 } }
          }
          // A platinum: the game's art, dimmed, under the platinum trophy.
          Art {
            visible: showTile.platinum
            anchors.fill: parent
            anchors.margins: 1
            source: showTile.platinum ? showTile.modelData.icon || "" : ""
            label: ""
            opacity: 0.45
          }
          Thumb {
            visible: showTile.platinum
            anchors.centerIn: parent
            style: root.iconSet
            metal: "platinum"
            width: parent.width * 0.55
            height: width
            scale: showHit.containsMouse ? 1.08 : 1
            Behavior on scale { NumberAnimation { duration: 140 } }
          }
          Hit { id: showHit; game: showTile.modelData }
          PanelToolTip {
            visible: showHit.containsMouse && !unpinHit.containsMouse
            text: showTile.modelData.name + " · " + showTile.modelData.game
                  + (showTile.modelData.percent !== null && showTile.modelData.percent !== undefined ? " · " + showTile.modelData.percent.toFixed(1) + "%" : "")
          }
          Rectangle {
            visible: showcaseHeader.picked && (showHit.containsMouse || unpinHit.containsMouse)
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.margins: 2
            width: 16
            height: 16
            radius: 8
            color: unpinHit.containsMouse ? Commons.Color.accent : Qt.alpha(Commons.Color.popups.background, 0.85)
            Accessible.role: Accessible.Button
            Accessible.name: "Take " + showTile.modelData.name + " off the showcase"
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "×"
              color: unpinHit.containsMouse ? Commons.Color.popups.background : root.foreground
              font.pixelSize: 12
              font.bold: true
            }
            MouseArea {
              id: unpinHit
              anchors.fill: parent
              anchors.margins: -2
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.unpin(showTile.modelData)
            }
          }
        }
      }
      // The slots still open once you've pinned something.
      Repeater {
        model: showcaseHeader.picked ? 6 - showcaseHeader.picks.length : 0
        delegate: Rectangle {
          width: showcaseRow.tile
          height: width
          radius: Commons.Style.cornerRadius
          color: "transparent"
          border.width: 1
          border.color: Qt.alpha(root.foreground, 0.12)
          Text {
            textFormat: Text.PlainText
            anchors.centerIn: parent
            text: "+"
            color: root.foreground
            opacity: 0.3
            font.pixelSize: Commons.Style.font.title
          }
        }
      }
    }

    Row {
      visible: root.cabinet !== null
      spacing: Commons.Style.space(16)
      Stat { value: root.cabinet ? root.cabinet.trophies : -1; label: "TROPHIES" }
      Stat { value: root.cabinet && root.cabinet.metals ? root.cabinet.metals.gold : -1; label: "RARE"; tint: root.metalColors.gold }
    }

    // ------------------------------------------------ completionist

    PanelSectionHeader {
      visible: root.cabinet !== null
      text: "COMPLETIONIST"
      foreground: root.foreground
    }

    // The two newest platinums, as the shelf draws them but bigger.
    Row {
      id: newestPlatinums
      readonly property var games: root.cabinet ? root.unhidden(root.cabinet.shelf).slice(0, 2) : []
      visible: games.length > 0
      spacing: Commons.Style.space(6)
      Repeater {
        model: newestPlatinums.games
        delegate: Rectangle {
          id: newestCard
          required property var modelData
          width: (root.width - Commons.Style.space(6)) / 2
          height: Math.round(width * 215 / 460)
          radius: Commons.Style.cornerRadius
          color: "transparent"
          border.width: 1
          border.color: Qt.alpha(root.metalColors.platinum, newestHit.containsMouse ? 1 : 0.45)
          Art {
            anchors.fill: parent
            anchors.margins: 1
            source: newestCard.modelData.header || ""
            label: newestCard.modelData.game
            zoom: newestHit.containsMouse ? 1.06 : 1
          }
          Rectangle {
            // Top corner: the art's own name label sits along the bottom.
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 4
            width: newestRow.width + 10
            height: newestRow.height + 4
            radius: height / 2
            color: Qt.alpha(Commons.Color.popups.background, 0.85)
            Row {
              id: newestRow
              anchors.centerIn: parent
              spacing: 4
              Thumb { style: root.iconSet; metal: "platinum"; width: 14; height: 14; anchors.verticalCenter: parent.verticalCenter }
              Text {
                textFormat: Text.PlainText
                anchors.verticalCenter: parent.verticalCenter
                text: newestCard.modelData.total + " trophies"
                color: root.foreground
                font.family: Commons.Style.font.family
                font.pixelSize: 10
                font.bold: true
              }
            }
          }
          Hit { id: newestHit; game: newestCard.modelData }
          PanelToolTip {
            visible: newestHit.containsMouse
            text: newestCard.modelData.game + " · platinum " + root.day(newestCard.modelData.platinum)
          }
        }
      }
    }

    Row {
      visible: root.cabinet !== null
      spacing: Commons.Style.space(16)
      Stat { value: root.cabinet ? root.cabinet.platinums : -1; label: "COMPLETED"; tint: root.metalColors.platinum }
      Stat { value: root.cabinet && root.cabinet.started !== undefined ? root.cabinet.started : -1; label: "STARTED" }
      Stat { value: root.cabinet && root.cabinet.completion !== undefined ? root.cabinet.completion : -1; label: "AVG COMPLETION"; suffix: "%" }
    }

    // ------------------------------------------------ playtime

    PanelSectionHeader {
      visible: playtimeRow.visible
      text: "PLAYTIME"
      foreground: root.foreground
    }

    Row {
      id: playtimeRow
      readonly property var minutes: root.cabinet && root.cabinet.playtime ? root.cabinet.playtime : null
      visible: minutes !== null && minutes.total > 0
      spacing: Commons.Style.space(16)
      Stat { value: playtimeRow.minutes ? Math.round(playtimeRow.minutes.recent / 60) : -1; label: "HOURS · 2 WEEKS" }
      Stat { value: playtimeRow.minutes ? Math.round(playtimeRow.minutes.total / 60) : -1; label: "HOURS IN ALL" }
    }

    Caption {
      visible: root.cabinet !== null && !favorite.visible && !playtimeRow.visible && showcase.count === 0
      width: root.width
      wrapMode: Text.WordWrap
      elide: Text.ElideNone
      opacity: 0.5
      text: "Play a game with achievements and your profile fills in here."
    }
  }

  // ------------------------------------------------------------------ Games

  TabPage {
    id: gamesTab
    visible: root.tab === "games"
    width: root.width
    spacing: Commons.Style.space(6)

    // ------------------------------------------------ sort and filter

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
        onPicked: value => root.remember("games-sort", "sort", value)
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

    // ------------------------------------------------ game list

    Repeater {
      model: root.shownGames
      // One game: art, name, count and a thin bar; a finished game carries
      // the platinum rail and date instead.
      delegate: Item {
        id: gameRow
        required property var modelData
        required property int index
        readonly property bool platinum: modelData.platinum > 0
        property real rise: 0
        opacity: 0
        transform: Translate { y: gameRow.rise }
        FadeIn { item: gameRow; order: gameRow.index }
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
          zoom: gameHit.containsMouse ? 1.06 : 1
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
            // hidden one so it can come back. Hiding a platinum takes it
            // off the shelf.
            Text {
              textFormat: Text.PlainText
              id: hideToggle
              anchors.right: gameCount.left
              anchors.rightMargin: Commons.Style.space(8)
              anchors.verticalCenter: parent.verticalCenter
              visible: gameHit.containsMouse || hideHit.containsMouse || gameRow.hiddenGame
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

    // ------------------------------------------------ pager

    // Previous, the page numbers and next, with which games these are.
    Item {
      width: root.width
      height: pager.height + Commons.Style.space(10)
      visible: root.gamesPageCount > 1
      Caption {
        anchors.left: parent.left
        anchors.verticalCenter: pager.verticalCenter
        opacity: 0.45
        text: (root.gamesPageIndex * root.gamesPage + 1) + "–"
              + Math.min(root.sortedGames.length, (root.gamesPageIndex + 1) * root.gamesPage)
              + " of " + root.sortedGames.length
      }
      Row {
        id: pager
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        spacing: Commons.Style.space(2)
        Repeater {
          model: [-2].concat(root.pageButtons(root.gamesPageIndex, root.gamesPageCount), [-3])
          // -2 and -3 are the arrows, -1 a gap, anything else a page.
          delegate: Rectangle {
            id: pageButton
            required property int modelData
            readonly property bool arrow: modelData === -2 || modelData === -3
            readonly property int target: modelData === -2 ? root.gamesPageIndex - 1
                                          : modelData === -3 ? root.gamesPageIndex + 1 : modelData
            readonly property bool usable: modelData !== -1 && target >= 0 && target < root.gamesPageCount
            readonly property bool chosen: !arrow && modelData === root.gamesPageIndex
            width: Math.max(height, pageText.implicitWidth + Commons.Style.space(10))
            height: pageText.implicitHeight + Commons.Style.space(8)
            radius: height / 2
            color: chosen ? Qt.alpha(Commons.Color.accent, 0.18)
                   : (pageHit.containsMouse && usable ? Commons.Style.hoverFill : "transparent")
            Accessible.role: Accessible.Button
            Accessible.name: modelData === -2 ? "Previous page" : modelData === -3 ? "Next page" : "Page " + (modelData + 1)
            Text {
              textFormat: Text.PlainText
              id: pageText
              anchors.centerIn: parent
              text: pageButton.modelData === -2 ? "‹" : pageButton.modelData === -3 ? "›"
                    : pageButton.modelData === -1 ? "…" : String(pageButton.modelData + 1)
              color: pageButton.chosen ? Commons.Color.accent : root.foreground
              opacity: pageButton.chosen ? 1 : (pageButton.usable || pageButton.modelData === -1 ? 0.65 : 0.2)
              font.family: Commons.Style.font.family
              font.pixelSize: pageButton.arrow ? Commons.Style.font.body : Commons.Style.font.caption
              font.bold: pageButton.chosen || pageButton.arrow
            }
            MouseArea {
              id: pageHit
              anchors.fill: parent
              hoverEnabled: true
              enabled: pageButton.usable && !pageButton.chosen
              cursorShape: Qt.PointingHandCursor
              onClicked: root.gamesPageIndex = pageButton.target
            }
          }
        }
      }
    }

    // ------------------------------------------------ empty and loading

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

  // --------------------------------------------------------------- Settings

  TabPage {
    id: settingsTab
    visible: root.tab === "settings"
    width: root.width
    spacing: root.spacing

    // ------------------------------------------------ toasts

    PanelSectionHeader { text: "TOASTS"; foreground: root.foreground }

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
          height: Commons.Style.space(78)
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
          // The chosen style's tick, in the corner like a radio mark.
          Rectangle {
            visible: styleCard.chosen
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: Commons.Style.space(5)
            width: 14
            height: 14
            radius: 7
            color: Commons.Color.accent
            Text {
              textFormat: Text.PlainText
              anchors.centerIn: parent
              text: "✓"
              color: Commons.Color.popups.background
              font.pixelSize: 10
              font.bold: true
            }
          }
          // The whole set, gold raised in the middle, so each card shows
          // what every tier will look like.
          Column {
            anchors.centerIn: parent
            spacing: Commons.Style.space(6)
            Row {
              anchors.horizontalCenter: parent.horizontalCenter
              spacing: -4
              Repeater {
                model: ["bronze", "gold", "silver"]
                delegate: Thumb {
                  required property string modelData
                  required property int index
                  anchors.bottom: parent.bottom
                  style: styleCard.modelData.id
                  metal: modelData
                  width: index === 1 ? 34 : 24
                  height: width
                  opacity: index === 1 || styleCard.chosen || pick.containsMouse ? 1 : 0.7
                }
              }
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

    // Every toast setting is the same kind of control, a row of chips,
    // so the tab reads at a glance. (A screen drawing for position and a
    // slider for glass looked nice but each needed learning.)
    SettingRow {
      label: "POSITION"
      Chips {
        options: [
          { value: "top-left", label: "Left" },
          { value: "top-center", label: "Center" },
          { value: "top-right", label: "Right" }
        ]
        value: root.position
        onPicked: value => root.set("position", value)
      }
    }

    // From see-through to the solid card.
    SettingRow {
      label: "GLASS"
      Chips {
        options: [
          { value: "clear", label: "Clear" },
          { value: "frosted", label: "Frosted" },
          { value: "solid", label: "Solid" }
        ]
        value: root.glass
        onPicked: value => root.set("glass", value)
      }
    }

    SettingRow {
      label: "SOUND"
      Chips {
        options: [
          { value: "omatrophy", label: "OmaTrophy" },
          { value: "classic", label: "Classic" },
          { value: "off", label: "Silent" }
        ]
        value: root.sound ? root.chimes : "off"
        onPicked: value => root.set("sound", value)
      }
    }

    // Last in the section, so a choice is made before it is tried.
    SettingRow {
      label: "TRY IT"
      Row {
        spacing: Commons.Style.space(6)
        Repeater {
          model: root.metals
          // A tile per metal that fires a real toast; its edge is the metal.
          delegate: Rectangle {
            id: tile
            required property string modelData
            width: Commons.Style.space(56)
            height: Commons.Style.space(46)
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
            Column {
              anchors.centerIn: parent
              spacing: Commons.Style.space(2)
              Thumb {
                anchors.horizontalCenter: parent.horizontalCenter
                style: root.iconSet
                metal: tile.modelData
                width: 22
                height: 22
                scale: fire.pressed ? 0.9 : 1
                Behavior on scale { NumberAnimation { duration: 90 } }
              }
              Text {
                textFormat: Text.PlainText
                anchors.horizontalCenter: parent.horizontalCenter
                text: tile.modelData.toUpperCase()
                color: root.metalColors[tile.modelData]
                opacity: fire.containsMouse ? 1 : 0.7
                font.family: Commons.Style.font.family
                font.pixelSize: 8
                font.letterSpacing: 1
              }
            }
          }
        }
      }
    }

    // Said under the toast rows only: the Steam rows below don't touch
    // toasts.
    Caption {
      width: root.width
      wrapMode: Text.WordWrap
      elide: Text.ElideNone
      opacity: 0.4
      text: "Changes apply to the next toast. A tile shows one now, with your settings."
    }

    // ------------------------------------------------ now tab

    Item { width: 1; height: Commons.Style.space(8) }

    PanelSectionHeader { text: "NOW TAB"; foreground: root.foreground }

    // Each section a chip of its own, lit while shown; the game you're
    // playing always shows.
    SettingRow {
      label: "SHOW"
      Row {
        spacing: Commons.Style.space(2)
        Repeater {
          model: root.nowSections
          delegate: Rectangle {
            id: showChip
            required property var modelData
            readonly property bool shown: root.nowShows[modelData.value] !== false
            width: showText.implicitWidth + Commons.Style.space(16)
            height: showText.implicitHeight + Commons.Style.space(8)
            radius: height / 2
            color: shown ? Qt.alpha(Commons.Color.accent, 0.18) : (showHit.containsMouse ? Commons.Style.hoverFill : "transparent")
            Accessible.role: Accessible.CheckBox
            Accessible.name: "Show " + modelData.label + " on the Now tab"
            Accessible.checked: shown
            Behavior on color { ColorAnimation { duration: 120 } }
            Text {
              textFormat: Text.PlainText
              id: showText
              anchors.centerIn: parent
              // The tick tells these apart from the one-of-many chips above.
              text: (showChip.shown ? "✓ " : "") + showChip.modelData.label
              color: showChip.shown ? Commons.Color.accent : root.foreground
              opacity: showChip.shown ? 1 : 0.6
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.caption
              font.bold: showChip.shown
            }
            MouseArea {
              id: showHit
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.set("now-" + showChip.modelData.value, showChip.shown ? "off" : "on")
            }
          }
        }
      }
    }

    // ------------------------------------------------ stores

    Item { width: 1; height: Commons.Style.space(8) }

    PanelSectionHeader { text: "STORES"; foreground: root.foreground }

    // Every store OmaTrophy knows, found or not, so "is GOG working?" has
    // an answer here; a store's own settings sit inside its card.
    StoreCard {
      storeId: "steam"
      missing: "Install Steam and play a game with achievements once. Steam somewhere else? Set STEAM_DIR."

      // The opt-in profile backfill (ADR 11). The switch goes through
      // `set community`, like every other setting.
      SettingRow {
        label: "PROFILE"
        Chips {
          options: [
            { value: "off", label: "Off" },
            { value: "on", label: "Fill in" }
          ]
          value: root.community ? "on" : "off"
          onPicked: value => root.set("community", value)
        }
      }

      Caption {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        opacity: 0.4
        text: root.backfillText()
      }

      // Steam shows its own popup for the same unlock. OmaTrophy only reads
      // Steam's files (ADR 1), and Steam rewrites its config while it runs,
      // so this opens Steam's Notifications page for the owner to switch it
      // off there. Page id and labels from Steam's own client UI (steamui).
      SettingRow {
        label: "POPUPS"
        Rectangle {
          id: steamButton
          width: steamText.implicitWidth + Commons.Style.space(20)
          height: steamText.implicitHeight + Commons.Style.space(10)
          radius: height / 2
          color: steamHit.containsMouse ? Commons.Style.hoverFill : "transparent"
          border.width: 1
          border.color: Qt.alpha(root.foreground, steamHit.containsMouse ? 0.35 : 0.18)
          Accessible.role: Accessible.Button
          Accessible.name: "Open Steam's settings to turn off its achievement popups"
          Behavior on color { ColorAnimation { duration: 120 } }
          Text {
            textFormat: Text.PlainText
            id: steamText
            anchors.centerIn: parent
            text: "Turn off in Steam ↗"
            color: root.foreground
            opacity: 0.8
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.caption
          }
          MouseArea {
            id: steamHit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: Qt.openUrlExternally("steam://open/settings/notifications")
          }
        }
      }

      Caption {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.WordWrap
        opacity: 0.4
        text: "Steam shows its own popup too. On the page this opens, find \"When I unlock an achievement\" and untick Show Toast (and Play Sound)."
      }
    }

    StoreCard {
      storeId: "gog"
      missing: "Play a GOG game once through Heroic Games Launcher, signed in to GOG."
      note: "Through Heroic Games Launcher. Toasts come live while you play; nothing to set."
    }
  }
}
