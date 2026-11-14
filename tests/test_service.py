"""Exercise Service's actual JavaScript in Qt, without a watcher or windows.
Quickshell is a runtime dependency; CI without it skips this integration check.
All files, including Quickshell's runtime state, stay in a temporary folder.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parent.parent
SERVICE = (ROOT / 'Service.qml').read_text()


def quiet_file_view():
    return re.search(r'  FileView \{\n    id: quietFile.*?^  \}',
                     SERVICE, re.M | re.S).group(0)


def service_function(name):
    return re.search(r'^  function ' + name + r'\([^\n]*\) \{.*?^  \}',
                     SERVICE, re.M | re.S).group(0)


@unittest.skipUnless(shutil.which('quickshell'), 'Quickshell is not installed')
class ServicePolicy(unittest.TestCase):
    def test_queue_dnd_and_monitor_policy(self):
        functions = '\n'.join(service_function(name) for name in (
            'cardOf', 'rankOf', 'enqueue', 'next', 'toastScreen', 'focusedScreen',
            'currentToastScreen', 'quietOn'))
        # Supply deterministic monitor objects instead of connecting to Hyprland.
        functions = functions.replace('Quickshell.screens', 'root.availableScreens').replace(
            'Hyprland.focusedMonitor', 'root.focusedMonitor')
        picker = (ROOT / 'StylePicker.qml').read_text()
        choices = re.search(r'^  function screenOptions\([^\n]*\) \{.*?^  \}',
                            picker, re.M | re.S).group(0)
        functions += '\n' + choices.replace('Quickshell.screens', 'root.availableScreens')
        cards = (ROOT / 'cards.json').read_text()
        script = '''
    function check(ok, reason) { if (!ok) throw new Error(reason) }
    function event(type, id) { return { type: type, id: id, tier: "gold" } }
    Timer { interval: 50; running: true; onTriggered: {
      try {
        check(!quietOn("") && !quietOn("{") && !quietOn("null"), "bad quiet JSON")
        check(!quietOn('[]') && !quietOn('{"dnd":"true"}') && !quietOn('{"dnd":1}'), "strict dnd boolean")
        check(quietOn('{"dnd":true}') && !quietOn('{"dnd":false}'), "quiet boolean")
        dnd = false
        enqueue(event("unlock", "startup"))
        check(current === null && queue.length === 1, "startup waits for quiet file result")
        dnd = true; quietLoaded = true
        check(current === null, "initial DND read keeps startup card held")
        queue = []
        for (var i = 0; i < 25; i++) enqueue(event("unlock", i))
        check(queue.length === 20 && current === null && played === 0, "held queue cap/silence")
        enqueue(event("recap", "recap"))
        enqueue(event("missable", "missable"))
        enqueue(event("difficulty", "difficulty"))
        check(queue.length === 23 && queue[0].type === "difficulty" && queue[1].type === "missable", "keep/ranks")
        var trial = event("unlock", "try"); trial.test = true; enqueue(trial)
        check(current.id === "try" && queue.length === 23 && played === 1, "Try bypasses full held queue")
        next()
        check(current === null && queue.length === 23, "Try does not release held cards")
        var impostor = event("unlock", "string-test"); impostor.test = "true"; enqueue(impostor)
        check(current === null && queue.length === 23, "only boolean true bypasses DND/cap")
        dndMode = "ignore"
        check(current.type === "difficulty", "ignore drains held queue")
        next(); check(current.type === "missable", "ranked reminder order")
        for (i = 0; i < 20; i++) { next(); check(current.id === i, "FIFO unlock order") }
        next(); check(current.type === "recap", "kept recap order")
        next(); check(current === null && queue.length === 0, "drained queue")
        dndMode = "hold"
        enqueue(event("milestone", "milestone")); dnd = false
        check(current.id === "milestone", "DND ending drains queue")
        check(screenOptions().length === 3, "connected monitor choices")
        screenName = "absent"
        var options = screenOptions()
        check(options.length === 4 && options[3].label === "absent (off)", "disconnected choice remains visible")
        screenName = "DP-2"
        check(screenOptions().length === 3, "connected choice is not duplicated")
        check(toastScreen().name === "DP-2", "named screen")
        screenName = "absent"
        check(toastScreen().name === "DP-1", "absent screen falls back to focus")
        focusedMonitor = null
        check(toastScreen().name === "DP-1", "missing focus falls back to first screen")
        availableScreens = []
        check(!toastScreen(), "no screens")
        availableScreens = [{ name: "DP-1" }, { name: "DP-2" }]
        screenName = "focused"; focusedMonitor = availableScreens[0]
        enqueue(event("unlock", "second")); next()
        check(currentScreenName === "DP-1", "screen captured on next card")
        focusedMonitor = availableScreens[1]; screenName = "DP-2"
        check(currentToastScreen().name === "DP-1", "visible card stays on starting screen")
        availableScreens = [availableScreens[1]]
        check(currentToastScreen().name === "DP-2", "unplugged screen falls back")
        console.log("SERVICE_POLICY_OK")
      } catch (e) { console.log("SERVICE_POLICY_FAILED", e) }
      Qt.quit()
    } }
'''
        dnd_default = re.search(r'^  property string dndMode:.*$', SERVICE, re.M).group(0)
        holding = re.search(r'^  readonly property bool holding:.*$', SERVICE, re.M).group(0)
        self.run_qml('''
import QtQuick
import Quickshell
ShellRoot {
  id: root
  property var queue: []
  property var current: null
  property string currentScreenName: ""
  property var cards: (''' + cards + ''')
  property var tiers: ["bronze", "silver", "gold", "platinum"]
  property bool followsDnd: true
  property bool dnd: true
''' + dnd_default + '''
  property bool quietLoaded: false
''' + holding + '''
  onHoldingChanged: if (!holding && !current) next()
  property int played: 0
  QtObject { id: chime; function play(tier) { root.played++ } }
  property string screenName: "focused"
  property var availableScreens: [{ name: "DP-1" }, { name: "DP-2" }]
  property var focusedMonitor: availableScreens[0]
''' + functions + script + '\n}')

    def test_quiet_file_changes_and_failure_fallback(self):
        # Use the real FileView declaration: exercise its failure handler and
        # directory watch as well as JSON parsing. The writer only knows HOME,
        # which run_qml isolates, and never opens Omarchy's actual state.
        quiet_view = quiet_file_view()
        writer = textwrap.dedent("""
            import json, os, pathlib, time
            path = pathlib.Path(os.environ['HOME']) / 'quiet.json'
            def sample(step, expected):
                print(json.dumps([step, expected]), flush=True)
                time.sleep(.5)
            def replace(text):
                temp = path.with_suffix('.tmp')
                temp.write_text(text)
                temp.replace(path)
            sample(0, False)
            replace('{"dnd":true}'); sample(1, True)
            replace('{"dnd":false}'); sample(2, False)
            replace('{"dnd":true}'); sample(3, True)
            replace('{'); sample(4, False)
            replace('{"dnd":true}'); sample(5, True)
            path.unlink(); sample(6, False)
            replace('{"dnd":true}'); sample(7, True)
            # A directory where a regular file was expected must fail open.
            path.unlink(); path.mkdir(); sample(8, False)
            path.rmdir(); replace('{"dnd":true}'); sample(9, True)
            if os.geteuid() != 0:
                path.chmod(0); sample(10, False)
                path.chmod(0o600); sample(11, True)
            replace(''); sample(12, False)
            replace('{"dnd":true}'); sample(13, True)
        """)
        self.run_qml('''
import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
  id: root
  property bool followsDnd: true
  property string quietPath: Quickshell.env("HOME") + "/quiet.json"
  property bool dnd: false
  property bool quietLoaded: false
  property var expected: []
''' + quiet_view + service_function('quietOn') + '''
  Process {
    command: ["python3", "-c", ''' + json.dumps(writer) + ''']
    running: true
    stdout: SplitParser { onRead: line => { root.expected = JSON.parse(line); verify.restart() } }
  }
  Timer {
    id: verify
    interval: 200
    onTriggered: {
      if (root.dnd !== root.expected[1]) {
        console.log("SERVICE_POLICY_FAILED quiet step", root.expected[0], root.dnd)
        Qt.quit()
      } else if (root.expected[0] === 13) {
        console.log("SERVICE_POLICY_OK")
        Qt.quit()
      }
    }
  }
}
''')

    def test_startup_gate_opens_whatever_quiet_json_holds(self):
        # A gate that never opens holds every card until the shell restarts,
        # so it must open whatever quiet.json holds, or without one. Binding
        # order can differ with how the path is written: check a literal
        # path and a HOME-built one.
        cases = [(path, content, dnd)
                 for path in ('"@HOME@/quiet.json"', 'Quickshell.env("HOME") + "/quiet.json"')
                 for content, dnd in ((None, 'false'), ('{"dnd":false}', 'false'),
                                      ('{"dnd":true}', 'true'), ('{', 'false'))]
        for path, content, dnd in cases:
            with self.subTest(path=path, content=content):
                setup = '' if content is None else (
                    'import pathlib, os; (pathlib.Path(os.environ["HOME"]) / "quiet.json")'
                    '.write_text(' + repr(content) + ')')
                self.run_qml('''
import QtQuick
import Quickshell
import Quickshell.Io
ShellRoot {
  id: root
  property bool followsDnd: true
  property string quietPath: ''' + path + '''
  property bool dnd: false
  property bool quietLoaded: false
''' + quiet_file_view() + service_function('quietOn') + '''
  Timer { interval: 300; running: true; onTriggered: {
    console.log(root.quietLoaded && root.dnd === ''' + dnd + '''
                ? "SERVICE_POLICY_OK" : "SERVICE_POLICY_FAILED " + root.quietLoaded + " " + root.dnd)
    Qt.quit()
  } }
}
''', setup)

    def run_qml(self, source, setup=''):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / 'runtime'
            runtime.mkdir(mode=0o700)
            (Path(tmp) / 'shell.qml').write_text(source.replace('@HOME@', tmp))
            if setup:
                subprocess.run(['python3', '-c', setup], check=True,
                               env=dict(os.environ, HOME=tmp))
            env = dict(os.environ, HOME=tmp, XDG_RUNTIME_DIR=str(runtime),
                       XDG_CONFIG_HOME=f'{tmp}/config', XDG_DATA_HOME=f'{tmp}/data',
                       XDG_CACHE_HOME=f'{tmp}/cache', XDG_STATE_HOME=f'{tmp}/state',
                       QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='')
            try:
                result = subprocess.run(['quickshell', '-p', tmp], env=env,
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, timeout=15)
            except subprocess.TimeoutExpired as exc:
                self.fail(f'Quickshell timed out: {exc.stdout!r}')
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn('SERVICE_POLICY_OK', result.stdout)
        self.assertNotIn('SERVICE_POLICY_FAILED', result.stdout)
