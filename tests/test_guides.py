import json, os, sys, tempfile, unittest

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

    def test_next_skips_done_and_puts_missables_first(self):
        items = {'a': {'name': 'a'}, 'b': {'name': 'b', 'missable': True}, 'c': {'name': 'c'}, 'd': {'name': 'd'}}
        done = {'c'}
        self.assertEqual(guides.open_order(['a', 'b', 'c', 'd'], items, done), ['b', 'a', 'd'])

    def test_next_waits_for_requires(self):
        items = {'pro': {'requires': ['vet']}, 'vet': {}, 'x': {}}
        self.assertEqual(guides.open_order(['pro', 'vet', 'x'], items, set()), ['vet', 'x'])
        self.assertEqual(guides.open_order(['pro', 'vet', 'x'], items, {'vet'}), ['pro', 'x'])

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
