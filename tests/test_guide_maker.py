import json, os, re, subprocess, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import guide_agents, guide_maker, guides

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
stage = 'research' if '<research>' in prompt else 'items' if '<items>' in prompt else 'route'
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


class Job(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.agent_dir = os.path.join(self.tmp.name, 'agent')
        self.guides = os.path.join(self.tmp.name, 'guides')
        write(self.agent_dir, 'fake.py', FAKE)
        write(self.agent_dir, 'items', ITEMS)
        write(self.agent_dir, 'route', ROUTE)
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

    def test_makes_files_and_verifies_quotes(self):
        self.assertEqual(guide_maker.make(self.job())['state'], 'done')
        md = os.path.join(self.guides, 'starfall-odyssey-1.md')
        notes, rows = guides.parse_markdown(read(md))
        self.assertIn('Short and gentle.', notes)
        self.assertEqual(len(rows), 4)
        plan = json.loads(read(md[:-3] + '.plan.json'))
        self.assertEqual(plan['format'], 2)
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
        self.assertEqual(self.calls(), 3)  # items twice, route once

    def test_unparsable_answers_fail_and_write_nothing(self):
        write(self.agent_dir, 'items', 'nothing useful')
        self.assertEqual(guide_maker.make(self.job())['state'], 'failed')
        self.assertFalse(os.path.exists(os.path.join(self.guides, 'starfall-odyssey-1.md')))
        self.assertIn('failed', guide_maker.status(self.guides)['line'])

    def test_stop_before_a_stage_keeps_the_old_guide(self):
        write(self.guides, 'starfall-odyssey-1.md', 'old guide\n')
        job = self.job()
        real = guide_maker.stop_requested
        with mock.patch.object(guide_maker, 'stop_requested', lambda folder=None: job.stage == 'gather' or real(folder)):
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
        self.assertEqual(guide_maker.check_item({'name': 'A', 'difficulty': ' 3 '}, {'A'})[0]['difficulty'], 3)

    def test_check_route(self):
        route, errors = guide_maker.check_route('<route>{"order": ["A", "Z", "A"], "sections": {}}</route>', {'A'})
        self.assertEqual(route['order'], ['A'])
        self.assertEqual(len(errors), 2)  # Z unknown, no overview

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
            guide_maker.write_json(guide_maker.status_path(d), {'state': 'running', 'pid': 2 ** 22 + 12345})
            self.assertEqual(guide_maker.status(d)['state'], 'failed')
            self.assertFalse(guide_maker.busy(d))


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
        self.assertEqual(guide_bench.score(m), 35 * 0.5 + 25 * 0.5 + 20 * 0.625 + 10 * 0.5 + 10 * 0.5)

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
        job.ask = lambda stage, text, check, merge: (seen.setdefault('text', text), None)[1:] + ([],)
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
            status = json.loads(read(guide_maker.status_path(d)))
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
