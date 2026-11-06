import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import guide_key

OURS = {'modmask': 68, 'key': 'G', 'submap': '', 'description': guide_key.DESCRIPTION}
GROUP = {'modmask': 72, 'key': 'G', 'submap': '', 'description': 'Move active window out of group'}


class GuideKey(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(guide_key.parse(' super+ctrl + g '), {'spec': 'SUPER + CTRL + G', 'modmask': 68, 'key': 'G'})
        self.assertEqual(guide_key.parse('')['spec'], '')
        self.assertIsNone(guide_key.parse('SUPER + HYPER + G'))
        self.assertIsNone(guide_key.parse('SUPER + G"); os.exit()'))
        # Regression: any word passed, and Hyprland refused it.
        self.assertIsNone(guide_key.parse('dsadsadsa'))
        self.assertIsNone(guide_key.parse('SUPER + dsadsadsa'))
        self.assertIsNone(guide_key.parse('G'))  # no modifier
        self.assertEqual(guide_key.parse('super + space')['spec'], 'SUPER + SPACE')
        self.assertEqual(guide_key.parse('f13')['spec'], 'F13')

    def test_binds_a_free_key(self):
        steps, result = guide_key.plan('SUPER + CTRL + G', [GROUP])
        self.assertEqual(len(steps), 1)
        self.assertIn('hl.bind("SUPER + CTRL + G"', steps[0])
        self.assertIn(guide_key.DESCRIPTION, steps[0])
        self.assertEqual(result, {'key': 'SUPER + CTRL + G', 'bound': 'SUPER + CTRL + G', 'error': ''})

    def test_keeps_its_own_bind_in_any_modifier_order(self):
        self.assertEqual(guide_key.plan('CTRL + SUPER + G', [OURS])[0], [])

    def test_refuses_a_taken_key_and_drops_the_old_one(self):
        steps, result = guide_key.plan('SUPER + ALT + G', [OURS, GROUP])
        self.assertEqual(steps, ['hl.unbind("SUPER + CTRL + G")'])
        self.assertEqual(result['bound'], '')
        self.assertIn('already bound to Move active window out of group', result['error'])

    def test_empty_unbinds_and_bad_text_says_how(self):
        self.assertEqual(guide_key.plan('', [OURS]), (['hl.unbind("SUPER + CTRL + G")'], {'key': '', 'bound': '', 'error': ''}))
        self.assertIn('is not a key', guide_key.plan('SUPER+', [])[1]['error'])

    def test_sync_runs_steps_and_saves_the_result(self):
        calls = []

        def run(*args):
            calls.append(args)
            return json.dumps([GROUP]) if args[0] == '-j' else 'ok'
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'XDG_STATE_HOME': d}):
            result = guide_key.sync('SUPER + CTRL + G', run)
            with open(os.path.join(d, 'omatrophy', 'guide-key.json')) as f:
                self.assertEqual(json.load(f), result)
        self.assertEqual(result['bound'], 'SUPER + CTRL + G')
        self.assertEqual(calls[1][0], 'eval')

    def test_check_says_what_holds_a_key_without_binding(self):
        run = lambda *a: json.dumps([GROUP, OURS]) if a[0] == '-j' else self.fail('check must not bind')
        self.assertEqual(guide_key.check('super+alt+g', run), {'key': 'SUPER + ALT + G', 'valid': True,
                                                               'taken': 'Move active window out of group'})
        self.assertEqual(guide_key.check('SUPER + CTRL + G', run)['taken'], '')
        self.assertFalse(guide_key.check('nope nope', run)['valid'])

    def test_set_guide_key_writes_the_spec_or_nothing(self):
        import io, omatrophy
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {'HOME': home}), redirect_stdout(io.StringIO()):
            omatrophy.set_option('guide-key', 'super+alt+t')
            with open(f'{home}/.config/omatrophy/config.json') as f:
                self.assertEqual(json.load(f)['guide-key'], 'SUPER + ALT + T')
            omatrophy.set_option('guide-key', 'none')
            with open(f'{home}/.config/omatrophy/config.json') as f:
                self.assertEqual(json.load(f)['guide-key'], '')
            with self.assertRaises(SystemExit):
                omatrophy.set_option('guide-key', 'SUPER + ')

    def test_a_refused_bind_reads_plainly(self):
        run = lambda *a: '[]' if a[0] == '-j' else 'error: return hl.bind(...):1: Unknown keysym'
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'XDG_STATE_HOME': d}):
            error = guide_key.sync('SUPER + PAUSE', run)['error']
        self.assertEqual(error, 'Hyprland did not accept SUPER + PAUSE as a key; pick another.')

    def test_free_skips_taken_keys_and_counts_ours_free(self):
        taken = [{'modmask': 68, 'key': k, 'submap': '', 'description': 'x'} for k in 'JMQ']
        self.assertEqual(guide_key.free(taken + [OURS], 3), ['SUPER + CTRL + G', 'SUPER + CTRL + U', 'SUPER + CTRL + X'])

    def test_sync_without_hyprland(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'XDG_STATE_HOME': d}):
            self.assertIn('did not answer', guide_key.sync('SUPER + CTRL + G', lambda *a: None)['error'])


if __name__ == '__main__':
    unittest.main()
