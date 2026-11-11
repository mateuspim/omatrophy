import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import guides

SAMPLES = os.path.join(os.path.dirname(__file__), '..', 'dev', 'samples', 'guides')
ACHS = [
    {'api': 'ACH_LANTERN', 'name': 'Last Lantern', 'unlocked': False},
    {'api': 'ACH_STARS', 'name': 'Star Counter', 'unlocked': False},
    {'api': 'ACH_QUIET', 'name': 'Quiet Hours', 'unlocked': False},
    {'api': 'A1', 'name': 'First Light', 'unlocked': True},
    {'api': 'A2', 'name': 'Long Way Home', 'unlocked': True},
    {'api': 'A3', 'name': 'Moth to a Flame', 'unlocked': False},
]


# guide_answer reads the "I'm here" pins from the state folder: a folder of
# the tests' own, never the owner's.
def setUpModule():
    state = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(state.cleanup)
    patch = mock.patch.dict(os.environ, {'XDG_STATE_HOME': state.name})
    patch.start()
    unittest.addModuleCleanup(patch.stop)


def touch(folder, name, text=''):
    with open(os.path.join(folder, name), 'w', encoding='utf-8') as f:
        f.write(text)


class FindGuide(unittest.TestCase):
    def test_outdated_only_for_made_guides_of_an_older_maker(self):
        self.assertTrue(guides.outdated({'generated': 1}))
        self.assertTrue(guides.outdated({'generated': 1, 'maker': guides.MAKER - 1}))
        self.assertFalse(guides.outdated({'generated': 1, 'maker': guides.MAKER}))
        self.assertFalse(guides.outdated({}))  # imported by hand

    def test_finds_by_trailing_id_not_slug(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, 'renamed-game-42.md')
            touch(d, 'other-gog-42.md')
            touch(d, 'doom-gog-1435827232.md')
            self.assertEqual(os.path.basename(guides.find_guide('steam', '42', d)), 'renamed-game-42.md')
            self.assertEqual(os.path.basename(guides.find_guide('gog', '1435827232', d)), 'doom-gog-1435827232.md')
            self.assertEqual(os.path.basename(guides.find_guide('gog', '42', d)), 'other-gog-42.md')
            self.assertIsNone(guides.find_guide('steam', '4', d))

    def test_steam_skips_other_store_files(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, 'doom-gog-5.md')
            self.assertIsNone(guides.find_guide('steam', '5', d))

    def test_missing_folder(self):
        self.assertIsNone(guides.find_guide('steam', '1', '/nonexistent-omatrophy-folder'))


class ParseMarkdown(unittest.TestCase):
    def test_notes_and_ticks(self):
        text = open(os.path.join(SAMPLES, 'starfall-odyssey-1.md'), encoding='utf-8').read()
        notes, rows = guides.parse_markdown(text)
        self.assertIn('Last Lantern', notes)
        self.assertIn('## Overview', notes)
        self.assertNotIn('First Light', notes)
        byname = {r['name']: r for r in rows}
        self.assertEqual(len(rows), 6)
        self.assertEqual((byname['First Light']['done'], byname['First Light']['hand']), (True, False))
        self.assertEqual((byname['Long Way Home']['done'], byname['Long Way Home']['hand']), (True, False))
        self.assertEqual((byname['Moth to a Flame']['done'], byname['Moth to a Flame']['hand']), (True, True))
        self.assertEqual((byname['Last Lantern']['done'], byname['Last Lantern']['hand']), (False, False))


class MatchItems(unittest.TestCase):
    def test_api_first_then_name(self):
        items = {'Renamed': {'name': 'Renamed', 'api': 'A1'}, 'Star Counter': {'name': 'Star Counter'}}
        out = guides.match_items(items, ACHS)
        self.assertEqual(out['A1']['name'], 'Renamed')
        self.assertIn('ACH_STARS', out)

    def test_duplicate_names_in_store_order(self):
        items = {'Twin': {'name': 'Twin', 'tips': 'first'}, 'Twin ': {'name': 'Twin', 'tips': 'second'}}
        achs = [{'api': 'X', 'name': 'Twin'}, {'api': 'Y', 'name': 'Twin'}]
        out = guides.match_items(items, achs)
        self.assertEqual((out['X']['tips'], out['Y']['tips']), ('first', 'second'))

    def test_format_1_key_is_the_name(self):
        out = guides.match_items({'Star Counter': {'phase': 'grind'}}, ACHS)
        self.assertEqual(out['ACH_STARS']['name'], 'Star Counter')


class GuideAnswer(unittest.TestCase):
    def folder(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        guides.import_guides(SAMPLES, folder=d.name)
        return d.name

    def test_sample(self):
        out = guides.guide_answer('steam', '1', ACHS, self.folder())
        self.assertEqual(out['file'], 'starfall-odyssey-1.md')
        self.assertEqual(out['order'], ['ACH_LANTERN', 'ACH_STARS', 'ACH_QUIET'])
        self.assertEqual(out['ticks'], ['A3'])
        self.assertEqual(out['next'], ['ACH_LANTERN', 'ACH_STARS', 'ACH_QUIET'])
        self.assertEqual(out['sections']['route'], 'Lantern first, then stars.')
        self.assertEqual(out['generated'], 1792990000)

    def test_walkthrough_steps_map_names_and_find_the_current_step(self):
        plan = {'walkthrough': [
            {'title': 'Act 1', 'text': 'Go.', 'achievements': ['a', 'gone'], 'missables': ['a']},
            {'title': 'Act 2', 'text': 'On.', 'achievements': ['b'], 'missables': [], 'unverified': True},
            {'title': 'Credits', 'achievements': []}, 'junk']}
        steps = guides.walkthrough_steps(plan, {'a': 'A1', 'b': 'B1'}, {'A1'})
        self.assertEqual([(s['title'], s['achievements'], s['done']) for s in steps],
                         [('Act 1', ['A1'], True), ('Act 2', ['B1'], False), ('Credits', [], False)])
        self.assertEqual(steps[0]['missables'], ['A1'])
        self.assertTrue(steps[1]['unverified'])
        self.assertEqual(guides.current_step(steps), 1)
        self.assertEqual(guides.current_step(steps[:1]), -1)

    def test_step_actions_map_achievements_and_keep_old_steps_plain(self):
        plan = {'walkthrough': [
            {'title': 'Act 1', 'text': 'Go.', 'achievements': ['a'],
             'actions': [{'where': 'Gate', 'what': 'Open it', 'achievement': 'a'},
                         {'what': 'Look around', 'achievement': 'gone'}, {'where': 'x', 'what': ' '}, 'junk']},
            {'title': 'Act 2', 'achievements': ['b']}]}
        steps = guides.walkthrough_steps(plan, {'a': 'A1', 'b': 'B1'}, set())
        self.assertEqual(steps[0]['actions'], [{'where': 'Gate', 'what': 'Open it', 'achievement': 'A1'},
                                               {'where': '', 'what': 'Look around', 'achievement': ''}])
        self.assertEqual(steps[1]['actions'], [])

    def test_the_tree_sample_matches_the_reader(self):
        # dev/render.sh guide-tree shows it; a sample the reader can't make
        # would check the view against a shape that never occurs.
        folder = os.path.join(SAMPLES, '..')
        with open(os.path.join(folder, 'guide-tree.json'), encoding='utf-8') as f:
            sample = json.load(f)
        self.assertEqual(sample['tree'], guides.tree(sample['order'], sample['items'], sample['walkthrough']))
        self.assertTrue(any(i.get('requires') for i in sample['items'].values()))
        self.assertTrue(any(s['actions'] for s in sample['walkthrough']))
        self.assertNotIn('L8', sample['next'])  # Lighthouse Keeper waits for Keeper
        done = set(sample['ticks']) | {'L12'}  # Ferryman, unlocked in game-tree.json
        self.assertEqual(sample['frontier'], guides.frontier(sample['order'], sample['items'], done,
                                                             sample['walkthrough'], sample['step']))

    def test_walkthrough_maps_unlocked_trophies_not_in_the_plan(self):
        with tempfile.TemporaryDirectory() as d:
            guides.import_guides(SAMPLES, folder=d)
            path = guides.find_guide('steam', '1', d)
            plan = guides.load_plan(path)
            plan['walkthrough'] = [{'title': 'Start', 'achievements': ['First Light']}]
            with open(guides.plan_path(path), 'w') as f:
                json.dump(plan, f)
            out = guides.guide_answer('steam', '1', ACHS, d)
        self.assertEqual(out['walkthrough'][0]['achievements'], ['A1'])

    def test_current_step_follows_the_latest_unlock(self):
        # Regression: MGSV put a player past mission 13 at step 2, where
        # a horse bond was still open.
        plan = {'walkthrough': [{'title': 'Prologue', 'achievements': ['awake']},
                                {'title': 'C2W', 'achievements': ['horse']},
                                {'title': 'Hellbound', 'achievements': ['gears']},
                                {'title': 'Mission 16', 'achievements': ['caravan']}]}
        ids = {n: n for n in ('awake', 'horse', 'gears', 'caravan')}
        steps = guides.walkthrough_steps(plan, ids, {'awake', 'gears'})
        self.assertEqual(guides.current_step(steps), 3)
        self.assertEqual(guides.current_step(guides.walkthrough_steps(plan, ids, set())), 0)

    def test_current_step_ignores_a_side_trophy_got_early(self):
        # Regression: RE5 showed a player who had cleared 3-1 at 4-1,
        # because 4-1's step holds a trophy they had already got in 3-1.
        plan = {'walkthrough': [{'title': '3-1', 'achievements': ['clear31']},
                                {'title': '3-2', 'achievements': ['clear32', 'aspirin']},
                                {'title': '3-3', 'achievements': ['clear33']},
                                {'title': '4-1', 'achievements': ['clear41', 'knife', 'flash']}]}
        ids = {n: n for s in plan['walkthrough'] for n in s['achievements']}
        steps = guides.walkthrough_steps(plan, ids, {'clear31', 'flash'})
        self.assertEqual(guides.current_step(steps), 1)
        # Nothing finished yet: the latest step with an unlock stands in.
        steps = guides.walkthrough_steps(plan, ids, {'flash'})
        self.assertEqual(guides.current_step(steps), 3)

    def test_walkthrough_steps_give_the_marker_and_cleared(self):
        plan = {'walkthrough': [{'title': '3-1', 'achievements': ['clear31', 'side'], 'marker': 'clear31'},
                                {'title': '3-2', 'achievements': ['clear32'], 'marker': 'side'},
                                {'title': '3-3', 'achievements': ['clear33'], 'marker': 'gone'},
                                {'title': 'Old', 'achievements': ['clear41']}]}
        ids = {n: n.upper() for n in ('clear31', 'side', 'clear32', 'clear33', 'clear41')}
        steps = guides.walkthrough_steps(plan, ids, {'CLEAR31'})
        # A marker of another step, or one the store doesn't know, is none.
        self.assertEqual([(s['marker'], s['cleared']) for s in steps],
                         [('CLEAR31', True), ('', False), ('', False), ('', False)])
        self.assertFalse(steps[0]['done'])  # its side trophy is still open

    def test_current_step_follows_the_markers(self):
        # RE5: 3-1 cleared, the 4-1 flash trophy got early, 3-2 cleared
        # with its aspirin trophy left open: the player is at 3-3.
        plan = {'walkthrough': [{'title': '3-1', 'achievements': ['clear31'], 'marker': 'clear31'},
                                {'title': '3-2', 'achievements': ['clear32', 'aspirin'], 'marker': 'clear32'},
                                {'title': '3-3', 'achievements': ['clear33'], 'marker': 'clear33'},
                                {'title': '4-1', 'achievements': ['clear41', 'flash'], 'marker': 'clear41'}]}
        ids = {n: n for s in plan['walkthrough'] for n in s['achievements']}
        steps = guides.walkthrough_steps(plan, ids, {'clear31', 'flash', 'clear32'})
        self.assertEqual(guides.current_step(steps), 2)
        # Nothing cleared, a side trophy of 4-1 got early: still at the
        # start, as 3-1's clear is still to come.
        self.assertEqual(guides.current_step(guides.walkthrough_steps(plan, ids, {'flash'})), 0)
        # Everything after the last clear done: the leftover pulls back.
        done = {'clear31', 'clear32', 'clear33', 'clear41', 'flash'}
        self.assertEqual(guides.current_step(guides.walkthrough_steps(plan, ids, done)), 1)

    def test_current_step_between_markers_uses_the_finished_rule(self):
        # Only the chapters carry markers; the steps between them don't.
        plan = {'walkthrough': [{'title': 'Ch 1', 'achievements': ['c1'], 'marker': 'c1'},
                                {'title': 'Ch 2 town', 'achievements': ['town']},
                                {'title': 'Ch 2 caves', 'achievements': ['bats']},
                                {'title': 'Ch 2 boss', 'achievements': ['c2'], 'marker': 'c2'},
                                {'title': 'Post-game', 'achievements': ['hoard']}]}
        ids = {n: n for s in plan['walkthrough'] for n in s['achievements']}
        self.assertEqual(guides.current_step(guides.walkthrough_steps(plan, ids, {'c1', 'town'})), 2)
        # The post-game trophy got early can't put them past Ch 2's clear.
        self.assertEqual(guides.current_step(guides.walkthrough_steps(plan, ids, {'c1', 'hoard'})), 1)
        # Old guides (no marker) keep the finished-step rule.
        old = {'walkthrough': [dict(s, marker='') for s in plan['walkthrough']]}
        self.assertEqual(guides.current_step(guides.walkthrough_steps(old, ids, {'c1', 'hoard'})), 1)
        self.assertEqual(guides.current_step(guides.walkthrough_steps(old, ids, {'hoard'})), 0)

    def test_a_cleared_marker_ends_a_pin(self):
        plan = {'walkthrough': [{'title': '3-1', 'achievements': ['clear31'], 'marker': 'clear31'},
                                {'title': '3-2', 'achievements': ['clear32', 'aspirin'], 'marker': 'clear32'}]}
        ids = {n: n for s in plan['walkthrough'] for n in s['achievements']}
        pin = guides.make_pin(guides.walkthrough_steps(plan, ids, set()), 1)
        self.assertEqual(guides.pinned_step(guides.walkthrough_steps(plan, ids, {'clear31'}), pin), 1)
        self.assertEqual(guides.pinned_step(guides.walkthrough_steps(plan, ids, {'clear32'}), pin), -1)

    def test_next_skips_done_and_puts_missables_first(self):
        items = {'a': {'name': 'a'}, 'b': {'name': 'b', 'missable': True}, 'c': {'name': 'c'}, 'd': {'name': 'd'}}
        done = {'c'}
        self.assertEqual(guides.open_order(['a', 'b', 'c', 'd'], items, done), ['b', 'a', 'd'])

    def test_next_waits_for_requires(self):
        items = {'pro': {'requires': ['vet']}, 'vet': {}, 'x': {}}
        self.assertEqual(guides.open_order(['pro', 'vet', 'x'], items, set()), ['vet', 'x'])
        self.assertEqual(guides.open_order(['pro', 'vet', 'x'], items, {'vet'}), ['pro', 'x'])

    def test_frontier_starts_at_the_current_step_with_its_missables(self):
        items = {'old': {}, 'c1': {}, 'c2': {}, 'miss': {'missable': True}, 'pro': {'requires': ['vet']},
                 'vet': {}, 'loose': {}}
        steps = [{'achievements': ['old', 'c1']}, {'achievements': ['c2', 'miss'], 'missables': ['miss']},
                 {'achievements': ['vet', 'pro']}]
        out = guides.frontier(['loose', 'pro'], items, {'c1'}, steps, 1)
        # Missable of this step first, then play order, the step-1 leftover
        # last; pro waits for vet.
        self.assertEqual(out, ['miss', 'c2', 'vet', 'loose', 'old'])
        self.assertEqual(guides.frontier(['a'], {'a': {}}, {'a'}), [])

    def test_tree_puts_story_chains_and_the_rest_apart(self):
        items = {'c1': {'phase': 'story'}, 'c2': {'phase': 'story'}, 'vet': {'phase': 'challenge'},
                 'pro': {'phase': 'challenge', 'requires': ['vet', 'c2']}, 'egg': {'phase': 'quick'},
                 'loop1': {'requires': ['loop2']}, 'loop2': {'requires': ['loop1']}}
        steps = [{'achievements': ['c2']}, {'achievements': ['c1']}]
        out = guides.tree(['c1', 'c2', 'egg', 'vet', 'pro', 'loop1', 'loop2'], items, steps)
        self.assertEqual(out['story'], ['c2', 'c1'])
        # A story prerequisite shows under its chain too, as a leaf.
        self.assertEqual(out['chains'], [{'api': 'pro', 'depth': 0}, {'api': 'vet', 'depth': 1}, {'api': 'c2', 'depth': 1}])
        # A cycle (an older or imported guide) has no root: its items stay
        # listed on their own rather than lost.
        self.assertEqual(out['alone'], ['egg', 'loop1', 'loop2'])

    def test_answer_gives_requires_as_apis(self):
        with tempfile.TemporaryDirectory() as d:
            guides.import_guides(SAMPLES, folder=d)
            path = guides.find_guide('steam', '1', d)
            plan = guides.load_plan(path)
            plan['items']['Star Counter']['requires'] = ['Last Lantern', 'Nope', 'Star Counter']
            with open(guides.plan_path(path), 'w') as f:
                json.dump(plan, f)
            out = guides.guide_answer('steam', '1', ACHS, d)
        self.assertEqual(out['items']['ACH_STARS']['requires'], ['ACH_LANTERN'])
        self.assertNotIn('ACH_STARS', out['next'])
        self.assertEqual(out['tree']['chains'], [{'api': 'ACH_STARS', 'depth': 0}, {'api': 'ACH_LANTERN', 'depth': 1}])

    def test_unlocked_items_leave_next(self):
        achs = [dict(a, unlocked=True) if a['api'] == 'ACH_LANTERN' else a for a in ACHS]
        out = guides.guide_answer('steam', '1', achs, self.folder())
        self.assertEqual(out['next'], ['ACH_STARS', 'ACH_QUIET'])

    def test_no_guide(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(guides.guide_answer('steam', '9', ACHS, d), {})

    def test_md_without_plan(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, 'x-7.md', '# X\n\n## Guide notes\n\nhello\n\n## Achievements\n\n- [x] **First Light** — d\n')
            out = guides.guide_answer('steam', '7', ACHS, d)
            self.assertEqual((out['items'], out['order'], out['ticks'], out['notes']), ({}, [], ['A1'], 'hello'))

    def test_broken_plan_still_shows_prose(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, 'x-7.md', '## Guide notes\n\nhi\n\n## Achievements\n')
            touch(d, 'x-7.plan.json', '{not json')
            self.assertEqual(guides.guide_answer('steam', '7', ACHS, d)['notes'], 'hi')

    def test_plan_with_foreign_keys_and_format_1(self):
        with tempfile.TemporaryDirectory() as d:
            touch(d, 'x-7.md', '## Achievements\n')
            touch(d, 'x-7.plan.json', json.dumps({'items': {'Star Counter': {'phase': 'grind'}},
                                                  'order': ['Star Counter'], 'progress': {}}))
            out = guides.guide_answer('steam', '7', ACHS, d)
            self.assertEqual(out['order'], ['ACH_STARS'])


class Pin(unittest.TestCase):
    PLAN = {'walkthrough': [{'title': '3-1', 'achievements': ['clear31']},
                            {'title': '3-2', 'achievements': ['clear32', 'aspirin']},
                            {'title': '3-3', 'achievements': ['clear33']},
                            {'title': '4-1', 'achievements': ['clear41', 'flash']}]}
    IDS = {n: n for s in PLAN['walkthrough'] for n in s['achievements']}

    def steps(self, done):
        return guides.walkthrough_steps(self.PLAN, self.IDS, set(done))

    def test_pin_wins_over_the_guess(self):
        steps = self.steps({'clear31', 'clear32'})
        self.assertEqual(guides.current_step(steps), 1)  # aspirin open
        pin = guides.make_pin(steps, 2)
        self.assertEqual(pin, {'step': 2, 'title': '3-3', 'finished': [0]})
        self.assertEqual(guides.pinned_step(steps, pin), 2)

    def test_pin_dropped_when_its_title_changed(self):
        pin = guides.make_pin(self.steps(set()), 2)
        remade = [dict(s, title='Chapter ' + s['title']) for s in self.steps(set())]
        self.assertEqual(guides.pinned_step(remade, pin), -1)
        self.assertEqual(guides.pinned_step(self.steps(set())[:2], pin), -1)  # fewer steps now
        self.assertEqual(guides.pinned_step(self.steps(set()), {'step': True, 'title': '3-2'}), -1)
        self.assertEqual(guides.pinned_step(self.steps(set()), None), -1)

    def test_pin_overtaken_once_a_step_at_or_after_it_finishes(self):
        pin = guides.make_pin(self.steps({'clear31'}), 2)
        # A step before the pin finishing doesn't move it.
        self.assertEqual(guides.pinned_step(self.steps({'clear31', 'clear32', 'aspirin'}), pin), 2)
        self.assertEqual(guides.pinned_step(self.steps({'clear31', 'clear33'}), pin), -1)
        self.assertEqual(guides.pinned_step(self.steps({'clear31', 'clear41', 'flash'}), pin), -1)

    def test_a_step_finished_before_pinning_doesnt_end_the_pin(self):
        # 4-1's side trophies all got early: finished before the pin, so
        # the pin on 3-3 still holds.
        steps = self.steps({'clear31', 'clear41', 'flash'})
        self.assertEqual(guides.pinned_step(steps, guides.make_pin(steps, 2)), 2)

    def test_save_and_clear_keep_other_games(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'XDG_STATE_HOME': d}):
            self.assertIsNone(guides.load_pin('steam', '1'))
            guides.save_pin('steam', '1', {'step': 2, 'title': '3-3', 'finished': []})
            guides.save_pin('gog', '1', {'step': 0, 'title': 'a', 'finished': []})
            self.assertEqual(guides.load_pin('steam', '1')['step'], 2)
            guides.save_pin('steam', '1', None)
            self.assertIsNone(guides.load_pin('steam', '1'))
            self.assertEqual(guides.load_pin('gog', '1')['title'], 'a')
            self.assertTrue(guides.here_path().startswith(d))

    def test_answer_gives_the_pin_and_says_so(self):
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as state, \
                mock.patch.dict(os.environ, {'XDG_STATE_HOME': state}):
            guides.import_guides(SAMPLES, folder=d)
            path = guides.find_guide('steam', '1', d)
            plan = guides.load_plan(path)
            plan['walkthrough'] = [{'title': 'Start', 'achievements': ['First Light']},
                                   {'title': 'Middle', 'achievements': ['Last Lantern']},
                                   {'title': 'End', 'achievements': ['Star Counter']}]
            with open(guides.plan_path(path), 'w') as f:
                json.dump(plan, f)
            out = guides.guide_answer('steam', '1', ACHS, d)
            self.assertEqual((out['step'], out['step_pinned']), (1, False))
            guides.save_pin('steam', '1', guides.make_pin(out['walkthrough'], 2))
            out = guides.guide_answer('steam', '1', ACHS, d)
            self.assertEqual((out['step'], out['step_pinned']), (2, True))
            # Do now starts at the pinned step: End's trophy before Middle's.
            self.assertLess(out['frontier'].index('ACH_STARS'), out['frontier'].index('ACH_LANTERN'))


class Import(unittest.TestCase):
    def test_copies_skips_and_replaces(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            touch(src, 'a-1.md', 'new')
            touch(src, 'a-1.plan.json', '{}')
            touch(src, 'a-1.sources.json', '{}')
            touch(src, 'b-2.md', 'b')
            touch(src, 'notes.txt', 'ignored')
            touch(dst, 'b-2.md', 'mine')
            self.assertEqual(guides.import_guides(src, folder=dst), (1, 1))
            self.assertEqual(sorted(os.listdir(dst)), ['a-1.md', 'a-1.plan.json', 'a-1.sources.json', 'b-2.md'])
            self.assertEqual(open(os.path.join(dst, 'b-2.md')).read(), 'mine')
            self.assertEqual(guides.import_guides(src, replace=True, folder=dst), (2, 0))
            self.assertEqual(open(os.path.join(dst, 'b-2.md')).read(), 'b')
            self.assertEqual(sorted(os.listdir(src)), ['a-1.md', 'a-1.plan.json', 'a-1.sources.json', 'b-2.md', 'notes.txt'])

    def test_not_a_folder(self):
        with self.assertRaises(SystemExit):
            guides.import_guides('/nonexistent-omatrophy-folder')


if __name__ == '__main__':
    unittest.main()
