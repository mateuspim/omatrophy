"""Exercise the Tree's actual QML JavaScript without a shell or real config.

Node is optional for Python-only environments; the offscreen visual review
also checks these functions under Qt's JavaScript engine.
"""
import pathlib
import re
import shutil
import subprocess
import unittest

TRACKER = pathlib.Path(__file__).resolve().parent.parent / 'TrackerView.qml'


@unittest.skipUnless(shutil.which('node'), 'Node is needed to execute QML JavaScript')
class TreeKeys(unittest.TestCase):
    def run_js(self, checks):
        text = TRACKER.read_text()
        names = ('pickInTree', 'pickTrackNode', 'treeBoxes', 'treeMove', 'setTreeKey',
                 'treeActivate', 'revealInPane', 'scrolledTo', 'needsLine', 'metalText')
        functions = []
        for name in names:
            found = re.search(r'^  function ' + name + r'\([^\n]*\) \{\n.*?^  }',
                              text, re.M | re.S)
            self.assertIsNotNone(found, name)
            functions.append(found.group())
        # The tracker's own handler, the one that cycles filters: the note
        # editor (ADR 21) has a Keys.onPressed at the same indent.
        pressed = next((m for m in re.finditer(r'^      Keys.onPressed: function\(event\) \{\n(.*?)^      }',
                                               text, re.M | re.S) if 'cycleFilter' in m[1]), None)
        self.assertIsNotNone(pressed)
        script = '\n'.join(functions) + '\nfunction press(event) {\n' + pressed[1] + '\n}\n' + checks
        harness = '''const vm = require('node:vm')
const assert = require('node:assert/strict')
const fs = require('node:fs')
vm.runInNewContext(fs.readFileSync(0, 'utf8'), {assert})
'''
        done = subprocess.run(['node', '-e', harness], input=script, text=True,
                              capture_output=True, timeout=5)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_escape_and_space_search_do_not_activate_or_close_early(self):
        self.run_js('''
var root = globalThis, search = '', treeKeys = true, treePick = 'A', treePickIn = 'chains'
var closed = 0, activated = 0, treeKeyShown = true
var Qt = {Key_Escape: 1, Key_Space: 2, ShiftModifier: 1}
var closeRequested = function() { closed++ }
var treeActivate = function() { activated++; return true }
press({key: Qt.Key_Escape})
assert.equal(treePick, '')
assert.equal(treePickIn, '')
assert.equal(closed, 0)
press({key: Qt.Key_Escape})
assert.equal(closed, 1)
search = 'first'; treePick = 'A'; treePickIn = 'now'
press({key: Qt.Key_Space, text: ' ', modifiers: 0})
assert.equal(search, 'first ')
assert.equal(activated, 0)
press({key: Qt.Key_Escape})
assert.equal(search, '')
assert.equal(treePick, 'A')
assert.equal(closed, 1)
press({key: Qt.Key_Space, text: ' ', modifiers: 0})
assert.equal(activated, 1)
''')

    def test_arrows_keep_tree_navigation_and_list_paging(self):
        self.run_js('''
var root = globalThis, treeKeys = true, search = '', calls = []
var Qt = {Key_Right: 1, Key_Left: 2, Key_Down: 3, Key_Up: 4,
          Key_PageDown: 5, Key_PageUp: 6, Key_Home: 7, Key_End: 8}
var list = {currentIndex: 10, count: 30}
var treeMove = function(x, y) { calls.push([x, y]) }
var cycleSort = function() { throw Error('Tree arrow changed saved sort') }
var moveTo = function(i) { calls.push(i) }, pageRows = function() { return 5 }
for (var key of [Qt.Key_Down, Qt.Key_Up, Qt.Key_Left, Qt.Key_Right,
                 Qt.Key_PageDown, Qt.Key_PageUp, Qt.Key_Home, Qt.Key_End]) {
  var event = {key}; press(event); assert.equal(event.accepted, true)
}
assert.deepEqual(calls, [[0, 1], [0, -1], [-1, 0], [1, 0], 15, 5, 0, 29])
''')

    def test_ctrl_keys_tick_and_count_by_hand_over_the_tree(self):
        # ADR 21: Ctrl+Enter and Ctrl+Up/Down act on the highlighted trophy
        # even while the Tree takes the plain arrows and Enter.
        self.run_js('''
var root = globalThis, treeKeys = true, search = '', calls = []
var Qt = {Key_Right: 1, Key_Left: 2, Key_Down: 3, Key_Up: 4, Key_Return: 9, Key_Enter: 10,
          Key_Space: 11, ShiftModifier: 1, ControlModifier: 2}
var treeMove = function() { calls.push('move') }
var treeActivate = function() { calls.push('activate'); return true }
var keyApi = function() { return 'A' }
var toggleTick = function(api) { calls.push('tick ' + api) }
var stepCount = function(api, by) { calls.push('count ' + api + ' ' + by) }
for (var key of [Qt.Key_Return, Qt.Key_Up, Qt.Key_Down]) press({key, modifiers: Qt.ControlModifier})
assert.deepEqual(calls, ['tick A', 'count A 1', 'count A -1'])
''')

    def test_spatial_navigation_activation_and_hidden_targets(self):
        self.run_js('''
var root = globalThis, guideColumn = {}, guidePane = {contentY: 0}
var treeKey = '', treeKeyShown = false, activated = 0
var Commons = {Style: {space: x => x}}
function target(key, x, y, visible = true) {
  return {key, activated: () => activated++, parent: {
    visible, width: 40, height: 40, parent: null, mapToItem: () => ({x, y})}}
}
var treeTargets = [target('B', 80, 0), target('C', 0, 80),
                   target('hidden', 0, 40, false), target('A', 0, 0)]
assert.deepEqual(treeBoxes().map(b => b.ring.key), ['A', 'B', 'C'])
assert.equal(treeActivate(), false)
treeMove(0, 1); assert.equal(treeKey, 'A')
treeMove(1, 0); assert.equal(treeKey, 'B')
treeMove(0, 1); assert.equal(treeKey, 'C')
treeMove(0, -1); assert.equal(treeKey, 'A')
assert.equal(treeActivate(), true); assert.equal(activated, 1)
treeKey = 'removed'; assert.equal(treeActivate(), false)
treeMove(0, 1); assert.equal(treeKey, 'A')
treeTargets = []; treeMove(0, 1)
''')

    def test_reveal_nested_scrollers_and_clamp_large_items(self):
        self.run_js('''
var Commons = {Style: {space: x => x}}
assert.equal(scrolledTo(0, 100, 500, 160, 20, 12), 92)
assert.equal(scrolledTo(200, 100, 500, 10, 20, 12), 0)
assert.equal(scrolledTo(0, 100, 500, 490, 20, 12), 400)
assert.equal(scrolledTo(0, 100, 500, 20, 180, 12), 8)
function flick(width, height, contentWidth, contentHeight, parent) {
  return {width, height, contentWidth, contentHeight, contentX: 0, contentY: 0,
          flickableDirection: 1, contentItem: {}, parent}
}
var outer = flick(200, 100, 200, 500, null)
var inner = flick(100, 40, 500, 40, outer)
var item = {parent: inner, width: 20, height: 20,
            mapToItem: c => c === inner.contentItem ? {x: 160, y: 0} : {x: 0, y: 180}}
revealInPane(item)
assert.equal(inner.contentX, 92)
assert.equal(outer.contentY, 112)
''')

    def test_track_selection_labels_and_theme_text(self):
        self.run_js('''
var walkSteps = [], trackPick = -1, trackHere = 1, treePick = '', treePickIn = '', highlightApi = ''
pickTrackNode(0, 'A'); assert.equal(treePick, 'A'); assert.equal(treePickIn, 'story')
pickTrackNode(0, 'A'); assert.equal(treePick, '')
walkSteps = [{}, {}]; pickTrackNode(0, ''); assert.equal(trackPick, 0)
pickTrackNode(1, ''); assert.equal(trackPick, -1)
var shownName = a => ({A: 'Keeper', B: 'Hidden achievement'})[a]
assert.equal(needsLine([]), '')
assert.equal(needsLine(['A']), 'needs Keeper')
assert.equal(needsLine(['B', 'A']), 'needs Hidden achievement and 1 more')
var lightTheme = false, metalColors = {gold: '#f3cf4a'}
var Qt = {darker: (color, factor) => color + ':' + factor}
assert.equal(metalText('gold', 'fallback'), '#f3cf4a')
lightTheme = true
assert.equal(metalText('gold', 'fallback'), '#f3cf4a:1.9')
assert.equal(metalText('unknown', 'fallback'), 'fallback')
''')


if __name__ == '__main__':
    unittest.main()
