import json, os, re, subprocess, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import guide_agents, guide_maker, guides


# guide_answer reads the "I'm here" pins from the state folder: a folder of
# the tests' own, never the owner's.
def setUpModule():
    state = tempfile.TemporaryDirectory()
    unittest.addModuleCleanup(state.cleanup)
    patch = mock.patch.dict(os.environ, {'XDG_STATE_HOME': state.name})
    patch.start()
    unittest.addModuleCleanup(patch.stop)


ACHS = [
    {'api': 'L', 'name': 'Last Lantern', 'desc': 'Carry the lantern to the end', 'unlocked': False, 'time': 0},
    {'api': 'S', 'name': 'Star Counter', 'desc': 'Count 50 stars', 'unlocked': False, 'time': 0},
    {'api': 'F', 'name': 'First Light', 'desc': 'Light the first beacon', 'unlocked': True, 'time': 1792990000},
    {'api': 'Q', 'name': 'Quiet Hours', 'desc': '', 'hidden': True, 'unlocked': False, 'time': 0},
]

# A stand-in agent: reads the prompt on stdin and answers per stage from
# canned files beside it; `calls` counts its runs.
FAKE = r'''
import os, sys
here = os.path.dirname(os.path.abspath(__file__))
prompt = sys.stdin.read()
with open(os.path.join(here, 'calls'), 'a') as f:
    f.write('x')
stage = ('research' if '<research>' in prompt else 'items' if '<items>' in prompt
         else 'walkthrough' if '<walkthrough>' in prompt else 'route')
retry = 'last answer had these problems' in prompt
name = os.path.join(here, stage + ('.retry' if retry else ''))
if not os.path.exists(name):
    name = os.path.join(here, stage)
print(open(name).read())
'''


class FakeAgent(guide_agents.Adapter):
    id, name, checked, web = 'fake', 'Fake', True, False

    def __init__(self, folder):
        self.folder = folder

    def command(self, tmp, web, model, effort):
        return [sys.executable, os.path.join(self.folder, 'fake.py')], None, {}


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def write(folder, name, text):
    os.makedirs(os.path.dirname(os.path.join(folder, name)), exist_ok=True)
    with open(os.path.join(folder, name), 'w', encoding='utf-8') as f:
        f.write(text)


ITEMS = ('<items>[{"name": "Last Lantern", "phase": "missable", "difficulty": 2, "time": "~20 min",'
         ' "minutes": [15, 25], "missable": true, "missable_note": "Before chapter 4", "tips": "Keep it lit.",'
         ' "cites": [{"source": "S1.1", "quote": "carry the lantern before chapter four"}]},'
         ' {"name": "Star Counter", "phase": "grind", "difficulty": 1, "counter": {"target": 50, "label": "stars"},'
         ' "tips": "Look up.", "cites": [{"source": "S1.1", "quote": "this quote is not anywhere at all"}]},'
         ' {"name": "Quiet Hours", "phase": "quick", "difficulty": 3}]</items>')
ROUTE = '<route>{"order": ["Last Lantern", "Quiet Hours", "Star Counter"], "sections": {"overview": "Short and gentle."}}</route>'
WALK = ('<walkthrough>{"steps": ['
        '{"title": "Chapter four", "text": "Carry the lantern.", "achievements": ["Last Lantern", "Nope"],'
        ' "missables": ["Last Lantern", "Star Counter"],'
        ' "cites": [{"source": "file:notes.txt", "quote": "carry the lantern before chapter four ends"}]},'
        '{"title": "Nights", "text": "Look up.", "achievements": ["Star Counter"], "missables": [], "cites": []}]}'
        '</walkthrough>')


class Job(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.agent_dir = os.path.join(self.tmp.name, 'agent')
        self.guides = os.path.join(self.tmp.name, 'guides')
        write(self.agent_dir, 'fake.py', FAKE)
        write(self.agent_dir, 'items', ITEMS)
        write(self.agent_dir, 'route', ROUTE)
        write(self.agent_dir, 'walkthrough', WALK)
        write(self.guides, 'sources/starfall-odyssey-1/notes.txt',
              'You must carry the lantern before chapter four ends. Stars come out at night.')

    def tearDown(self):
        self.tmp.cleanup()

    def job(self, **kw):
        return guide_maker.Job('steam', '1', 'Starfall Odyssey', [dict(a) for a in ACHS], FakeAgent(self.agent_dir),
                               web=False, folder=self.guides, list_guides=lambda app: [], fetch=lambda url: None, **kw)

    def calls(self):
        with open(os.path.join(self.agent_dir, 'calls')) as f:
            return len(f.read())

    def test_fetch_replaces_agent_summaries_and_skips_listings(self):
        fetched = []
        job = guide_maker.Job('steam', '1', 'G', [dict(a) for a in ACHS], FakeAgent(self.agent_dir), web=False,
                              folder=self.guides, list_guides=lambda app: [],
                              fetch=lambda url: fetched.append(url) or 'full page text ' * 400)
        job.add_source('https://a.example/guide', 'a short summary', 'agent')
        job.add_source('https://b.example/guide', 'kept as found ' * 400, 'agent')
        for url in ('https://a.example/guide', 'https://b.example/guide', 'https://p.example/page/1177/',
                    'https://p.example/author/x/page/494/'):
            job.fetch_into(url, 'research')
        self.assertEqual(fetched, ['https://a.example/guide'])
        self.assertTrue(job.sources['https://a.example/guide']['text'].startswith('full page text'))

    def test_makes_files_and_verifies_quotes(self):
        self.assertEqual(guide_maker.make(self.job())['state'], 'done')
        md = os.path.join(self.guides, 'starfall-odyssey-1.md')
        notes, rows = guides.parse_markdown(read(md))
        self.assertIn('Short and gentle.', notes)
        self.assertEqual(len(rows), 4)
        plan = json.loads(read(md[:-3] + '.plan.json'))
        self.assertEqual(plan['format'], 2)
        self.assertEqual(plan['maker'], guides.MAKER)
        self.assertEqual(plan['order'], ['Last Lantern', 'Quiet Hours', 'Star Counter'])
        lantern, stars = plan['items']['Last Lantern'], plan['items']['Star Counter']
        self.assertEqual(lantern['api'], 'L')
        self.assertTrue(lantern['cites'][0]['verified'])
        self.assertEqual(lantern['cites'][0]['source'], 'file:notes.txt')
        self.assertFalse(stars['cites'][0]['verified'])
        self.assertIn('counter', stars['unverified'])
        self.assertEqual(guide_maker.status(self.guides)['state'], 'done')
        sources = json.loads(read(md[:-3] + '.sources.json'))
        self.assertIn('file:notes.txt', sources)
        answer = guides.guide_answer('steam', '1', ACHS, self.guides)
        self.assertEqual(answer['next'][0], 'L')
        self.assertEqual(answer['agent']['name'], 'fake')

    def test_announce_says_done_and_failed_and_status_names_the_work(self):
        said = []
        with mock.patch.object(guide_maker, 'notify', lambda summary, body: said.append(summary)):
            guide_maker.make(self.job(), announce=True)
            write(self.agent_dir, 'items', 'nothing useful')
            guide_maker.make(self.job(), announce=True)
            guide_maker.make(self.job())
        self.assertEqual(said, ['Guide ready: Starfall Odyssey', 'Guide failed: Starfall Odyssey'])
        found = guide_maker.status(self.guides)
        self.assertEqual((found['open'], found['web']), (3, False))

    def test_bad_answer_is_asked_again_once(self):
        write(self.agent_dir, 'items', 'no tags at all')
        write(self.agent_dir, 'items.retry', ITEMS)
        self.assertEqual(guide_maker.make(self.job())['state'], 'done')
        self.assertEqual(self.calls(), 5)  # items twice, route once, walkthrough twice (it names "Nope")
        plan = json.loads(read(os.path.join(self.guides, 'starfall-odyssey-1.plan.json')))
        walk = [u for u in plan['usage'] if u['stage'] == 'walkthrough']
        self.assertTrue(any("'Nope'" in e for e in walk[0]['errors']))
        self.assertNotIn('errors', [u for u in plan['usage'] if u['stage'] == 'route'][0])

    def test_a_worse_retry_does_not_replace_the_first_walkthrough(self):
        # Regression: `b or a` kept the retry even when it placed fewer of
        # the open achievements (HANDOFF 2026-11-10).
        write(self.agent_dir, 'walkthrough.retry', '<walkthrough>{"steps": [{"title": "Nights", "text": "Look up.",'
              ' "achievements": ["Star Counter"], "missables": [], "cites": []}]}</walkthrough>')
        self.assertEqual(guide_maker.make(self.job())['state'], 'done')
        plan = json.loads(read(os.path.join(self.guides, 'starfall-odyssey-1.plan.json')))
        self.assertEqual([s['title'] for s in plan['walkthrough']], ['Chapter four', 'Nights'])

    def test_a_better_retry_replaces_the_first_answer(self):
        write(self.agent_dir, 'walkthrough.retry', WALK.replace('"Nope"', '"Quiet Hours"'))
        self.assertEqual(guide_maker.make(self.job())['state'], 'done')
        plan = json.loads(read(os.path.join(self.guides, 'starfall-odyssey-1.plan.json')))
        self.assertEqual(plan['walkthrough'][0]['achievements'], ['Last Lantern', 'Quiet Hours'])

    def test_walkthrough_steps_are_checked_and_verified(self):
        self.assertEqual(guide_maker.make(self.job())['state'], 'done')
        plan = json.loads(read(os.path.join(self.guides, 'starfall-odyssey-1.plan.json')))
        first, second = plan['walkthrough']
        self.assertEqual(first['achievements'], ['Last Lantern'])
        self.assertEqual(first['missables'], ['Last Lantern'])
        self.assertTrue(first['cites'][0]['verified'])
        self.assertFalse(first['unverified'])
        self.assertTrue(second['unverified'])

    def test_walkthrough_marks_missable_items_and_wants_more_than_the_store_says(self):
        job = self.job()
        job.sources = {'https://x.example/g': {'text': 'Carry the lantern to the end. In chapter four keep the lantern lit.'}}
        answer = ('<walkthrough>{"steps": [{"title": "Chapter four", "achievements": ["Last Lantern", "Star Counter"],'
                  ' "missables": [], "cites": [{"source": "https://x.example/g", "quote": "Carry the lantern to the end"}]},'
                  ' {"title": "Nights", "achievements": ["Quiet Hours"], "missables": [],'
                  ' "cites": [{"source": "https://x.example/g", "quote": "In chapter four keep the lantern lit"}]}]}</walkthrough>')
        job.ask = lambda stage, text, check, merge=None, **kw: check(answer)
        table = {'Last Lantern': {'missable': True}, 'Star Counter': {}, 'Quiet Hours': {}}
        steps, errors = job.walkthrough(table, list(table), [])
        self.assertEqual(errors, [])
        self.assertEqual(steps[0]['missables'], ['Last Lantern'])
        # The first quote is only the store's description: no proof.
        self.assertTrue(steps[0]['unverified'])
        self.assertFalse(steps[1]['unverified'])

    def test_walkthrough_is_told_the_unlocked_ones(self):
        job = self.job()
        seen = []
        job.ask = lambda stage, text, check, merge=None, **kw: (seen.append(text) or ([], []))
        job.walkthrough({'Last Lantern': {'phase': 'story'}}, ['Last Lantern'], [])
        self.assertIn('- First Light [unlocked]: done — Light the first beacon', seen[0])

    def test_a_failed_walkthrough_keeps_the_guide(self):
        write(self.agent_dir, 'walkthrough', 'no tags')
        self.assertEqual(guide_maker.make(self.job())['state'], 'done')
        plan = json.loads(read(os.path.join(self.guides, 'starfall-odyssey-1.plan.json')))
        self.assertEqual(plan['walkthrough'], [])
        self.assertIn('Last Lantern', plan['items'])

    def test_unparsable_answers_fail_and_write_nothing(self):
        write(self.agent_dir, 'items', 'nothing useful')
        self.assertEqual(guide_maker.make(self.job())['state'], 'failed')
        self.assertFalse(os.path.exists(os.path.join(self.guides, 'starfall-odyssey-1.md')))
        self.assertIn('failed', guide_maker.status(self.guides)['line'])

    def test_stop_before_a_stage_keeps_the_old_guide(self):
        write(self.guides, 'starfall-odyssey-1.md', 'old guide\n')
        job = self.job()
        real = guide_maker.stop_requested
        with mock.patch.object(guide_maker, 'stop_requested',
                               lambda folder=None, store='', app='': job.stage == 'gather' or real(folder, store, app)):
            self.assertEqual(guide_maker.make(job)['state'], 'stopped')
        self.assertEqual(read(os.path.join(self.guides, 'starfall-odyssey-1.md')), 'old guide\n')
        self.assertEqual(guide_maker.status(self.guides)['state'], 'stopped')

    def test_remake_keeps_hand_ticks_unknown_keys_and_a_previous_copy(self):
        write(self.guides, 'renamed-1.md', '# Old\n\n## Achievements\n\n- [x] **Star Counter** — Count 50 stars.\n')
        write(self.guides, 'renamed-1.plan.json', json.dumps(
            {'items': {'Star Counter': {'name': 'Star Counter', 'details': {'steps': ['a']}}}, 'progress': {'x': 1}}))
        self.assertEqual(guide_maker.make(self.job())['name'], 'renamed-1')
        plan = json.loads(read(os.path.join(self.guides, 'renamed-1.plan.json')))
        self.assertEqual(plan['progress'], {'x': 1})
        self.assertEqual(plan['items']['Star Counter']['details'], {'steps': ['a']})
        _, rows = guides.parse_markdown(read(os.path.join(self.guides, 'renamed-1.md')))
        self.assertTrue(next(r for r in rows if r['name'] == 'Star Counter')['hand'])
        self.assertTrue(os.path.exists(os.path.join(self.guides, 'renamed-1.md.prev')))


class Checks(unittest.TestCase):
    def test_tagged_takes_the_last_block_and_strips_fences(self):
        self.assertEqual(guide_maker.tagged('<x>[1]</x> then <x>```json\n[2]\n```</x>', 'x'), [2])
        with self.assertRaises(ValueError):
            guide_maker.tagged('<x>{bad</x>', 'x')

    def test_check_item_drops_bad_fields(self):
        item, errors = guide_maker.check_item({'name': 'A', 'phase': 'nope', 'difficulty': 9, 'minutes': [30, 10],
                                               'counter': {'target': 1}, 'combine_with': ['B', 'Z', 'A']}, {'A', 'B'})
        self.assertNotIn('phase', item)
        self.assertNotIn('difficulty', item)
        self.assertEqual(item['minutes'], [10, 30])
        self.assertIsNone(item['counter'])
        self.assertEqual(item['combine_with'], ['B'])
        self.assertEqual(len(errors), 2)
        self.assertEqual(guide_maker.check_item({'name': 'Z'}, {'A'})[0], None)

    def test_check_item_keeps_known_requires_only(self):
        item, errors = guide_maker.check_item({'name': 'A', 'phase': 'quick', 'requires': ['B', 'A', 'Z', 'B']}, {'A', 'B'})
        self.assertEqual(item['requires'], ['B'])
        self.assertEqual(len(errors), 1)
        self.assertIn("'Z'", errors[0])
        self.assertEqual(guide_maker.check_item({'name': 'A', 'requires': 'B'}, {'A', 'B'})[0]['requires'], [])

    def test_requires_cycles_break_at_the_closing_edge(self):
        text = ('<items>[{"name": "Pro", "phase": "challenge", "difficulty": 4, "requires": ["Vet"]},'
                ' {"name": "Vet", "phase": "challenge", "difficulty": 3, "requires": ["Pro", "Nor"]}]</items>')
        items, errors = guide_maker.check_items(text, ['Pro', 'Vet'], ['Pro', 'Vet', 'Nor'], {'Nor': ['Pro']})
        # Pro -> Vet is kept; Vet -> Pro closes the loop, and Vet -> Nor
        # closes one through the earlier batch (Nor needs Pro).
        self.assertEqual(items['Pro']['requires'], ['Vet'])
        self.assertEqual(items['Vet']['requires'], [])
        self.assertEqual(len([e for e in errors if 'already needs' in e]), 2)
        loop = {'X': {'requires': ['Y']}, 'Y': {'requires': ['X']}}
        self.assertEqual(len(guide_maker.prune_requires(loop, {})), 1)
        self.assertEqual((loop['X']['requires'], loop['Y']['requires']), (['Y'], []))

    def test_requires_is_a_claim_and_reaches_the_route_table(self):
        item, _ = guide_maker.check_item({'name': 'A', 'phase': 'challenge', 'requires': ['B']}, {'A', 'B'})
        self.assertEqual(guide_maker.verify_cites(item, {}, [])['unverified'], ['requires'])
        self.assertIn('needs first B', guide_maker.table_line('A', item, False))

    def test_an_estimated_time_stays_unverified_beside_a_verified_quote(self):
        raw = {'name': 'A', 'phase': 'quick', 'time': '~5 min', 'time_estimate': True, 'tips': 'Open the door twice.',
               'cites': [{'source': 'https://x', 'quote': 'open the red door twice in chapter one'}]}
        item, _ = guide_maker.check_item(raw, {'A'})
        self.assertEqual(item['unverified'], ['time'])
        sources = {'https://x': {'text': 'Tip: open the red door twice in chapter one to get it.'}}
        self.assertEqual(guide_maker.verify_cites(item, sources, [])['unverified'], ['time'])
        sourced, _ = guide_maker.check_item(dict(raw, time_estimate=False), {'A'})
        self.assertEqual(guide_maker.verify_cites(sourced, sources, [])['unverified'], [])
        self.assertEqual(guide_maker.check_item({'name': 'A', 'difficulty': ' 3 '}, {'A'})[0]['difficulty'], 3)

    def test_check_route(self):
        route, errors = guide_maker.check_route('<route>{"order": ["A", "Z", "A"], "sections": {}}</route>', {'A'})
        self.assertEqual(route['order'], ['A'])
        self.assertEqual(len(errors), 2)  # Z unknown, no overview

    def test_route_meta_talk_is_rejected_and_scrubbed(self):
        # Regression: the MGSV guide of 2026-11-04 talked about "the
        # provided table" and cited `table` all through its prose.
        overview = ('You have 13 of 42. The provided table has no source URLs or chunk ids. '
                    'Executed is hard (`table`: "challenge; difficulty 4").')
        route = '1. **Story.** Play Skull. It "combines with Accomplished" (`table`).\n2. Do Hero, then Truth.'
        answer = json.dumps({'order': ['A'], 'sections': {'overview': overview, 'route': route}})
        found, errors = guide_maker.check_route(f'<route>{answer}</route>', {'A'})
        self.assertEqual(len(errors), 2)
        self.assertIn('sections.overview talks about your input', errors[0])
        self.assertEqual(found['sections']['overview'], 'You have 13 of 42. Executed is hard.')
        self.assertEqual(found['sections']['route'],
                         '1. **Story.** Play Skull. It "combines with Accomplished".\n2. Do Hero, then Truth.')

    def test_meta_talk_leaves_game_prose_alone(self):
        for text in ('Put the key on the table in the lab.', 'A list of missables follows.',
                     'Source the parts in chapter 2.'):
            self.assertEqual(guide_maker.meta_talk(text), [], text)
            self.assertEqual(guide_maker.scrub_meta(text), text)

    def test_route_prompt_asks_for_no_citations(self):
        text = guide_maker.prompt('route', game='G', progress='0 of 1', table='- A: story')
        self.assertNotIn('chunk id (like', text)
        self.assertIn('no quotes and no citations', text)

    def test_check_walkthrough(self):
        steps, errors = guide_maker.check_walkthrough(
            '<walkthrough>{"steps": [{"title": "Act 1", "text": "The provided table says go.", '
            '"achievements": ["A", "Z"], "missables": ["A", "B"]}, {"text": "no title"}]}</walkthrough>', {'A', 'B'})
        self.assertEqual(steps, [{'title': 'Act 1', 'text': '', 'achievements': ['A'], 'missables': ['A'], 'actions': [],
                                  'marker': '', 'cites': []}])
        self.assertEqual(len(errors), 3)  # meta talk, Z unknown, step 2 untitled
        self.assertEqual(guide_maker.check_walkthrough('<walkthrough>[]</walkthrough>', {'A'})[0], [])

    def test_check_actions_keeps_ordered_known_actions(self):
        raw = [{'where': 'Chapter 2-1, the gate', 'what': 'Shoot the three lamps', 'achievement': 'A'},
               {'where': '', 'what': 'Talk to the guard', 'achievement': 'Z'},
               {'where': 'Hub', 'what': '  '}, 'junk',
               {'where': 'Hub', 'what': 'The provided table says wait'}]
        actions, errors = guide_maker.check_actions(raw, 3, {'A'})
        self.assertEqual(actions[:2], [{'where': 'Chapter 2-1, the gate', 'what': 'Shoot the three lamps', 'achievement': 'A'},
                                       {'where': '', 'what': 'Talk to the guard', 'achievement': ''}])
        self.assertEqual(len(actions), 2)  # the last was only talk about the input
        self.assertEqual(len(errors), 4)  # Z unknown, two with no `what`, meta talk
        self.assertTrue(all(e.startswith('step 3 action') for e in errors))
        self.assertEqual(guide_maker.check_actions(None, 1, {'A'}), ([], []))

    def test_check_actions_asks_to_split_a_long_cleanup(self):
        raw = [{'where': f'Chapter {n}', 'what': 'Find the emblem'} for n in range(guide_maker.STEP_ACTIONS + 3)]
        actions, errors = guide_maker.check_actions(raw, 1, set())
        self.assertEqual(len(actions), guide_maker.STEP_ACTIONS)
        self.assertIn('split it by chapter or area', errors[0])

    def test_check_walkthrough_keeps_actions(self):
        steps, errors = guide_maker.check_walkthrough(
            '<walkthrough>{"steps": [{"title": "Chapter 1", "text": "Reach the market.", "achievements": ["A"],'
            ' "actions": [{"where": "Market", "what": "Survive the crowd", "achievement": "A"}]}]}</walkthrough>', {'A'})
        self.assertEqual(errors, [])
        self.assertEqual(steps[0]['actions'], [{'where': 'Market', 'what': 'Survive the crowd', 'achievement': 'A'}])

    def test_walk_words_need_a_number_after_everyday_words(self):
        for text in ('Act 2 opens', 'Stage IV boss', 'level 3', 'Chapter one', 'the mission', 'walkthrough'):
            self.assertTrue(guide_maker.WALK_WORDS.search(text), text)
        for text in ('act fast here', 'the area around the lake', 'level up your gun', 'set the stage for it'):
            self.assertIsNone(guide_maker.WALK_WORDS.search(text), text)

    def test_cut_off_quotes_do_not_verify(self):
        self.assertTrue(guide_maker.cut_off('they will also unlock the'))
        self.assertTrue(guide_maker.cut_off('beat the boss and'))
        self.assertFalse(guide_maker.cut_off('beat the boss without a hit'))
        self.assertFalse(guide_maker.cut_off('you need it before the.'))
        self.assertFalse(guide_maker.cut_off(''))
        sources = {'https://x.example/g': {'text': 'Finish chapter two. They will also unlock the vault door later.'}}
        cites = [{'source': 'https://x.example/g', 'quote': 'They will also unlock the'},
                 {'source': 'https://x.example/g', 'quote': 'They will also unlock the vault door'}]
        found = guide_maker.verify_quotes(cites, sources, [])
        self.assertEqual([c['verified'] for c in found], [False, True])

    def test_check_walkthrough_asks_again_for_open_ones_in_no_step(self):
        answer = '<walkthrough>{"steps": [{"title": "Act 1", "achievements": ["A"]}]}</walkthrough>'
        steps, errors = guide_maker.check_walkthrough(answer, {'A', 'B', 'C'}, ['A', 'B'])
        self.assertEqual(len(steps), 1)
        self.assertEqual(len(errors), 1)
        self.assertIn('in no step: B;', errors[0])
        self.assertEqual(guide_maker.check_walkthrough(answer, {'A', 'B'}, ['A'])[1], [])

    def test_check_walkthrough_keeps_an_achievement_in_its_first_step_only(self):
        steps, errors = guide_maker.check_walkthrough(
            '<walkthrough>{"steps": [{"title": "Mission 2", "achievements": ["Skilled"], "missables": ["Skilled"]},'
            ' {"title": "S-rank all", "achievements": ["Hero", "Skilled"], "missables": ["Skilled"]}]}</walkthrough>',
            {'Skilled', 'Hero'}, ['Skilled', 'Hero'])
        self.assertEqual(errors, [])
        self.assertEqual([s['achievements'] for s in steps], [['Skilled'], ['Hero']])
        self.assertEqual(steps[1]['missables'], [])

    def test_check_walkthrough_keeps_a_marker_of_the_step_only(self):
        steps, errors = guide_maker.check_walkthrough(
            '<walkthrough>{"steps": ['
            '{"title": "1-1", "achievements": ["Clear 1-1", "Flash"], "marker": "Clear 1-1"},'
            '{"title": "1-2", "achievements": ["Clear 1-2"], "marker": "Flash"},'
            '{"title": "1-3", "achievements": ["Clear 1-3"], "marker": "Made up"},'
            '{"title": "Credits", "achievements": [], "marker": ""},'
            '{"title": "Post-game", "achievements": ["Hoarder"]}]}</walkthrough>',
            {'Clear 1-1', 'Clear 1-2', 'Clear 1-3', 'Flash', 'Hoarder'})
        self.assertEqual([s['marker'] for s in steps], ['Clear 1-1', '', '', '', ''])
        # Another step's achievement and an unknown name both ask again.
        self.assertEqual(len(errors), 2)
        self.assertTrue(errors[0].startswith("step 2 marker 'Flash'"))
        self.assertIn('chapter or mission clear', errors[1])

    def test_walkthrough_prompt_asks_for_a_marker(self):
        text = guide_maker.prompt('walkthrough', game='G', progress='0 of 1', excerpts='', table='- A: story')
        self.assertIn('`marker`', text)
        self.assertIn('"marker":', text)

    def test_walkthrough_prompt_puts_a_collect_all_where_it_finishes(self):
        text = guide_maker.prompt('walkthrough', game='G', progress='0 of 1', excerpts='', table='- A: story')
        self.assertIn('exactly one step', text)
        self.assertIn('goes where it finishes', text)

    def test_walkthrough_prompt_drops_play_through_actions(self):
        # Regression: the RE5 bench of 2026-11-10 gave 15 of 65 actions as
        # "Play through to the end of the chapter" for the story trophy.
        text = guide_maker.prompt('walkthrough', game='G', progress='0 of 1', excerpts='', table='- A: story')
        self.assertIn('only says to play or finish the chapter', text)
        self.assertIn('A step with nothing else to do has no', text)

    def test_walkthrough_excerpts_prefer_chapters(self):
        pieces = guide_maker.chunks({'https://x.example': {'text': 'unrelated words only'},
                                     'https://www.powerpyx.com/g': {'text': 'Chapter 2: the bridge. Mission 3 next.'}})
        self.assertEqual([p['url'] for p in guide_maker.walkthrough_excerpts([], pieces)], ['https://www.powerpyx.com/g'])

    def test_kept_sources_drop_old_and_listing_pages(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'g.sources.json')
            write(d, 'g.sources.json', json.dumps({
                'https://a.example/guide': {'kind': 'research', 'fetched': 100, 'text': 'ok'},
                'https://a.example/page/3/': {'kind': 'research', 'fetched': 100, 'text': 'list'},
                'https://b.example/old': {'kind': 'research', 'fetched': 0, 'text': 'stale'}}))
            kept = guide_maker.kept_sources(path, guide_maker.SOURCES_KEPT)
            self.assertEqual(list(kept), ['https://a.example/guide'])

    def test_listing_page(self):
        self.assertTrue(guide_maker.listing_page('https://www.powerpyx.com/guide/page/1132/'))
        self.assertTrue(guide_maker.listing_page('https://www.powerpyx.com/author/powerpyx/page/494/'))
        self.assertFalse(guide_maker.listing_page('https://www.powerpyx.com/guides/mgsv-trophy-guide.html'))
        self.assertFalse(guide_maker.listing_page('https://www.powerpyx.com/?p=1482'))

    def test_fold_matches_typographic_quotes(self):
        self.assertIn(guide_maker.fold('don’t  go — "now"'), guide_maker.fold('Don\'t go - “now”!'))

    def test_chunks_cut_long_text(self):
        pieces = guide_maker.chunk_text('word ' * 1000, 300)
        self.assertTrue(all(len(p) <= 300 for p in pieces))
        self.assertEqual(sum(len(p.split()) for p in pieces), 1000)

    def test_excerpts_prefer_the_name_and_research_hints(self):
        pieces = guide_maker.chunks({'https://a': {'text': 'nothing here about it'},
                                     'https://b': {'text': 'Last Lantern: carry it far.'},
                                     'https://c': {'text': 'the hinted words live here'}})
        ach = {'name': 'Last Lantern', 'desc': 'Carry it'}
        self.assertEqual(guide_maker.excerpts_for(ach, pieces)[0]['url'], 'https://b')
        self.assertEqual(guide_maker.excerpts_for(ach, pieces, ['hinted words'])[0]['url'], 'https://c')

    def test_html_text_drops_scripts(self):
        self.assertEqual(guide_maker.html_text('<p>Hi</p><script>x()</script><p>there</p>'), 'Hi\nthere')

    def test_unverified_keeps_only_claims_the_item_makes(self):
        item = {'time': '~5 min', 'tips': 'Go.', 'missable': False, 'unverified': ['difficulty', 'missable', 'time'],
                'cites': [{'source': 'u', 'quote': 'a quote that is in the page'}]}
        out = guide_maker.verify_cites(item, {'u': {'text': 'Yes, a quote that is in the page.'}}, [])
        self.assertTrue(out['cites'][0]['verified'])
        self.assertEqual(out['unverified'], ['time'])
        out = guide_maker.verify_cites(dict(item, cites=[]), {}, [])
        self.assertEqual(out['unverified'], ['time', 'tips'])

    # Regression: a local model "verified" items by quoting their own name
    # or DLC ("End of Zoe DLC"), which is on the page but proves nothing.
    def test_a_quote_of_the_store_text_does_not_verify(self):
        page = {'u': {'text': 'King of the Swamp. End of Zoe DLC. Punch the boss without guns: block, then '
                              'counter after its slam. Win a fight in End of Zoe.'}}
        given = ('King of the Swamp', 'Win a fight in End of Zoe.', 'End of Zoe')

        def verified(quote):
            item = {'cites': [{'source': 'u', 'quote': quote}]}
            return guide_maker.verify_cites(item, page, [], given)['cites'][0]['verified']
        self.assertFalse(verified('King of the Swamp'))
        self.assertFalse(verified('End of Zoe DLC'))
        self.assertFalse(verified('Win a fight in End of Zoe.'))
        self.assertTrue(verified('block, then counter after its slam'))

    def test_search_result_pages_are_no_source(self):
        self.assertTrue(guide_maker.search_page('https://www.bing.com/search?q=x'))
        self.assertTrue(guide_maker.search_page('https://lite.duckduckgo.com/lite/?q=x'))
        self.assertTrue(guide_maker.search_page('https://searx.example/search?q=x'))
        self.assertFalse(guide_maker.search_page('https://steamcommunity.com/app/1/guides/'))
        self.assertFalse(guide_maker.search_page('https://www.powerpyx.com/re7-trophy-guide/'))

    def test_player_page_is_a_steam_profile_only(self):
        self.assertTrue(guide_maker.player_page('https://steamcommunity.com/profiles/1/achievements/418370'))
        self.assertTrue(guide_maker.player_page('https://steamcommunity.com/id/someone/stats/418370'))
        self.assertFalse(guide_maker.player_page('https://steamcommunity.com/achievements/418370'))
        self.assertFalse(guide_maker.player_page('https://steamcommunity.com/sharedfiles/filedetails/?id=1'))
        self.assertFalse(guide_maker.player_page('https://example.com/profiles/1'))

    def test_slug(self):
        self.assertEqual(guide_maker.slug('DOOM: The Dark Ages™'), 'doom-the-dark-ages')

    def test_steam_guide_urls(self):
        page = 'href="https://steamcommunity.com/sharedfiles/filedetails/?id=11" ?id=11 sharedfiles/filedetails/?id=22'
        self.assertEqual(guide_maker.steam_guide_urls('5', get=lambda url: page),
                         ['https://steamcommunity.com/sharedfiles/filedetails/?id=11',
                          'https://steamcommunity.com/sharedfiles/filedetails/?id=22'])

    def test_fetch_refuses_plain_http(self):
        self.assertIsNone(guide_maker.fetch_page('http://example.com/'))

    def test_dead_running_job_reads_failed(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(guide_maker.jobs_dir(d))
            guide_maker.write_json(guide_maker.status_path(d, 'steam', '1'),
                                   {'state': 'running', 'store': 'steam', 'app': '1', 'pid': 2 ** 22 + 12345, 'time': 9e9})
            self.assertEqual(guide_maker.status(d, 'steam', '1')['state'], 'failed')
            self.assertFalse(guide_maker.busy(d))

    def test_jobs_are_per_game_and_stop_one_or_all(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(guide_maker.jobs_dir(d))
            me = os.getpid()
            for app, started in (('1', 10), ('2', 20)):
                guide_maker.write_json(guide_maker.status_path(d, 'steam', app),
                                       {'state': 'running', 'store': 'steam', 'app': app, 'pid': me, 'started': started})
            guide_maker.write_json(guide_maker.status_path(d, 'gog', '9'),
                                   {'state': 'done', 'store': 'gog', 'app': '9', 'time': 1, 'started': 1})
            self.assertEqual([j['app'] for j in guide_maker.jobs(d)], ['2', '1'])  # the old done one is pruned
            self.assertFalse(os.path.exists(guide_maker.status_path(d, 'gog', '9')))
            self.assertTrue(guide_maker.busy(d, 'steam', '1'))
            self.assertFalse(guide_maker.busy(d, 'steam', '3'))
            self.assertEqual(guide_maker.status(d)['app'], '2')
            guide_maker.request_stop(d, 'steam', '1')
            self.assertEqual((guide_maker.stop_requested(d, 'steam', '1'), guide_maker.stop_requested(d, 'steam', '2')),
                             (True, False))
            self.assertEqual(guide_maker.request_stop(d), 2)
            self.assertTrue(guide_maker.stop_requested(d, 'steam', '2'))


class Agents(unittest.TestCase):
    def test_claude_lock_flags(self):
        argv, _, _ = guide_agents.Claude().command('/x', False, 'sonnet', 'high')
        self.assertEqual(argv[argv.index('--tools') + 1:], [''])
        self.assertIn('--strict-mcp-config', argv)
        self.assertNotIn('bypassPermissions', argv)
        argv, _, _ = guide_agents.Claude().command('/x', True, '', '')
        self.assertIn('WebFetch', argv)
        self.assertNotIn('Bash', argv)

    def test_opencode_runs_its_own_server_with_the_lock(self):
        argv, _, env = guide_agents.OpenCode().command('/x', False, 'local/qwen', '')
        self.assertIn('--standalone', argv)
        lock = json.loads(env['OPENCODE_CONFIG_CONTENT'])
        self.assertEqual((lock['permission']['bash'], lock['permission']['edit']), ('deny', 'deny'))
        self.assertFalse(lock['tools']['bash'])
        self.assertEqual(lock['permission']['webfetch'], 'deny')
        self.assertIn('--standalone', guide_agents.OpenCode.models_command)

    # Regression: only text parts were read, so a local model's research
    # (webfetch results, tokens) never reached sources.json or the usage.
    def test_opencode_answer_reads_fetched_pages_links_and_usage(self):
        events = [
            {'type': 'tool_use', 'part': {'type': 'tool', 'tool': 'websearch', 'state': {
                'status': 'error', 'input': {'query': 'q'}, 'error': 'Unable to search'}}},
            {'type': 'tool_use', 'part': {'type': 'tool', 'tool': 'websearch', 'state': {
                'status': 'completed', 'input': {'query': 'q'},
                'output': 'Guide https://example.com/guide and https://example.org/b)'}}},
            {'type': 'tool_use', 'part': {'type': 'tool', 'tool': 'webfetch', 'state': {
                'status': 'completed', 'input': {'url': 'https://example.com/guide'}, 'output': '# Page text'}}},
            {'type': 'step_finish', 'part': {'type': 'step-finish', 'cost': 0,
                                            'tokens': {'input': 10, 'output': 2, 'reasoning': 1,
                                                       'cache': {'read': 5, 'write': 0}}}},
            {'type': 'text', 'part': {'type': 'text', 'text': '<answer/>'}},
            {'type': 'step_finish', 'part': {'type': 'step-finish', 'tokens': {'input': 4, 'output': 3}}},
        ]
        found = guide_agents.OpenCode().answer('\n'.join(json.dumps(e) for e in events), '/x')
        self.assertEqual(found['text'], '<answer/>')
        self.assertEqual(found['pages'], [{'url': 'https://example.com/guide', 'text': '# Page text'}])
        self.assertEqual(found['links'], ['https://example.com/guide', 'https://example.org/b'])
        self.assertEqual((found['usage']['input'], found['usage']['output']), (19, 6))

    def test_no_adapter_ever_auto_approves(self):
        for a in guide_agents.ADAPTERS:
            try:
                argv, _, env = a.command('/x', True, 'm', 'e')
            except NotImplementedError:
                continue
            text = ' '.join(argv) + json.dumps(env)
            for flag in ('bypass', 'yolo', '--auto', 'danger', 'approve-for-me'):
                self.assertNotIn(flag, text, a.id)

    def test_claude_stream_answer(self):
        lines = [{'type': 'assistant', 'message': {'content': [
                    {'type': 'tool_use', 'id': 't1', 'name': 'WebFetch', 'input': {'url': 'https://a'}},
                    {'type': 'tool_use', 'id': 't2', 'name': 'WebSearch', 'input': {'query': 'q'}}]}},
                 {'type': 'user', 'message': {'content': [
                    {'type': 'tool_result', 'tool_use_id': 't1', 'content': [{'type': 'text', 'text': 'page'}]},
                    {'type': 'tool_result', 'tool_use_id': 't2', 'content': 'see https://b/c and more'}]}},
                 {'type': 'result', 'result': 'done', 'total_cost_usd': 0.5,
                  'usage': {'input_tokens': 3, 'cache_read_input_tokens': 4, 'output_tokens': 2}}]
        out = guide_agents.Claude().answer('\n'.join(json.dumps(l) for l in lines) + '\nnoise', '/x')
        self.assertEqual(out['text'], 'done')
        self.assertEqual(out['pages'], [{'url': 'https://a', 'text': 'page'}])
        self.assertEqual(out['links'], ['https://b/c'])
        self.assertEqual(out['usage'], {'input': 7, 'output': 2, 'cost_usd': 0.5})

    def test_jailed_wraps_the_command_and_passes_only_named_env(self):
        with mock.patch.dict(os.environ, {'ANTHROPIC_BASE_URL': 'http://x', 'SECRET_THING': 'y'}), \
                mock.patch.object(guide_agents.shutil, 'which', return_value=None):
            argv = guide_agents.jailed(['claude', '-p'], {'OPENCODE_CONFIG_CONTENT': '{}'})
        self.assertEqual(argv[:2], ['ai-jail', '--exec'])
        self.assertEqual(argv[argv.index('--') + 1:], ['claude', '-p'])
        envs = [argv[i + 1] for i, a in enumerate(argv) if a == '--env']
        self.assertIn('ANTHROPIC_BASE_URL', envs)
        self.assertIn('OPENCODE_CONFIG_CONTENT', envs)
        self.assertNotIn('SECRET_THING', ' '.join(argv))
        self.assertNotIn('--docker', argv)

    # Regression: Codex's search runs server-side and gave OmaTrophy no
    # page, so GPT-6.1 Sol and GPT-6 Luna verified 0 of 11 on RE7.
    def test_codex_answer_keeps_its_search_and_opened_links(self):
        lines = [{'type': 'item.completed', 'item': {'type': 'web_search', 'action': {'type': 'search'},
                                                     'results': [{'url': 'https://www.powerpyx.com/a'},
                                                                 {'url': 'http://plain/x'}, {'title': 'no url'}]}},
                 {'type': 'item.completed', 'item': {'type': 'web_search',
                                                     'action': {'type': 'open_page', 'url': 'https://b/page'},
                                                     'results': [{'url': 'https://www.powerpyx.com/a'}]}},
                 {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'done'}}]
        with tempfile.TemporaryDirectory() as d:
            out = guide_agents.Codex().answer('\n'.join(json.dumps(l) for l in lines), d)
        self.assertEqual(out['text'], 'done')
        self.assertEqual(out['links'], ['https://www.powerpyx.com/a', 'https://b/page'])

    def test_codex_models_cache(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, 'models_cache.json', json.dumps({'models': [
                {'slug': 'gpt-x', 'display_name': 'GPT X', 'visibility': 'list',
                 'supported_reasoning_levels': [{'effort': 'low'}, {'effort': 'high'}]},
                {'slug': 'hidden', 'visibility': 'hide'}]}))
            with mock.patch.dict(os.environ, {'CODEX_HOME': d}):
                self.assertEqual(guide_agents.Codex().models(),
                                 [{'id': 'gpt-x', 'name': 'GPT X', 'efforts': ['low', 'high']}])

    def test_resolve_errors_say_what_to_do(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'HOME': d}):
            with self.assertRaisesRegex(SystemExit, 'no agent picked'):
                guide_agents.resolve('')
            with self.assertRaisesRegex(SystemExit, 'no one-shot'):
                guide_agents.resolve('openclaw')
            with self.assertRaisesRegex(SystemExit, 'not an agent'):
                guide_agents.resolve('vim')
            with mock.patch.object(guide_agents.Codex, 'installed', lambda self: True):
                with self.assertRaisesRegex(SystemExit, "can't run locked down yet; check it in Settings > Guides "
                                                        r"\(or: omatrophy.py guide check codex\), or pick claude"):
                    guide_agents.resolve('codex')

    def test_listing_marks_default_and_picks(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'HOME': d}):
            write(d, '.config/omarchy/defaults/agent', 'codex\n')
            with mock.patch.object(guide_agents.Adapter, 'installed', lambda self: False):
                rows = guide_agents.listing({'guide-models': {'claude': {'model': 'opus', 'effort': 'high'}}})
        by = {r['agent']: r for r in rows}
        self.assertNotIn('openclaw', by)
        self.assertTrue(by['codex']['default'])
        self.assertEqual((by['claude']['model'], by['claude']['effort']), ('opus', 'high'))
        self.assertTrue(by['claude']['supported'])
        self.assertFalse(by['gemini']['supported'])

    def test_run_stops_and_times_out(self):
        class Sleeper(guide_agents.Adapter):
            id = 'sleeper'
            def command(self, folder, web, model, effort):
                return [sys.executable, '-c', 'import time; time.sleep(30)'], None, {}
        out = guide_agents.run(Sleeper(), 'hi', stopped=lambda: True)
        self.assertTrue(out['stopped'])
        out = guide_agents.run(Sleeper(), 'hi', timeout=0)
        self.assertFalse(out['ok'])
        self.assertIn('took over', out['error'])


if __name__ == '__main__':
    unittest.main()


class Bench(unittest.TestCase):
    def test_parse_entry(self):
        import guide_bench
        self.assertEqual(guide_bench.parse_entry('claude:sonnet:high'),
                         {'agent': 'claude', 'model': 'sonnet', 'effort': 'high', 'endpoint': ''})
        self.assertEqual(guide_bench.parse_entry('opencode:local/qwen3:8b')['model'], 'local/qwen3:8b')
        self.assertEqual(guide_bench.parse_entry('claude:qwen@http://127.0.0.1:8080')['endpoint'], 'http://127.0.0.1:8080')
        self.assertEqual(guide_bench.parse_entry('claude')['model'], '')
        with self.assertRaises(SystemExit):
            guide_bench.parse_entry('Claude Sonnet')

    def test_metrics_and_score(self):
        import guide_bench
        plan = {'order': ['A', 'B'], 'sections': {'overview': 'x', 'route': 'y'}, 'items': {
            'A': {'api': 'a', 'name': 'A', 'phase': 'quick', 'difficulty': 1, 'time': '5 min', 'tips': 't',
                  'cites': [{'verified': True}]},
            'B': {'api': 'b', 'name': 'B', 'phase': 'grind', 'cites': [{'verified': False}], 'unverified': ['tips']}}}
        m = guide_bench.metrics(plan, {'a', 'b', 'c', 'd'})
        self.assertEqual((m['coverage'], m['verified'], m['complete'], m['route'], m['sections']),
                         (0.5, 0.5, 0.625, 0.5, 0.5))
        self.assertEqual(m['walkthrough'], 0.0)
        self.assertEqual(guide_bench.score(m), round(35 * 0.5 + 25 * 0.5 + 15 * 0.625 + 10 * 0.5 + 5 * 0.5, 1))
        self.assertEqual(sum(guide_bench.WEIGHTS.values()), 100)

    def test_walkthrough_measure_places_open_ones_and_counts_grounded_steps(self):
        import guide_bench
        items = {'A': {'api': 'a', 'name': 'A'}, 'B': {'api': 'b', 'name': 'B'}, 'Done': {'api': 'z', 'name': 'Done'}}
        plan = {'items': items, 'walkthrough': [
            {'title': 'Prologue', 'achievements': ['Done', 'A'], 'cites': [{'verified': True}]},
            {'title': 'Act 1', 'achievements': ['A'], 'cites': [{'verified': False}]},
            {'title': 'Act 2', 'achievements': [], 'cites': []},
            {'title': 'Epilogue', 'achievements': ['Ghost'], 'cites': [{'verified': True}]}]}
        # A of a, b, c, d placed (the unlocked one and an unknown name don't
        # count, A twice counts once); 2 of 4 steps grounded.
        self.assertEqual(guide_bench.walkthrough_measure(plan, {'a', 'b', 'c', 'd'}), 0.5 * 0.25 + 0.5 * 0.5)
        self.assertEqual(guide_bench.metrics(plan, {'a', 'b', 'c', 'd'})['steps'], 4)

    def test_plan_measure_counts_requires_and_actions_unscored(self):
        import guide_bench
        plan = {'items': {
            'A': {'api': 'a', 'name': 'A', 'requires': ['B']},
            'B': {'api': 'b', 'name': 'B', 'requires': ['C'], 'unverified': ['requires']},
            'C': {'api': 'c', 'name': 'C'},
            'D': {'api': 'z', 'name': 'D', 'requires': ['C']}},
            'walkthrough': [{'title': 'One', 'actions': [{'where': 'Gate', 'what': 'x'}, {'where': ' ', 'what': 'y'}],
                             'marker': 'A'},
                            {'title': 'Two', 'actions': [{'where': 'Hub', 'what': 'z'}, 'junk'], 'marker': ''},
                            {'title': 'Old'}]}
        m = guide_bench.metrics(plan, {'a', 'b', 'c'})
        # D is done, so not counted; B's requires has no verified quote.
        self.assertEqual((m['needs'], m['needs_cited'], m['actions'], m['where']), (2, 1, 3, 0.667))
        self.assertNotIn('needs', guide_bench.WEIGHTS)
        self.assertNotIn('where', guide_bench.WEIGHTS)
        self.assertEqual(guide_bench.plan_measure({}, {'a'})['where'], 0.0)
        # One step of three names a marker; not scored either.
        self.assertEqual(m['markers'], 0.333)
        self.assertNotIn('markers', guide_bench.WEIGHTS)
        self.assertEqual(guide_bench.plan_measure({}, {'a'})['markers'], 0.0)
        self.assertIn('marker', guide_bench.table([{'entry': 'e', 'score': 1, 'state': 'done', 'metrics': m}]))

    def test_walkthrough_measure_is_zero_without_steps_or_open_ones(self):
        import guide_bench
        plan = {'items': {'A': {'api': 'a', 'name': 'A'}},
                'walkthrough': [{'title': 'One', 'achievements': ['A'], 'cites': [{'verified': True}]}]}
        self.assertEqual(guide_bench.walkthrough_measure(plan, {'a'}), 1.0)
        self.assertEqual(guide_bench.walkthrough_measure(plan, set()), 0.0)
        self.assertEqual(guide_bench.walkthrough_measure({'items': plan['items']}, {'a'}), 0.0)

    def test_ranked_ties_go_to_the_cheaper_then_faster(self):
        import guide_bench
        rows = [{'entry': 'a', 'score': 80, 'cost_usd': None, 'seconds': 10},
                {'entry': 'b', 'score': 80, 'cost_usd': 0.5, 'seconds': 90},
                {'entry': 'c', 'score': 80, 'cost_usd': 0.5, 'seconds': 30},
                {'entry': 'd', 'score': 90, 'cost_usd': 3.0, 'seconds': 300}]
        self.assertEqual([r['entry'] for r in guide_bench.ranked(rows)], ['d', 'c', 'b', 'a'])

    def test_endpoint_is_claude_only(self):
        self.assertEqual(guide_agents.endpoint_env(guide_agents.Claude(), 'http://x'), {'ANTHROPIC_BASE_URL': 'http://x'})
        self.assertEqual(guide_agents.endpoint_env(guide_agents.Codex(), ''), {})
        with self.assertRaisesRegex(SystemExit, 'claude only'):
            guide_agents.endpoint_env(guide_agents.Codex(), 'http://x')

    def test_bench_runs_each_entry_apart_and_keeps_the_winner(self):
        import guide_bench
        with tempfile.TemporaryDirectory() as d:
            good, bad = os.path.join(d, 'good'), os.path.join(d, 'bad')
            for folder, items in ((good, ITEMS), (bad, 'no tags')):
                write(folder, 'fake.py', FAKE)
                write(folder, 'items', items)
                write(folder, 'route', ROUTE)
            guides_dir = os.path.join(d, 'guides')
            write(guides_dir, 'starfall-odyssey-1.md', 'mine\n')
            # The owner's saved page: every entry must read it.
            write(guides_dir, 'sources/starfall-odyssey-1/notes.txt', 'You must carry the lantern before chapter four ends.')
            said = []
            run_dir, results = guide_bench.bench(
                'steam', '1', 'Starfall Odyssey', [dict(a) for a in ACHS],
                [guide_bench.parse_entry('fakebad:m1'), guide_bench.parse_entry('fakegood:m2:high')],
                web=False, folder=guides_dir, say=said.append,
                adapters={'fakegood': FakeAgent(good), 'fakebad': FakeAgent(bad)},
                list_guides=lambda app: [], fetch=lambda url: None)
            self.assertEqual([(r['entry'], r['state']) for r in results],
                             [('fakegood:m2:high', 'done'), ('fakebad:m1', 'failed')])
            self.assertGreater(results[0]['score'], 50)
            self.assertEqual(results[0]['metrics']['cited'], 1)
            self.assertEqual(read(os.path.join(guides_dir, 'starfall-odyssey-1.md')), 'mine\n')
            saved = json.loads(read(os.path.join(run_dir, 'results.json')))
            self.assertEqual(saved['results'][0]['entry'], 'fakegood:m2:high')
            self.assertIn('fakegood:m2:high', guide_bench.table(results))
            guide_bench.keep(results[0], guides_dir)
            self.assertIn('Short and gentle.', read(os.path.join(guides_dir, 'starfall-odyssey-1.md')))
            self.assertEqual(read(os.path.join(guides_dir, 'starfall-odyssey-1.md.prev')), 'mine\n')


class JobsCommand(unittest.TestCase):
    # Regression: `guide jobs` printed the usage, as the dispatcher didn't
    # route it, and the tracker and panel saw no job at all.
    def test_guide_jobs_runs_through_main(self):
        import io, omatrophy
        from contextlib import redirect_stdout
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'HOME': d, 'XDG_DATA_HOME': d}), \
                redirect_stdout(out):
            omatrophy.main(['x', 'guide', 'jobs'])
        self.assertEqual(json.loads(out.getvalue()), {'jobs': [], 'max': guide_maker.MAX_JOBS})


class ModelPick(unittest.TestCase):
    def test_guide_model_saves_effort_and_endpoint_and_clears(self):
        import io, omatrophy
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'HOME': d}), redirect_stdout(io.StringIO()):
            omatrophy.main(['x', 'guide', 'model', 'claude', 'qwen', 'high', '@http://127.0.0.1:8080'])
            cfg = json.loads(read(os.path.join(d, '.config/omatrophy/config.json')))
            self.assertEqual(cfg['guide-models']['claude'],
                             {'model': 'qwen', 'effort': 'high', 'endpoint': 'http://127.0.0.1:8080'})
            omatrophy.main(['x', 'guide', 'model', 'claude', 'default'])
            cfg = json.loads(read(os.path.join(d, '.config/omatrophy/config.json')))
            self.assertNotIn('claude', cfg['guide-models'])
            with self.assertRaises(SystemExit):
                omatrophy.main(['x', 'guide', 'model', 'codex', 'm', '@http://x'])


class RouteTable(unittest.TestCase):
    # A local model left `dlc` empty and the route, seeing only names,
    # folded "Get the true ending in Daughters" into the main story.
    def test_rows_carry_the_description_but_a_locked_hidden_one_keeps_its_secret(self):
        item = {'phase': 'story', 'difficulty': 2, 'dlc': ''}
        self.assertTrue(guide_maker.table_line('One', item, False, 'Get the true ending in Daughters.')
                        .endswith('— Get the true ending in Daughters.'))
        self.assertNotIn('—', guide_maker.table_line('One', item, False))

    def test_the_route_prompt_gets_descriptions(self):
        seen = {}
        job = guide_maker.Job('steam', '1', 'Game', [dict(a) for a in ACHS], guide_agents.BY_ID['claude'])
        job.ask = lambda stage, text, check, merge=None, **kw: (seen.setdefault('text', text), None)[1:] + ([],)
        items = {a['name']: {'phase': 'story', 'difficulty': 1} for a in ACHS}
        job.route(items)
        self.assertIn('Carry the lantern to the end', seen['text'])
        self.assertNotIn('Quiet Hours: story; difficulty 1; time ? —', seen['text'])


class JobStatus(unittest.TestCase):
    # The panel's strip built the store's old header URL itself, a 404 for
    # newer apps; the job now passes on the poster OmaTrophy found.
    def test_status_carries_the_header(self):
        with tempfile.TemporaryDirectory() as d:
            job = guide_maker.Job('steam', '1', 'Game', [dict(a) for a in ACHS], guide_agents.BY_ID['claude'],
                                  folder=d, header='file:///art/1_header.jpg')
            job.report('gather')
            status = json.loads(read(guide_maker.status_path(d, 'steam', '1')))
        self.assertEqual(status['header'], 'file:///art/1_header.jpg')


class CompleteGame(unittest.TestCase):
    # A make on a platinum game sent the agent nothing to classify and
    # wrote a page of filler on the owner's tokens.
    def test_a_game_at_100_percent_is_refused(self):
        import omatrophy
        store = mock.Mock(id='steam')
        store.game_name.return_value = 'Done Game'
        done = [dict(a, unlocked=True) for a in ACHS]
        with mock.patch.object(omatrophy, 'guide_target', return_value=(store, done, 60)), \
                mock.patch.object(guide_agents, 'resolve', return_value=guide_agents.BY_ID['claude']), \
                mock.patch.object(guide_maker, 'busy', return_value=False), \
                mock.patch.object(guide_maker, 'make', side_effect=AssertionError('made')):
            with self.assertRaises(SystemExit) as e:
                omatrophy.guide_make('steam', '1', [], {})
        self.assertIn('100%', str(e.exception))


class JailOptions(unittest.TestCase):
    # A local model inside ai-jail may need its key file (OpenCode at a
    # local server worked without the jail, failed in it).
    def test_jailed_puts_the_options_before_the_agent_with_home_expanded(self):
        with mock.patch.dict(os.environ, {'HOME': '/h'}), \
                mock.patch.object(guide_agents.shutil, 'which', return_value=None):
            argv = guide_agents.jailed(['opencode', 'run'], {}, ['--env', 'K', '--map', '~/k.key'])
        cut = argv.index('--')
        self.assertEqual(argv[cut - 4:cut], ['--env', 'K', '--map', '/h/k.key'])
        self.assertEqual(argv[cut + 1:], ['opencode', 'run'])

    # Regression: ai-jail 3.1 refused claude and codex ("--network and
    # --allow-host ... are mutually exclusive") and left agents logged out.
    def test_jailed_on_3x_starts_clean_with_agent_state_and_the_harness(self):
        with mock.patch.object(guide_agents.shutil, 'which', return_value=None):
            argv = guide_agents.jailed(['claude', '-p'], {}, harness='claude', version='3.1.0')
            cut = argv.index('--')
            for flag in ('--clean', '--agent-state', '--network'):
                self.assertIn(flag, argv[:cut])
            self.assertEqual(argv[argv.index('--harness') + 1], 'claude')
            self.assertEqual(argv[cut + 1:], ['claude', '-p'])
            unknown = guide_agents.jailed(['hermes'], {}, harness='hermes', version='3.1.0')
            self.assertNotIn('--harness', unknown)

    def test_jailed_on_2x_keeps_the_old_argv(self):
        with mock.patch.object(guide_agents.shutil, 'which', return_value=None):
            for version in ('2.15.0', ''):
                argv = guide_agents.jailed(['claude', '-p'], {}, harness='claude', version=version)
                for flag in ('--clean', '--agent-state', '--harness'):
                    self.assertNotIn(flag, argv)

    def test_suggested_is_the_bench_pick_when_the_agent_lists_it(self):
        self.assertEqual(guide_agents.suggested('claude', [{'id': 'opus'}, {'id': 'haiku'}])['model'], 'opus')
        self.assertEqual(guide_agents.suggested('claude', [])['model'], 'opus')
        self.assertEqual(guide_agents.suggested('claude', [{'id': 'haiku'}]), {})
        self.assertEqual(guide_agents.suggested('opencode', [{'id': 'x'}]), {})

    def test_jail_major(self):
        self.assertEqual(guide_agents.jail_major('3.1.0'), 3)
        self.assertEqual(guide_agents.jail_major('2.15.0'), 2)
        self.assertEqual(guide_agents.jail_major(''), 0)

    # Regression: mise fails with "Read-only file system" in the jail, so
    # every agent installed through mise failed there; its tool runs fine.
    def test_jailed_runs_the_tool_behind_a_mise_shim(self):
        runner = mock.Mock(return_value=mock.Mock(stdout='/mise/installs/claude/latest/claude\n'))
        with mock.patch.object(guide_agents.shutil, 'which', return_value='/shims/claude'), \
                mock.patch.object(guide_agents.os.path, 'realpath', side_effect=lambda p: '/usr/bin/mise' if p == '/shims/claude' else p):
            self.assertEqual(guide_agents.jail_binary('claude', runner), '/mise/installs/claude/latest/claude')
        with mock.patch.object(guide_agents.shutil, 'which', return_value='/usr/bin/claude'):
            self.assertEqual(guide_agents.jail_binary('claude', runner), 'claude')

    def test_jail_options_checks_each_word(self):
        self.assertEqual(guide_agents.jail_options(['--env=K', '--allow-loopback-listen', '--map', '~/a']),
                         ['--env', 'K', '--allow-loopback-listen', '--map', '~/a'])
        for bad in (['--no-network'], ['--forward-port', '8080'], ['--allow-host', 'x.org'], ['--map'], ['--map', '--rw-map', 'a'], ['8080'],
                    ['--', 'sh']):
            with self.assertRaises(SystemExit, msg=bad):
                guide_agents.jail_options(bad)

    def test_a_bad_hand_edit_reads_as_no_options(self):
        # ai-jail refuses --forward-port next to our --network: a saved one
        # is dropped, the rest kept.
        cfg = {'guide-jail-options': {'opencode': ['--forward-port', '8080', '--map', '~/k', '--allow-host=x'],
                                      'claude': ['--no-landlock'],
                                      'codex': '--map x'}}
        self.assertEqual(guide_agents.saved_jail_options('opencode', cfg), ['--map', '~/k'])
        self.assertEqual(guide_agents.saved_jail_options('claude', cfg), [])
        self.assertEqual(guide_agents.saved_jail_options('codex', cfg), [])
        self.assertEqual(guide_agents.saved_jail_options('opencode', {}), [])

    def test_cli_saves_one_panel_string_and_clears(self):
        import io, omatrophy
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'HOME': d}), redirect_stdout(io.StringIO()):
            path = os.path.join(d, '.config/omatrophy/config.json')
            omatrophy.main(['x', 'guide', 'jail-options', 'opencode', '--env K --map "~/my keys/a.key"'])
            self.assertEqual(json.loads(read(path))['guide-jail-options']['opencode'],
                             ['--env', 'K', '--map', '~/my keys/a.key'])
            self.assertEqual(guide_agents.saved_jail_options('opencode'),
                             ['--env', 'K', '--map', '~/my keys/a.key'])
            omatrophy.main(['x', 'guide', 'jail-options', 'opencode', ''])
            self.assertNotIn('opencode', json.loads(read(path))['guide-jail-options'])
            with self.assertRaises(SystemExit):
                omatrophy.main(['x', 'guide', 'jail-options', 'opencode', '--rw-map', '/', '--no-network'])


class SandboxWithoutJail(unittest.TestCase):
    def test_the_saved_setting_without_ai_jail_counts_as_off_and_says_so(self):
        import omatrophy
        said = []
        with mock.patch.object(guide_agents, 'jail_installed', return_value=False):
            self.assertFalse(omatrophy.use_jail(None, {'guide-jail': True}, say=said.append))
            self.assertIn('akitaonrails/ai-jail', said[0])
            self.assertFalse(omatrophy.use_jail(False, {'guide-jail': True}, say=said.append))
            with self.assertRaises(SystemExit):
                omatrophy.use_jail(True, {}, say=said.append)
        with mock.patch.object(guide_agents, 'jail_installed', return_value=True):
            self.assertTrue(omatrophy.use_jail(None, {'guide-jail': True}, say=said.append))
        self.assertEqual(len(said), 1)

    # The bench followed the saved Sandbox with no way out, so ai-jail 3.1
    # (which refused every agent) blocked benching unless the setting changed.
    def test_bench_no_jail_overrides_the_saved_setting(self):
        import omatrophy, guide_bench
        store = mock.Mock(id='steam')
        seen = {}

        def fake_bench(*a, **kw):
            seen.update(kw)
            return '/x', [{'state': 'done', 'agent': 'claude', 'model': 'haiku', 'effort': '', 'endpoint': ''}]
        with mock.patch.object(guide_agents, 'jail_installed', return_value=True), \
                mock.patch.object(guide_agents, 'resolve'), \
                mock.patch.object(omatrophy, 'guide_target', return_value=(store, [], 60)), \
                mock.patch.object(guide_bench, 'bench', side_effect=fake_bench), \
                mock.patch.object(guide_bench, 'table', return_value=''), mock.patch('builtins.print'):
            omatrophy.guide_bench('steam', '1', ['claude:haiku', '--no-jail'], {'guide-jail': True})
            self.assertFalse(seen['jail'])
            omatrophy.guide_bench('steam', '1', ['claude:haiku'], {'guide-jail': True})
            self.assertTrue(seen['jail'])

    def test_jail_version_reads_the_number_or_nothing(self):
        answer = lambda out: (lambda argv, **kw: mock.Mock(stdout=out))
        with mock.patch.object(guide_agents, 'jail_installed', return_value=True):
            self.assertEqual(guide_agents.jail_version(answer('ai-jail 2.15.0\n')), '2.15.0')
            self.assertEqual(guide_agents.jail_version(answer('')), '')
            def slow(argv, **kw):
                raise guide_agents.subprocess.TimeoutExpired(argv, 4)
            self.assertEqual(guide_agents.jail_version(slow), '')
        with mock.patch.object(guide_agents, 'jail_installed', return_value=False):
            self.assertEqual(guide_agents.jail_version(answer('ai-jail 2.15.0')), '')


class LockCheck(unittest.TestCase):
    def fake_run(self, writes):
        def runner(adapter, prompt, web=False, model='', timeout=0, jail=False):
            path = re.search(r'Create the file (\S+) ', prompt).group(1)
            if writes:
                write(os.path.dirname(path), os.path.basename(path), 'hello')
            return {'ok': True, 'text': 'I have no tools.', 'error': ''}
        return runner

    def test_a_pass_is_recorded_for_this_binary_and_an_update_relocks(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'HOME': d}):
            codex = guide_agents.Codex()
            with mock.patch.object(guide_agents, 'fingerprint', lambda a: 'bin:1'):
                self.assertFalse(guide_agents.checked(codex))
                out = guide_agents.check_lock(codex, runner=self.fake_run(False), say=lambda l: None)
                self.assertTrue(out['passed'])
                self.assertEqual(len(out['runs']), 2)
                self.assertTrue(guide_agents.checked(codex))
            with mock.patch.object(guide_agents, 'fingerprint', lambda a: 'bin:2'):
                self.assertFalse(guide_agents.checked(codex))

    # Regression: a mise shim is a link to mise itself, so the stamp missed
    # agent updates and differed between the shell's PATH and a terminal's.
    def test_a_mise_shim_is_stamped_by_the_tool_it_runs(self):
        with tempfile.TemporaryDirectory() as d:
            tool = os.path.join(d, 'installs', 'opencode')
            write(os.path.dirname(tool), 'opencode', 'tool')
            calls = []

            def runner(argv, **kw):
                calls.append(argv)
                return mock.Mock(stdout=tool + '\n')
            self.assertEqual(guide_agents.mise_target('/usr/bin/mise', 'opencode', runner), tool)
            self.assertEqual(calls, [['/usr/bin/mise', 'which', 'opencode']])
            self.assertEqual(guide_agents.mise_target('/usr/bin/opencode', 'opencode', runner), '/usr/bin/opencode')
            self.assertEqual(len(calls), 1)
            failed = mock.Mock(side_effect=subprocess.TimeoutExpired('mise', 4))
            self.assertEqual(guide_agents.mise_target('/usr/bin/mise', 'opencode', failed), '/usr/bin/mise')

    def test_a_write_fails_and_records_nothing_and_a_jail_pass_records_nothing(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {'HOME': d}), \
                mock.patch.object(guide_agents, 'fingerprint', lambda a: 'bin:1'):
            codex = guide_agents.Codex()
            out = guide_agents.check_lock(codex, runner=self.fake_run(True), say=lambda l: None)
            self.assertFalse(out['passed'])
            self.assertEqual(out['runs'][0]['wrote'], ['wrote-0.txt'])
            guide_agents.check_lock(codex, runner=self.fake_run(False), jail=True, say=lambda l: None)
            self.assertFalse(guide_agents.checked(codex))

    def test_headless(self):
        self.assertTrue(guide_agents.headless(guide_agents.Codex()))
        self.assertFalse(guide_agents.headless(guide_agents.BY_ID['gemini']))
