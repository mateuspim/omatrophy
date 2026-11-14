#!/usr/bin/env bash
# Render one OmaTrophy view to a PNG offscreen, from a throwaway Quickshell
# instance: no window shows and the live shell is never touched.
#
#   dev/render.sh now out.png            the bar panel's Now tab, mid-game
#   dev/render.sh idle out.png           the Now tab with nothing running
#   dev/render.sh empty out.png          the Now tab before any game has achievements
#   dev/render.sh profile out.png        the Profile tab
#   dev/render.sh games out.png          the Games tab
#   dev/render.sh loading out.png        the Now tab's skeleton, before data
#   dev/render.sh tracker-loading out.png
#   dev/render.sh settings out.png       its Settings tab (settings-toasts, -now, -guides, -stores: one section)
#   dev/render.sh settings-monitors out.png  Toasts with many monitors and a long disconnected name
#   dev/render.sh tracker out.png        the achievement tracker (tracker-hand: ticks, a count and notes by hand;
#                                        tracker-note: a note being written; tracker-done: a finished game,
#                                        its Save image)
#   dev/render.sh guide out.png          its Guide view (guide-making: a make running; guide-empty: none yet;
#                                        guide-failed: the last make failed; guide-steps: a guide with
#                                        step actions; guide-tree: its Tree; guide-tree-done, -locked,
#                                        -bare (no steps, no chains), -narrow, -pick, -wide (a chain wider
#                                        than its card), -wide-keys (focus its far edge): its edge states;
#                                        guide-tree-pinned: the player pinned step 3 (I'm here);
#                                        guide-tree-keys: arrow keys pressed, the focus ring on a node;
#                                        guide-tree-pinnable: step 4 shown, its I'm here button;
#                                        guide-steps-pinned: the Steps view with step 3 pinned;
#                                        guide-tree-narrow-pinned, -narrow-pinnable, ...: a state on
#                                        the narrow card, its track down the side;
#                                        guide-hand: ticks and notes by hand)
#   dev/render.sh share out.png          the saved platinum image (omatrophy.py share), 2400x1260
#   dev/render.sh gold out.png           a toast: bronze, silver, gold, platinum; difficulty, missable: the launch reminders; recap: a session; milestone: a counter
#   dev/render.sh --live tracker out.png the views read your real stores
#   dev/render.sh --font 16 now out.png  at another theme font size (the base is 12)
#   dev/render.sh --tall guide-tree out.png  a guide view on a tall card, to see the whole guide column
#   dev/render.sh --theme flexoki-light guide-tree out.png  under another installed theme (approximate)
#
# Sample data is fake (dev/samples/) so captures are safe for the README;
# --live output shows your own games and stays out of git. The software
# renderer drops MultiEffect layers, so the omarchy set's accent inlay is
# missing here; check it with dev/preview.sh.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
live=false
font=""
tall=false
themeName=""
while [[ ${1:-} == --* ]]; do
  case $1 in
    --live) live=true; shift ;;
    --tall) tall=true; shift ;;
    --font)
      [[ $# -ge 2 && -n $2 ]] || { echo "--font needs a size in pixels" >&2; exit 2; }
      font=$2; shift 2 ;;
    --theme)
      [[ $# -ge 2 && -n $2 ]] || { echo "--theme needs an installed theme name" >&2; exit 2; }
      themeName=$2; shift 2 ;;
    *) break ;;
  esac
done
[[ -z $font || $font =~ ^[0-9]+$ && $font -ge 6 && $font -le 40 ]] ||
  { echo "--font takes a theme base size in pixels, 6 to 40, not '$font'" >&2; exit 2; }
[[ $# -eq 2 ]] || { sed -n '5,33p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
target=$1
out=$(realpath -m "$2")
theme=$HOME/.local/state/omarchy/current/theme
# --theme: another installed Omarchy theme, for a light-theme look without
# switching the desktop's. Its shell.toml is generated only when a theme
# is applied, so surfaces fall back to the theme's palette: close to the
# real thing, not exact.
if [[ -n $themeName ]]; then
  [[ $live == false ]] || { echo "--theme renders sample data only; drop --live" >&2; exit 2; }
  [[ $themeName =~ ^[a-z0-9-]+$ ]] || { echo "--theme takes a theme name like flexoki-light, not '$themeName'" >&2; exit 2; }
  theme=$HOME/.config/omarchy/themes/$themeName
  [[ -d $theme ]] || theme=/usr/share/omarchy/themes/$themeName
  [[ -f $theme/colors.toml ]] || { echo "no theme named '$themeName' (omarchy theme list)" >&2; exit 2; }
fi
# The paths are pasted into QML strings below; refuse any that could end
# the string and add code to the throwaway shell.
for path in "$repo" "$out" "$theme"; do
  [[ $path != *[\"\\]* && $path != *$'\n'* ]] ||
    { echo "can't render with a quote, backslash or newline in a path: $path" >&2; exit 2; }
done

# share: the image `omatrophy.py share` saves, drawn by share.py itself
# (its own offscreen Quickshell, on the GPU) from the sample platinum.
if [[ $target == share ]]; then
  [[ $live == false && -z $font ]] || { echo "share renders the sample platinum only; drop --live and --font" >&2; exit 2; }
  python3 - "$repo" "$out" "$theme" <<'PY'
import json, sys
repo, out, theme = sys.argv[1:]
sys.path.insert(0, repo)
import share
ev = json.load(open(f'{repo}/dev/samples/events.json'))['platinum']
ev.update(hero=f"{repo}/{ev['hero']}", header=f"{repo}/{ev['header']}", platinum=ev['last'],
          store_name='Steam', icon_set='omarchy')
try:
    print(share.render(ev, out, theme=theme))
except RuntimeError as e:
    sys.exit(f'no image: {e}')
PY
  exit
fi

extra=""
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

# --font: the theme's shell.toml with another [font] base-size, which
# every font token and (by default) the spacing scale follow. Commons.Color
# reads the real theme itself once it starts, after the FileView below, so
# the copy is applied again a moment later, over any base-size of the
# user's own.
fontShell=""
panel=420
if [[ -n $font ]]; then
  awk -v size="$font" '
    /^\[/ { if (infont && !done) { print "base-size = " size; done = 1 } infont = ($0 == "[font]") }
    infont && /^base-size[ \t]*=/ { print "base-size = " size; done = 1; next }
    { print }
    END { if (!done) { if (!infont) print "[font]"; print "base-size = " size } }
  ' "$theme/shell.toml" > "$dir/font-shell.toml" 2>/dev/null || printf '[font]\nbase-size = %s\n' "$font" > "$dir/font-shell.toml"
  fontShell="FileView { id: fontShell; path: \"$dir/font-shell.toml\"; blockLoading: true }
  Timer {
    interval: 600; running: true
    onTriggered: {
      var user = Object.assign({}, Commons.Color.userShellValues)
      delete user[\"font.base-size\"]
      Commons.Color.userShellValues = user
      Commons.Color.loadShell(fontShell.text())
    }
  }"
  # The bar popup is Style.space(420) wide, so it grows with the font.
  panel=$(( (420 * font + 6) / 12 ))
fi
# Commons.Color finds the theme under $HOME and loads it after the
# FileViews below, so --theme runs the throwaway shell with a HOME of its
# own whose current theme is the one asked for.
qsHome=$HOME
if [[ -n $themeName ]]; then
  qsHome=$dir/home
  mkdir -p "$qsHome/.local/state/omarchy/current"
  ln -s "$theme" "$qsHome/.local/state/omarchy/current/theme"
fi
ln -s /usr/share/omarchy/shell/Commons "$dir/Commons"
ln -s /usr/share/omarchy/shell/Ui "$dir/Ui"

case $target in
  now|idle|empty|profile|settings|settings-*|games|loading)
    w=$(( panel + 40 )) h=900 at=2500
    section=overview; [[ $target == settings-* ]] && { section=${target#settings-}; target=settings; }
    monitors=false; [[ $section == monitors ]] && { monitors=true; section=toasts; }
    tab=now; [[ $target == settings || $target == games || $target == profile ]] && tab=$target
    data=now.json; [[ $target == idle || $target == empty ]] && data=$target.json; [[ $target == games ]] && data=games.json
    feed="item.cabinet = JSON.parse(sample.text())"
    [[ $target == games ]] && feed="item.games = JSON.parse(sample.text())"
    [[ $target == loading ]] && feed=""
    if [[ $target == now ]]; then
      extra="FileView { id: jobSample; path: \"$repo/dev/samples/guide-job.json\"; blockLoading: true }"
      # Two jobs at once: guides are made in parallel.
      feed="$feed; var j = JSON.parse(jobSample.text()); item.guideJobs = [j, Object.assign({}, j, { app: \"2\", game: \"Ember Tide\", line: \"route: order and notes\", done: 4 })]"
    fi
    if [[ $target == settings ]]; then
      extra="FileView { id: agentSample; path: \"$repo/dev/samples/agents.json\"; blockLoading: true }"
      feed="$feed; item.guideAgents = JSON.parse(agentSample.text()); item.guideModels = ({ claude: { model: \"sonnet\", effort: \"medium\" } }); item.guideJail = true; item.defaultKeyCheck = ({ key: \"SUPER + CTRL + G\", valid: true, taken: \"\" }); item.settingsSection = \"$section\""
      if $monitors; then
        feed="$feed; item.screenName = 'HEADLESS-' + 'LONG'.repeat(14); item.screenChoices = [{ value: 'focused', label: 'Focused' }].concat(['DP-1', 'DP-2', 'HDMI-A-1', 'HDMI-A-2', 'eDP-1', item.screenName].map(function(name) { return { value: name, label: name + (name === item.screenName ? ' (off)' : '') } }))"
      fi
    fi
    view="Loader {
        x: 20; y: 20; width: $panel
        source: \"file:$repo/StylePicker.qml\"
        onLoaded: {
          item.width = $panel
          item.live = $live
          if (!$live) { $feed }
          item.tab = \"$tab\"
        }
      }" ;;
  tracker|tracker-loading|tracker-hand|tracker-note|tracker-done)
    w=1000 h=900 at=3000
    [[ $target == tracker-loading ]] && live=skeleton
    # By hand (ADR 21): The Quiet Part ticked, Collector counted by hand
    # (its store count taken away, its guide's target kept), notes on a
    # trophy and on the game; tracker-note opens a note for editing.
    hand=""
    [[ $target == tracker-hand || $target == tracker-note ]] && hand="var g = item.game; g.achievements.forEach(function(a) { if (a.api === 'A6') a.progress = null }); g.hand = { ticks: ['A4'], unticks: [], counts: { A6: 31 }, notes: { A4: 'Got it on the Deck copy; Steam never synced it.', A5: 'Skip the bridge guard: the vents past the canteen.' }, note: 'Hard first, then Madness unlocks.' }; item.guide = { items: { A6: { counter: { target: 80, label: 'relics' } } }, ticks: [] }; item.game = null; item.game = g; item.sortBy = 'game'"
    # Opened after the rows' entry cascade, as a key press would be: a row
    # that grows mid-transition isn't re-laid by ListView.
    [[ $target == tracker-note ]] && hand="$hand; var t = Qt.createQmlObject(\"import QtQuick; Timer { interval: 1500; running: true }\", item); t.triggered.connect(function() { item.editNote('A5') })"
    # tracker-done: every achievement unlocked, so the header shows the
    # platinum with Completionist and Save image.
    [[ $target == tracker-done ]] && hand="var g = item.game; item.game = Object.assign({}, g, { achievements: g.achievements.map(function(a) { return Object.assign({}, a, { unlocked: true, time: a.time || 1793000000 }) }), unlocked: g.total, platinum: 1793000000 })"
    view="Loader {
        anchors.centerIn: parent
        source: \"file:$repo/TrackerView.qml\"
        onLoaded: {
          item.maxWidth = 960; item.maxHeight = 860
          if (\"$live\" === \"true\") item.load({})
          else if (\"$live\" === \"false\") { item.game = JSON.parse(sample.text()); ${hand:-} }
        }
      }"
    data=game.json ;;
  guide|guide-making|guide-empty|guide-failed|guide-steps|guide-steps-pinned|guide-tree|guide-tree-*|guide-hand)
    w=1300 h=960 at=3000
    $tall && h=2400
    # guide-steps and guide-tree: a made-up game whose guide has requires
    # and step actions (maker 4).
    guideFile=guide.json data=game.json tree=false
    [[ $target == guide-steps* || $target == guide-tree* ]] && guideFile=guide-tree.json data=game-tree.json
    [[ $target == guide-tree* ]] && tree=true
    # The Tree's edge states, from the same sample: every trophy done;
    # everything left waiting on something; no steps and no chains (the
    # track falls back to the story trophies); a narrow card; a chain
    # node picked.
    tweak="" later="" width=1260
    # -narrow-<state>: that state on a narrow card, where the track runs
    # down the side.
    state=$target
    if [[ $target == guide-tree-narrow-* ]]; then width=820; state=guide-tree-${target#guide-tree-narrow-}; fi
    case $state in
      guide-hand) tweak="item.game = Object.assign({}, item.game, { hand: { ticks: ['A5'], unticks: [], counts: {}, notes: { A3: 'Ask the cartographer twice; the second talk marks the last system.' }, note: 'Played on the Deck first: Spark was unlocked there.\\nSave before the finale.' } })" ;;
      guide-tree-done) tweak="item.game = Object.assign({}, item.game, { achievements: item.game.achievements.map(function(a) { return Object.assign({}, a, { unlocked: true, time: a.time || 1793060000 }) }), unlocked: item.game.total }); g.step = -1; g.frontier = []; g.walkthrough.forEach(function(s) { s.done = true })" ;;
      guide-tree-locked) tweak="Object.keys(g.items).forEach(function(k) { if (!item.byApi[k].unlocked) g.items[k].requires = [k === 'L9' ? 'L8' : 'L9'] }); g.frontier = []" ;;
      guide-tree-bare) tweak="g.walkthrough = []; g.step = -1; g.tree.chains = []; g.tree.alone = g.tree.alone.concat(['L5', 'L6', 'L7', 'L8', 'L9', 'L15'])" ;;
      guide-tree-narrow) width=820 ;;
      # A goal with twelve leaves: wider even than the full guide column.
      guide-tree-wide|guide-tree-wide-keys) tweak="var more = ['L0', 'L1', 'L2', 'L3', 'L4', 'L10', 'L11', 'L12', 'L13', 'L14']; g.items.L9.requires = g.items.L9.requires.concat(more); g.tree.chains = g.tree.chains.slice(0, 4).concat(more.map(function(a) { return { api: a, depth: 1 } }), g.tree.chains.slice(4)); g.tree.alone = []" ;;
      # Arrow keys pressed once it has drawn: the focus ring on a track
      # node (each press is one arrow; the first only shows the ring).
      guide-tree-keys) later="['down', 'down', 'down', 'right', 'right'].forEach(function(k) { item.treeMove(k === 'right' ? 1 : 0, k === 'down' ? 1 : 0) })" ;;
      guide-tree-pick) tweak="item.treePick = 'L8'; item.treePickIn = 'chains'" ;;
      guide-tree-pinned|guide-steps-pinned) tweak="g.step = 2; g.step_pinned = true" ;;
      # After the guide is set: its onGuideChanged can still see no steps.
      guide-tree-pinnable) tweak="Qt.callLater(function() { item.trackPick = 3 })" ;;
      guide-tree) ;;
      guide-tree-*) echo "unknown view: $target" >&2; exit 2 ;;
    esac
    if [[ $state == guide-tree-wide-keys ]]; then
      later="var boxes = item.treeBoxes().filter(function(b) { return b.ring.key.indexOf('chain:L9:') === 0 }); boxes.sort(function(a, b) { return a.x - b.x }); item.setTreeKey(boxes[boxes.length - 1])"
    fi
    guide="JSON.parse(guideSample.text())"; [[ $target == guide-empty || $target == guide-making || $target == guide-failed ]] && guide="({})"
    job="({})"; [[ $target == guide-making ]] && job="JSON.parse(jobSample.text())"
    [[ $target == guide-failed ]] && job="Object.assign(JSON.parse(jobSample.text()), { state: 'failed', line: 'failed: route: opencode: the agent could not reach its model server inside the sandbox; the old guide is unchanged' })"
    extra="FileView { id: guideSample; path: \"$repo/dev/samples/$guideFile\"; blockLoading: true }
  FileView { id: agentSample; path: \"$repo/dev/samples/agents.json\"; blockLoading: true }
  FileView { id: jobSample; path: \"$repo/dev/samples/guide-job.json\"; blockLoading: true }"
    view="Loader {
        id: view
        anchors.centerIn: parent
        // --tall: set again after the font reload, which put the card's
        // own height back.
        Timer { id: tallTimer; interval: 1200; onTriggered: view.item.height = $h - 40 }
        Timer { id: laterTimer; interval: 1600; onTriggered: { var item = view.item; ${later:-} } }
        source: \"file:$repo/TrackerView.qml\"
        onLoaded: {
          item.maxWidth = ${width:-1260}; item.maxHeight = 920
          item.game = JSON.parse(sample.text())
          item.agents = JSON.parse(agentSample.text())
          item.choosePick()
          var g = $guide
          ${tweak:-}
          item.guide = g
          item.makerOpen = !item.hasGuide
          item.job = $job
          item.filter = \"guide\"
          item.treeShown = $tree
          if ($tall) tallTimer.start()
          laterTimer.start()
        }
      }" ;;
  bronze|silver|gold|platinum|difficulty|missable|recap|milestone)
    # The platinum card takes about six seconds to open fully.
    # A missable card with four rows of two-line notes runs past 400.
    w=1000 h=$([[ $target == missable ]] && echo 560 || { [[ $target == platinum || $target == recap ]] && echo 400 || echo 260; }) at=$([[ $target == platinum ]] && echo 6500 || echo 3500)
    card=TrophyToast; [[ $target == platinum ]] && card=PlatinumCard; [[ $target == difficulty ]] && card=DifficultyCard; [[ $target == missable ]] && card=MissableCard; [[ $target == recap ]] && card=RecapCard; [[ $target == milestone ]] && card=MilestoneCard
    view="Loader {
        anchors.horizontalCenter: parent.horizontalCenter
        source: \"file:$repo/$card.qml\"
        onLoaded: item.event = JSON.parse(sample.text())[\"$target\"]
      }"
    data=events.json ;;
  *) echo "unknown view: $target" >&2; exit 2 ;;
esac

cat > "$dir/shell.qml" <<QML
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Commons as Commons

ShellRoot {
  // The real shell loads the current theme into Commons.Color at startup.
  FileView { path: "$theme/colors.toml"; blockLoading: true; onLoaded: Commons.Color.loadColors(text()) }
  FileView { path: "$theme/shell.toml"; blockLoading: true; printErrors: false; onLoaded: Commons.Color.loadShell(text()) }
  FileView { id: sample; path: "$repo/dev/samples/$data"; blockLoading: true }
  $fontShell
  $extra
  FloatingWindow {
    implicitWidth: $w
    implicitHeight: $h
    color: Commons.Color.popups.background
    Item {
      id: frame
      anchors.fill: parent
      Rectangle { anchors.fill: parent; color: Commons.Color.popups.background }
      $view
    }
    Timer {
      interval: $at
      running: true
      onTriggered: frame.grabToImage(function(r) { r.saveToFile("$out"); Qt.quit() })
    }
  }
}
QML
HOME=$qsHome QT_QPA_PLATFORM=offscreen timeout 30 quickshell -p "$dir" >"$dir/log" 2>&1 || true
grep -iE "error|warn" "$dir/log" | grep -v qmlscanner | sort -u | head -20 || true
[[ -f $out ]] && echo "$out" || { echo "no image; log:" >&2; tail -20 "$dir/log" >&2; exit 1; }
