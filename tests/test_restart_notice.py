"""Settings > Toasts' Try after an update the shell hasn't loaded: the
panel is built from its current text, the shell keeps the Service.qml and
watcher it started with, so a Try for a card the old watcher drops showed
nothing (owner's report, 2026-11-14). Runs the panel's actual JS in Node;
no shell, Qt window or user files."""
import json
import pathlib
import re
import shutil
import subprocess
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PICKER = ROOT / 'StylePicker.qml'
SERVICE = ROOT / 'Service.qml'


def function(text, name):
    return re.search(r'^  function ' + name + r'\([^\n]*\) \{\n.*?^  \}', text, re.M | re.S).group(0)


@unittest.skipUnless(shutil.which('node'), 'Node is needed to execute QML JavaScript without Qt')
class RestartNotice(unittest.TestCase):
    def run_js(self, assertions):
        picker = PICKER.read_text()
        functions = '\n'.join(function(picker, n) for n in ('canTry', 'reminderOptions', 'shellRunning'))
        functions += '\n' + function(SERVICE.read_text(), 'versionOf')
        script = r'''
const vm = require('node:vm')
const assert = require('node:assert/strict')
const state = { metals: ['bronze', 'silver', 'gold', 'platinum'], shellState: {}, shellStale: false }
vm.createContext(state)
vm.runInContext(FUNCTIONS, state)
const set = s => { state.shellState = s; state.shellStale = s.stale === true }
const labels = kind => JSON.parse(JSON.stringify(state.reminderOptions({ value: 'on', label: 'At launch' }, kind).map(o => o.value)))
'''.replace('FUNCTIONS', json.dumps(functions)) + assertions
        result = subprocess.run(['node', '-e', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_current_shell_tries_everything(self):
        self.run_js('''
for (const kind of ['difficulty', 'missable', 'recap', 'milestone', 'gold', 'platinum'])
  assert.equal(state.canTry(kind), true, kind)
assert.deepEqual(labels('recap'), ['on', 'off', 'try'])
// Not read yet, or no watcher running: Try as before.
set({ stale: false, running: false })
assert.equal(state.canTry('recap'), true)
''')

    def test_an_old_shell_offers_a_restart_for_cards_it_lacks(self):
        self.run_js('''
set({ stale: true, running: true, cards: ['unlock', 'platinum', 'difficulty'], shell: null, watcher: null, installed: '1.0.0' })
assert.equal(state.canTry('recap'), false)
assert.equal(state.canTry('milestone'), false)
assert.equal(state.canTry('missable'), false)
assert.equal(state.canTry('difficulty'), true)
assert.equal(state.canTry('silver'), true)
assert.equal(state.canTry('platinum'), true)
assert.deepEqual(labels('recap'), ['on', 'off', 'restart'])
assert.deepEqual(labels('difficulty'), ['on', 'off', 'try'])
assert.equal(state.shellRunning(), 'an older OmaTrophy')
set({ stale: true, running: true, cards: ['unlock', 'platinum'], shell: '0.9.0', watcher: '1.0.0' })
assert.equal(state.shellRunning(), 'OmaTrophy 0.9.0')
''')

    def test_the_service_reads_only_a_plain_version(self):
        self.run_js('''
assert.equal(state.versionOf('{"version": "1.0.0"}'), '1.0.0')
assert.equal(state.versionOf('{"version": "1.0.0 --x"}'), '')
assert.equal(state.versionOf('{"version": 1}'), '')
assert.equal(state.versionOf('{'), '')
assert.equal(state.versionOf(''), '')
''')


class Wiring(unittest.TestCase):
    def test_the_service_passes_its_version_and_the_panel_reads_running(self):
        service = SERVICE.read_text()
        self.assertIn('"--shell", shellVersion', service)
        picker = PICKER.read_text()
        self.assertIn('root.helperPath, "running"]', picker)
        for kind in ('difficulty', 'missable', 'recap', 'milestone'):
            self.assertRegex(picker, r'root\.reminderOptions\(\{[^}]*\}, "' + kind + '"\)')
            self.assertIn(f'value === "try" ? root.preview("{kind}") : (value === "restart" ? null', picker)


if __name__ == '__main__':
    unittest.main()
