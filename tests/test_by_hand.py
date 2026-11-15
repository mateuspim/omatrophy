"""Tests for by_hand.py: ticks, counts and notes by hand (ADR 21). Every
file lives in a temporary folder; the owner's by-hand.json is never read."""
import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import by_hand  # noqa: E402

ACHS = [{'api': 'A', 'name': 'Alpha', 'unlocked': False},
        {'api': 'B', 'name': 'Beta', 'unlocked': True},
        {'api': 'C', 'name': 'Gamma', 'unlocked': False}]


class Folder(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        patch = mock.patch.dict(os.environ, {'XDG_DATA_HOME': d.name})
        patch.start()
        self.addCleanup(patch.stop)
        self.path = by_hand.hand_path()

    def write(self, text):
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        with open(self.path, 'w') as f:
            f.write(text)


class Read(Folder):
    def test_path_follows_xdg_data_home(self):
        self.assertTrue(self.path.endswith(os.path.join('omatrophy', 'by-hand.json')))
        self.assertTrue(self.path.startswith(os.environ['XDG_DATA_HOME']))

    def test_missing_and_broken_read_as_empty(self):
        self.assertEqual(by_hand.read_file(), ({'format': 1, 'games': {}}, False))
        for text in ('{', '[]', '{"games": []}'):
            self.write(text)
            self.assertEqual(by_hand.read_file(), ({'format': 1, 'games': {}}, True))

    def test_game_hand_skips_unlocked_unknown_and_junk(self):
        self.write(json.dumps({'games': {'steam:1': {
            'ticks': {'A': {'done': True}, 'B': {'done': True}, 'C': {'done': False}, 'Z': {'done': True},
                      'X': 'junk'},
            'counts': {'A': {'value': 3}, 'C': {'value': -1}, 'B': {'value': True}, 'Z': {'value': 2}},
            'notes': {'A': {'text': 'hi'}, 'C': {'text': ''}, 'Z': {'text': 'gone'}},
            'note': {'text': 'game'}}}}))
        self.assertEqual(by_hand.game_hand('steam', '1', ACHS),
                         {'ticks': ['A'], 'unticks': ['C'], 'counts': {'A': 3}, 'notes': {'A': 'hi'}, 'note': 'game'})
        self.assertEqual(by_hand.game_hand('gog', '1', ACHS),
                         {'ticks': [], 'unticks': [], 'counts': {}, 'notes': {}, 'note': ''})

    def test_merged_ticks_adds_the_files_and_drops_its_unticks(self):
        hand = {'ticks': ['C'], 'unticks': ['A']}
        self.assertEqual(by_hand.merged_ticks(['A', 'B'], hand, ACHS), ['B', 'C'])
        self.assertEqual(by_hand.merged_ticks([], {}, ACHS), [])


class Clean(unittest.TestCase):
    def test_note_drops_control_characters_and_keeps_newlines(self):
        self.assertEqual(by_hand.clean_note('  a\x1b[31mb\r\nc\td\x85 ', 10), 'a[31mb\nc d')

    def test_note_over_the_limit_is_refused(self):
        self.assertEqual(by_hand.clean_note('x' * 5, 5), 'x' * 5)
        with self.assertRaises(ValueError) as e:
            by_hand.clean_note('x' * 6, 5)
        self.assertIn('at most 5', str(e.exception))

    def test_count_sets_moves_and_clamps(self):
        self.assertEqual(by_hand.parse_count('12', 3, 50), 12)
        self.assertEqual(by_hand.parse_count('+1', 3, 50), 4)
        self.assertEqual(by_hand.parse_count('-5', 3, 50), 0)
        self.assertEqual(by_hand.parse_count('99', 3, 50), 50)
        self.assertIsNone(by_hand.parse_count('clear', 3, 50))
        for bad in ('', '+', 'x', '1.5', '--1'):
            with self.assertRaises(ValueError):
                by_hand.parse_count(bad, 3, 50)


class Update(Folder):
    def test_changes_one_game_and_keeps_the_others(self):
        by_hand.update('steam', '1', lambda e, now: by_hand.set_tick(e, 'A', True, now), clock=lambda: 5)
        by_hand.update('gog', '2', lambda e, now: by_hand.set_note(e, 'game', 'hello', now), clock=lambda: 6)
        by_hand.update('steam', '1', lambda e, now: by_hand.set_count(e, 'C', 4, now), clock=lambda: 7)
        whole = by_hand.read_file()[0]
        self.assertEqual(whole['games'], {
            'steam:1': {'ticks': {'A': {'done': True, 'time': 5}}, 'counts': {'C': {'value': 4, 'time': 7}}},
            'gog:2': {'note': {'text': 'hello', 'time': 6}}})

    def test_emptied_game_leaves_no_trace(self):
        by_hand.update('steam', '1', lambda e, now: by_hand.set_note(e, 'A', 'x', now))
        by_hand.update('steam', '1', lambda e, now: by_hand.set_note(e, 'A', '', now))
        by_hand.update('steam', '1', lambda e, now: by_hand.set_count(e, 'A', None, now))
        self.assertEqual(by_hand.read_file()[0]['games'], {})

    def test_unknown_keys_survive(self):
        self.write(json.dumps({'format': 1, 'extra': 1, 'games': {'steam:1': {'mine': [1]}}}))
        by_hand.update('steam', '1', lambda e, now: by_hand.set_tick(e, 'A', False, now), clock=lambda: 1)
        whole = by_hand.read_file()[0]
        self.assertEqual(whole['extra'], 1)
        self.assertEqual(whole['games']['steam:1']['mine'], [1])

    def test_broken_file_is_kept_aside(self):
        self.write('{not json')
        by_hand.update('steam', '1', lambda e, now: by_hand.set_tick(e, 'A', True, now))
        with open(self.path + '.bad') as f:
            self.assertEqual(f.read(), '{not json')
        self.assertIn('steam:1', by_hand.read_file()[0]['games'])

    def test_clear_removes_the_game(self):
        by_hand.update('steam', '1', lambda e, now: by_hand.set_tick(e, 'A', True, now))
        by_hand.update('steam', '1', lambda e, now: e.clear())
        self.assertEqual(by_hand.read_file()[0]['games'], {})


class Unsafe(Folder):
    """Marketplace review finding 9: another local user who can write in
    the data folder must not get a hand edit to clobber a file through a
    link. Each case plants something and checks the victim is untouched."""

    def setUp(self):
        super().setUp()
        self.folder = os.path.dirname(self.path)
        os.makedirs(self.folder, mode=0o700)
        self.victim = os.path.join(os.environ['XDG_DATA_HOME'], 'victim')
        with open(self.victim, 'w') as f:
            f.write('precious')

    def tick(self):
        by_hand.update('steam', '1', lambda e, now: by_hand.set_tick(e, 'A', True, now))

    def assert_victim_whole(self):
        with open(self.victim) as f:
            self.assertEqual(f.read(), 'precious')

    def test_new_folder_is_private(self):
        os.rmdir(self.folder)
        self.tick()
        self.assertEqual(os.stat(self.folder).st_mode & 0o777, 0o700)

    def test_lock_link_is_refused_not_followed(self):
        os.symlink(self.victim, self.path + '.lock')
        with self.assertRaisesRegex(OSError, 'is a link'):
            self.tick()
        self.assert_victim_whole()
        self.assertFalse(os.path.exists(self.path))

    def test_lock_hard_link_is_refused(self):
        os.link(self.victim, self.path + '.lock')
        with self.assertRaisesRegex(OSError, 'not a plain file'):
            self.tick()
        self.assert_victim_whole()

    def test_existing_lock_is_not_truncated(self):
        with open(self.path + '.lock', 'w') as f:
            f.write('kept')
        self.tick()
        with open(self.path + '.lock') as f:
            self.assertEqual(f.read(), 'kept')

    def test_bad_link_is_replaced_not_written_through(self):
        self.write('{not json')
        os.symlink(self.victim, self.path + '.bad')
        self.tick()
        self.assert_victim_whole()
        self.assertFalse(os.path.islink(self.path + '.bad'))
        with open(self.path + '.bad') as f:
            self.assertEqual(f.read(), '{not json')

    def test_folder_others_can_write_is_refused(self):
        os.chmod(self.folder, 0o777)
        with self.assertRaisesRegex(OSError, 'chmod go-w'):
            self.tick()
        self.assertFalse(os.path.exists(self.path + '.lock'))

    def test_folder_link_is_refused(self):
        os.rmdir(self.folder)
        elsewhere = os.path.join(os.environ['XDG_DATA_HOME'], 'elsewhere')
        os.mkdir(elsewhere, 0o700)
        os.symlink(elsewhere, self.folder)
        with self.assertRaisesRegex(OSError, 'not a folder owned by you'):
            self.tick()
        self.assertEqual(os.listdir(elsewhere), [])


if __name__ == '__main__':
    unittest.main()
