import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons as Commons

// The tracker's card: one game's every achievement, with rarity, the date
// you got it, and filters (all, locked, unlocked, rare) plus type-to-search;
// and the game's 100% guide (the Guide filter), with a Make guide button
// that starts `omatrophy.py guide make` through the user's agent (ADR 14).
// It changes nothing in a game; the only things it writes are your own
// settings through omatrophy.py (its sort; trophies pinned to the Profile
// showcase with ☆, finished games to its completionist tile). Built from its text by Tracker.qml (FreshObject.qml), so it must not use
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
  // The rows shown, in order. The ListView's model is `rowModel`, kept in
  // step with this by applyRows() through inserts, removes and moves, so
  // the list can animate a change instead of swapping wholesale.
  property var rows: []
  // `rowModel`'s api names in order, mirrored in JS so diffing a long list
  // doesn't call ListModel.get() for every comparison.
  property var shownApis: []
  property var byApi: ({})
  // True while a game's rows first fill, so they cascade in; rows that
  // arrive later through a filter use the list's add transition instead.
  property bool cascading: false
  // Hidden achievements revealed with Enter, by api name; hover reveals too.
  property var revealed: ({})
  // Reveal all: every hidden one shows its name and tip, for a player
  // who'd rather plan than be surprised. Kept in config.json
  // (`reveal-hidden`): the owner turned it on for every game and every
  // open, and found clicking it again each time no better than one by one.
  property bool revealAll: false
  // Nothing left to unlock: a make would spend the owner's tokens on a
  // guide with nothing to plan (it did, for a platinum game).
  readonly property bool complete: game !== null && game.total > 0 && game.unlocked >= game.total
  readonly property int secretCount: game ? game.achievements.filter(function(a) { return a.hidden && !a.unlocked }).length : 0
  // The Profile showcase's picks from config.json, so a ★ shows lit;
  // "store:game:api", or "store:game" for a game's platinum.
  property var showcaseKeys: []
  readonly property int showcaseMax: 6
  // Finished games pinned to the Profile's completionist tile, "store:game".
  property var completionistKeys: []
  readonly property int completionistMax: 4
  // An achievement to highlight once the game loads, from the request.
  property string focusApi: ""

  // The 100% guide view (filter "guide"; docs/specs/guides.md). `live`
  // is set by load(): dev/render.sh fills these from samples instead.
  property bool live: false
  // Opened on a named game (a panel row), not "the game running now": with
  // nothing running the latter falls back to the last game played, and the
  // owner saw RE7 open with no word why.
  property bool pickedGame: false
  // The last game read came with its guide (`game --guide`).
  property bool guideWithGame: false
  // `guide <store> <app>`: null until read, {} when there is none.
  property var guide: null
  // `guide agents`: every agent, with its models and the saved picks.
  property var agents: []
  // `guide status`: the latest make job, of any game.
  property var job: ({})
  // The agent, model and effort the next make uses; saved as they change.
  property string pickAgent: ""
  property string pickModel: ""
  property string pickEffort: ""
  property string configAgent: ""
  // The first `guide status` after a game loads: a make under way for this
  // game opens the tracker on its Guide tab.
  property bool jobSeen: false
  // The trophy picked on the guide side (an Up next row): the trophy list
  // scrolls to it and lights it.
  property string highlightApi: ""
  // Walkthrough steps the player opened or folded, by index: true or
  // false. Unset, the current step (the first with an achievement left)
  // is open, so the in-game guide opens on where the player is (ADR 17).
  // Several stay open at once: with one, opening a later step folded the
  // current one, and the owner saw a lit step with no text.
  property var stepOpen: ({})
  readonly property var walkSteps: guide && Array.isArray(guide.walkthrough) ? guide.walkthrough : []
  readonly property int currentStep: guide && guide.step >= 0 ? guide.step : -1
  // The player said where they are (`guide here`): `step` is that pin.
  readonly property bool stepPinned: !!guide && guide.step_pinned === true
  readonly property bool walked: hasGuide && walkSteps.length > 0
  // Open trophies of the guide that no step holds, listed after the steps
  // so none is lost track of.
  readonly property var unplaced: {
    if (!walked) return []
    var placed = {}
    walkSteps.forEach(function(s) { (s.achievements || []).forEach(function(a) { placed[a] = true }) })
    return (guide.order || []).filter(function(api) { return !placed[api] && byApi[api] && !guideDone(api) })
  }
  // The Guide view as a tree (ADR 20) instead of its steps or Up next:
  // Do now, the story as a track, chains as small skill trees, the rest
  // as a grid by phase.
  property bool treeShown: false
  // The story step whose actions show under the track; -1 follows the
  // current step.
  property int trackPick: -1
  // The trophy picked in the tree, its tips and needs shown inline in the
  // part it was picked in (`treePickIn`: "now", "story", "chains", "alone").
  property string treePick: ""
  property string treePickIn: ""
  // On their own's phase groups the player folded, by phase.
  property var foldedPhases: ({})
  // Do now shows three; the rest unfold on a click.
  property bool doNowAll: false
  // Open trophies whose prerequisites are done, from the reader's
  // `frontier` (an answer from before it has only `next`); one unlocked or
  // ticked since drops out at once.
  readonly property var doNowApis: {
    if (!guide) return []
    var from = Array.isArray(guide.frontier) ? guide.frontier : guide.next || []
    return from.filter(function(api) { return !!byApi[api] && !guideDone(api) && lockedBy(api).length === 0 })
  }
  // The chains' rows ({api, depth}) as trees: a depth-0 row is a goal,
  // the rows under it one deeper are what it needs first.
  readonly property var chainTrees: {
    var out = [], stack = []
    guideTree.chains.forEach(function(row) {
      var node = { api: row.api, kids: [] }
      stack.length = row.depth
      if (row.depth === 0) out.push(node)
      else if (stack[row.depth - 1]) stack[row.depth - 1].kids.push(node)
      stack.push(node)
    })
    return out
  }
  // The story's track: the walkthrough's steps, or with none the story
  // trophies one per node.
  readonly property var trackNodes: {
    if (walkSteps.length > 0) return walkSteps.map(function(s, i) { return { step: i, api: "", achievements: s.achievements || [] } })
    return guideTree.story.map(function(api) { return { step: -1, api: api, achievements: [api] } })
  }
  // Where the player is on the track: the current step, or with no steps
  // the first story trophy left; -1 when all is done.
  readonly property int trackHere: {
    if (walkSteps.length > 0) return currentStep
    for (var i = 0; i < trackNodes.length; i++) if (!guideDone(trackNodes[i].api)) return i
    return -1
  }
  readonly property int trackShown: trackPick >= 0 ? trackPick : trackHere
  readonly property var guideTree: guide && guide.tree && Array.isArray(guide.tree.chains)
                                   ? guide.tree : ({ story: [], chains: [], alone: [] })
  // Only story and chains make an outline worth a toggle; a guide from
  // before the tree (no `tree`) shows as it always did.
  readonly property bool hasTree: hasGuide && guideTree.story.length + guideTree.chains.length > 0
  readonly property bool treeOn: treeShown && hasTree && !appliedSearch
  // The steps, Up next and sections: hidden while the outline shows.
  readonly property bool listShown: !appliedSearch && !treeOn
  // The agent and model picker; folded away under a made guide.
  property bool makerOpen: false
  // Which Make-guide picker is unfolded: "agent", "model", "effort" or "".
  property string makerMenu: ""
  readonly property bool hasGuide: !!guide && !!guide.items && (Object.keys(guide.items).length > 0 || !!guide.notes)
  readonly property bool making: job.state === "running"
  // Guides are made in parallel (up to `jobsMax`), one job per game: `job`
  // is this game's, `othersRunning` counts the rest.
  property int othersRunning: 0
  property int jobsMax: 3
  readonly property bool jobsFull: othersRunning + (making ? 1 : 0) >= jobsMax
  readonly property bool jobHere: !!game && job.store === game.store && String(job.app) === String(game.app)
  // `job` is always this game's now; kept as a name for the views below.
  readonly property bool makingHere: making && jobHere
  readonly property var runnable: agents.filter(function(a) { return a.installed && a.supported })
  readonly property var pickedRow: agents.find(function(a) { return a.agent === pickAgent }) || null
  readonly property var phases: ["missable", "story", "quick", "challenge", "grind", "collect", "online"]
  readonly property var phaseNames: ({ missable: "Missable", story: "Story", quick: "Quick", challenge: "Challenge",
                                       grind: "Grind", collect: "Collectibles", online: "Online", other: "Other" })

  readonly property color foreground: Commons.Color.menu.text
  readonly property color background: Commons.Color.menu.background
  readonly property var metalColors: ({ bronze: "#e9a46b", silver: "#dfe6ee", gold: "#f3cf4a", platinum: "#e2eaff" })
  readonly property string helperPath: decodeURIComponent(String(Qt.resolvedUrl("omatrophy.py")).replace(/^file:\/\//, ""))
  readonly property real rarePercent: 10

  signal closeRequested()

  // The guide gets a wider card: the guide on the left, every trophy of
  // the game on the right.
  width: Math.min(maxWidth, Commons.Style.space(filter === "guide" ? 1200 : 760))
  height: Math.min(maxHeight, Commons.Style.space(filter === "guide" ? 880 : 820))
  Behavior on width { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
  Behavior on height { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

  // Called by Tracker.qml with the summon payload: {store, app}, or empty
  // for the game running now (or played last).
  function load(request) {
    // A view kept from the last open starts as a fresh one would.
    error = ""
    search = ""
    appliedSearch = ""
    revealed = ({})
    highlightApi = ""
    guide = null
    job = ({})
    jobSeen = false
    makerOpen = false
    makerMenu = ""
    othersRunning = 0
    filter = request && request.view === "guide" ? "guide" : "all"
    game = null
    forceKeys()
    live = true
    focusApi = request && request.api ? String(request.api) : ""
    pickedGame = !!(request && request.store && request.app)
    // The game and its guide in one process: two in a row (game, then its
    // guide) made the Guide key slow to show anything.
    var args = ["python3", helperPath, "game"]
    if (request && request.store && request.app) args = args.concat([String(request.store), String(request.app)])
    loader.command = args.concat(["--guide"])
    loader.running = true
  }

  function stepIsOpen(index) {
    return stepOpen[index] !== undefined ? stepOpen[index] : index === currentStep
  }

  function toggleStep(index) {
    var next = Object.assign({}, stepOpen)
    next[index] = !stepIsOpen(index)
    stepOpen = next
  }

  onGuideChanged: if (trackPick >= walkSteps.length) trackPick = -1
  onGameChanged: {
    stepOpen = ({})
    trackPick = -1
    treePick = ""
    treePickIn = ""
    var index = {}
    if (game) game.achievements.forEach(function(a) { index[a.api] = a })
    byApi = index
    rowModel.clear()
    shownApis = []
    cascading = true
    rebuild()
    cascadeEnd.restart()
    if (focusApi) Qt.callLater(focusRequested)
    if (live && game) readGuide(guideWithGame)
    guideWithGame = false
  }
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
    rows = game ? sorted(game.achievements.filter(keep)) : []
    applyRows(rows.map(function(a) { return a.api }))
    list.currentIndex = -1
    list.positionViewAtBeginning()
  }

  // Turns the shown list into `want` with the fewest visible steps: rows
  // that no longer match leave (in runs, from the end), then each wanted
  // row is moved into place or inserted. The list's transitions animate
  // each step, so a search narrowing to one row shows the rest leaving.
  function applyRows(want) {
    var keep = {}
    want.forEach(function(api) { keep[api] = true })
    var order = shownApis.slice()
    var i = order.length - 1
    while (i >= 0) {
      if (keep[order[i]]) { i--; continue }
      var end = i
      while (i >= 0 && !keep[order[i]]) i--
      rowModel.remove(i + 1, end - i)
      order.splice(i + 1, end - i)
    }
    for (var k = 0; k < want.length; k++) {
      if (order[k] === want[k]) continue
      var j = order.indexOf(want[k], k + 1)
      if (j >= 0) {
        rowModel.move(j, k, 1)
        order.splice(j, 1)
      } else {
        rowModel.insert(k, { api: want[k] })
      }
      order.splice(k, 0, want[k])
    }
    shownApis = order
  }

  // Opened on one achievement (a rarest unlock in the panel): clear what
  // could hide it, then highlight it in the middle of the list, revealed
  // if it is a hidden one.
  function focusRequested() {
    var api = focusApi
    focusApi = ""
    if (!byApi[api]) return
    if (!keep(byApi[api])) {
      filter = "all"
      search = ""
      appliedSearch = ""
      rebuild()
    }
    var index = rows.findIndex(function(a) { return a.api === api })
    if (index < 0) return
    list.currentIndex = index
    list.positionViewAtIndex(index, ListView.Center)
    if (byApi[api].hidden) {
      var next = Object.assign({}, revealed)
      next[api] = true
      revealed = next
    }
  }

  function showcaseKey(api) {
    return game ? game.store + ":" + game.app + (api ? ":" + api : "") : ""
  }

  function pinned(api) {
    return showcaseKeys.indexOf(showcaseKey(api)) >= 0
  }

  // Pins or unpins one trophy (no api: the game's platinum) on the Profile
  // showcase. Shown at once; omatrophy.py writes config.json, which the
  // panel reads on its next open. A full showcase takes no more.
  function togglePin(api) {
    var key = showcaseKey(api)
    var add = showcaseKeys.indexOf(key) < 0
    if (add && showcaseKeys.length >= showcaseMax) return
    showcaseKeys = add ? showcaseKeys.concat([key]) : showcaseKeys.filter(function(k) { return k !== key })
    var args = ["python3", helperPath, "showcase", add ? "add" : "remove", String(game.store), String(game.app)]
    saver.exec(api ? args.concat([api]) : args)
  }

  // "I'm here": pin the step at `index`, or with -1 go back to the
  // automatic guess (OmaTrophy only sees trophies, so the guess can be
  // wrong). `guide here` saves it and answers with the guide.
  function pinStep(index) {
    if (!game || !live) return
    trackPick = -1
    pinner.command = ["python3", helperPath, "guide", "here", String(game.store), String(game.app),
                      index < 0 ? "clear" : String(index + 1)]
    pinner.running = true
  }

  // Pins or unpins this finished game on the completionist tile.
  function toggleCompletionist() {
    var key = showcaseKey("")
    var add = completionistKeys.indexOf(key) < 0
    if (add && completionistKeys.length >= completionistMax) return
    completionistKeys = add ? completionistKeys.concat([key]) : completionistKeys.filter(function(k) { return k !== key })
    saver.exec(["python3", helperPath, "completionist", add ? "add" : "remove", String(game.store), String(game.app)])
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

  function toggleRevealAll() {
    revealAll = !revealAll
    if (live) saver.exec(["python3", helperPath, "set", "reveal-hidden", revealAll ? "on" : "off"])
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
    if (kind === "guide") return hasGuide ? "✦ " + name : name
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
    var all = ["all", "locked", "unlocked", "rare", "guide"]
    filter = all[(all.indexOf(filter) + step + all.length) % all.length]
  }

  // ------------------------------------------------------------ guide

  // The make job's stages, for the progress list; research only runs with
  // web search on.
  function jobStages() {
    var out = [{ key: "gather", label: "Gather sources" }]
    if (job.web) out.push({ key: "research", label: "Search the web for guides" })
    out.push({ key: "classify", label: "Classify " + (job.open || "the open") + " achievements" })
    out.push({ key: "route", label: "Plan the route and write the notes" })
    out.push({ key: "walkthrough", label: "Walk through the game, step by step" })
    out.push({ key: "verify", label: "Check every quote against its page" })
    return out
  }

  function shown(api) {
    return !appliedSearch || guideMatches(api)
  }

  // Open achievements the guide has no entry for (or every open one, with
  // no guide), in the store's order.
  function unguided() {
    if (!game) return []
    return game.achievements.filter(function(a) {
      return !guideDone(a.api) && !(guide && guide.items && guide.items[a.api]) && shown(a.api)
    }).map(function(a) { return a.api })
  }

  // Done achievements (unlocked, or ticked by hand), newest first.
  function doneApis() {
    if (!game) return []
    return game.achievements.filter(function(a) { return guideDone(a.api) && shown(a.api) })
             .sort(function(a, b) { return b.time - a.time }).map(function(a) { return a.api })
  }

  // `known`: the guide came with the game (load()); only the agents and
  // jobs are left to read.
  function readGuide(known) {
    if (!known) {
      guideReader.command = ["python3", helperPath, "guide", String(game.store), String(game.app)]
      guideReader.running = true
    }
    if (!agentsReader.running && agents.length === 0) agentsReader.running = true
    jobReader.running = true
  }

  // The saved pick, else Omarchy's default agent, else the first that runs.
  function choosePick() {
    var row = agents.find(function(a) { return a.agent === configAgent && a.installed && a.supported })
           || agents.find(function(a) { return a.default && a.installed && a.supported })
           || runnable[0] || null
    pickAgent = row ? row.agent : ""
    pickModel = row ? row.model : ""
    pickEffort = row ? row.effort : ""
  }

  function pickAgentNamed(id) {
    var row = agents.find(function(a) { return a.agent === id })
    if (!row) return
    pickAgent = id
    pickModel = row.model
    pickEffort = row.effort
    Quickshell.execDetached(["python3", helperPath, "set", "guide-agent", id])
  }

  // "" is the agent's own default; written per agent (`guide-models`).
  function pickModelNamed(model, effort) {
    pickModel = model
    pickEffort = model ? effort : ""
    var args = ["python3", helperPath, "guide", "model", pickAgent, model || "default"]
    Quickshell.execDetached(model && effort ? args.concat([effort]) : args)
  }

  // The Make-guide pickers' rows ({value, name, detail}), the same lists
  // Settings > Guides unfolds.
  function agentRows() {
    return runnable.map(function(a) {
      return { value: a.agent, name: a.name + (a.default ? " · default" : ""),
               detail: a.model ? "Model: " + modelName(a, a.model) : "Its default model" }
    })
  }

  function modelName(row, id) {
    var m = row ? row.models.find(function(x) { return x.id === id }) : null
    return m ? m.name : id
  }

  function modelRows() {
    var row = pickedRow
    if (!row) return []
    var pick = row.suggested || ({})
    var rows = [{ value: "", name: "Agent's default", detail: row.name + " picks it" }]
    // The guide bench's best pick right after the default, with why.
    if (pick.model) rows.push({ value: pick.model, name: modelName(row, pick.model) + "  ★", detail: pick.why })
    row.models.forEach(function(m) {
      if (m.id === pick.model) return
      var bits = []
      if (m.name.toLowerCase() !== m.id.toLowerCase()) bits.push(m.id)
      if (m.efforts && m.efforts.length) bits.push(m.efforts.join(" · "))
      rows.push({ value: m.id, name: m.name, detail: bits.join("  ·  ") })
    })
    return rows
  }

  function effortRows() {
    return [{ value: "", name: "Model's default", detail: "Whatever the model uses on its own" }].concat(
      modelEfforts().map(function(e) { return { value: e, name: e.charAt(0).toUpperCase() + e.slice(1), detail: "" } }))
  }

  function toggleMakerMenu(name) {
    makerMenu = makerMenu === name ? "" : name
  }

  function modelEfforts() {
    if (!pickedRow) return []
    var m = pickedRow.models.find(function(m) { return m.id === pickModel })
    return m ? m.efforts : (pickedRow.models.length ? pickedRow.models[0].efforts : [])
  }

  // Runs detached: the job outlives this card, which only shows it.
  function makeGuide() {
    if (!game || !pickAgent || making || jobsFull) return
    // --notify: the owner may close this long before it ends.
    var args = ["python3", helperPath, "guide", "make", String(game.store), String(game.app), "--notify", "--agent", pickAgent]
    if (pickModel) args = args.concat(["--model", pickModel])
    if (pickEffort) args = args.concat(["--effort", pickEffort])
    Quickshell.execDetached(args)
    job = { state: "running", store: game.store, app: String(game.app), game: game.game, stage: "gather",
            done: 0, total: 1, line: "starting " + pickAgent, agent: pickAgent, model: pickModel }
    makerOpen = false
    jobPoll.restart()
  }

  function stopGuide() {
    Quickshell.execDetached(["python3", helperPath, "guide", "stop"])
    job = Object.assign({}, job, { line: "stopping…" })
  }

  // A walkthrough step's achievements in one line: a hidden one stays
  // secret like its row, a missable one is marked, a done one ticked.
  function stepDone(step) {
    return (step.achievements || []).filter(function(api) { return guideDone(api) }).length
  }

  function stepNames(step) {
    var missables = step.missables || []
    return factJoin((step.achievements || []).map(function(api) {
      var a = byApi[api] || { name: api }
      var secret = a.hidden && !a.unlocked && !revealed[api] && !revealAll
      // The item's own missable flag counts too: MGSV's walkthrough left
      // War Buddy out of every step's missables.
      var item = guide && guide.items ? guide.items[api] || {} : {}
      // No-break spaces keep ⚠ and ✓ with the name: at a large font the
      // line broke before the ✓ and left it alone on the next line.
      return ((missables.indexOf(api) >= 0 || item.missable) && !guideDone(api) ? "⚠\u00a0" : "") + (secret ? "Hidden achievement" : a.name)
             + (guideDone(api) ? "\u00a0✓" : "")
    }))
  }

  function guideItem(api) {
    return guide && guide.items ? guide.items[api] || ({}) : ({})
  }

  function isSecret(api) {
    var a = byApi[api]
    return !!a && a.hidden && !a.unlocked && !revealed[api] && !revealAll
  }

  // Picks a trophy from the tree: the list scrolls to it, and its tips
  // show in the part it was picked in; a second click puts them away.
  function pickInTree(api, part) {
    highlightApi = api
    var same = treePick === api && treePickIn === part
    treePick = same ? "" : api
    treePickIn = same ? "" : part
  }

  function stepOf(api) {
    for (var i = 0; i < walkSteps.length; i++)
      if ((walkSteps[i].achievements || []).indexOf(api) >= 0) return i
    return -1
  }

  // The step action that gives a trophy: {step, where, what}, null when
  // no step holds it.
  function actionOf(api) {
    var i = stepOf(api)
    if (i < 0) return null
    var act = (walkSteps[i].actions || []).find(function(a) { return a.achievement === api })
    return { step: i, where: act ? act.where : "", what: act ? act.what : "" }
  }

  // Where a trophy is got, as a player scans for it: the step's number
  // and the action's place ("Step 2 · Sea wall"), else the step's title;
  // with no step, a missable's last chance, else its phase.
  function placeOf(api) {
    var at = actionOf(api)
    var item = guideItem(api)
    if (!at) return item.missable && item.missable_note ? item.missable_note : phaseNames[item.phase] || ""
    return unbroken("Step " + (at.step + 1)) + "  ·\u00a0\u00a0" + (at.where || walkSteps[at.step].title)
  }

  // The one-line move: the action, else the tip, else the store's
  // description; nothing for a secret.
  function moveOf(api) {
    var at = actionOf(api)
    if (at && at.what) return at.what
    if (isSecret(api)) return ""
    var a = byApi[api] || {}
    return guideItem(api).tips || (a.hidden ? "" : a.desc || "")
  }

  // A counter's progress, {fraction, text}, or null with no counter.
  function counterOf(api) {
    var item = guideItem(api), a = byApi[api] || {}
    var max = item.counter && item.counter.target ? item.counter.target : a.progress ? a.progress.max : 0
    if (!max) return null
    var value = guideDone(api) ? max : a.progress ? a.progress.value : 0
    var label = item.counter && item.counter.label ? " " + item.counter.label : ""
    return { fraction: Math.min(1, value / max), text: unbroken(value + " / " + max + label) }
  }

  function isMissable(api) {
    if (guideItem(api).missable) return true
    var i = stepOf(api)
    return i >= 0 && (walkSteps[i].missables || []).indexOf(api) >= 0
  }

  // Missables still open in a step the player has left: the chance has
  // gone (until a new game), so the track flags it.
  function lostAt(index) {
    if (walkSteps.length === 0 || currentStep < 0 || index >= currentStep) return []
    return (walkSteps[index].achievements || []).filter(function(api) { return isMissable(api) && !guideDone(api) })
  }

  // What a trophy opens: the guide's items that need it first.
  function opensOf(api) {
    if (!guide || !guide.items) return []
    return Object.keys(guide.items).filter(function(k) { return (guide.items[k].requires || []).indexOf(api) >= 0 })
  }

  // A chain laid out as a small tree, goal on top: leaves take slots left
  // to right and a parent sits over the middle of its children. `x` is in
  // slots, `parent` an index into `nodes` (-1 for the goal).
  function chainLayout(tree) {
    var nodes = [], slot = 0, rows = 0
    function place(n, depth, parent) {
      var me = { api: n.api, depth: depth, parent: parent, x: 0 }
      var at = nodes.length
      nodes.push(me)
      rows = Math.max(rows, depth + 1)
      if (n.kids.length === 0) { me.x = slot++; return me.x }
      var xs = n.kids.map(function(k) { return place(k, depth + 1, at) })
      me.x = (xs[0] + xs[xs.length - 1]) / 2
      return me.x
    }
    place(tree, 0, -1)
    return { nodes: nodes, cols: slot, rows: rows }
  }

  // On their own by phase, in the reader's order, each {phase, apis, done}.
  function aloneGroups() {
    var groups = {}
    ;(guideTree.alone || []).forEach(function(api) {
      if (!byApi[api]) return
      var p = phases.indexOf(guideItem(api).phase) >= 0 ? guideItem(api).phase : "other"
      if (!groups[p]) groups[p] = []
      groups[p].push(api)
    })
    return phases.concat(["other"]).filter(function(p) { return !!groups[p] }).map(function(p) {
      return { phase: p, apis: groups[p], done: groups[p].filter(function(a) { return guideDone(a) }).length }
    })
  }

  function togglePhase(phase) {
    var next = Object.assign({}, foldedPhases)
    next[phase] = !next[phase]
    foldedPhases = next
  }

  // What an item still waits for: its `requires` not done yet.
  function lockedBy(api) {
    var item = guide && guide.items ? guide.items[api] : null
    var needs = item && Array.isArray(item.requires) ? item.requires : []
    return needs.filter(function(r) { return !guideDone(r) })
  }

  // A trophy's name for one line, a hidden one kept secret like its row.
  function shownName(api) {
    var a = byApi[api]
    if (!a) return ""
    return a.hidden && !a.unlocked && !revealed[api] && !revealAll ? "Hidden achievement" : a.name
  }

  function guideDone(api) {
    var a = byApi[api]
    return (a && a.unlocked) || (!!guide && (guide.ticks || []).indexOf(api) >= 0)
  }

  // The guide's open items by phase, in the route's order, missables first.
  function phaseGroups() {
    if (!guide || !guide.items) return []
    var groups = {}
    var order = (guide.order || []).concat(Object.keys(guide.items).filter(function(a) { return (guide.order || []).indexOf(a) < 0 }))
    order.forEach(function(api) {
      var item = guide.items[api]
      if (!item || !byApi[api] || guideDone(api)) return
      if (appliedSearch && !guideMatches(api)) return
      var phase = phases.indexOf(item.phase) >= 0 ? item.phase : "other"
      if (!groups[phase]) groups[phase] = []
      groups[phase].push(api)
    })
    return phases.concat(["other"]).filter(function(p) { return !!groups[p] })
                 .map(function(p) { return { phase: p, apis: groups[p] } })
  }

  function guideMatches(api) {
    var q = appliedSearch.toLowerCase()
    var a = byApi[api], item = (guide && guide.items && guide.items[api]) || {}
    var secret = a.hidden && !a.unlocked
    return a.name.toLowerCase().indexOf(q) >= 0 || (!secret && (item.tips || "").toLowerCase().indexOf(q) >= 0)
  }

  function doneCount() {
    if (!guide || !guide.items) return 0
    return Object.keys(guide.items).filter(function(api) { return byApi[api] && guideDone(api) }).length
  }

  // Guide prose is the agent's (or an imported file's) text: images, as
  // Markdown or HTML, are dropped so showing it fetches nothing.
  function safeMarkdown(text) {
    return String(text || "").replace(/!\[[^\]]*\]\([^)]*\)/g, "").replace(/<img\b[^>]*>/gi, "")
  }

  // Short facts in a wrapping line ("~1-2 h", "9 / 14 systems") stay
  // whole: the line broke between "9 /" and "14 systems".
  function unbroken(text) {
    return String(text).replace(/ /g, "\u00a0")
  }

  // Joins a wrapping line's parts with " · ", the dot kept with the part
  // after it: the line broke after the dot and left it hanging at the end.
  function factJoin(parts) {
    return parts.join("  ·\u00a0\u00a0")
  }

  function dots(n) {
    var out = ""
    for (var i = 1; i <= 5; i++) out += i <= n ? "●" : "○"
    return out
  }

  function madeLine() {
    if (!guide || !guide.generated) return "Imported guide"
    var a = guide.agent || {}
    var who = a.name ? " with " + a.name + (a.model ? " · " + a.model : "") : ""
    var made = "Made " + day(guide.generated) + who + (guide.cost_usd ? " · $" + guide.cost_usd.toFixed(2) : "")
    // A newer maker writes better guides (guides.MAKER): say so, as the
    // owner judged an older MGSV guide thin without knowing.
    return made + (guide.outdated ? " · older maker" : "")
  }

  function forceKeys() {
    keys.forceActiveFocus()
  }

  Component.onCompleted: Qt.callLater(function() { keys.forceActiveFocus() })

  // Caption line height, for the tree's fixed-size nodes.
  FontMetrics {
    id: captionMetrics
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.caption
  }

  FileView {
    // Only when live: an offscreen render (dev/render.sh) shows the
    // samples, not the owner's settings and model picks.
    path: root.live ? Quickshell.env("HOME") + "/.config/omatrophy/config.json" : ""
    printErrors: false
    onLoaded: {
      var c = {}
      try { c = JSON.parse(text()) } catch (e) { return }
      if (c.icons) root.iconSet = c.icons
      if (c["tracker-sort"]) root.sortBy = c["tracker-sort"]
      if (Array.isArray(c.showcase)) root.showcaseKeys = c.showcase
      if (Array.isArray(c.completionist)) root.completionistKeys = c.completionist
      if (typeof c["guide-agent"] === "string") root.configAgent = c["guide-agent"]
      root.revealAll = c["reveal-hidden"] === true
    }
  }

  Process {
    id: guideReader
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.guide = JSON.parse(text) || {} } catch (e) { root.guide = {} }
        root.makerOpen = !root.hasGuide
      }
    }
  }

  // A failed pin prints nothing: read the guide again rather than lose it.
  Process {
    id: pinner
    stdout: StdioCollector {
      onStreamFinished: {
        var found = null
        try { found = JSON.parse(text) } catch (e) {}
        if (found && Array.isArray(found.walkthrough)) root.guide = found
        else root.readGuide()
      }
    }
  }

  Process {
    id: agentsReader
    command: ["python3", root.helperPath, "guide", "agents"]
    stdout: StdioCollector {
      onStreamFinished: {
        try { root.agents = JSON.parse(text) || [] } catch (e) { root.agents = [] }
        root.choosePick()
      }
    }
  }

  Process {
    id: jobReader
    command: ["python3", root.helperPath, "guide", "jobs"]
    stdout: StdioCollector {
      onStreamFinished: {
        var was = root.job
        var found = {}
        try { found = JSON.parse(text) || {} } catch (e) { return }
        var list = Array.isArray(found.jobs) ? found.jobs : []
        var g = root.game
        var mine = g ? list.find(function(j) { return j.store === g.store && String(j.app) === String(g.app) }) : null
        root.job = mine || {}
        root.othersRunning = list.filter(function(j) { return j.state === "running" && j !== mine }).length
        if (found.max) root.jobsMax = found.max
        if (!root.jobSeen) {
          root.jobSeen = true
          var fresh = root.job.state === "done" && Date.now() / 1000 - (root.job.time || 0) < 900
          if ((root.making || fresh) && root.jobHere) root.filter = "guide"
        }
        // A make of this game just ended: show what it wrote, or reopen
        // the maker with what went wrong (it closed when the make began,
        // and with no guide the tab was left empty).
        if (was.state === "running" && root.job.state === "done" && root.jobHere) root.readGuide()
        if (was.state === "running" && (root.job.state === "failed" || root.job.state === "stopped") && root.jobHere)
          root.makerOpen = true
      }
    }
  }

  // The job writes status.json as it goes; a light poll while it runs.
  Timer {
    id: jobPoll
    interval: 1500
    repeat: true
    running: root.live && (root.making || root.othersRunning > 0)
    onTriggered: if (!jobReader.running) jobReader.running = true
  }

  Timer {
    id: searchPause
    interval: 180
    onTriggered: root.appliedSearch = root.search
  }

  ListModel { id: rowModel }

  Timer {
    id: cascadeEnd
    interval: 400
    onTriggered: root.cascading = false
  }

  Process { id: saver }

  Process {
    id: loader
    stdout: StdioCollector {
      onStreamFinished: {
        if (!text) return
        var found = null
        try { found = JSON.parse(text) } catch (e) { root.error = "Couldn't read the game's achievements."; return }
        var guide = found.guide
        delete found.guide
        root.guideWithGame = guide !== undefined
        root.game = found
        if (guide !== undefined) {
          root.guide = guide || {}
          root.makerOpen = !root.hasGuide
        }
      }
    }
    stderr: StdioCollector {
      onStreamFinished: if (text && !root.game) root.error = text.trim()
    }
  }

  // One trophy, drawn the way the cards draw it (the omarchy set's inlay
  // painted in the theme accent).
  // A ★ that pins a trophy to the Profile showcase: lit while pinned,
  // dim on offer, and "full" when six are already pinned.
  component PinStar: Rectangle {
    id: pin
    property bool on: false
    readonly property bool full: !on && root.showcaseKeys.length >= root.showcaseMax
    readonly property bool hovered: pinHit.containsMouse
    signal toggled()
    width: Commons.Style.space(26)
    height: width
    radius: width / 2
    color: pinHit.containsMouse && !full ? Commons.Style.hoverFill : "transparent"
    Accessible.role: Accessible.CheckBox
    Accessible.name: on ? "Pinned to the showcase" : "Pin to the showcase"
    Accessible.checked: on
    Text {
      textFormat: Text.PlainText
      anchors.centerIn: parent
      text: pin.on ? "★" : "☆"
      color: pin.on ? Commons.Color.accent : root.foreground
      opacity: pin.on ? 1 : (pin.full ? 0.2 : (pinHit.containsMouse ? 0.9 : 0.5))
      font.pixelSize: Commons.Style.font.title
    }
    MouseArea {
      id: pinHit
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: pin.full ? Qt.ArrowCursor : Qt.PointingHandCursor
      onClicked: if (!pin.full) pin.toggled()
    }
    PanelToolTip {
      visible: pinHit.containsMouse
      text: pin.on ? "On your showcase · click to take it off"
            : pin.full ? "Your showcase is full (6) · unpin one first"
            : "Pin to your Profile's showcase"
    }
  }

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
    // clip cuts to the box, not the rounded edge: the band showed square
    // corners around the round ring placeholder. A round bone pulses
    // instead.
    readonly property bool round: radius * 2 >= Math.min(width, height) - 1
    color: Qt.alpha(root.foreground, 0.07)
    radius: 3
    clip: true
    SequentialAnimation on opacity {
      running: bone.round && bone.visible
      loops: Animation.Infinite
      NumberAnimation { to: 0.55; duration: 650; easing.type: Easing.InOutSine }
      NumberAnimation { to: 1; duration: 650; easing.type: Easing.InOutSine }
    }
    Rectangle {
      visible: !bone.round
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

  // A field that shows a choice and unfolds its list below (Make guide's
  // agent, model and effort): repeated from StylePicker.qml, since views
  // built by FreshObject.qml can't share types.
  component PickerField: Rectangle {
    id: picker
    property string title: ""
    property string detail: ""
    property bool open: false
    signal toggled()
    width: parent ? parent.width : 0
    height: pickerText.implicitHeight + Commons.Style.space(18)
    radius: Commons.Style.cornerRadius
    color: pickerHit.containsMouse ? Commons.Style.hoverFill : Qt.alpha(root.foreground, 0.04)
    border.width: 1
    border.color: open ? Qt.alpha(Commons.Color.accent, 0.6) : Qt.alpha(root.foreground, pickerHit.containsMouse ? 0.25 : 0.12)
    Accessible.role: Accessible.ComboBox
    Accessible.name: title + (detail ? ", " + detail : "")
    Behavior on color { ColorAnimation { duration: 120 } }
    Column {
      id: pickerText
      x: Commons.Style.space(12)
      anchors.verticalCenter: parent.verticalCenter
      width: parent.width - Commons.Style.space(48)
      spacing: Commons.Style.space(1)
      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: picker.title
        color: root.foreground
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        font.bold: true
      }
      Caption {
        width: parent.width
        visible: text !== ""
        text: picker.detail
        opacity: 0.5
      }
    }
    Text {
      textFormat: Text.PlainText
      anchors.right: parent.right
      anchors.rightMargin: Commons.Style.space(14)
      anchors.verticalCenter: parent.verticalCenter
      text: "▾"
      color: picker.open ? Commons.Color.accent : root.foreground
      opacity: picker.open ? 1 : 0.5
      rotation: picker.open ? 180 : 0
      font.pixelSize: Commons.Style.font.title * 1.4
      Behavior on rotation { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
    }
    MouseArea {
      id: pickerHit
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: picker.toggled()
    }
  }

  // The list a PickerField unfolds: one row per choice, a dot on the
  // current one, a line under each name.
  component PickerList: Rectangle {
    id: plist
    property var rows: []
    property string current: ""
    signal picked(string value)
    width: parent ? parent.width : 0
    height: plistRows.height + Commons.Style.space(8)
    radius: Commons.Style.cornerRadius
    color: Qt.alpha(root.foreground, 0.03)
    border.width: 1
    border.color: Qt.alpha(root.foreground, 0.08)
    Column {
      id: plistRows
      y: Commons.Style.space(4)
      width: parent.width
      Repeater {
        model: plist.visible ? plist.rows : []
        delegate: Rectangle {
          id: prow
          required property var modelData
          readonly property bool chosen: plist.current === modelData.value
          width: plistRows.width
          height: prowName.implicitHeight + (prowDetail.visible ? prowDetail.implicitHeight : 0) + Commons.Style.space(14)
          color: prowHit.containsMouse ? Commons.Style.hoverFill : "transparent"
          Accessible.role: Accessible.RadioButton
          Accessible.name: modelData.name
          Accessible.checked: chosen
          MouseArea {
            id: prowHit
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: plist.picked(prow.modelData.value)
          }
          Text {
            textFormat: Text.PlainText
            id: prowDot
            x: Commons.Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            text: prow.chosen ? "◉" : "○"
            color: prow.chosen ? Commons.Color.accent : root.foreground
            opacity: prow.chosen ? 1 : 0.5
            font.pixelSize: Commons.Style.font.body
          }
          Column {
            anchors.left: prowDot.right
            anchors.leftMargin: Commons.Style.space(10)
            anchors.right: parent.right
            anchors.rightMargin: Commons.Style.space(12)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Commons.Style.space(1)
            Text {
              textFormat: Text.PlainText
              id: prowName
              width: parent.width
              text: prow.modelData.name
              color: root.foreground
              wrapMode: Text.Wrap
              maximumLineCount: 2
              elide: Text.ElideRight
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.bodySmall
              font.bold: prow.chosen
            }
            Caption {
              id: prowDetail
              width: parent.width
              visible: text !== ""
              opacity: 0.5
              text: prow.modelData.detail || ""
            }
          }
        }
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

  // A small caps label over a guide section.
  component SectionLabel: Text {
    textFormat: Text.PlainText
    color: root.foreground
    opacity: 0.55
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.caption
    font.letterSpacing: 1.5
    font.bold: true
  }

  // A filled button for the one action that starts something (Make guide).
  component ActionButton: Rectangle {
    id: actionButton
    property string text: ""
    property bool accent: true
    signal clicked()
    width: actionText.implicitWidth + Commons.Style.space(24)
    height: actionText.implicitHeight + Commons.Style.space(12)
    radius: height / 2
    color: accent ? (actionHit.containsMouse ? Qt.lighter(Commons.Color.accent, 1.15) : Commons.Color.accent)
                  : (actionHit.containsMouse ? Commons.Style.hoverFill : "transparent")
    border.width: accent ? 0 : 1
    border.color: Qt.alpha(root.foreground, 0.25)
    Accessible.role: Accessible.Button
    Accessible.name: text
    Text {
      textFormat: Text.PlainText
      id: actionText
      anchors.centerIn: parent
      text: actionButton.text
      color: actionButton.accent ? root.background : root.foreground
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      font.bold: true
    }
    MouseArea {
      id: actionHit
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: actionButton.clicked()
    }
  }

  // Under an open step: "I'm here" on a step that isn't where the player
  // is, "Back to automatic" on the one they pinned; none on the guessed one.
  component StepPinButton: Item {
    id: pinBtn
    property int index: -1
    property bool shown: true
    readonly property bool pinnedHere: root.stepPinned && index === root.currentStep
    visible: shown && index >= 0 && (pinnedHere || index !== root.currentStep)
    width: pinAction.width
    height: visible ? pinAction.height + Commons.Style.space(4) : 0
    ActionButton {
      id: pinAction
      y: Commons.Style.space(4)
      accent: false
      text: pinBtn.pinnedHere ? "Back to automatic" : "I'm here"
      onClicked: root.pinStep(pinBtn.pinnedHere ? -1 : pinBtn.index)
    }
  }

  // Guide prose (Markdown from the agent or an imported guide). Links open
  // in the browser only when they are https.
  component Prose: Text {
    textFormat: Text.MarkdownText
    wrapMode: Text.Wrap
    color: root.foreground
    opacity: 0.85
    linkColor: Commons.Color.accent
    font.family: Commons.Style.font.family
    font.pixelSize: Commons.Style.font.bodySmall
    onLinkActivated: function(link) { if (/^https:\/\//.test(link)) Qt.openUrlExternally(link) }
    HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
  }

  // A trophy's art for the tree: framed in its metal once done, dim while
  // open, greyed with a lock while it waits for something. `ready` (its
  // prerequisites done, itself open) glows in the accent; `badge` adds the
  // metal's trophy in a corner.
  component ArtIcon: Item {
    id: art
    property string api: ""
    property real size: Commons.Style.space(36)
    property bool ready: false
    property bool picked: false
    property bool badge: false
    property bool tick: false
    readonly property var ach: root.byApi[api] || ({})
    readonly property bool done: root.guideDone(api)
    readonly property bool locked: !done && root.lockedBy(api).length > 0
    readonly property color metal: root.metalColors[ach.tier] || root.metalColors.bronze
    width: size
    height: size
    // The glow, as soft rings: the software renderer drops MultiEffect.
    Repeater {
      model: art.ready ? [Commons.Style.space(7), Commons.Style.space(3.5)] : []
      delegate: Rectangle {
        required property real modelData
        anchors.centerIn: parent
        width: art.size + modelData * 2
        height: width
        radius: 5 + modelData
        color: Qt.alpha(Commons.Color.accent, modelData > Commons.Style.space(5) ? 0.10 : 0.20)
      }
    }
    Rectangle {
      anchors.fill: parent
      radius: 5
      color: Qt.alpha(root.foreground, 0.08)
      border.width: art.done || art.ready || art.picked ? 2 : 1
      border.color: art.picked ? Commons.Color.accent : art.done ? art.metal
                    : art.ready ? Commons.Color.accent : Qt.alpha(root.foreground, 0.16)
      Behavior on border.color { ColorAnimation { duration: 160 } }
      Image {
        anchors.fill: parent
        anchors.margins: 2
        source: art.done ? art.ach.icon || "" : (art.ach.icon_locked || art.ach.icon || "")
        asynchronous: true
        sourceSize: Qt.size(96, 96)
        opacity: status !== Image.Ready ? 0 : art.done ? 1 : art.locked ? 0.25 : 0.7
      }
    }
    // `tick`: a done one says so in its corner too.
    Rectangle {
      visible: art.tick && art.done
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: -Commons.Style.space(4)
      width: Commons.Style.space(14)
      height: width
      radius: width / 2
      color: Commons.Color.accent
      border.width: 1.5
      border.color: root.background
      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: "✓"
        color: root.background
        font.pixelSize: Math.round(Commons.Style.font.caption * 0.8)
        font.bold: true
      }
    }
    LockGlyph {
      visible: art.locked
      anchors.centerIn: parent
      scale: art.size >= Commons.Style.space(30) ? 1 : 0.8
    }
    Rectangle {
      visible: art.badge
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.margins: -Commons.Style.space(4)
      width: Math.round(art.size * 0.42)
      height: width
      radius: width / 2
      color: root.background
      border.width: 1
      border.color: Qt.alpha(art.metal, art.done ? 0.8 : 0.3)
      Trophy {
        anchors.centerIn: parent
        style: root.iconSet
        metal: art.ach.tier || "bronze"
        width: parent.width * 0.62
        height: width
        opacity: art.done ? 1 : 0.5
      }
    }
  }

  // A padlock drawn from boxes, so it shows in any theme font.
  component LockGlyph: Rectangle {
    width: Commons.Style.space(18)
    height: width
    radius: width / 2
    color: Qt.alpha(root.background, 0.75)
    Rectangle {
      x: (parent.width - width) / 2
      y: parent.height * 0.2
      width: parent.width * 0.38
      height: parent.height * 0.42
      radius: width / 2
      color: "transparent"
      border.width: Math.max(1.5, Commons.Style.space(1.5))
      border.color: root.foreground
      opacity: 0.85
    }
    Rectangle {
      x: (parent.width - width) / 2
      y: parent.height * 0.43
      width: parent.width * 0.52
      height: parent.height * 0.36
      radius: 2
      color: root.foreground
      opacity: 0.85
    }
  }

  // A thin progress bar that fills when it first shows.
  component MeterBar: Rectangle {
    id: meter
    property real fraction: 0
    property color fill: Commons.Color.accent
    property real shown: 0
    height: Math.max(3, Commons.Style.space(3))
    radius: height / 2
    color: Qt.alpha(root.foreground, 0.12)
    Component.onCompleted: shown = Qt.binding(function() { return meter.fraction })
    Behavior on shown { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
    Rectangle {
      height: parent.height
      radius: parent.radius
      width: parent.width * Math.max(0, Math.min(1, meter.shown))
      color: meter.fill
    }
  }

  // A drawn pin beside YOU ARE HERE when the player set the step; drawn,
  // not an emoji, so it needs no emoji font.
  component PinMark: Item {
    property real size: Commons.Style.space(12)
    width: size * 0.8
    height: size
    Accessible.name: "pinned by you"
    Item {
      anchors.fill: parent
      rotation: 30
      Rectangle {
        x: (parent.width - width) / 2
        y: parent.height * 0.42
        width: Math.max(1.5, parent.width * 0.14)
        height: parent.height * 0.58
        radius: width / 2
        color: Commons.Color.accent
      }
      Rectangle {
        x: (parent.width - width) / 2
        width: parent.width * 0.78
        height: width
        radius: width / 2
        color: Commons.Color.accent
      }
    }
  }

  // A small upper-case tag: MISSABLE, READY, YOU ARE HERE.
  component Tag: Rectangle {
    id: tag
    property string text: ""
    property color tint: Commons.Color.accent
    property bool solid: false
    width: tagText.implicitWidth + Commons.Style.space(10)
    height: tagText.implicitHeight + Commons.Style.space(3)
    radius: height / 2
    color: solid ? tint : Qt.alpha(tint, 0.14)
    border.width: solid ? 0 : 1
    border.color: Qt.alpha(tint, 0.5)
    Text {
      textFormat: Text.PlainText
      id: tagText
      anchors.centerIn: parent
      text: tag.text
      color: tag.solid ? root.background : tag.tint
      font.family: Commons.Style.font.family
      font.pixelSize: Math.round(Commons.Style.font.caption * 0.85)
      font.letterSpacing: 1
      font.bold: true
    }
  }

  // One step action (maker 4): where above what, ticked once the trophy
  // it gives is done. With `picking` (the tree) a click on one that gives
  // a trophy picks it.
  component ActionLine: Item {
    id: actRow
    property var action: ({})
    property bool picking: false
    property string part: ""
    readonly property bool ticked: action.achievement !== "" && root.guideDone(action.achievement)
    readonly property bool pickable: picking && action.achievement !== ""
    height: Math.max(actMark.implicitHeight, actText.height)
    Rectangle {
      visible: actRow.pickable && actHover.hovered
      anchors.fill: parent
      anchors.margins: -Commons.Style.space(2)
      radius: Commons.Style.cornerRadius
      color: Commons.Style.hoverFill
    }
    HoverHandler { id: actHover; enabled: actRow.pickable; cursorShape: Qt.PointingHandCursor }
    TapHandler { enabled: actRow.pickable; onTapped: root.pickInTree(actRow.action.achievement, actRow.part) }
    Text {
      textFormat: Text.PlainText
      id: actMark
      width: Commons.Style.space(18)
      text: actRow.ticked ? "✓" : actRow.action.achievement !== "" ? "○" : "·"
      color: actRow.ticked ? Commons.Color.accent : root.foreground
      opacity: actRow.ticked ? 0.8 : 0.6
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.bodySmall
      font.bold: true
    }
    // Where above what: the place is what a player scans for.
    Column {
      id: actText
      anchors.left: actMark.right
      anchors.right: parent.right
      opacity: actRow.ticked ? 0.5 : 1
      Caption {
        textFormat: Text.PlainText
        width: parent.width
        visible: (actRow.action.where || "") !== ""
        wrapMode: Text.Wrap
        elide: Text.ElideNone
        text: actRow.action.where || ""
        font.bold: true
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        wrapMode: Text.Wrap
        text: actRow.action.what
              + (actRow.action.achievement ? "  ·  " + root.shownName(actRow.action.achievement) : "")
        color: root.foreground
        opacity: 0.85
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
      }
    }
  }

  // Do now: one trophy the player can get now, as a tile: its art in its
  // metal, name, where (from its step action), the move, a counter's bar
  // and MISSABLE. `stacked` lays it out tall, for three side by side.
  component DoTile: Rectangle {
    id: tile
    property string api: ""
    property bool stacked: false
    property bool first: false
    readonly property var ach: root.byApi[api] || ({})
    readonly property bool secret: root.isSecret(api) && !tileHover.hovered
    readonly property var counter: root.counterOf(api)
    readonly property bool missable: root.isMissable(api)
    readonly property bool picked: root.treePick === api && root.treePickIn === "now"
    readonly property real pad: Commons.Style.space(10)
    implicitHeight: (stacked ? tileArt.height + Commons.Style.space(8) : 0) + tileBody.height + pad * 2
    implicitWidth: 0
    radius: Commons.Style.cornerRadius
    color: tileHover.hovered ? Commons.Style.hoverFill : first ? Qt.alpha(Commons.Color.accent, 0.08) : Qt.alpha(root.foreground, 0.035)
    border.width: 1
    border.color: picked ? Commons.Color.accent : first ? Qt.alpha(Commons.Color.accent, 0.45) : Qt.alpha(root.foreground, 0.1)
    Behavior on color { ColorAnimation { duration: 120 } }
    Accessible.role: Accessible.Button
    Accessible.name: (secret ? "Hidden achievement" : ach.name || "") + ", " + root.placeOf(api)
    HoverHandler { id: tileHover; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: root.pickInTree(tile.api, "now") }
    ArtIcon {
      id: tileArt
      x: tile.pad
      y: tile.pad
      api: tile.api
      size: Commons.Style.space(tile.stacked ? 34 : 40)
      badge: true
      picked: tile.picked
    }
    // Share of players, in the metal's colour, as the list has it.
    Text {
      textFormat: Text.PlainText
      anchors.right: parent.right
      anchors.rightMargin: tile.pad
      y: tile.pad
      visible: tile.ach.percent !== null && tile.ach.percent !== undefined
      text: visible ? tile.ach.percent.toFixed(1) + "%" : ""
      color: root.metalColors[tile.ach.tier] || root.foreground
      opacity: 0.75
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.caption
      font.bold: true
    }
    Column {
      id: tileBody
      x: tile.stacked ? tile.pad : tileArt.x + tileArt.width + Commons.Style.space(12)
      y: tile.stacked ? tileArt.y + tileArt.height + Commons.Style.space(8) : tile.pad
      width: parent.width - x - tile.pad - (tile.stacked ? 0 : Commons.Style.space(44))
      spacing: Commons.Style.space(3)
      Tag {
        visible: tile.missable
        text: "MISSABLE"
        tint: Commons.Color.urgent
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: tile.secret ? "Hidden achievement" : tile.ach.name || ""
        color: root.foreground
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
        font.bold: true
        font.italic: tile.secret
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
      }
      Caption {
        width: parent.width
        visible: text !== ""
        text: root.placeOf(tile.api)
        color: Commons.Color.accent
        opacity: 0.95
        wrapMode: Text.Wrap
        maximumLineCount: 2
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        visible: text !== ""
        text: root.moveOf(tile.api)
        color: root.foreground
        opacity: 0.75
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.caption
        wrapMode: Text.Wrap
        maximumLineCount: tile.stacked ? 3 : 2
        elide: Text.ElideRight
      }
      Item {
        visible: tile.counter !== null
        width: parent.width
        height: tileCount.implicitHeight
        MeterBar {
          anchors.left: parent.left
          anchors.right: tileCount.left
          anchors.rightMargin: Commons.Style.space(6)
          anchors.verticalCenter: parent.verticalCenter
          fraction: tile.counter ? tile.counter.fraction : 0
        }
        Caption {
          id: tileCount
          anchors.right: parent.right
          text: tile.counter ? tile.counter.text : ""
          elide: Text.ElideNone
        }
      }
    }
  }

  // The trophy picked in the tree, inline: what it needs and opens, the
  // tip, where it's got, its counter. A hidden one keeps its secret.
  component PickDetail: Rectangle {
    id: pick
    property string api: ""
    readonly property var ach: root.byApi[api] || ({})
    readonly property var item: root.guideItem(api)
    readonly property bool done: root.guideDone(api)
    readonly property bool secret: root.isSecret(api)
    readonly property var needs: Array.isArray(item.requires) ? item.requires : []
    readonly property var opens: root.opensOf(api)
    readonly property var counter: root.counterOf(api)
    readonly property real pad: Commons.Style.space(12)
    width: parent ? parent.width : 0
    height: pickBody.height + pad * 2
    radius: Commons.Style.cornerRadius
    color: Qt.alpha(Commons.Color.accent, 0.06)
    border.width: 1
    border.color: Qt.alpha(Commons.Color.accent, 0.35)
    opacity: 0
    Component.onCompleted: opacity = 1
    Behavior on opacity { NumberAnimation { duration: 160 } }
    ArtIcon {
      id: pickArt
      x: pick.pad
      y: pick.pad
      api: pick.api
      size: Commons.Style.space(44)
      badge: true
    }
    Text {
      textFormat: Text.PlainText
      id: pickClose
      anchors.right: parent.right
      anchors.rightMargin: pick.pad
      y: pick.pad - Commons.Style.space(3)
      text: "×"
      color: root.foreground
      opacity: pickCloseHover.hovered ? 0.9 : 0.45
      font.pixelSize: Commons.Style.font.bodySmall
      HoverHandler { id: pickCloseHover; cursorShape: Qt.PointingHandCursor }
      TapHandler { onTapped: { root.treePick = ""; root.treePickIn = "" } }
    }
    Column {
      id: pickBody
      x: pickArt.x + pickArt.width + Commons.Style.space(14)
      y: pick.pad
      width: parent.width - x - pick.pad - pickClose.width - Commons.Style.space(6)
      spacing: Commons.Style.space(4)
      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: (pick.done ? "✓ " : "") + (pick.secret ? "Hidden achievement" : pick.ach.name || "")
        color: root.foreground
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        font.bold: true
        font.italic: pick.secret
        wrapMode: Text.Wrap
      }
      Caption {
        width: parent.width
        wrapMode: Text.Wrap
        elide: Text.ElideNone
        text: root.factJoin([
          (pick.ach.tier || "bronze").replace(/^./, function(c) { return c.toUpperCase() })
            + (pick.ach.percent !== null && pick.ach.percent !== undefined ? root.unbroken(" · " + pick.ach.percent.toFixed(1) + "% of players") : ""),
          pick.item.difficulty ? root.dots(pick.item.difficulty) : "",
          pick.done ? (pick.ach.unlocked ? "unlocked " + root.day(pick.ach.time) : "ticked") : root.placeOf(pick.api)
        ].filter(function(p) { return p !== "" }))
      }
      Caption {
        width: parent.width
        visible: root.isMissable(pick.api) && !pick.done
        wrapMode: Text.Wrap
        elide: Text.ElideNone
        text: "⚠ Missable" + (pick.item.missable_note ? ": " + pick.item.missable_note : "")
        color: Commons.Color.urgent
        opacity: 1
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        visible: text !== ""
        text: pick.secret ? "Reveal all shows its name and tip." : (pick.item.tips || (pick.ach.hidden ? "" : pick.ach.desc || ""))
        color: root.foreground
        opacity: pick.secret ? 0.45 : 0.85
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
        font.italic: pick.secret
        wrapMode: Text.Wrap
      }
      Item {
        visible: pick.counter !== null
        width: parent.width
        height: pickCount.implicitHeight
        MeterBar {
          anchors.left: parent.left
          anchors.right: pickCount.left
          anchors.rightMargin: Commons.Style.space(8)
          anchors.verticalCenter: parent.verticalCenter
          fraction: pick.counter ? pick.counter.fraction : 0
        }
        Caption { id: pickCount; anchors.right: parent.right; text: pick.counter ? pick.counter.text : ""; elide: Text.ElideNone }
      }
      // What it waits for and what waits for it: the tree's edges, named.
      Caption {
        width: parent.width
        visible: pick.needs.length > 0
        wrapMode: Text.Wrap
        elide: Text.ElideNone
        text: "Needs first:  " + root.factJoin(pick.needs.map(function(r) {
          return (root.guideDone(r) ? "✓ " : "○ ") + root.shownName(r)
        }))
      }
      Caption {
        width: parent.width
        visible: pick.opens.length > 0
        wrapMode: Text.Wrap
        elide: Text.ElideNone
        text: "Opens:  " + root.factJoin(pick.opens.map(function(r) { return root.shownName(r) }))
      }
    }
  }

  // A node of the story track: solid once done, ringed with a slow pulse
  // where the player is, hollow ahead; a red flag where a missable was
  // left behind.
  component TrackDot: Item {
    id: dot
    property int number: 0
    property bool done: false
    property bool here: false
    property bool behind: false
    property bool chosen: false
    property int lost: 0
    property real size: Commons.Style.space(28)
    width: size
    height: size
    // The one loop in the tree: where the player is breathes gently.
    Rectangle {
      visible: dot.here
      anchors.centerIn: parent
      width: dot.size
      height: width
      radius: width / 2
      color: "transparent"
      border.width: 2
      border.color: Commons.Color.accent
      SequentialAnimation on scale {
        running: dot.here && dot.visible
        loops: Animation.Infinite
        NumberAnimation { from: 1; to: 1.55; duration: 1400; easing.type: Easing.OutCubic }
        PauseAnimation { duration: 500 }
      }
      SequentialAnimation on opacity {
        running: dot.here && dot.visible
        loops: Animation.Infinite
        NumberAnimation { from: 0.7; to: 0; duration: 1400; easing.type: Easing.OutCubic }
        PauseAnimation { duration: 500 }
      }
    }
    Rectangle {
      anchors.fill: parent
      radius: width / 2
      color: dot.done ? Commons.Color.accent : dot.here ? Qt.tint(root.background, Qt.alpha(Commons.Color.accent, 0.22)) : root.background
      border.width: dot.done ? 0 : dot.here || dot.chosen ? 2 : 1.5
      border.color: dot.here || dot.chosen ? Commons.Color.accent
                    : dot.behind ? Qt.alpha(Commons.Color.accent, 0.6) : Qt.alpha(root.foreground, 0.3)
      Behavior on color { ColorAnimation { duration: 200 } }
      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: dot.done ? "✓" : String(dot.number)
        color: dot.done ? root.background : dot.here || dot.chosen ? Commons.Color.accent : root.foreground
        opacity: dot.done || dot.here || dot.chosen ? 1 : 0.55
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.caption
        font.bold: true
      }
    }
    Rectangle {
      visible: dot.lost > 0
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: -Commons.Style.space(4)
      width: Math.round(dot.size * 0.5)
      height: width
      radius: width / 2
      color: Commons.Color.urgent
      border.width: 1.5
      border.color: root.background
      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: "!"
        color: root.background
        font.family: Commons.Style.font.family
        font.pixelSize: Math.round(Commons.Style.font.caption * 0.85)
        font.bold: true
      }
    }
  }

  // A chain as a small skill tree: the goal on top, what it needs below,
  // joined by lines that light in the accent once the lower one is done.
  // A node whose needs are done while it is open is READY and glows.
  component ChainCard: Rectangle {
    id: chain
    property var tree: ({ api: "", kids: [] })
    property real maxWidth: 400
    readonly property var layout: root.chainLayout(tree)
    readonly property var apis: layout.nodes.map(function(n) { return n.api })
    readonly property int got: apis.filter(function(a) { return root.guideDone(a) }).length
    readonly property real pad: Commons.Style.space(12)
    readonly property real slot: Math.max(Commons.Style.space(64), Math.min(Commons.Style.space(96), (maxWidth - pad * 2) / Math.max(1, layout.cols)))
    readonly property real nodeSize: Commons.Style.space(36)
    readonly property real labelH: Commons.Style.space(6) + captionMetrics.height * 3 + Commons.Style.space(4)
    readonly property real rowH: nodeSize + labelH + Commons.Style.space(18)
    readonly property bool goalDone: root.guideDone(tree.api)
    width: Math.min(maxWidth, Math.max(Commons.Style.space(210), chainGraph.width + pad * 2))
    height: chainHead.height + chainGraph.height + pad * 2 + Commons.Style.space(14)
    radius: Commons.Style.cornerRadius
    color: Qt.alpha(root.foreground, 0.035)
    border.width: 1
    border.color: goalDone ? Qt.alpha(root.metalColors[(root.byApi[tree.api] || {}).tier] || root.metalColors.bronze, 0.5) : Qt.alpha(root.foreground, 0.1)
    Column {
      id: chainHead
      x: chain.pad
      y: chain.pad
      width: chain.width - chain.pad * 2
      spacing: Commons.Style.space(6)
      Item {
        width: parent.width
        height: chainGoal.implicitHeight
        Text {
          textFormat: Text.PlainText
          id: chainGoal
          width: parent.width - chainCount.implicitWidth - Commons.Style.space(8)
          text: root.shownName(chain.tree.api)
          color: root.foreground
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.bodySmall
          font.bold: true
          elide: Text.ElideRight
        }
        Caption {
          id: chainCount
          anchors.right: parent.right
          anchors.verticalCenter: parent.verticalCenter
          text: root.unbroken(chain.got + " of " + chain.apis.length)
          color: chain.goalDone ? Commons.Color.accent : root.foreground
          elide: Text.ElideNone
        }
      }
      MeterBar {
        width: parent.width
        fraction: chain.apis.length ? chain.got / chain.apis.length : 0
      }
    }
    Item {
      id: chainGraph
      x: Math.round((chain.width - width) / 2)
      y: chainHead.y + chainHead.height + Commons.Style.space(14)
      width: chain.slot * chain.layout.cols
      height: chain.rowH * chain.layout.rows - Commons.Style.space(18)
      Canvas {
        id: chainLines
        anchors.fill: parent
        // Repaint when anything is unlocked or ticked.
        property int state: chain.got
        onStateChanged: requestPaint()
        onWidthChanged: requestPaint()
        onPaint: {
          var c = getContext("2d")
          c.reset()
          c.lineWidth = 2
          c.lineJoin = "round"
          var nodes = chain.layout.nodes
          // Dim lines first, so a lit one is never drawn under one.
          ;[false, true].forEach(function(lit) {
            c.strokeStyle = lit ? Commons.Color.accent : Qt.alpha(root.foreground, 0.2)
            nodes.forEach(function(n) {
              if (n.parent < 0 || root.guideDone(n.api) !== lit) return
              var p = nodes[n.parent]
              var x1 = (n.x + 0.5) * chain.slot, y1 = n.depth * chain.rowH - Commons.Style.space(2)
              var x2 = (p.x + 0.5) * chain.slot, y2 = p.depth * chain.rowH + chain.nodeSize + chain.labelH
              var mid = (y1 + y2) / 2
              c.beginPath()
              c.moveTo(x1, y1)
              c.lineTo(x1, mid)
              c.lineTo(x2, mid)
              c.lineTo(x2, y2)
              c.stroke()
            })
          })
        }
      }
      Repeater {
        model: chain.layout.nodes
        delegate: Item {
          id: cnode
          required property var modelData
          required property int index
          readonly property string api: modelData.api
          readonly property bool done: root.guideDone(api)
          readonly property var waits: done ? [] : root.lockedBy(api)
          readonly property bool ready: !done && waits.length === 0
          readonly property bool picked: root.treePick === api && root.treePickIn === "chains"
          x: modelData.x * chain.slot
          y: modelData.depth * chain.rowH
          width: chain.slot
          height: chain.nodeSize + chain.labelH
          opacity: 0
          SequentialAnimation on opacity {
            PauseAnimation { duration: 60 + cnode.index * 50 }
            NumberAnimation { to: 1; duration: 220; easing.type: Easing.OutCubic }
          }
          Accessible.role: Accessible.Button
          Accessible.name: root.shownName(api) + (done ? ", done" : ready ? ", ready" : ", locked")
          Rectangle {
            anchors.fill: parent
            anchors.margins: -Commons.Style.space(3)
            radius: Commons.Style.cornerRadius
            color: cnodeHover.hovered ? Commons.Style.hoverFill : "transparent"
          }
          HoverHandler { id: cnodeHover; cursorShape: Qt.PointingHandCursor }
          TapHandler { onTapped: root.pickInTree(cnode.api, "chains") }
          ArtIcon {
            id: cnodeArt
            anchors.horizontalCenter: parent.horizontalCenter
            api: cnode.api
            size: chain.nodeSize
            ready: cnode.ready
            picked: cnode.picked
            tick: true
          }
          MeterBar {
            readonly property var counter: root.counterOf(cnode.api)
            visible: counter !== null && !cnode.done
            x: cnodeArt.x
            y: chain.nodeSize + Commons.Style.space(3)
            width: chain.nodeSize
            fraction: counter ? counter.fraction : 0
          }
          Column {
            y: chain.nodeSize + Commons.Style.space(8)
            width: parent.width
            Text {
              textFormat: Text.PlainText
              width: parent.width - Commons.Style.space(4)
              anchors.horizontalCenter: parent.horizontalCenter
              horizontalAlignment: Text.AlignHCenter
              text: root.shownName(cnode.api)
              color: root.foreground
              opacity: cnode.done ? 0.6 : cnode.ready ? 1 : 0.5
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.caption
              font.bold: cnode.ready
              wrapMode: Text.Wrap
              maximumLineCount: 2
              elide: Text.ElideRight
            }
            Caption {
              width: parent.width - Commons.Style.space(4)
              anchors.horizontalCenter: parent.horizontalCenter
              horizontalAlignment: Text.AlignHCenter
              visible: !cnode.done
              text: cnode.ready ? "READY" : "needs " + cnode.waits.map(function(r) { return root.shownName(r) }).join(", ")
              color: cnode.ready ? Commons.Color.accent : root.foreground
              opacity: cnode.ready ? 1 : 0.45
              font.bold: cnode.ready
              font.letterSpacing: cnode.ready ? 1 : 0
            }
          }
        }
      }
    }
  }

  // On their own: one trophy as a small tile, its art in its metal once
  // done, a thin bar for a counter.
  component GridTile: Item {
    id: gt
    property string api: ""
    property int order: 0
    readonly property var counter: root.counterOf(api)
    readonly property bool done: root.guideDone(api)
    readonly property bool picked: root.treePick === api && root.treePickIn === "alone"
    width: Commons.Style.space(74)
    height: gtArt.height + Commons.Style.space(8) + Commons.Style.space(5) + captionMetrics.height * 2 + Commons.Style.space(8)
    opacity: 0
    SequentialAnimation on opacity {
      PauseAnimation { duration: 60 + gt.order * 35 }
      NumberAnimation { to: 1; duration: 200; easing.type: Easing.OutCubic }
    }
    Accessible.role: Accessible.Button
    Accessible.name: root.shownName(api) + (done ? ", done" : "")
    Rectangle {
      anchors.fill: parent
      radius: Commons.Style.cornerRadius
      color: gtHover.hovered ? Commons.Style.hoverFill : "transparent"
    }
    HoverHandler { id: gtHover; cursorShape: Qt.PointingHandCursor }
    TapHandler { onTapped: root.pickInTree(gt.api, "alone") }
    ArtIcon {
      id: gtArt
      y: Commons.Style.space(6)
      anchors.horizontalCenter: parent.horizontalCenter
      api: gt.api
      size: Commons.Style.space(40)
      picked: gt.picked
      tick: true
    }
    // An open missable, flagged on its corner.
    Rectangle {
      visible: !gt.done && root.isMissable(gt.api)
      x: gtArt.x - Commons.Style.space(4)
      y: gtArt.y - Commons.Style.space(4)
      width: Commons.Style.space(14)
      height: width
      radius: width / 2
      color: Commons.Color.urgent
      border.width: 1.5
      border.color: root.background
      Text {
        textFormat: Text.PlainText
        anchors.centerIn: parent
        text: "!"
        color: root.background
        font.family: Commons.Style.font.family
        font.pixelSize: Math.round(Commons.Style.font.caption * 0.85)
        font.bold: true
      }
    }
    MeterBar {
      visible: gt.counter !== null
      x: gtArt.x
      y: gtArt.y + gtArt.height + Commons.Style.space(4)
      width: gtArt.width
      fraction: gt.counter ? gt.counter.fraction : 0
    }
    Text {
      textFormat: Text.PlainText
      y: gtArt.y + gtArt.height + Commons.Style.space(10)
      width: parent.width - Commons.Style.space(4)
      anchors.horizontalCenter: parent.horizontalCenter
      horizontalAlignment: Text.AlignHCenter
      text: root.shownName(gt.api)
      color: root.foreground
      opacity: gt.done ? 0.55 : 0.9
      font.family: Commons.Style.font.family
      font.pixelSize: Commons.Style.font.caption
      font.italic: root.isSecret(gt.api)
      wrapMode: Text.Wrap
      maximumLineCount: 2
      elide: Text.ElideRight
    }
  }

  // One achievement as the guide describes it: time, difficulty, counter,
  // missable point, tip, combos, and what no source backs. A hidden one
  // keeps its name and tip secret until hovered or revealed with Enter.
  component GuideRow: Rectangle {
    id: grow
    property string api: ""
    // In the trophy list (right); otherwise on the guide side, where a
    // click finds the trophy in that list.
    property bool listed: false
    readonly property bool lit: listed && root.highlightApi === api
    onLitChanged: if (lit) Qt.callLater(function() { allPane.reveal(grow) })
    readonly property var ach: root.byApi[api] || ({ name: "", desc: "", icon: "", hidden: false, unlocked: false })
    readonly property var item: root.guide && root.guide.items ? root.guide.items[api] || ({}) : ({})
    readonly property bool done: root.guideDone(api)
    readonly property bool secret: ach.hidden && !ach.unlocked && !growHover.hovered && !root.revealed[api] && !root.revealAll
    readonly property string meta: {
      var parts = []
      if (item.missable && !done) parts.push("⚠ Missable" + (item.missable_note ? ": " + item.missable_note : ""))
      if (item.time) parts.push(root.unbroken(item.time))
      if (item.difficulty) parts.push(root.dots(item.difficulty))
      if (item.counter && item.counter.target) {
        var at = ach.progress ? ach.progress.value + " / " : ""
        parts.push(root.unbroken(at + item.counter.target + (item.counter.label ? " " + item.counter.label : "")))
      }
      if (item.dlc) parts.push("DLC: " + item.dlc)
      return root.factJoin(parts)
    }
    width: parent ? parent.width : 0
    height: Math.max(growBody.height, growIcon.height, growSide.height) + Commons.Style.space(14)
    radius: Commons.Style.cornerRadius
    color: lit ? Qt.alpha(Commons.Color.accent, 0.16) : growHover.hovered ? Commons.Style.hoverFill : "transparent"
    border.width: lit ? 1 : 0
    border.color: Qt.alpha(Commons.Color.accent, 0.6)
    Behavior on color { ColorAnimation { duration: 200 } }
    HoverHandler { id: growHover; cursorShape: grow.listed ? Qt.ArrowCursor : Qt.PointingHandCursor }
    TapHandler { enabled: !grow.listed; onTapped: root.highlightApi = grow.api }
    // An unlocked trophy carries its metal as a rail, like the list.
    Rectangle {
      visible: grow.ach.unlocked
      x: 0
      anchors.verticalCenter: parent.verticalCenter
      width: 3
      height: parent.height - Commons.Style.space(14)
      radius: 1.5
      color: root.metalColors[grow.ach.tier] || root.metalColors.bronze
    }
    // The metal it earns and the share of players, as in the list.
    Column {
      id: growSide
      anchors.right: parent.right
      anchors.rightMargin: Commons.Style.space(10)
      y: Commons.Style.space(9)
      width: Commons.Style.space(76)
      spacing: Commons.Style.space(3)
      Row {
        anchors.right: parent.right
        spacing: Commons.Style.space(5)
        Text {
          textFormat: Text.PlainText
          anchors.verticalCenter: parent.verticalCenter
          text: grow.ach.percent !== null && grow.ach.percent !== undefined ? grow.ach.percent.toFixed(1) + "%" : "–"
          color: root.metalColors[grow.ach.tier] || root.foreground
          opacity: grow.ach.unlocked ? 1 : 0.7
          font.family: Commons.Style.font.family
          font.pixelSize: Commons.Style.font.caption
          font.bold: true
        }
        Trophy {
          anchors.verticalCenter: parent.verticalCenter
          style: root.iconSet
          metal: grow.ach.tier || "bronze"
          width: 16
          height: 16
          opacity: grow.ach.unlocked ? 1 : 0.35
        }
      }
      Caption {
        anchors.right: parent.right
        visible: text !== ""
        text: grow.ach.unlocked ? root.day(grow.ach.time) : (root.guide && (root.guide.ticks || []).indexOf(grow.api) >= 0 ? "ticked" : "")
        opacity: 0.45
      }
    }

    Rectangle {
      id: growIcon
      x: Commons.Style.space(10)
      y: Commons.Style.space(7)
      width: Commons.Style.space(36)
      height: width
      radius: 4
      color: Qt.alpha(root.foreground, 0.08)
      clip: true
      Image {
        anchors.fill: parent
        source: grow.ach.unlocked ? grow.ach.icon : (grow.ach.icon_locked || grow.ach.icon || "")
        asynchronous: true
        sourceSize: Qt.size(96, 96)
        opacity: status === Image.Ready ? (grow.ach.unlocked ? 1 : 0.6) : 0
      }
    }
    Column {
      id: growBody
      opacity: grow.done ? 0.6 : 1
      anchors.left: growIcon.right
      anchors.leftMargin: Commons.Style.space(12)
      anchors.right: growSide.left
      anchors.rightMargin: Commons.Style.space(8)
      y: Commons.Style.space(7)
      spacing: Commons.Style.space(3)
      Text {
        textFormat: Text.PlainText
        width: parent.width
        text: (grow.done ? "✓ " : "") + (grow.secret ? "Hidden achievement" : grow.ach.name)
        color: root.foreground
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.body
        font.bold: !grow.done
        font.italic: grow.secret
        wrapMode: Text.Wrap
        maximumLineCount: 2
        elide: Text.ElideRight
      }
      Caption {
        width: parent.width
        visible: text !== ""
        text: grow.meta
        wrapMode: Text.Wrap
        elide: Text.ElideNone
        color: grow.item.missable && !grow.done ? Commons.Color.accent : root.foreground
        opacity: grow.item.missable && !grow.done ? 0.95 : 0.6
      }
      Text {
        textFormat: Text.PlainText
        width: parent.width
        visible: text !== ""
        text: grow.secret ? (grow.item.tips ? "Hover or press Enter to reveal the tip" : "")
                          : (grow.item.tips || (grow.ach.hidden ? "" : grow.ach.desc))
        color: root.foreground
        opacity: grow.secret ? 0.4 : 0.8
        wrapMode: Text.Wrap
        font.family: Commons.Style.font.family
        font.pixelSize: Commons.Style.font.bodySmall
        font.italic: grow.secret
      }
      Caption {
        width: parent.width
        visible: text !== "" && !grow.secret
        text: (grow.item.combine_with || []).length ? "Do with " + grow.item.combine_with.join(", ") : ""
        opacity: 0.5
      }
      // A claim no quote backs is shown, but says so (ADR 14).
      Caption {
        width: parent.width
        visible: (grow.item.unverified || []).length > 0 && !grow.secret
        text: "(unverified: " + (grow.item.unverified || []).join(", ") + ")"
        opacity: 0.4
        font.italic: true
      }
    }
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
        } else if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && (event.modifiers & Qt.ShiftModifier)) {
          root.toggleRevealAll()
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
      // Whole pixels inside the frame: a theme's 1.5 px border put the art
      // on half pixels, and it painted over the frame's right edge.
      x: Math.ceil(card.contentLeftInset)
      y: Math.ceil(card.contentTopInset)
      width: parent.width - x - Math.ceil(card.contentRightInset)
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
          visible: root.game !== null
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
          Rectangle {
            visible: root.game !== null && !root.game.playing && !root.pickedGame && root.live
            width: lastText.width + Commons.Style.space(12)
            height: lastText.height + Commons.Style.space(4)
            radius: height / 2
            color: Qt.alpha(root.background, 0.55)
            border.width: 1
            border.color: Qt.alpha(root.foreground, 0.35)
            Text {
              textFormat: Text.PlainText
              id: lastText
              anchors.centerIn: parent
              text: "NOTHING RUNNING · LAST PLAYED"
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
            // A finished game can go on the Profile's completionist tile;
            // labelled, so it doesn't read as one more star or favorite.
            Rectangle {
              id: completionistButton
              readonly property bool on: root.game !== null && root.completionistKeys.indexOf(root.showcaseKey("")) >= 0
              readonly property bool full: !on && root.completionistKeys.length >= root.completionistMax
              anchors.verticalCenter: parent.verticalCenter
              width: completionistText.implicitWidth + Commons.Style.space(14)
              height: completionistText.implicitHeight + Commons.Style.space(6)
              radius: height / 2
              color: on ? Qt.alpha(Commons.Color.accent, 0.25) : (completionistHit.containsMouse && !full ? Commons.Style.hoverFill : Qt.alpha(root.background, 0.5))
              border.width: 1
              border.color: on ? Commons.Color.accent : Qt.alpha(root.foreground, 0.25)
              opacity: full ? 0.5 : 1
              Accessible.role: Accessible.CheckBox
              Accessible.name: "On the Profile's completionist tile"
              Accessible.checked: on
              Text {
                textFormat: Text.PlainText
                id: completionistText
                anchors.centerIn: parent
                text: (completionistButton.on ? "★" : "☆") + " Completionist"
                color: completionistButton.on ? Commons.Color.accent : root.foreground
                font.family: Commons.Style.font.family
                font.pixelSize: Commons.Style.font.caption
                font.bold: completionistButton.on
              }
              MouseArea {
                id: completionistHit
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: completionistButton.full ? Qt.ArrowCursor : Qt.PointingHandCursor
                onClicked: if (!completionistButton.full) root.toggleCompletionist()
              }
              PanelToolTip {
                visible: completionistHit.containsMouse
                text: completionistButton.on ? "On your Profile's completionist tile · click to take it off"
                      : completionistButton.full ? "The completionist tile is full (4) · unpin one first"
                      : "Show this platinum on your Profile's completionist tile"
              }
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
          wrapMode: Text.Wrap
          maximumLineCount: 2
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
            { value: "rare", label: "Rare", kind: "rare" },
            { value: "guide", label: "Guide", kind: "guide" }
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
        // The guide keeps its route's order; the sort is the list's.
        opacity: root.filter === "guide" ? 0 : 1
        enabled: root.filter !== "guide"
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
      visible: root.filter !== "guide"
      model: rowModel
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


      // A row leaving slides right and fades; the rows below it close the
      // gap; rows coming back fade in where they belong.
      add: Transition {
        NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 220; easing.type: Easing.OutCubic }
      }
      remove: Transition {
        NumberAnimation { property: "opacity"; to: 0; duration: 170; easing.type: Easing.InQuad }
        NumberAnimation { property: "x"; to: Commons.Style.space(24); duration: 170; easing.type: Easing.InQuad }
      }
      displaced: Transition {
        NumberAnimation { property: "y"; duration: 260; easing.type: Easing.OutCubic }
        // A row displaced mid-add or mid-remove settles fully visible.
        NumberAnimation { property: "opacity"; to: 1; duration: 120 }
        NumberAnimation { property: "x"; to: 0; duration: 120 }
      }
      move: Transition {
        NumberAnimation { property: "y"; duration: 260; easing.type: Easing.OutCubic }
      }
      moveDisplaced: Transition {
        NumberAnimation { property: "y"; duration: 260; easing.type: Easing.OutCubic }
      }

      delegate: Rectangle {
        id: row
        required property string api
        required property int index
        readonly property var ach: root.byApi[api] || ({ api: api, name: "", desc: "", tier: "bronze", percent: null })
        // Hidden achievements stay a secret until unlocked, or until you
        // hover or press Enter to reveal them.
        readonly property bool secret: ach.hidden && !ach.unlocked && !rowHover.containsMouse && !root.revealed[ach.api]
                                       && !root.revealAll
        width: list.width
        // Grows for a name or description on two lines, instead of cutting
        // them at one.
        height: Math.max(Commons.Style.space(56), rowBody.implicitHeight + Commons.Style.space(16))
        radius: Commons.Style.cornerRadius
        color: ListView.isCurrentItem || rowHover.containsMouse ? Commons.Style.hoverFill
               : (ach.unlocked ? Qt.alpha(root.metalColors[ach.tier] || root.metalColors.bronze, 0.035) : "transparent")
        // A game's first screenful arrives in a short cascade; rows
        // scrolled to later, or added by a filter, don't wait on it.
        Component.onCompleted: if (root.cascading) { opacity = 0; entry.start() }
        SequentialAnimation {
          id: entry
          // A row leaving the ListModel reports index -1, and a negative
          // pause floods the shell log with warnings.
          PauseAnimation { duration: Math.max(0, Math.min(row.index, 12)) * 22 }
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
            opacity: status !== Image.Ready ? 0 : (row.ach.unlocked ? 1 : 0.55)
            Behavior on opacity { NumberAnimation { duration: 220 } }
          }
        }

        Column {
          id: rowBody
          anchors.left: iconFrame.right
          anchors.leftMargin: Commons.Style.space(12)
          anchors.right: rowPin.left
          anchors.rightMargin: Commons.Style.space(8)
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
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
          }
          Caption {
            width: parent.width
            wrapMode: Text.Wrap
            maximumLineCount: 2
            text: row.secret ? "Hover or press Enter to reveal" : row.ach.desc
            visible: text !== ""
          }
        }

        // Only an earned trophy can go on the showcase; the star shows on
        // hover, or always once pinned.
        PinStar {
          id: rowPin
          anchors.right: side.left
          anchors.rightMargin: Commons.Style.space(6)
          anchors.verticalCenter: parent.verticalCenter
          visible: row.ach.unlocked
          on: root.pinned(row.ach.api)
          opacity: on || rowHover.containsMouse || hovered ? 1 : 0
          onToggled: root.togglePin(row.ach.api)
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

    // ------------------------------------------------------------ guide

    Flickable {
      id: guidePane
      anchors.top: toolbar.bottom
      anchors.topMargin: Commons.Style.space(10)
      anchors.bottom: footer.top
      anchors.bottomMargin: Commons.Style.space(6)
      x: toolbar.x
      width: Math.round(toolbar.width * 0.44)
      visible: root.filter === "guide" && root.game !== null
      clip: true
      contentWidth: width
      contentHeight: guideColumn.height
      boundsBehavior: Flickable.StopAtBounds

      WheelHandler {
        target: null
        acceptedDevices: PointerDevice.Mouse
        onWheel: function(event) {
          var notch = Math.max(-120, Math.min(120, event.angleDelta.y)) / 120
          var bottom = Math.max(0, guidePane.contentHeight - guidePane.height)
          guidePane.contentY = Math.max(0, Math.min(bottom, guidePane.contentY - notch * Commons.Style.space(120)))
        }
      }

      Column {
        id: guideColumn
        width: guidePane.width
        spacing: Commons.Style.space(12)

        // Other games' makes: one line, only when they hold Make back.
        Caption {
          textFormat: Text.PlainText
          width: parent.width
          visible: !root.making && root.jobsFull
          wrapMode: Text.Wrap
          elide: Text.ElideNone
          text: root.othersRunning + " guides are being made for other games, the most at once: Make guide waits until one is done."
        }

        // This game's make job, while it runs.
        Rectangle {
          width: parent.width
          visible: root.makingHere
          height: jobBody.height + Commons.Style.space(24)
          radius: Commons.Style.cornerRadius
          color: Qt.alpha(Commons.Color.accent, 0.08)
          border.width: 1
          border.color: Qt.alpha(Commons.Color.accent, 0.4)
          Column {
            id: jobBody
            x: Commons.Style.space(14)
            y: Commons.Style.space(12)
            width: parent.width - Commons.Style.space(28)
            spacing: Commons.Style.space(6)
            Item {
              width: parent.width
              height: stopButton.height
              SectionLabel {
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.right: stopButton.left
                anchors.rightMargin: Commons.Style.space(10)
                elide: Text.ElideRight
                text: "MAKING THIS GAME'S GUIDE"
                color: Commons.Color.accent
                opacity: 1
              }
              Row {
                id: stopButton
                anchors.right: parent.right
                spacing: Commons.Style.space(6)
                ActionButton {
                  accent: false
                  text: "Stop"
                  onClicked: root.stopGuide()
                }
                // Closing is safe: the job runs on its own (detached).
                ActionButton {
                  text: "Close"
                  onClicked: root.closeRequested()
                }
              }
            }
            Text {
              textFormat: Text.PlainText
              width: parent.width
              text: root.job.line || ""
              color: root.foreground
              wrapMode: Text.Wrap
              maximumLineCount: 2
              elide: Text.ElideRight
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.body
            }
            Rectangle {
              width: parent.width
              height: 4
              radius: 2
              color: Qt.alpha(root.foreground, 0.12)
              Rectangle {
                width: root.job.total ? parent.width * Math.min(1, (root.job.done + 0.5) / root.job.total) : 0
                height: parent.height
                radius: parent.radius
                color: Commons.Color.accent
                Behavior on width { NumberAnimation { duration: 400; easing.type: Easing.OutCubic } }
              }
            }
            Caption {
              width: parent.width
              text: "With " + (root.job.agent || "your agent") + (root.job.model ? " · " + root.job.model : "")
                    + ". You can close this (Close, Esc or a click outside): it keeps going, the panel shows it under its tabs,"
                    + " and a notification says when it's ready." + (root.hasGuide ? " The current guide stays until then." : "")
              wrapMode: Text.Wrap
              elide: Text.ElideNone
              opacity: 0.5
            }
          }
        }

        // A first guide on its way: the stages as they pass (the trophies
        // it covers are on the right).
        Column {
          width: parent.width
          visible: root.making && root.jobHere && !root.hasGuide
          spacing: Commons.Style.space(6)
          Repeater {
            model: root.making && root.jobHere ? root.jobStages() : []
            delegate: Row {
              id: stageRow
              required property var modelData
              required property int index
              readonly property int at: root.jobStages().findIndex(function(s) { return s.key === root.job.stage })
              readonly property bool done: index < at
              readonly property bool now: index === at
              spacing: Commons.Style.space(10)
              Text {
                textFormat: Text.PlainText
                width: Commons.Style.space(16)
                horizontalAlignment: Text.AlignHCenter
                text: stageRow.done ? "✓" : stageRow.now ? "●" : "○"
                color: stageRow.done || stageRow.now ? Commons.Color.accent : root.foreground
                opacity: stageRow.done || stageRow.now ? 1 : 0.35
                font.pixelSize: Commons.Style.font.bodySmall
                SequentialAnimation on opacity {
                  running: stageRow.now
                  loops: Animation.Infinite
                  NumberAnimation { to: 0.3; duration: 700 }
                  NumberAnimation { to: 1; duration: 700 }
                }
              }
              Text {
                textFormat: Text.PlainText
                text: stageRow.modelData.label
                color: root.foreground
                opacity: stageRow.now ? 1 : stageRow.done ? 0.6 : 0.35
                font.family: Commons.Style.font.family
                font.pixelSize: Commons.Style.font.bodySmall
                font.bold: stageRow.now
              }
            }
          }
        }

        // What made the guide, and Make again; or the picker itself.
        Item {
          width: parent.width
          visible: root.hasGuide && !root.makerOpen && !root.makingHere
          // The chip is taller than the caption; sized to the caption,
          // the pane's clip cut the chip's top off.
          height: Math.max(madeText.implicitHeight, againButton.visible ? againButton.height : 0) + Commons.Style.space(4)
          Caption {
            id: madeText
            anchors.left: parent.left
            anchors.right: againButton.left
            anchors.rightMargin: Commons.Style.space(8)
            anchors.verticalCenter: parent.verticalCenter
            // A local model's name is long ("strata/qwen3.8-flash-next-
            // q2_0"): wrap, or "older maker" was cut off.
            wrapMode: Text.Wrap
            elide: Text.ElideNone
            text: root.madeLine()
          }
          Chip {
            id: againButton
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: !root.complete
            chosen: !!root.guide && !!root.guide.outdated
            text: "↻ Make again"
            onClicked: root.makerOpen = true
          }
        }

        // A game at 100% needs no guide: say so instead of offering one.
        // The pane's whole height, so the note sits in its middle.
        Item {
          width: parent.width
          height: guidePane.height
          visible: root.complete && !root.hasGuide && !root.makingHere && root.guide !== null
          Column {
            anchors.centerIn: parent
            width: Math.min(parent.width, Commons.Style.space(420))
            spacing: Commons.Style.space(10)
            Trophy {
              anchors.horizontalCenter: parent.horizontalCenter
              style: root.iconSet
              metal: "platinum"
              width: 72
              height: 72
            }
            Text {
              textFormat: Text.PlainText
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              text: "You already have the platinum"
              color: Commons.Color.accent
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.title
              font.bold: true
            }
            Caption {
              width: parent.width
              horizontalAlignment: Text.AlignHCenter
              wrapMode: Text.Wrap
              elide: Text.ElideNone
              text: "All " + (root.game ? root.game.total : 0) + " achievements are unlocked, so there's nothing left for a guide to plan. Making one would only spend your agent's tokens."
            }
          }
        }

        Rectangle {
          id: maker
          width: parent.width
          visible: root.makerOpen && !root.makingHere && root.guide !== null && !root.complete
          height: makerBody.height + Commons.Style.space(24)
          radius: Commons.Style.cornerRadius
          color: Qt.alpha(root.foreground, 0.04)
          border.width: 1
          border.color: Qt.alpha(root.foreground, 0.1)
          Column {
            id: makerBody
            x: Commons.Style.space(14)
            y: Commons.Style.space(12)
            width: parent.width - Commons.Style.space(28)
            spacing: Commons.Style.space(10)

            Text {
              textFormat: Text.PlainText
              width: parent.width
              visible: !root.hasGuide
              text: "No guide for this game yet"
              color: root.foreground
              font.family: Commons.Style.font.family
              font.pixelSize: Commons.Style.font.title
              font.bold: true
            }
            Caption {
              width: parent.width
              wrapMode: Text.Wrap
              elide: Text.ElideNone
              text: root.runnable.length
                    ? "Your coding agent reads achievement guides (and searches the web if it can), then OmaTrophy checks every quote it gives. It takes a few minutes; a cloud agent bills your account."
                    : root.agents.length
                      ? "No agent that can make guides is installed. Install Claude Code (omarchy default agent claude), then open this again."
                      : "Looking for your coding agents…"
            }

            SectionLabel { visible: root.runnable.length > 0; text: "AGENT" }
            PickerField {
              visible: root.runnable.length > 0
              open: root.makerMenu === "agent"
              title: root.pickedRow ? root.pickedRow.name : "Pick an agent"
              detail: root.pickedRow && root.pickedRow.default ? "Omarchy's default agent" : ""
              onToggled: root.toggleMakerMenu("agent")
            }
            PickerList {
              visible: root.makerMenu === "agent"
              rows: root.agentRows()
              current: root.pickAgent
              onPicked: value => { root.pickAgentNamed(value); root.makerMenu = "" }
            }

            SectionLabel { visible: root.pickedRow !== null; text: "MODEL" }
            PickerField {
              visible: root.pickedRow !== null
              open: root.makerMenu === "model"
              title: root.pickModel ? root.modelName(root.pickedRow, root.pickModel) : "Agent's default"
              detail: {
                var pick = root.pickedRow && root.pickedRow.suggested ? root.pickedRow.suggested.model : ""
                if (!root.pickModel) return (root.pickedRow ? root.pickedRow.name + " picks it" : "")
                                            + (pick ? " · ★ bench pick: " + root.modelName(root.pickedRow, pick) : "")
                return root.pickEffort ? root.pickEffort + " effort" : ""
              }
              onToggled: root.toggleMakerMenu("model")
            }
            PickerList {
              visible: root.makerMenu === "model"
              rows: root.modelRows()
              current: root.pickModel
              onPicked: value => {
                var pick = root.pickedRow && root.pickedRow.suggested ? root.pickedRow.suggested : ({})
                root.pickModelNamed(value, root.pickEffort || (value === pick.model ? pick.effort || "" : ""))
                root.makerMenu = ""
              }
            }
            // Any model the list doesn't name: a full id, an alias, a
            // provider/model for a local endpoint.
            Rectangle {
              readonly property bool custom: root.pickModel !== "" && root.pickedRow !== null
                                             && !root.pickedRow.models.some(function(m) { return m.id === root.pickModel })
              visible: root.makerMenu === "model" || custom
              width: parent.width
              height: Commons.Style.space(32)
              radius: Commons.Style.cornerRadius
              color: Qt.alpha(root.foreground, 0.04)
              border.width: 1
              border.color: modelField.activeFocus || custom ? Qt.alpha(Commons.Color.accent, 0.6) : Qt.alpha(root.foreground, 0.1)
              TextInput {
                id: modelField
                anchors.fill: parent
                anchors.leftMargin: Commons.Style.space(12)
                anchors.rightMargin: Commons.Style.space(12)
                verticalAlignment: TextInput.AlignVCenter
                clip: true
                color: root.foreground
                selectionColor: Qt.alpha(Commons.Color.accent, 0.4)
                font.family: Commons.Style.font.family
                font.pixelSize: Commons.Style.font.bodySmall
                text: parent.custom ? root.pickModel : ""
                onAccepted: { root.pickModelNamed(text.trim(), root.pickEffort); root.makerMenu = ""; root.forceKeys() }
                Keys.onEscapePressed: root.forceKeys()
                Text {
                  textFormat: Text.PlainText
                  anchors.verticalCenter: parent.verticalCenter
                  visible: !modelField.text && !modelField.activeFocus
                  text: "Other model: type any model id, then Enter"
                  color: root.foreground
                  opacity: 0.4
                  font: modelField.font
                }
              }
            }

            SectionLabel { visible: root.pickedRow !== null && root.modelEfforts().length > 0; text: "EFFORT" }
            PickerField {
              visible: root.pickedRow !== null && root.modelEfforts().length > 0
              open: root.makerMenu === "effort"
              title: root.pickEffort ? root.pickEffort.charAt(0).toUpperCase() + root.pickEffort.slice(1) : "Model's default"
              onToggled: root.toggleMakerMenu("effort")
            }
            PickerList {
              visible: root.makerMenu === "effort"
              rows: root.effortRows()
              current: root.pickEffort
              onPicked: value => { root.pickModelNamed(root.pickModel, value); root.makerMenu = "" }
            }

            Caption {
              width: parent.width
              visible: text !== ""
              text: {
                var others = root.agents.filter(function(a) { return a.installed && !a.supported }).map(function(a) { return a.name })
                return others.length ? others.join(", ") + ": off until checked; Check them in the panel's Settings > Guides." : ""
              }
              wrapMode: Text.Wrap
              elide: Text.ElideNone
              opacity: 0.4
            }

            // The last make's failure, in full: in the button row a long
            // agent error ran past the card.
            Caption {
              width: parent.width
              visible: root.jobHere && (root.job.state === "failed" || root.job.state === "stopped")
              wrapMode: Text.Wrap
              elide: Text.ElideNone
              text: root.job.state === "stopped" ? "Stopped; the old guide is unchanged."
                                                  : "Last try " + (root.job.line || "failed")
              color: root.job.state === "failed" ? Commons.Color.accent : root.foreground
              opacity: root.job.state === "failed" ? 0.9 : 0.6
            }

            Row {
              visible: root.runnable.length > 0
              spacing: Commons.Style.space(10)
              ActionButton {
                text: root.jobsFull ? "Waiting for a free slot" : root.hasGuide ? "Make it again" : "Make guide"
                accent: !root.jobsFull
                onClicked: root.makeGuide()
              }
              ActionButton {
                visible: root.hasGuide
                accent: false
                text: "Cancel"
                onClicked: root.makerOpen = false
              }
            }
          }
        }

        // ---- the guide itself

        // Steps (or Up next) and the outline of what needs what (ADR 20).
        Row {
          visible: root.hasTree && !root.appliedSearch
          spacing: Commons.Style.space(6)
          Chip {
            text: root.walked ? "Steps" : "Up next"
            chosen: !root.treeShown
            onClicked: root.treeShown = false
          }
          Chip {
            text: "Tree"
            chosen: root.treeShown
            onClicked: root.treeShown = true
          }
        }

        Item {
          width: parent.width
          height: Math.max(upNextTitle.implicitHeight, upNextReveal.visible ? upNextReveal.height : 0)
          visible: root.hasGuide && (root.guide.next || []).length > 0 && root.listShown && !root.walked
          SectionLabel {
            id: upNextTitle
            anchors.verticalCenter: parent.verticalCenter
            text: "UP NEXT"
            color: Commons.Color.accent
            opacity: 1
          }
          // Next to where the guide starts too: Up next can be all secrets.
          Chip {
            id: upNextReveal
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            visible: root.secretCount > 0
            chosen: root.revealAll
            text: root.revealAll ? "Hide secrets" : "Reveal all"
            onClicked: root.toggleRevealAll()
          }
        }
        Column {
          width: parent.width
          visible: root.hasGuide && root.listShown && !root.walked
          spacing: Commons.Style.space(2)
          Repeater {
            model: root.hasGuide ? root.guide.next || [] : []
            delegate: GuideRow { required property string modelData; api: modelData }
          }
        }

        // With a walkthrough, the overview leads and the steps carry the
        // rest: route, combos and Up next said the same things again.
        Item {
          width: parent.width
          height: walkOverview.height
          visible: root.walked && !root.appliedSearch && !root.treeOn && walkOverview.text !== ""
          Column {
            id: walkOverview
            property string text: root.guide && root.guide.sections ? root.guide.sections.overview || "" : ""
            width: parent.width
            spacing: Commons.Style.space(4)
            Row {
              width: parent.width
              SectionLabel { text: "OVERVIEW"; width: parent.width - walkReveal.width }
              Chip {
                id: walkReveal
                visible: root.secretCount > 0
                chosen: root.revealAll
                text: root.revealAll ? "Hide secrets" : "Reveal all"
                onClicked: root.toggleRevealAll()
              }
            }
            Prose { width: parent.width; text: root.safeMarkdown(walkOverview.text) }
          }
        }

        // The walkthrough (ADR 17): the game's chapters in play order, each
        // with its trophies, the current one open; a click opens another.
        SectionLabel {
          visible: root.hasGuide && root.walkSteps.length > 0 && root.listShown
          text: "WALKTHROUGH" + (root.guide && root.guide.step >= 0 ? " · STEP " + (root.guide.step + 1) + " OF " + root.walkSteps.length : "")
                + (root.stepPinned ? " · PINNED BY YOU" : "")
        }
        Column {
          width: parent.width
          visible: root.hasGuide && root.walkSteps.length > 0 && root.listShown
          spacing: Commons.Style.space(2)
          Repeater {
            model: root.hasGuide && !root.appliedSearch ? root.walkSteps : []
            delegate: Rectangle {
              id: walkRow
              required property var modelData
              required property int index
              readonly property bool open: root.stepIsOpen(index)
              readonly property bool here: root.currentStep === index
              // Behind the current step counts as passed, achievements or
              // not (a prologue with none never got its ✓).
              // An earlier step with something still open keeps its number.
              readonly property bool passed: modelData.done || (root.currentStep > index && modelData.achievements.length === 0)
              width: parent.width
              height: walkBody.height + Commons.Style.space(12)
              radius: Commons.Style.cornerRadius
              color: here ? Qt.alpha(Commons.Color.accent, 0.10) : walkHover.hovered ? Commons.Style.hoverFill : "transparent"
              opacity: passed && !open ? 0.5 : 1
              HoverHandler { id: walkHover }
              Text {
                textFormat: Text.PlainText
                id: walkNumber
                x: Commons.Style.space(8)
                y: Commons.Style.space(6)
                width: Commons.Style.space(22)
                text: walkRow.passed ? "✓" : String(walkRow.index + 1)
                color: walkRow.here ? Commons.Color.accent : root.foreground
                opacity: walkRow.here ? 1 : 0.5
                font.family: Commons.Style.font.family
                font.pixelSize: Commons.Style.font.bodySmall
                font.bold: true
              }
              Column {
                id: walkBody
                anchors.left: walkNumber.right
                anchors.right: parent.right
                anchors.rightMargin: Commons.Style.space(8)
                y: Commons.Style.space(6)
                spacing: Commons.Style.space(3)
                Text {
                  textFormat: Text.PlainText
                  width: parent.width
                  wrapMode: Text.Wrap
                  rightPadding: walkCount.implicitWidth + Commons.Style.space(8)
                  text: walkRow.modelData.title
                  // Only the title folds: a click on a trophy row finds it
                  // in the list instead.
                  HoverHandler { cursorShape: Qt.PointingHandCursor }
                  TapHandler { onTapped: root.toggleStep(walkRow.index) }
                  Caption {
                    id: walkCount
                    anchors.right: parent.right
                    anchors.top: parent.top
                    visible: walkRow.modelData.achievements.length > 0
                    text: root.stepDone(walkRow.modelData) + " / " + walkRow.modelData.achievements.length
                  }
                  color: walkRow.here ? Commons.Color.accent : root.foreground
                  font.family: Commons.Style.font.family
                  font.pixelSize: Commons.Style.font.bodySmall
                  font.bold: true
                }
                Prose {
                  width: parent.width
                  visible: walkRow.open && text !== ""
                  text: root.safeMarkdown(walkRow.modelData.text)
                }
                // Its actions in order (maker 4), each ticked when the
                // trophy it gives is done; a step from an older guide has
                // none and keeps its text alone.
                Repeater {
                  model: walkRow.open ? walkRow.modelData.actions || [] : []
                  delegate: ActionLine { required property var modelData; width: walkBody.width; action: modelData }
                }
                Caption {
                  textFormat: Text.PlainText
                  width: parent.width
                  visible: !walkRow.open && text !== ""
                  wrapMode: Text.Wrap
                  maximumLineCount: 2
                  text: root.stepNames(walkRow.modelData)
                }
                // Open, a step lists its trophies in full, done ones too,
                // so every one can be followed where the game asks for it.
                Repeater {
                  model: walkRow.open ? walkRow.modelData.achievements : []
                  delegate: GuideRow { required property string modelData; api: modelData }
                }
                Caption {
                  textFormat: Text.PlainText
                  visible: walkRow.open && walkRow.modelData.unverified
                  text: "(unverified: no source backs this step)"
                  font.italic: true
                  opacity: 0.45
                }
                StepPinButton { index: walkRow.index; shown: walkRow.open }
              }
            }
          }
        }

        SectionLabel {
          visible: root.unplaced.length > 0 && root.listShown
          text: "NOT IN A STEP · " + root.unplaced.length
        }
        Column {
          width: parent.width
          visible: root.unplaced.length > 0 && root.listShown
          spacing: Commons.Style.space(2)
          Repeater {
            model: root.appliedSearch ? [] : root.unplaced
            delegate: GuideRow { required property string modelData; api: modelData }
          }
        }

        // The tree (ADR 20): what can be done now, the story as a track,
        // chains as small skill trees, the rest as a grid by phase. A click
        // on any trophy picks it: the list finds it, its tips show inline.

        // DO NOW: the frontier, open trophies whose needs are all done.
        Column {
          id: doNow
          width: parent.width
          visible: root.treeOn
          spacing: Commons.Style.space(8)
          // Three side by side while each keeps room for a short line;
          // narrower, they stack as rows.
          readonly property int cols: width >= Commons.Style.space(150) * 3 + Commons.Style.space(16) ? 3 : 1
          readonly property var apis: root.doNowAll ? root.doNowApis : root.doNowApis.slice(0, 3)
          readonly property int openLeft: root.game ? root.game.achievements.filter(function(a) { return !root.guideDone(a.api) }).length : 0
          Item {
            width: parent.width
            height: Math.max(doNowHead.height, doNowReveal.visible ? doNowReveal.height : 0)
            Row {
              id: doNowHead
              anchors.verticalCenter: parent.verticalCenter
              spacing: Commons.Style.space(8)
              SectionLabel { text: "DO NOW"; color: Commons.Color.accent; opacity: 1 }
              Caption {
                visible: root.doNowApis.length > 0
                text: root.doNowApis.length + " open to you"
                opacity: 0.5
              }
            }
            // Here as on the Steps view: Do now can be all secrets.
            Chip {
              id: doNowReveal
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              visible: root.secretCount > 0
              chosen: root.revealAll
              text: root.revealAll ? "Hide secrets" : "Reveal all"
              onClicked: root.toggleRevealAll()
            }
          }
          GridLayout {
            width: parent.width
            visible: doNow.apis.length > 0
            columns: doNow.cols
            columnSpacing: Commons.Style.space(8)
            rowSpacing: Commons.Style.space(8)
            Repeater {
              model: root.treeOn ? doNow.apis : []
              delegate: DoTile {
                id: doTile
                required property string modelData
                required property int index
                api: modelData
                first: index === 0
                stacked: doNow.cols > 1 && index < 3
                Layout.fillWidth: true
                Layout.fillHeight: index < 3
                Layout.preferredWidth: 1
                Layout.columnSpan: index < 3 ? 1 : doNow.cols
                opacity: 0
                SequentialAnimation on opacity {
                  PauseAnimation { duration: Math.min(doTile.index, 6) * 50 }
                  NumberAnimation { to: 1; duration: 220; easing.type: Easing.OutCubic }
                }
              }
            }
          }
          // Nothing open: all done, or what's left waits for something.
          Rectangle {
            width: parent.width
            visible: root.doNowApis.length === 0
            height: doNowEmpty.height + Commons.Style.space(20)
            radius: Commons.Style.cornerRadius
            color: Qt.alpha(root.foreground, 0.035)
            border.width: 1
            border.color: Qt.alpha(root.foreground, 0.1)
            Row {
              id: doNowEmpty
              x: Commons.Style.space(12)
              anchors.verticalCenter: parent.verticalCenter
              width: parent.width - Commons.Style.space(24)
              spacing: Commons.Style.space(10)
              Trophy {
                anchors.verticalCenter: parent.verticalCenter
                visible: doNow.openLeft === 0
                style: root.iconSet
                metal: "platinum"
                width: Commons.Style.space(22)
                height: width
              }
              Text {
                textFormat: Text.PlainText
                width: parent.width - (doNow.openLeft === 0 ? Commons.Style.space(32) : 0)
                anchors.verticalCenter: parent.verticalCenter
                wrapMode: Text.Wrap
                text: doNow.openLeft === 0 ? "Every trophy is done. Nothing left to chase here."
                      : "Nothing is open right now: what's left needs something first. Chains below show what."
                color: root.foreground
                opacity: 0.75
                font.family: Commons.Style.font.family
                font.pixelSize: Commons.Style.font.bodySmall
              }
            }
          }
          Text {
            textFormat: Text.PlainText
            visible: root.doNowApis.length > 3
            text: root.doNowAll ? "Show three" : "Show " + (root.doNowApis.length - 3) + " more open to you"
            color: Commons.Color.accent
            opacity: doNowMore.hovered ? 1 : 0.8
            font.family: Commons.Style.font.family
            font.pixelSize: Commons.Style.font.caption
            font.bold: true
            HoverHandler { id: doNowMore; cursorShape: Qt.PointingHandCursor }
            TapHandler { onTapped: root.doNowAll = !root.doNowAll }
          }
          Loader {
            width: parent.width
            active: root.treeOn && root.treePickIn === "now" && root.treePick !== ""
            visible: active
            sourceComponent: Component { PickDetail { api: root.treePick } }
          }
        }

        // STORY: the walkthrough's steps as a journey track (the story
        // trophies, with no steps): the line fills to where the player is.
        Column {
          id: story
          width: parent.width
          visible: root.treeOn && root.trackNodes.length > 0
          spacing: Commons.Style.space(10)
          // Too narrow for a track across: it runs down instead.
          readonly property bool upright: width < Commons.Style.space(380)
          // Every node fits across while each keeps room for a short
          // title; past that the track scrolls.
          readonly property real slot: width / Math.max(1, root.trackNodes.length) >= Commons.Style.space(58)
                                       ? width / Math.max(1, root.trackNodes.length) : Commons.Style.space(70)
          readonly property real dotSize: Commons.Style.space(26)
          readonly property bool stepped: root.walkSteps.length > 0
          readonly property int fillTo: root.trackHere >= 0 ? root.trackHere : root.trackNodes.length - 1
          Row {
            spacing: Commons.Style.space(8)
            SectionLabel { text: "STORY" }
            Caption {
              text: story.stepped
                    ? (root.trackHere >= 0 ? "step " + (root.trackHere + 1) + " of " + root.walkSteps.length : "every step done")
                    : root.guideTree.story.filter(function(a) { return root.guideDone(a) }).length + " of " + root.guideTree.story.length + " done"
              opacity: 0.5
            }
          }
          Flickable {
            id: trackView
            visible: !story.upright
            width: parent.width
            height: track.height
            contentWidth: track.width
            contentHeight: track.height
            clip: true
            interactive: contentWidth > width
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            // A long story scrolls; the step shown stays in view.
            function keepInView() {
              var i = root.trackShown
              if (i < 0) return
              var centre = story.slot * (i + 0.5)
              contentX = Math.max(0, Math.min(contentWidth - width, centre - width / 2))
            }
            onWidthChanged: Qt.callLater(keepInView)
            Component.onCompleted: Qt.callLater(keepInView)
            Connections {
              target: root
              function onTrackShownChanged() { trackView.keepInView() }
            }
            Item {
              id: track
              // Room for YOU ARE HERE only while there is a here.
              readonly property real tagH: root.trackHere >= 0 ? captionMetrics.height + Commons.Style.space(4) : 0
              readonly property real lineY: tagH + Commons.Style.space(8) + story.dotSize / 2
              property bool grown: false
              width: story.slot * root.trackNodes.length
              height: lineY + story.dotSize / 2 + Commons.Style.space(6) + captionMetrics.height * (story.stepped ? 3 : 2) + Commons.Style.space(6)
              Component.onCompleted: grown = true
              Rectangle {
                x: story.slot / 2
                y: track.lineY - 1
                width: track.width - story.slot
                height: 2
                color: Qt.alpha(root.foreground, 0.14)
              }
              Rectangle {
                x: story.slot / 2
                y: track.lineY - 1.5
                height: 3
                radius: 1.5
                width: track.grown ? story.slot * story.fillTo : 0
                color: Commons.Color.accent
                Behavior on width { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
              }
              Repeater {
                model: root.treeOn ? root.trackNodes : []
                delegate: Item {
                  id: tnode
                  required property var modelData
                  required property int index
                  readonly property int total: modelData.achievements.length
                  readonly property int got: modelData.achievements.filter(function(a) { return root.guideDone(a) }).length
                  readonly property bool here: index === root.trackHere
                  readonly property bool done: total > 0 ? got === total : (root.trackHere < 0 || index < root.trackHere)
                  readonly property bool behind: !done && root.trackHere >= 0 && index < root.trackHere
                  readonly property bool chosen: story.stepped ? index === root.trackShown
                                                               : root.treePick === modelData.api && root.treePickIn === "story"
                  x: index * story.slot
                  width: story.slot
                  height: track.height
                  opacity: 0
                  SequentialAnimation on opacity {
                    PauseAnimation { duration: 80 + Math.min(tnode.index, 12) * 45 }
                    NumberAnimation { to: 1; duration: 220; easing.type: Easing.OutCubic }
                  }
                  Accessible.role: Accessible.Button
                  Accessible.name: tnodeTitle.text + ", " + got + " of " + total + (here ? ", you are here" : "")
                                   + (here && root.stepPinned ? ", pinned by you" : "")
                  Rectangle {
                    x: Commons.Style.space(2)
                    y: track.tagH + Commons.Style.space(2)
                    width: parent.width - Commons.Style.space(4)
                    height: parent.height - y
                    radius: Commons.Style.cornerRadius
                    color: tnodeHover.hovered ? Commons.Style.hoverFill : "transparent"
                  }
                  HoverHandler { id: tnodeHover; cursorShape: Qt.PointingHandCursor }
                  TapHandler {
                    onTapped: {
                      if (!story.stepped) root.pickInTree(tnode.modelData.api, "story")
                      else root.trackPick = tnode.index === root.trackHere ? -1 : tnode.index
                    }
                  }
                  // Kept inside the track at its ends.
                  Row {
                    visible: tnode.here
                    spacing: Commons.Style.space(4)
                    x: Math.max(-tnode.x, Math.min(track.width - tnode.x - width, (tnode.width - width) / 2))
                    y: 0
                    Tag { id: hereTag; text: "YOU ARE HERE"; solid: true }
                    PinMark { visible: root.stepPinned; size: hereTag.height; anchors.verticalCenter: parent.verticalCenter }
                  }
                  TrackDot {
                    x: (tnode.width - width) / 2
                    y: track.lineY - height / 2
                    size: story.dotSize
                    number: tnode.index + 1
                    done: tnode.done
                    here: tnode.here
                    behind: tnode.behind
                    chosen: tnode.chosen
                    lost: root.lostAt(tnode.index).length
                  }
                  Column {
                    y: track.lineY + story.dotSize / 2 + Commons.Style.space(6)
                    width: parent.width
                    Caption {
                      anchors.horizontalCenter: parent.horizontalCenter
                      visible: story.stepped
                      text: tnode.got + "/" + tnode.total
                      color: tnode.here || tnode.chosen ? Commons.Color.accent : root.foreground
                      opacity: tnode.here || tnode.chosen ? 1 : 0.5
                      elide: Text.ElideNone
                    }
                    Text {
                      textFormat: Text.PlainText
                      id: tnodeTitle
                      width: parent.width - Commons.Style.space(8)
                      anchors.horizontalCenter: parent.horizontalCenter
                      horizontalAlignment: Text.AlignHCenter
                      text: story.stepped ? root.walkSteps[tnode.index].title : root.shownName(tnode.modelData.api)
                      color: root.foreground
                      opacity: tnode.here || tnode.chosen ? 0.95 : tnode.done ? 0.45 : 0.6
                      font.family: Commons.Style.font.family
                      font.pixelSize: Commons.Style.font.caption
                      font.bold: tnode.here || tnode.chosen
                      wrapMode: Text.Wrap
                      maximumLineCount: 2
                      elide: Text.ElideRight
                    }
                  }
                }
              }
            }
          }
          // The narrow track: the same nodes down the side, titles beside.
          Column {
            visible: story.upright
            width: parent.width
            Repeater {
              model: root.treeOn && story.upright ? root.trackNodes : []
              delegate: Item {
                id: unode
                required property var modelData
                required property int index
                readonly property int total: modelData.achievements.length
                readonly property int got: modelData.achievements.filter(function(a) { return root.guideDone(a) }).length
                readonly property bool here: index === root.trackHere
                readonly property bool done: total > 0 ? got === total : (root.trackHere < 0 || index < root.trackHere)
                readonly property bool chosen: story.stepped ? index === root.trackShown
                                                             : root.treePick === modelData.api && root.treePickIn === "story"
                width: parent.width
                height: Math.max(story.dotSize, unodeText.height) + Commons.Style.space(12)
                opacity: 0
                SequentialAnimation on opacity {
                  PauseAnimation { duration: 80 + Math.min(unode.index, 12) * 45 }
                  NumberAnimation { to: 1; duration: 220; easing.type: Easing.OutCubic }
                }
                Rectangle {
                  anchors.fill: parent
                  radius: Commons.Style.cornerRadius
                  color: unodeHover.hovered ? Commons.Style.hoverFill : unode.chosen && !unode.here ? Qt.alpha(Commons.Color.accent, 0.06) : "transparent"
                }
                HoverHandler { id: unodeHover; cursorShape: Qt.PointingHandCursor }
                TapHandler {
                  onTapped: {
                    if (!story.stepped) root.pickInTree(unode.modelData.api, "story")
                    else root.trackPick = unode.index === root.trackHere ? -1 : unode.index
                  }
                }
                // The line, in halves above and below the dot, lit up to
                // where the player is.
                Rectangle {
                  visible: unode.index > 0
                  x: Commons.Style.space(6) + story.dotSize / 2 - 1
                  width: 2
                  height: parent.height / 2
                  color: unode.index <= story.fillTo ? Commons.Color.accent : Qt.alpha(root.foreground, 0.14)
                }
                Rectangle {
                  visible: unode.index < root.trackNodes.length - 1
                  x: Commons.Style.space(6) + story.dotSize / 2 - 1
                  y: parent.height / 2
                  width: 2
                  height: parent.height / 2
                  color: unode.index < story.fillTo ? Commons.Color.accent : Qt.alpha(root.foreground, 0.14)
                }
                TrackDot {
                  x: Commons.Style.space(6)
                  anchors.verticalCenter: parent.verticalCenter
                  size: story.dotSize
                  number: unode.index + 1
                  done: unode.done
                  here: unode.here
                  behind: !unode.done && root.trackHere >= 0 && unode.index < root.trackHere
                  chosen: unode.chosen
                  lost: root.lostAt(unode.index).length
                }
                Column {
                  id: unodeText
                  x: Commons.Style.space(6) + story.dotSize + Commons.Style.space(10)
                  width: parent.width - x - Commons.Style.space(8)
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Commons.Style.space(2)
                  Text {
                    textFormat: Text.PlainText
                    width: parent.width
                    text: story.stepped ? root.walkSteps[unode.index].title : root.shownName(unode.modelData.api)
                    color: unode.here ? Commons.Color.accent : root.foreground
                    opacity: unode.here || unode.chosen ? 1 : unode.done ? 0.5 : 0.75
                    font.family: Commons.Style.font.family
                    font.pixelSize: Commons.Style.font.bodySmall
                    font.bold: unode.here || unode.chosen
                    wrapMode: Text.Wrap
                  }
                  Row {
                    spacing: Commons.Style.space(8)
                    Caption { visible: story.stepped; text: unode.got + " of " + unode.total; elide: Text.ElideNone }
                    Tag { id: uhereTag; visible: unode.here; text: "YOU ARE HERE"; solid: true }
                    PinMark { visible: unode.here && root.stepPinned; size: uhereTag.height; anchors.verticalCenter: parent.verticalCenter }
                  }
                }
              }
            }
          }
          // The step shown: its actions as a checklist, then its trophies
          // no action names.
          Rectangle {
            id: stepPanel
            // `|| null`: a guide made again can have fewer steps than the
            // one a step was picked in.
            readonly property var step: story.stepped && root.trackShown >= 0 ? root.walkSteps[root.trackShown] || null : null
            readonly property var loose: step ? step.achievements.filter(function(api) {
              return !(step.actions || []).some(function(a) { return a.achievement === api })
            }) : []
            readonly property var lost: step ? root.lostAt(root.trackShown) : []
            width: parent.width
            visible: step !== null
            height: visible ? stepBody.height + Commons.Style.space(24) : 0
            radius: Commons.Style.cornerRadius
            color: Qt.alpha(root.foreground, 0.035)
            border.width: 1
            border.color: root.trackShown === root.trackHere ? Qt.alpha(Commons.Color.accent, 0.4) : Qt.alpha(root.foreground, 0.1)
            Column {
              id: stepBody
              x: Commons.Style.space(12)
              y: Commons.Style.space(12)
              width: parent.width - Commons.Style.space(24)
              spacing: Commons.Style.space(6)
              Item {
                width: parent.width
                height: stepTitle.height
                Text {
                  textFormat: Text.PlainText
                  id: stepTitle
                  width: parent.width - stepCount.implicitWidth - Commons.Style.space(10)
                  text: stepPanel.step ? (root.trackShown + 1) + ".  " + stepPanel.step.title : ""
                  color: root.trackShown === root.trackHere ? Commons.Color.accent : root.foreground
                  font.family: Commons.Style.font.family
                  font.pixelSize: Commons.Style.font.bodySmall
                  font.bold: true
                  wrapMode: Text.Wrap
                }
                Caption {
                  id: stepCount
                  anchors.right: parent.right
                  visible: stepPanel.step && stepPanel.step.achievements.length > 0
                  text: stepPanel.step ? root.stepDone(stepPanel.step) + " / " + stepPanel.step.achievements.length : ""
                  elide: Text.ElideNone
                }
              }
              Prose {
                width: parent.width
                visible: text !== ""
                text: stepPanel.step ? root.safeMarkdown(stepPanel.step.text) : ""
              }
              Caption {
                width: parent.width
                visible: stepPanel.lost.length > 0
                wrapMode: Text.Wrap
                elide: Text.ElideNone
                text: "⚠ Left behind here: " + stepPanel.lost.map(function(a) { return root.shownName(a) }).join(", ")
                color: Commons.Color.urgent
                opacity: 1
              }
              Repeater {
                model: stepPanel.step ? stepPanel.step.actions || [] : []
                delegate: ActionLine {
                  required property var modelData
                  width: stepBody.width
                  action: modelData
                  picking: true
                  part: "story"
                }
              }
              Flow {
                width: parent.width
                visible: stepPanel.loose.length > 0
                spacing: Commons.Style.space(6)
                Repeater {
                  model: stepPanel.loose
                  delegate: Rectangle {
                    id: looseChip
                    required property string modelData
                    width: looseRow.width + Commons.Style.space(12)
                    height: looseRow.height + Commons.Style.space(8)
                    radius: height / 2
                    color: looseHover.hovered ? Commons.Style.hoverFill : Qt.alpha(root.foreground, 0.04)
                    border.width: 1
                    border.color: root.treePick === modelData && root.treePickIn === "story" ? Commons.Color.accent : Qt.alpha(root.foreground, 0.1)
                    HoverHandler { id: looseHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { onTapped: root.pickInTree(looseChip.modelData, "story") }
                    Row {
                      id: looseRow
                      anchors.centerIn: parent
                      spacing: Commons.Style.space(6)
                      ArtIcon { api: looseChip.modelData; size: Commons.Style.space(20); anchors.verticalCenter: parent.verticalCenter }
                      Caption {
                        anchors.verticalCenter: parent.verticalCenter
                        text: (root.guideDone(looseChip.modelData) ? "✓ " : "") + root.shownName(looseChip.modelData)
                        elide: Text.ElideNone
                        opacity: root.guideDone(looseChip.modelData) ? 0.5 : 0.85
                      }
                    }
                  }
                }
              }
              Caption {
                visible: stepPanel.step && stepPanel.step.unverified
                text: "(unverified: no source backs this step)"
                font.italic: true
                opacity: 0.45
              }
              StepPinButton { index: root.trackShown }
            }
          }
          Loader {
            width: parent.width
            active: root.treeOn && root.treePickIn === "story" && root.treePick !== ""
            visible: active
            sourceComponent: Component { PickDetail { api: root.treePick } }
          }
        }

        // CHAINS: what needs what, each a card with its goal on top.
        Column {
          width: parent.width
          visible: root.treeOn && root.chainTrees.length > 0
          spacing: Commons.Style.space(8)
          Row {
            spacing: Commons.Style.space(8)
            SectionLabel { text: "CHAINS" }
            Caption { text: "each needs the ones under it first"; opacity: 0.5 }
          }
          Flow {
            id: chainFlow
            width: parent.width
            spacing: Commons.Style.space(8)
            Repeater {
              model: root.treeOn ? root.chainTrees : []
              delegate: ChainCard {
                required property var modelData
                tree: modelData
                maxWidth: chainFlow.width
              }
            }
          }
          Loader {
            width: parent.width
            active: root.treeOn && root.treePickIn === "chains" && root.treePick !== ""
            visible: active
            sourceComponent: Component { PickDetail { api: root.treePick } }
          }
        }

        // ON THEIR OWN: the rest as a grid, by phase; a phase folds.
        Column {
          width: parent.width
          visible: root.treeOn && (root.guideTree.alone || []).length > 0
          spacing: Commons.Style.space(6)
          Row {
            spacing: Commons.Style.space(8)
            SectionLabel { text: "ON THEIR OWN" }
            Caption {
              text: (root.guideTree.alone || []).filter(function(a) { return root.guideDone(a) }).length
                    + " of " + (root.guideTree.alone || []).length + " done"
              opacity: 0.5
            }
          }
          Repeater {
            model: root.treeOn ? root.aloneGroups() : []
            delegate: Column {
              id: phaseGroup
              required property var modelData
              readonly property bool folded: !!root.foldedPhases[modelData.phase]
              width: parent.width
              spacing: Commons.Style.space(2)
              Rectangle {
                width: parent.width
                height: phaseHead.implicitHeight + Commons.Style.space(8)
                radius: Commons.Style.cornerRadius
                color: phaseHover.hovered ? Commons.Style.hoverFill : "transparent"
                HoverHandler { id: phaseHover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: root.togglePhase(phaseGroup.modelData.phase) }
                Accessible.role: Accessible.Button
                Accessible.name: (root.phaseNames[phaseGroup.modelData.phase] || "") + (phaseGroup.folded ? ", folded" : "")
                Row {
                  id: phaseHead
                  x: Commons.Style.space(4)
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Commons.Style.space(8)
                  // "›" turned down while open: the theme fonts lack ▸ and ▾.
                  Caption {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "›"
                    rotation: phaseGroup.folded ? 0 : 90
                    font.bold: true
                    elide: Text.ElideNone
                    Behavior on rotation { NumberAnimation { duration: 140 } }
                  }
                  Caption {
                    text: (root.phaseNames[phaseGroup.modelData.phase] || "").toUpperCase()
                    font.bold: true
                    font.letterSpacing: 1
                    opacity: 0.7
                    elide: Text.ElideNone
                  }
                  Caption {
                    text: phaseGroup.modelData.done + " of " + phaseGroup.modelData.apis.length
                    opacity: 0.4
                    elide: Text.ElideNone
                  }
                }
              }
              Flow {
                width: parent.width
                visible: !phaseGroup.folded
                spacing: Commons.Style.space(4)
                Repeater {
                  model: phaseGroup.folded ? [] : phaseGroup.modelData.apis
                  delegate: GridTile {
                    required property string modelData
                    required property int index
                    api: modelData
                    order: index
                  }
                }
              }
            }
          }
          Loader {
            width: parent.width
            active: root.treeOn && root.treePickIn === "alone" && root.treePick !== ""
            visible: active
            sourceComponent: Component { PickDetail { api: root.treePick } }
          }
        }

        Repeater {
          model: root.hasGuide && root.listShown && !root.walked
                 ? [{ key: "overview", title: "OVERVIEW" }, { key: "route", title: "RECOMMENDED ROUTE" },
                    { key: "missables", title: "MISSABLES" }, { key: "combos", title: "COMBOS" }] : []
          delegate: Column {
            required property var modelData
            readonly property string body: root.guide.sections ? root.guide.sections[modelData.key] || "" : ""
            width: guideColumn.width
            visible: body !== ""
            spacing: Commons.Style.space(4)
            SectionLabel { text: parent.modelData.title }
            Prose { width: parent.width; text: root.safeMarkdown(parent.body) }
          }
        }
        // An imported guide may have prose but no sections.
        Prose {
          width: parent.width
          visible: root.hasGuide && !root.appliedSearch && !!root.guide.notes
                   && !(root.guide.sections && root.guide.sections.overview)
          text: root.guide ? root.safeMarkdown(root.guide.notes) : ""
        }

        Item { width: 1; height: Commons.Style.space(8) }
      }
    }

    Rectangle {
      visible: guidePane.visible
      x: guidePane.x + guidePane.width + Commons.Style.space(11)
      y: guidePane.y
      width: 1
      height: guidePane.height
      color: Qt.alpha(root.foreground, 0.1)
    }

    // Every trophy of the game: open ones by the guide's phases in its
    // route order, then those it doesn't cover, then the ones done.
    Flickable {
      id: allPane
      anchors.top: guidePane.top
      anchors.bottom: guidePane.bottom
      x: guidePane.x + guidePane.width + Commons.Style.space(22)
      width: toolbar.x + toolbar.width - x
      visible: guidePane.visible
      clip: true
      contentWidth: width
      contentHeight: allColumn.height
      boundsBehavior: Flickable.StopAtBounds

      // Scrolls a row of this list to a third of the way down.
      function reveal(row) {
        var y = row.mapToItem(allColumn, 0, 0).y - height / 3
        contentY = Math.max(0, Math.min(Math.max(0, contentHeight - height), y))
      }
      Behavior on contentY { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

      WheelHandler {
        target: null
        acceptedDevices: PointerDevice.Mouse
        onWheel: function(event) {
          var notch = Math.max(-120, Math.min(120, event.angleDelta.y)) / 120
          var bottom = Math.max(0, allPane.contentHeight - allPane.height)
          allPane.contentY = Math.max(0, Math.min(bottom, allPane.contentY - notch * Commons.Style.space(120)))
        }
      }

      Column {
        id: allColumn
        width: allPane.width
        spacing: Commons.Style.space(12)

        Item {
          width: parent.width
          height: Math.max(allTitle.implicitHeight, allReveal.visible ? allReveal.height : 0)
          SectionLabel {
            id: allTitle
            anchors.verticalCenter: parent.verticalCenter
            text: root.hasGuide ? "ALL TROPHIES · IN THE GUIDE'S ORDER" : root.making && root.jobHere ? "THE GUIDE WILL COVER" : "ALL TROPHIES"
          }
          Chip {
            id: allReveal
            anchors.right: doneCount.left
            anchors.rightMargin: Commons.Style.space(12)
            anchors.verticalCenter: allTitle.verticalCenter
            visible: root.secretCount > 0
            chosen: root.revealAll
            text: (root.revealAll ? "Hide secrets · " : "Reveal all · ") + root.secretCount
            onClicked: root.toggleRevealAll()
          }
          Caption {
            id: doneCount
            anchors.right: parent.right
            anchors.verticalCenter: allTitle.verticalCenter
            text: root.game ? root.game.unlocked + " of " + root.game.total + " done" : ""
            opacity: 0.45
          }
        }

        Repeater {
          model: root.hasGuide ? root.phaseGroups() : []
          delegate: Column {
            required property var modelData
            width: allColumn.width
            spacing: Commons.Style.space(2)
            SectionLabel {
              text: (root.phaseNames[parent.modelData.phase] || parent.modelData.phase).toUpperCase()
                    + " · " + parent.modelData.apis.length + " open"
              color: parent.modelData.phase === "missable" ? Commons.Color.accent : root.foreground
            }
            Repeater {
              model: parent.modelData.apis
              delegate: GuideRow { required property string modelData; api: modelData; listed: true }
            }
          }
        }

        Column {
          width: parent.width
          spacing: Commons.Style.space(2)
          visible: root.unguided().length > 0
          SectionLabel { text: (root.hasGuide ? "NOT IN THE GUIDE · " : "OPEN · ") + root.unguided().length }
          Repeater {
            model: root.unguided()
            delegate: GuideRow { required property string modelData; api: modelData; listed: true }
          }
        }

        Column {
          width: parent.width
          spacing: Commons.Style.space(2)
          visible: root.doneApis().length > 0
          SectionLabel { text: "DONE · " + root.doneApis().length }
          Repeater {
            model: root.doneApis()
            delegate: GuideRow { required property string modelData; api: modelData; listed: true }
          }
        }
        Item { width: 1; height: Commons.Style.space(8) }
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
        Key { cap: "⇧Enter"; action: "reveal all" }
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
