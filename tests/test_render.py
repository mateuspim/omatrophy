"""dev/render.sh refuses a bad --theme before it starts any Quickshell, and
the Tree's keyboard focus stays wired: every part the arrows reach names
itself and acts on Enter. Nothing here renders, so CI needs no Quickshell."""
import os, re, subprocess, tempfile, unittest

HERE = os.path.join(os.path.dirname(__file__), '..')
RENDER = os.path.join(HERE, 'dev', 'render.sh')


def render(*args):
    with tempfile.TemporaryDirectory() as home:
        env = dict(os.environ, HOME=home)
        return subprocess.run(['bash', RENDER, *args, os.path.join(home, 'out.png')],
                              capture_output=True, text=True, env=env)


class ThemeFlag(unittest.TestCase):
    def test_refuses_a_name_that_could_be_a_path(self):
        done = render('--theme', '../../etc', 'guide-tree')
        self.assertEqual(done.returncode, 2)
        self.assertIn('takes a theme name', done.stderr)

    def test_refuses_a_theme_not_installed(self):
        done = render('--theme', 'no-such-theme-here', 'guide-tree')
        self.assertEqual(done.returncode, 2)
        self.assertIn("no theme named 'no-such-theme-here'", done.stderr)

    def test_refuses_live_data(self):
        # --theme runs the shell under a throwaway HOME, where live reads
        # would find no stores.
        done = render('--live', '--theme', 'white', 'guide-tree')
        self.assertEqual(done.returncode, 2)
        self.assertIn('drop --live', done.stderr)


class TreeFocus(unittest.TestCase):
    def test_every_focus_has_a_key_and_an_action(self):
        with open(os.path.join(HERE, 'TrackerView.qml'), encoding='utf-8') as f:
            text = f.read()
        uses = [m.start() for m in re.finditer(r'\bTreeFocus\s*\{', text)]
        self.assertGreaterEqual(len(uses), 9)
        for at in uses:
            # The block up to its closing brace at the same depth.
            depth, end = 0, at
            for end in range(text.index('{', at), len(text)):
                depth += {'{': 1, '}': -1}.get(text[end], 0)
                if depth == 0:
                    break
            block = text[at:end]
            line = text[:at].count('\n') + 1
            self.assertRegex(block, r'\bkey:', f'TrackerView.qml:{line}: TreeFocus without a key')
            self.assertRegex(block, r'\bonActivated:', f'TrackerView.qml:{line}: TreeFocus that does nothing on Enter')


if __name__ == '__main__':
    unittest.main()
