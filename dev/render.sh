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
#   dev/render.sh tracker out.png        the achievement tracker
#   dev/render.sh guide out.png          its Guide view (guide-making: a make running; guide-empty: none yet;
#                                        guide-failed: the last make failed; guide-steps: a guide with
#                                        step actions; guide-tree: its Tree; guide-tree-done, -locked,
#                                        -bare (no steps, no chains), -narrow, -pick: its edge states)
#   dev/render.sh gold out.png           a toast: bronze, silver, gold, platinum
#   dev/render.sh --live tracker out.png the views read your real stores
#   dev/render.sh --font 16 now out.png  at another theme font size (the base is 12)
#   dev/render.sh --tall guide-tree out.png  a guide view on a tall card, to see the whole guide column
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
while [[ ${1:-} == --* ]]; do
  case $1 in
    --live) live=true; shift ;;
    --tall) tall=true; shift ;;
    --font) font=${2:-}; shift 2 || true ;;
    *) break ;;
  esac
done
[[ -z $font || $font =~ ^[0-9]+$ && $font -ge 6 && $font -le 40 ]] ||
  { echo "--font takes a theme base size in pixels, 6 to 40, not '$font'" >&2; exit 2; }
[[ $# -eq 2 ]] || { sed -n '5,21p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }
target=$1
out=$(realpath -m "$2")
theme=$HOME/.local/state/omarchy/current/theme
# The paths are pasted into QML strings below; refuse any that could end
# the string and add code to the throwaway shell.
for path in "$repo" "$out" "$theme"; do
  [[ $path != *[\"\\]* && $path != *$'\n'* ]] ||
    { echo "can't render with a quote, backslash or newline in a path: $path" >&2; exit 2; }
done

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
ln -s /usr/share/omarchy/shell/Commons "$dir/Commons"
ln -s /usr/share/omarchy/shell/Ui "$dir/Ui"

case $target in
  now|idle|empty|profile|settings|settings-*|games|loading)
    w=$(( panel + 40 )) h=900 at=2500
    section=overview; [[ $target == settings-* ]] && { section=${target#settings-}; target=settings; }
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
  tracker|tracker-loading)
    w=1000 h=900 at=3000
    [[ $target == tracker-loading ]] && live=skeleton
    view="Loader {
        anchors.centerIn: parent
        source: \"file:$repo/TrackerView.qml\"
        onLoaded: {
          item.maxWidth = 960; item.maxHeight = 860
          if (\"$live\" === \"true\") item.load({})
          else if (\"$live\" === \"false\") item.game = JSON.parse(sample.text())
        }
      }"
    data=game.json ;;
  guide|guide-making|guide-empty|guide-failed|guide-steps|guide-tree|guide-tree-*)
    w=1300 h=960 at=3000
    $tall && h=2400
    # guide-steps and guide-tree: a made-up game whose guide has requires
    # and step actions (maker 4).
    guideFile=guide.json data=game.json tree=false
    [[ $target == guide-steps || $target == guide-tree* ]] && guideFile=guide-tree.json data=game-tree.json
    [[ $target == guide-tree* ]] && tree=true
    # The Tree's edge states, from the same sample: every trophy done;
    # everything left waiting on something; no steps and no chains (the
    # track falls back to the story trophies); a narrow card; a chain
    # node picked.
    tweak="" width=1260
    case $target in
      guide-tree-done) tweak="item.game = Object.assign({}, item.game, { achievements: item.game.achievements.map(function(a) { return Object.assign({}, a, { unlocked: true, time: a.time || 1793060000 }) }), unlocked: item.game.total }); g.step = -1; g.frontier = []; g.walkthrough.forEach(function(s) { s.done = true })" ;;
      guide-tree-locked) tweak="Object.keys(g.items).forEach(function(k) { if (!item.byApi[k].unlocked) g.items[k].requires = [k === 'L9' ? 'L8' : 'L9'] }); g.frontier = []" ;;
      guide-tree-bare) tweak="g.walkthrough = []; g.step = -1; g.tree.chains = []; g.tree.alone = g.tree.alone.concat(['L5', 'L6', 'L7', 'L8', 'L9', 'L15'])" ;;
      guide-tree-narrow) width=820 ;;
      guide-tree-pick) tweak="item.treePick = 'L8'; item.treePickIn = 'chains'" ;;
      guide-tree) ;;
      guide-tree-*) echo "unknown view: $target" >&2; exit 2 ;;
    esac
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
        }
      }" ;;
  bronze|silver|gold|platinum)
    # The platinum card takes about six seconds to open fully.
    w=1000 h=$([[ $target == platinum ]] && echo 400 || echo 260) at=$([[ $target == platinum ]] && echo 6500 || echo 3500)
    card=$([[ $target == platinum ]] && echo PlatinumCard || echo TrophyToast)
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
QT_QPA_PLATFORM=offscreen timeout 30 quickshell -p "$dir" >"$dir/log" 2>&1 || true
grep -iE "error|warn" "$dir/log" | grep -v qmlscanner | sort -u | head -20 || true
[[ -f $out ]] && echo "$out" || { echo "no image; log:" >&2; tail -20 "$dir/log" >&2; exit 1; }
