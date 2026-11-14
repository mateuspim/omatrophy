"""Execute the tracker's actual JS functions with fake processes and games.

Node is an optional development test runner, never a runtime dependency;
no shell, launcher, network, Qt window or user files are used here.
"""
import json
import pathlib
import re
import shutil
import subprocess
import unittest


TRACKER = pathlib.Path(__file__).resolve().parents[1] / 'TrackerView.qml'


@unittest.skipUnless(shutil.which('node'), 'Node is needed to execute QML JavaScript without Qt')
class TrackerHand(unittest.TestCase):
    def run_js(self, assertions):
        functions = re.findall(r'^  function \w+\([^\n]*\) \{\n.*?^  \}',
                               TRACKER.read_text(), re.M | re.S)
        script = r'''
const vm = require('node:vm')
const assert = require('node:assert/strict')
const state = {
  game: {store: 'steam', app: '1', unlocked: 1, total: 3,
         achievements: [{api: 'A'}, {api: 'B', unlocked: true}, {api: 'C', hidden: true}]},
  guide: {ticks: ['A'], items: {A: {counter: {target: 10}}}},
  hand: {ticks: [], unticks: [], counts: {}, notes: {}, note: ''},
  handQueue: [], handJob: {}, handGeneration: 1, handReadGeneration: -1,
  handRecovering: false, handError: '', guideCommitted: null,
  live: true, helperPath: 'omatrophy.py', noteApi: '',
  revealed: {}, revealAll: false, highlightApi: '', filter: 'all',
  list: {currentIndex: 0}, rows: [{api: 'A'}],
  handWriter: {running: false}, handReader: {running: false},
  keys: {forceActiveFocus() {}},
}
state.byApi = Object.fromEntries(state.game.achievements.map(a => [a.api, a]))
state.handCommitted = state.hand
state.root = state
vm.createContext(state)
vm.runInContext(FUNCTIONS, state)
// Cross-realm objects compare by value here, not prototype identity.
const plain = x => JSON.parse(JSON.stringify(x))
'''.replace('FUNCTIONS', json.dumps('\n'.join(functions))) + assertions
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ticks_merge_untick_and_store_unlock_wins(self):
        self.run_js('''
assert.equal(state.guideDone('A'), true)
state.hand.unticks = ['A']
assert.equal(state.guideDone('A'), false)
state.toggleTick('A')
assert.equal(state.byHand('A'), true)
assert.equal(state.handCount(), 1)
assert.deepEqual(plain(state.handWriter.command), ['python3', 'omatrophy.py', 'hand', 'tick', 'steam', '1', 'A'])
state.toggleTick('A')
assert.equal(state.byHand('A'), false)
assert.equal(state.guideDone('B'), true)
state.toggleTick('B')
assert.equal(state.handQueue.length, 1)
assert.equal(state.game.unlocked, 1)
''')

    def test_counts_clamp_and_never_tick_or_override_the_store(self):
        self.run_js('''
state.guide.ticks = []
assert.equal(state.handCounter('B'), null)
assert.equal(state.handCounter('C'), null)
state.stepCount('A', 20)
assert.equal(state.handCounter('A').value, 10)
assert.equal(state.guideDone('A'), false)
state.stepCount('A', -30)
assert.equal(state.handCounter('A').value, 0)
state.byApi.A.progress = {value: 2, max: 10}
assert.equal(state.handCounter('A'), null)
state.stepCount('A', 1)
assert.equal(state.hand.counts.A, 0)
''')

    def test_notes_keep_secrets_and_plain_text_and_count_unicode(self):
        self.run_js('''
state.editNote('C')
assert.equal(state.noteApi, '')
state.editNote('C', true)
assert.equal(state.noteApi, 'C')
assert.equal(state.revealed.C, true)
state.cancelNote()
assert.equal(state.noteApi, '')
assert.equal(state.handQueue.length, 0)
state.editNote('A')
state.saveNote('A', '<b>literal</b>\\nsecond line')
assert.equal(state.noteOf('A'), '<b>literal</b>\\nsecond line')
assert.equal(state.noteLength('😀'.repeat(1000)), 1000)
state.saveNote('A', '😀'.repeat(1001))
assert.equal(state.noteOf('A'), '<b>literal</b>\\nsecond line')
state.saveNote('game', 'x'.repeat(4000))
assert.equal(state.noteOf('game').length, 4000)
state.saveNote('A', '')
assert.equal(state.noteOf('A'), '')
state.filter = 'guide'
state.editNote('game')
assert.equal(state.gameNotesOpen, true)
assert.equal(state.keyApi(), '')
state.editNote('A')
assert.equal(state.keyApi(), 'A')
''')

    def test_bursts_keep_the_latest_optimistic_edit_until_last_answer(self):
        self.run_js('''
state.toggleTick('A')
state.toggleTick('A')
const first = {hand: {ticks: [], unticks: ['A']}, guide: {ticks: []}}
state.finishHand(JSON.stringify(first))
assert.equal(state.byHand('A'), true)
state.handWriter.running = false
state.nextHand()
assert.equal(state.handQueue.length, 0)
const last = {hand: {ticks: ['A'], unticks: []}, guide: {ticks: ['A'], step: 2}}
state.finishHand(JSON.stringify(last))
assert.equal(state.guide.step, 2)
assert.deepEqual(plain(state.hand), last.hand)
''')

    def test_late_answers_cannot_replace_another_games_state(self):
        self.run_js('''
state.toggleTick('A')
state.handGeneration++
const current = state.hand
state.finishHand(JSON.stringify({hand: {ticks: ['C']}, guide: {step: 9}}))
assert.equal(state.hand, current)
state.finishHand('')
assert.equal(state.handError, '')
assert.equal(state.handReader.running, false)
''')

    def test_failure_rolls_back_and_reads_both_hand_and_guide_before_more_writes(self):
        self.run_js('''
state.toggleTick('A')
state.toggleTick('A')
state.finishHand(JSON.stringify({hand: {ticks: [], unticks: ['A']}, guide: {ticks: [], step: 1}}))
state.handWriter.running = false
state.nextHand()
state.toggleTick('A')
state.finishHand('not JSON')
assert.equal(state.handQueue.length, 0)
assert.equal(state.handRecovering, true)
assert.equal(state.byHand('A'), false)
assert.equal(state.guide.step, 1)
assert.deepEqual(plain(state.handReader.command), ['python3', 'omatrophy.py', 'game', 'steam', '1', '--guide'])
state.toggleTick('A')
state.stepCount('A', 1)
state.saveNote('A', 'cannot race recovery')
assert.equal(state.handQueue.length, 0)
state.handQueue = [{command: ['later'], generation: 2}]
state.handWriter.running = false
state.nextHand()
assert.equal(state.handWriter.running, false)
''')

    def test_writes_are_argv_and_simulations_never_start_processes(self):
        self.run_js('''
state.live = false
state.toggleTick('A')
assert.equal(state.handQueue.length, 0)
state.live = true
const note = '$(touch nope); "literal"'
state.saveNote('A', note)
assert.equal(state.handWriter.command.at(-1), note)
''')


if __name__ == '__main__':
    unittest.main()
