"""Tests for omatrophy.py and the Steam store: Steam's binary KeyValues, the
stats cache, unlock diffing, the panel's and tracker's JSON, the test inbox and
settings. Everything runs against temporary
folders built here; no Steam install, no network, no real config.

Run from the repo root: python3 -m unittest discover -s tests
"""
import io, json, os, struct, sys, tempfile, time, unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import omatrophy  # noqa: E402
from stores import steam, steam_community  # noqa: E402

APP = '123450'
UID = '42'


def kv(d):
    """Encode a dict as Steam binary KeyValues (the subset omatrophy.py reads)."""
    out = b''
    for k, v in d.items():
        key = k.encode() + b'\0'
        if isinstance(v, dict):
            out += b'\x00' + key + kv(v) + b'\x08'
        elif isinstance(v, str):
            out += b'\x01' + key + v.encode() + b'\0'
        elif isinstance(v, float):
            out += b'\x03' + key + struct.pack('<f', v)
        else:
            out += b'\x02' + key + struct.pack('<i', v)
    return out


def schema(names):
    """A one-stat schema with one achievement bit per name."""
    bits = {str(i): {'name': f'ACH_{i}', 'display': {'name': {'english': n}, 'desc': {'english': f'Do {n}'},
                                                      'icon': f'{i}.jpg'}}
            for i, n in enumerate(names)}
    return {APP: {'stats': {'1': {'bits': bits}}}}


def user(unlocked):
    """User stats with the given {bit: unix time} unlocked."""
    data = sum(1 << b for b in unlocked)
    return {'cache': {'1': {'data': data, 'AchievementTimes': {str(b): t for b, t in unlocked.items()}}}}


class SteamDir:
    """A throwaway <Steam>/appcache/stats folder."""

    def __init__(self, names):
        self.tmp = tempfile.TemporaryDirectory()
        self.stats = os.path.join(self.tmp.name, 'appcache', 'stats')
        os.makedirs(self.stats)
        self.write(f'UserGameStatsSchema_{APP}.bin', kv(schema(names)))

    def write(self, name, body):
        with open(os.path.join(self.stats, name), 'wb') as f:
            f.write(body)

    def unlock(self, unlocked, uid=UID, app=APP):
        self.write(f'UserGameStats_{uid}_{app}.bin', kv(user(unlocked)))

    def close(self):
        self.tmp.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class Progress(unittest.TestCase):
    SPEC = {'value': {'operation': 'statvalue', 'operand1': 'relics'}, 'min_val': '0', 'max_val': '15'}

    def test_counts_the_named_stat(self):
        self.assertEqual(steam.progress(self.SPEC, {'relics': 12.0}), {'value': 12.0, 'max': 15.0})

    def test_clamps_to_the_bounds(self):
        self.assertEqual(steam.progress(self.SPEC, {'relics': 40.0})['value'], 15.0)
        self.assertEqual(steam.progress(self.SPEC, {'relics': -3.0})['value'], 0.0)

    def test_counts_from_min_val(self):
        spec = dict(self.SPEC, min_val=10, max_val=20)
        self.assertEqual(steam.progress(spec, {'relics': 14.0}), {'value': 4.0, 'max': 10.0})

    def test_unknown_stat_or_bad_bounds_mean_no_progress(self):
        self.assertIsNone(steam.progress(self.SPEC, {}))
        self.assertIsNone(steam.progress(dict(self.SPEC, max_val='0'), {'relics': 1.0}))
        self.assertIsNone(steam.progress(dict(self.SPEC, max_val='lots'), {'relics': 1.0}))
        self.assertIsNone(steam.progress(None, {'relics': 1.0}))

    def test_other_operations_are_skipped(self):
        spec = dict(self.SPEC, value={'operation': 'sum', 'operand1': 'relics'})
        self.assertIsNone(steam.progress(spec, {'relics': 1.0}))

    def test_stat_values_fall_back_to_the_default(self):
        schema_stats = {'1': {'bits': {}}, '3': {'type': 'INT', 'name': 'relics', 'default': 0},
                        '4': {'type': 'FLOAT', 'name': 'miles', 'default': '2.5'}}
        self.assertEqual(steam.stat_values(schema_stats, {'3': {'data': 7}}), {'relics': 7.0, 'miles': 2.5})

    def test_locked_counter_achievement_carries_progress(self):
        with SteamDir(['Collector', 'Spark']) as fake:
            sch = schema(['Collector', 'Spark'])
            sch[APP]['stats']['1']['bits']['0']['progress'] = self.SPEC
            sch[APP]['stats']['1']['bits']['1']['progress'] = self.SPEC
            sch[APP]['stats']['3'] = {'type': 'INT', 'name': 'relics', 'default': 0}
            fake.write(f'UserGameStatsSchema_{APP}.bin', kv(sch))
            body = user({1: 1000})
            body['cache']['3'] = {'data': 12}
            fake.write(f'UserGameStats_{UID}_{APP}.bin', kv(body))
            achs = steam.read_achievements(fake.stats, UID, APP)
        self.assertEqual(achs[0]['progress'], {'value': 12.0, 'max': 15.0})
        # Unlocked ones need no counter.
        self.assertNotIn('progress', achs[1])


class Tier(unittest.TestCase):
    def test_rarity_picks_the_metal(self):
        self.assertEqual(omatrophy.tier(None), 'bronze')
        self.assertEqual(omatrophy.tier(64.0), 'bronze')
        self.assertEqual(omatrophy.tier(35.0), 'silver')
        self.assertEqual(omatrophy.tier(10.1), 'silver')
        self.assertEqual(omatrophy.tier(10.0), 'gold')
        self.assertEqual(omatrophy.tier(0.4), 'gold')


class ParseKV(unittest.TestCase):
    def test_round_trips_nested_values(self):
        d = {'a': {'b': 'text', 'n': -7}, 'f': 1.5}
        self.assertEqual(steam.parse_kv(kv(d))[0], d)

    def test_reads_wide_strings_and_uint64(self):
        blob = b'\x05w\0' + 'hé'.encode('utf-16le') + b'\0\0' + b'\x07q\0' + struct.pack('<Q', 2 ** 40)
        self.assertEqual(steam.parse_kv(blob)[0], {'w': 'hé', 'q': 2 ** 40})

    def test_rejects_unknown_types(self):
        with self.assertRaises(ValueError):
            steam.parse_kv(b'\x09k\0')


class Cache(unittest.TestCase):
    def setUp(self):
        self.steam = SteamDir(['First', 'Second', 'Third'])

    def tearDown(self):
        self.steam.close()

    def test_reads_names_and_unlocks(self):
        self.steam.unlock({0: 1000})
        achs = steam.read_achievements(self.steam.stats, UID, APP)
        self.assertEqual([a['name'] for a in achs], ['First', 'Second', 'Third'])
        self.assertEqual([a['unlocked'] for a in achs], [True, False, False])
        self.assertEqual(achs[0]['time'], 1000)

    def test_bit_without_time_counts_as_unlocked(self):
        self.steam.write(f'UserGameStats_{UID}_{APP}.bin', kv({'cache': {'1': {'data': 0b10}}}))
        achs = steam.read_achievements(self.steam.stats, UID, APP)
        self.assertEqual([a['unlocked'] for a in achs], [False, True, False])

    def test_missing_user_file_reads_as_no_achievements(self):
        self.assertEqual(steam.read_achievements(self.steam.stats, UID, APP), [])

    def test_account_with_most_games_wins(self):
        self.steam.unlock({}, uid='7')
        self.steam.unlock({}, uid='9', app='1')
        self.steam.unlock({}, uid='9', app='2')
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('STEAM_ACCOUNT', None)
            self.assertEqual(steam.account_id(self.steam.stats), '9')
        with mock.patch.dict(os.environ, {'STEAM_ACCOUNT': '7'}):
            self.assertEqual(steam.account_id(self.steam.stats), '7')


class CheckApp(unittest.TestCase):
    """The watcher's diff: what becomes a toast and when the platinum fires."""

    def setUp(self):
        self.steam = SteamDir(['First', 'Second'])
        env = mock.patch.dict(os.environ, {'STEAM_DIR': os.path.dirname(os.path.dirname(self.steam.stats)),
                                           'STEAM_ACCOUNT': UID})
        env.start()
        self.addCleanup(env.stop)
        self.store = steam.Steam()
        offline = [mock.patch.object(steam.Steam, 'percent', return_value=22.7),
                   mock.patch.object(steam.Steam, 'game_name', return_value='Sample Game'),
                   mock.patch.object(omatrophy, 'cached', side_effect=lambda url, name: url),
                   mock.patch.object(steam, 'cached', side_effect=lambda url, name: url)]
        for p in offline:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.steam.close()

    def events(self, seen):
        out = io.StringIO()
        with redirect_stdout(out):
            omatrophy.check_game(self.store, APP, seen)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    def test_new_unlock_becomes_one_event(self):
        self.steam.unlock({})
        seen = {('steam', APP): set()}
        self.steam.unlock({0: int(time.time())})
        [ev] = self.events(seen)
        self.assertEqual((ev['type'], ev['store'], ev['name'], ev['tier']), ('unlock', 'steam', 'First', 'silver'))
        self.assertTrue(ev['icon'].endswith(f'/{APP}/0.jpg'))
        self.assertEqual((ev['unlocked'], ev['total']), (1, 2))
        self.assertEqual(self.events(seen), [])

    def test_last_unlock_also_fires_platinum(self):
        now = int(time.time())
        self.steam.unlock({0: now - 60, 1: now})
        evs = self.events({('steam', APP): {'ACH_0'}})
        self.assertEqual([e['type'] for e in evs], ['unlock', 'platinum'])
        self.assertEqual(evs[1]['first'], now - 60)

    def test_old_unlocks_from_a_cache_sync_stay_quiet(self):
        old = int(time.time()) - omatrophy.FRESH_SECONDS - 60
        self.steam.unlock({0: old, 1: old})
        self.assertEqual(self.events({}), [])


class Cabinet(unittest.TestCase):
    ROWS = [{'app': 'done', 'unlocked': 10, 'total': 10}, {'app': 'untouched', 'unlocked': 0, 'total': 5},
            {'app': 'half', 'unlocked': 5, 'total': 10}, {'app': 'close', 'unlocked': 44, 'total': 46},
            {'app': 'small', 'unlocked': 9, 'total': 10}, {'app': 'big', 'unlocked': 90, 'total': 100}]

    def test_nearest_skips_finished_and_untouched_games(self):
        self.assertEqual([r['app'] for r in omatrophy.nearest_platinum(self.ROWS, 3)], ['close', 'small', 'big'])

    def test_nearest_ties_go_to_fewer_left(self):
        self.assertEqual(omatrophy.nearest_platinum(self.ROWS, 2)[1]['app'], 'small')

    def test_totals_count_trophies_and_platinums(self):
        self.assertEqual(omatrophy.totals(self.ROWS), {'games': 6, 'trophies': 158, 'platinums': 1})


LOCALCONFIG = """"UserLocalConfigStore"
{
	"Software"
	{
		"Valve"
		{
			"Steam"
			{
				"apps"
				{
					"10"
					{
						"LastPlayed"		"1700000000"
					}
					"20"
					{
						"LastPlayed"		"1800000000"
						"Playtime"		"5"
					}
					"30"
					{
						"LastPlayed"		"0"
					}
				}
			}
		}
	}
}
"""


class Played(unittest.TestCase):
    def test_text_vdf_nests_and_unescapes_nothing(self):
        self.assertEqual(steam.parse_text_vdf('"a" { "b" "1" "c" { "d" "x \\"y\\"" } }'),
                         {'a': {'b': '1', 'c': {'d': 'x \\"y\\"'}}})

    def test_last_played_newest_first_without_never_played(self):
        self.assertEqual(steam.last_played(LOCALCONFIG), [(1800000000, '20'), (1700000000, '10')])

    def test_store_reads_its_accounts_localconfig(self):
        sd = SteamDir(['First'])
        self.addCleanup(sd.close)
        root = os.path.dirname(os.path.dirname(sd.stats))
        os.makedirs(f'{root}/userdata/{UID}/config')
        with open(f'{root}/userdata/{UID}/config/localconfig.vdf', 'w') as f:
            f.write(LOCALCONFIG)
        sd.unlock({})
        with mock.patch.dict(os.environ, {'STEAM_DIR': root, 'STEAM_ACCOUNT': UID}):
            self.assertEqual(steam.Steam().recent()[0], (1800000000, '20'))

    def test_launch_line_names_the_app(self):
        line = b'/Steam/ubuntu12_32/reaper\0SteamLaunch\0AppId=1774580\0--\0/proton\0waitforexitandrun\0'
        self.assertEqual(steam.launched_app(line), '1774580')

    def test_a_shell_mentioning_steamlaunch_is_not_a_game(self):
        self.assertIsNone(steam.launched_app(b'bash\0-c\0pgrep -f "SteamLaunch AppId=12"\0'))

    def test_start_time_survives_odd_process_names(self):
        stat = '42 (we (ird) name) S ' + ' '.join(['0'] * 18) + ' 500 0'
        self.assertEqual(steam.started_at(stat, 1000, 100), 1005)

    def test_running_game_from_a_fake_proc(self):
        with tempfile.TemporaryDirectory() as proc:
            with open(f'{proc}/stat', 'w') as f:
                f.write('cpu 1 2 3\nbtime 1000\n')
            for pid, cmd in (('7', b'bash\0'), ('9', b'reaper\0SteamLaunch\0AppId=55\0')):
                os.makedirs(f'{proc}/{pid}')
                with open(f'{proc}/{pid}/cmdline', 'wb') as f:
                    f.write(cmd)
                with open(f'{proc}/{pid}/stat', 'w') as f:
                    f.write(f'{pid} (x) S ' + ' '.join(['0'] * 18) + f' {os.sysconf("SC_CLK_TCK") * 30} 0')
            self.assertEqual(steam.running_game(proc), {'game': '55', 'since': 1030})


class Rarity(unittest.TestCase):
    def test_cached_a_day_and_kept_when_offline(self):
        body = {'achievementpercentages': {'achievements': [{'name': 'ACH_0', 'percent': '12.5'}]}}
        with tempfile.TemporaryDirectory() as cache, mock.patch.object(steam, 'CACHE', cache):
            with mock.patch.object(steam, 'http_json', return_value=body) as http:
                self.assertEqual(steam.Steam.percents(None, APP), {'ACH_0': 12.5})
                self.assertEqual(steam.Steam.percent(steam.Steam.__new__(steam.Steam), APP, 'ACH_0'), 12.5)
                self.assertEqual(http.call_count, 1)
            with open(f'{cache}/rarity/{APP}.json') as f:
                stale = json.load(f)
            stale['time'] = 0
            with open(f'{cache}/rarity/{APP}.json', 'w') as f:
                json.dump(stale, f)
            with mock.patch.object(steam, 'http_json', side_effect=OSError('offline')):
                self.assertEqual(steam.Steam.percents(None, APP), {'ACH_0': 12.5})


def ach(api, unlocked=False, t=0, **kw):
    return dict({'api': api, 'name': api.title(), 'desc': f'Do {api}', 'icon': f'{api}.jpg',
                 'unlocked': unlocked, 'time': t}, **kw)


class NowTab(unittest.TestCase):
    def test_platinum_time_is_the_last_unlock_of_a_complete_game(self):
        self.assertEqual(omatrophy.platinum_time([ach('a', True, 5), ach('b', True, 9)]), 9)
        self.assertEqual(omatrophy.platinum_time([ach('a', True, 5), ach('b')]), 0)
        self.assertEqual(omatrophy.platinum_time([]), 0)

    def test_latest_unlocks_newest_first_since_a_time(self):
        achs = [ach('a', True, 5), ach('b', True, 9), ach('c'), ach('d', True, 7), ach('e', True, 0)]
        self.assertEqual([a['api'] for a in omatrophy.latest_unlocks(achs, 2)], ['b', 'd'])
        self.assertEqual([a['api'] for a in omatrophy.latest_unlocks(achs, 5, since=7)], ['b', 'd'])

    def test_next_up_is_the_most_common_locked(self):
        achs = [ach('a', True, 5), ach('b'), ach('c'), ach('d')]
        pcts = {'a': 90.0, 'b': 10.0, 'c': 60.0}
        self.assertEqual([a['api'] for a in omatrophy.next_up(achs, pcts, 2)], ['c', 'b'])

    def test_recent_games_skip_the_running_one_and_unknown_games(self):
        played = [(9, ('steam', '1')), (8, ('steam', 'x')), (7, ('steam', '2')), (6, ('steam', '3'))]
        owned = {('steam', '1'), ('steam', '2'), ('steam', '3')}
        self.assertEqual(omatrophy.recent_games(played, owned, ('steam', '1'), 2),
                         [(7, ('steam', '2')), (6, ('steam', '3'))])

    def test_hidden_and_locked_icon_come_from_the_schema(self):
        sd = SteamDir(['First'])
        self.addCleanup(sd.close)
        sch = schema(['First'])
        sch[APP]['stats']['1']['bits']['0']['display'].update(hidden='1', icon_gray='0g.jpg')
        sd.write(f'UserGameStatsSchema_{APP}.bin', kv(sch))
        sd.unlock({})
        [a] = steam.read_achievements(sd.stats, UID, APP)
        self.assertEqual((a['hidden'], a['icon_locked']), (True, '0g.jpg'))

    def test_tracker_detail_carries_rarity_and_tier(self):
        d = omatrophy.detail(ach('a', hidden=True, icon_locked='g.jpg'), {'a': 4.0})
        self.assertEqual((d['percent'], d['tier'], d['hidden'], d['icon_locked']), (4.0, 'gold', True, 'g.jpg'))
        self.assertEqual(omatrophy.detail(ach('b'), {})['tier'], 'bronze')


class FakeLibrary:
    """A whole throwaway Steam install for the panel's and tracker's JSON:
    three games' stats, the account's localconfig, library art, and warm
    name and rarity caches, so nothing reaches the network. Use as a
    context manager; it patches the environment and the store's paths."""

    GAMES = {'10': ('Done Game', 2, {0: 100, 1: 200}),
             '20': ('Half Game', 4, {0: 300, 1: 400}),
             '30': ('Fresh Game', 3, {})}

    def __init__(self, played=None, running=None, hidden=()):
        self.played = played if played is not None else {'20': 1800000000, '10': 1700000000}
        self.running = running
        self.hidden = list(hidden)

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.root = os.path.join(self.tmp.name, 'Steam')
        stats = os.path.join(root, 'appcache', 'stats')
        os.makedirs(stats)
        for app, (name, count, unlocked) in self.GAMES.items():
            bits = {str(i): {'name': f'ACH_{i}', 'display': {'name': {'english': f'{name} {i}'}}}
                    for i in range(count)}
            with open(f'{stats}/UserGameStatsSchema_{app}.bin', 'wb') as f:
                f.write(kv({app: {'stats': {'1': {'bits': bits}}}}))
            with open(f'{stats}/UserGameStats_{UID}_{app}.bin', 'wb') as f:
                f.write(kv(user(unlocked)))
            os.makedirs(f'{root}/appcache/librarycache/{app}')
            open(f'{root}/appcache/librarycache/{app}/library_hero.jpg', 'w').close()
        os.makedirs(f'{root}/userdata/{UID}/config')
        apps = ''.join(f'"{a}" {{ "LastPlayed" "{t}" }}' for a, t in self.played.items())
        with open(f'{root}/userdata/{UID}/config/localconfig.vdf', 'w') as f:
            f.write(f'"UserLocalConfigStore" {{ "Software" {{ "Valve" {{ "Steam" {{ "apps" {{ {apps} }} }} }} }} }}')
        home = os.path.join(self.tmp.name, 'home')
        os.makedirs(f'{home}/.config/omatrophy')
        with open(f'{home}/.config/omatrophy/config.json', 'w') as f:
            json.dump({'hidden': self.hidden}, f)
        cache = os.path.join(self.tmp.name, 'cache')
        for app in self.GAMES:
            os.makedirs(f'{cache}/rarity', exist_ok=True)
            with open(f'{cache}/rarity/{app}.json', 'w') as f:
                json.dump({'time': int(time.time()), 'percents': {'ACH_0': 50.0, 'ACH_1': 5.0, 'ACH_3': 30.0}}, f)
        names = os.path.join(self.tmp.name, 'names.json')
        with open(names, 'w') as f:
            json.dump({a: g[0] for a, g in self.GAMES.items()}, f)
        self.patches = [mock.patch.dict(os.environ, {'STEAM_DIR': root, 'STEAM_ACCOUNT': UID, 'HOME': home}),
                        mock.patch.object(steam, 'NAMES', names), mock.patch.object(steam, 'CACHE', cache),
                        mock.patch.object(steam, 'running_game', return_value=self.running),
                        mock.patch('urllib.request.urlopen', side_effect=AssertionError('network in a test'))]
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()


class PanelJson(unittest.TestCase):
    def test_games_lists_every_game_with_names_art_and_hidden(self):
        with FakeLibrary(hidden=['steam:30']):
            rows = {r['app']: r for r in omatrophy.games()}
        self.assertEqual(set(rows), {'10', '20', '30'})
        self.assertEqual((rows['20']['game'], rows['20']['unlocked'], rows['20']['total']), ('Half Game', 2, 4))
        self.assertEqual(rows['10']['platinum'], 200)
        self.assertEqual(rows['20']['played'], 1800000000)
        self.assertEqual(rows['30']['played'], 0)
        self.assertEqual([a for a, r in rows.items() if r['hidden']], ['30'])
        self.assertTrue(rows['10']['header'].startswith('https://'))

    def test_now_while_playing(self):
        with FakeLibrary(running={'game': '20', 'since': 350}):
            now = omatrophy.now()
        self.assertEqual((now['games'], now['trophies'], now['platinums']), (3, 4, 1))
        playing = now['playing']
        self.assertEqual((playing['app'], playing['since']), ('20', 350))
        self.assertTrue(playing['hero'].startswith('file://'))
        self.assertEqual([a['name'] for a in playing['session']], ['Half Game 1'])
        self.assertEqual([a['name'] for a in playing['next']], ['Half Game 3', 'Half Game 2'])
        self.assertEqual([c['app'] for c in now['recent']], ['10'])
        self.assertEqual([c['app'] for c in now['shelf']], ['10'])
        self.assertEqual(now['shelf'][0]['latest'], [])

    def test_now_idle_lists_recent_games(self):
        with FakeLibrary():
            now = omatrophy.now()
        self.assertIsNone(now['playing'])
        self.assertEqual([c['app'] for c in now['recent']], ['20', '10'])

    def test_game_detail_for_the_tracker(self):
        with FakeLibrary(running={'game': '20', 'since': 0}):
            store = steam.Steam()
            d = omatrophy.game_detail(store, '20')
        self.assertTrue(d['playing'])
        self.assertEqual((d['game'], d['unlocked'], d['total'], d['platinum']), ('Half Game', 2, 4, 0))
        tiers = {a['api']: (a['percent'], a['tier']) for a in d['achievements']}
        self.assertEqual(tiers['ACH_0'], (50.0, 'bronze'))
        self.assertEqual(tiers['ACH_1'], (5.0, 'gold'))
        self.assertEqual(tiers['ACH_2'], (None, 'bronze'))

    def test_game_detail_without_cached_achievements_says_what_to_do(self):
        with FakeLibrary():
            with self.assertRaises(SystemExit) as e:
                omatrophy.game_detail(steam.Steam(), '999')
        self.assertIn('launch it once', str(e.exception))


def community_page(app, unlocked, name='Remote Game', extra=()):
    """A profile achievement page as Steam serves it: the data sits in a
    JSON script whose renderContext.queryData is itself JSON (ADR 11)."""
    schema = {'appid': int(app), 'groups': [{'id': 0, 'achievements': [
        {'internal_key': 256, 'api_name': 'ACH_A', 'name': 'Alpha', 'description': 'Do alpha', 'hidden': False,
         'archived': False, 'icon_achieved': 'https://x/a.jpg', 'icon_unachieved': 'https://x/a_g.jpg'},
        {'internal_key': 257, 'api_name': 'ACH_B', 'name': 'Beta', 'description': 'Secret', 'hidden': True,
         'archived': False, 'icon_achieved': 'https://x/b.jpg', 'icon_unachieved': 'https://x/b_g.jpg'},
        {'internal_key': 258, 'api_name': 'ACH_OLD', 'name': 'Gone', 'archived': True}]}]}
    user = {'appid': int(app), 'achievements': {str(k): {'internal_key': k, 'unlocked': True, 'unlock_time': t}
                                                for k, t in unlocked.items()}}
    queries = [{'queryKey': ['achievements', int(app), 'user_achievements', '1'], 'state': {'data': user}},
               {'queryKey': ['achievements', int(app), 'schema'], 'state': {'data': schema}},
               {'queryKey': ['StoreItem', f'app_{app}', 'default_info'], 'state': {'data': {'name': name}}},
               {'queryKey': ['AOWarningCookie'], 'state': {'data': None}}] + list(extra)
    ssr = json.dumps({'route': '/id/:vanityurl/achievements/:appid',
                      'renderContext': {'queryData': json.dumps({'mutations': [], 'queries': queries})}})
    return f'<html><script type="application/json" id="valve-ssr-data" nonce="n">{ssr}</script></html>'


class CommunityPage(unittest.TestCase):
    def test_reads_schema_unlocks_and_name(self):
        page = steam_community.parse_page(community_page('55', {256: 1700000000}), '55')
        self.assertEqual(page['name'], 'Remote Game')
        a, b = page['achievements']
        self.assertEqual((a['api'], a['name'], a['desc'], a['unlocked'], a['time']),
                         ('ACH_A', 'Alpha', 'Do alpha', True, 1700000000))
        self.assertEqual((a['icon'], a['icon_locked']), ('https://x/a.jpg', 'https://x/a_g.jpg'))
        self.assertEqual((b['unlocked'], b['time'], b['hidden']), (False, 0, True))

    def test_archived_achievements_are_left_out(self):
        page = steam_community.parse_page(community_page('55', {}), '55')
        self.assertNotIn('ACH_OLD', [a['api'] for a in page['achievements']])

    def test_pages_without_achievement_data_read_as_none(self):
        # A game without achievements redirects to the profile page.
        self.assertIsNone(steam_community.parse_page('<html><body>profile</body></html>', '55'))
        self.assertIsNone(steam_community.parse_page(
            '<script id="valve-ssr-data">{"renderContext": {"queryData": "not json"}}</script>', '55'))
        # Another game's data is not this game's.
        self.assertIsNone(steam_community.parse_page(community_page('66', {}), '55'))

    def test_empty_achievement_page_is_an_error_not_none(self):
        self.assertIsNone(steam_community.page_or_none('<html></html>', '55', 'https://steamcommunity.com/id/me'))
        for url in ('https://steamcommunity.com/id/me/achievements/55',
                    'https://steamcommunity.com/profiles/1/stats/55/achievements/'):
            with self.assertRaises(ValueError):
                steam_community.page_or_none('<html></html>', '55', url)
        self.assertIsNone(steam_community.page_or_none('<html></html>', '55', 'https://steamcommunity.com/id/me/achievements/551'))
        self.assertTrue(steam_community.page_or_none(community_page('55', {}), '55', url))

    def test_steamid64_from_the_account_id(self):
        self.assertEqual(steam_community.steamid64('12345678'), 76561197972611406)


class CommunityBackfill(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(steam_community, 'CACHE', tmp.name)
        patch.start()
        self.addCleanup(patch.stop)
        self.asked = []

    def fetch(self, pages):
        def fetch_page(account, app):
            self.asked.append(app)
            if isinstance(pages.get(app), Exception):
                raise pages[app]
            return pages.get(app)
        return fetch_page

    def run_backfill(self, played, local=(), pages=None):
        page = steam_community.parse_page(community_page('1', {256: 5}), '1')
        pages = pages if pages is not None else {'1': page, '2': None}
        return steam_community.backfill('42', played, set(local), fetch_page=self.fetch(pages), sleep=lambda s: None)

    def test_fetches_played_games_without_local_stats_newest_first(self):
        result = self.run_backfill([(30, '2'), (20, '1'), (10, '3')], local={'3'})
        self.assertEqual(result, (2, False))
        self.assertEqual(self.asked, ['2', '1'])
        self.assertEqual(set(steam_community.cached_games()), {'1'})
        self.assertEqual(steam_community.cached('1')['achievements'][0]['time'], 5)
        self.assertIn('2', steam_community.none_index())

    def test_fresh_pages_and_known_nones_are_not_fetched_again(self):
        self.run_backfill([(30, '2'), (20, '1')])
        self.asked.clear()
        self.run_backfill([(30, '2'), (20, '1')])
        self.assertEqual(self.asked, [])
        # Played since the last fetch: fetch again.
        self.run_backfill([(30, '2'), (time.time() + 60, '1')])
        self.assertEqual(self.asked, ['1'])

    def test_rate_limits_are_waited_out_then_give_up(self):
        import urllib.error
        limit = urllib.error.HTTPError('u', 429, 'Too Many Requests', {}, None)
        calls = iter([limit, limit, None])
        waits = []
        result = steam_community.backfill('42', [(1, '9')], set(), fetch_page=lambda a, g: (
            (_ for _ in ()).throw(e) if isinstance(e := next(calls), Exception) else e), sleep=waits.append)
        self.assertEqual(result, (1, False))
        self.assertEqual(waits, [60, 120])
        self.assertEqual(steam_community.status()['line'], 'done: 1 fetched')
        always = steam_community.backfill('42', [(1, '8')], set(),
                                          fetch_page=lambda a, g: (_ for _ in ()).throw(limit), sleep=waits.append)
        self.assertEqual(always, (0, True))

    def test_dormant_games_refresh_less_often(self):
        day = 86400
        now = 10_000_000_000
        page = f'{steam_community.cache_dir()}/games/5.json'
        active, dormant = now - 50 * day, now - 400 * day
        steam_community.write_atomic(page, {'time': now - 3 * day})
        self.assertFalse(steam_community.due('5', active, now, {}))
        self.assertTrue(steam_community.due('5', now - day, now, {}))  # played since the fetch
        steam_community.write_atomic(page, {'time': now - 10 * day})
        self.assertTrue(steam_community.due('5', active, now, {}))
        self.assertFalse(steam_community.due('5', dormant, now, {}))
        steam_community.write_atomic(page, {'time': now - 61 * day})
        self.assertTrue(steam_community.due('5', dormant, now, {}))
        self.assertTrue(steam_community.due('6', dormant, now, {}))  # never fetched

    def test_first_error_stops_the_run(self):
        result = self.run_backfill([(30, '1'), (20, '2')], pages={'1': OSError('429'), '2': None})
        self.assertEqual(result, (0, True))
        self.assertEqual(self.asked, ['1'])


class CommunityStore(unittest.TestCase):
    """The Steam store with `community` on: cached pages fill in games that
    never ran here, local data wins, and remote unlocks never toast."""

    def write_page(self, app, unlocked):
        page = steam_community.parse_page(community_page(app, unlocked), app)
        steam_community.write_atomic(f'{steam_community.cache_dir()}/games/{app}.json', dict(page, time=1))

    def lib(self, community):
        lib = FakeLibrary()
        lib.__enter__()
        self.addCleanup(lib.__exit__)
        with open(os.path.join(os.environ['HOME'], '.config/omatrophy/config.json'), 'w') as f:
            json.dump({'community': community}, f)
        patch = mock.patch.object(steam_community, 'CACHE', steam.CACHE)
        patch.start()
        self.addCleanup(patch.stop)
        self.write_page('40', {256: 1700000000})
        self.write_page('10', {})
        return steam.Steam()

    def test_cached_pages_add_games_with_remote_achievements(self):
        store = self.lib(True)
        self.assertEqual(set(store.games()), {'10', '20', '30', '40'})
        achs = store.achievements('40')
        self.assertEqual([a['unlocked'] for a in achs], [True, False])
        self.assertTrue(all(a['remote'] for a in achs))
        # Local stats win over a cached page.
        self.assertEqual(store.achievements('10')[0]['name'], 'Done Game 0')

    def test_off_means_local_only(self):
        store = self.lib(False)
        self.assertEqual(set(store.games()), {'10', '20', '30'})
        self.assertEqual(store.achievements('40'), [])

    def test_remote_unlocks_never_toast(self):
        store = self.lib(True)
        self.write_page('40', {256: int(time.time()), 257: int(time.time())})
        out = io.StringIO()
        with redirect_stdout(out):
            omatrophy.check_game(store, '40', {})
        self.assertEqual(out.getvalue(), '')

    def test_page_names_fill_the_name_cache(self):
        store = self.lib(True)
        store.remember_names()
        with open(steam.NAMES) as f:
            self.assertEqual(json.load(f)['40'], 'Remote Game')

    def test_set_community_writes_a_bool(self):
        self.lib(False)
        with redirect_stdout(io.StringIO()):
            omatrophy.set_option('community', 'on')
        self.assertIs(read_config()['community'], True)


def read_config():
    with open(os.path.join(os.environ['HOME'], '.config/omatrophy/config.json')) as f:
        return json.load(f)


class PickGame(unittest.TestCase):
    def test_running_game_wins(self):
        with FakeLibrary(running={'game': '30', 'since': 0}):
            store, app = omatrophy.pick_game(omatrophy.found_stores())
        self.assertEqual((store.id, app), ('steam', '30'))

    def test_running_game_without_achievements_falls_back_to_last_played(self):
        with FakeLibrary(running={'game': '777', 'since': 0}):
            _, app = omatrophy.pick_game(omatrophy.found_stores())
        self.assertEqual(app, '20')

    def test_last_played_skips_games_without_achievements(self):
        with FakeLibrary(played={'555': 1900000000, '10': 1700000000}):
            _, app = omatrophy.pick_game(omatrophy.found_stores())
        self.assertEqual(app, '10')

    def test_nothing_played_says_how_to_name_a_game(self):
        with FakeLibrary(played={}):
            with self.assertRaises(SystemExit) as e:
                omatrophy.pick_game(omatrophy.found_stores())
        self.assertIn('omatrophy.py game steam', str(e.exception))


class Stores(unittest.TestCase):
    def test_missing_steam_is_unavailable(self):
        with tempfile.TemporaryDirectory() as home, \
             mock.patch.dict(os.environ, {'HOME': home, 'STEAM_DIR': f'{home}/none'}):
            os.environ.pop('STEAM_ACCOUNT', None)
            self.assertFalse(steam.Steam().available())

    def test_every_store_fills_the_contract(self):
        import stores
        for cls in stores.STORES:
            self.assertTrue(cls.id and cls.id.isidentifier(), cls)
            self.assertTrue(cls.name, cls)
            self.assertTrue(issubclass(cls, stores.base.Store), cls)


class Inbox(unittest.TestCase):
    def test_forwards_only_new_lines(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(omatrophy, 'INBOX', f'{tmp}/inbox.jsonl'):
            self.assertEqual(omatrophy.drain_inbox(0), 0)
            with open(omatrophy.INBOX, 'w') as f:
                f.write('{"type": "unlock"}\n')
            out = io.StringIO()
            with redirect_stdout(out):
                offset = omatrophy.drain_inbox(0)
                self.assertEqual(omatrophy.drain_inbox(offset), offset)
            self.assertEqual(out.getvalue(), '{"type": "unlock"}\n')


class Settings(unittest.TestCase):
    def test_set_writes_config_and_rejects_unknown_values(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {'HOME': home}):
            with redirect_stdout(io.StringIO()):
                omatrophy.set_option('position', 'top-left')
                omatrophy.set_option('sound', 'off')
            with open(f'{home}/.config/omatrophy/config.json') as f:
                self.assertEqual(json.load(f), {'position': 'top-left', 'sound': False})
            with redirect_stdout(io.StringIO()):
                omatrophy.set_option('sound', 'classic')
            with open(f'{home}/.config/omatrophy/config.json') as f:
                self.assertEqual(json.load(f), {'position': 'top-left', 'sound': True, 'chimes': 'classic'})
            with self.assertRaises(SystemExit):
                omatrophy.set_option('icons', 'neon')
            with redirect_stdout(io.StringIO()):
                omatrophy.set_option('tracker-sort', 'rarity')
            with open(f'{home}/.config/omatrophy/config.json') as f:
                self.assertEqual(json.load(f)['tracker-sort'], 'rarity')
            with self.assertRaises(SystemExit):
                omatrophy.set_option('tracker-sort', 'random')


class WarmNames(unittest.TestCase):
    def test_looks_up_every_game_and_survives_failures(self):
        asked = []

        class Fake:
            def game_name(self, game):
                asked.append(game)
                if game == 'bad':
                    raise OSError('offline')
                return f'Game {game}'

        fake = Fake()
        omatrophy.warm_names([(fake, '1'), (fake, 'bad'), (fake, '2')], threads=2)
        self.assertEqual(sorted(asked), ['1', '2', 'bad'])


class Hidden(unittest.TestCase):
    def test_with_hidden_adds_removes_and_sorts(self):
        self.assertEqual(omatrophy.with_hidden(['steam:9'], 'steam:1', True), ['steam:1', 'steam:9'])
        self.assertEqual(omatrophy.with_hidden(['steam:1', 'steam:9'], 'steam:1', False), ['steam:9'])
        self.assertEqual(omatrophy.with_hidden(['steam:1'], 'steam:1', True), ['steam:1'])
        # A hand-broken list starts over rather than failing.
        self.assertEqual(omatrophy.with_hidden('oops', 'steam:1', True), ['steam:1'])

    def test_hide_writes_config_and_keeps_other_settings(self):
        with tempfile.TemporaryDirectory() as home, mock.patch.dict(os.environ, {'HOME': home}):
            with redirect_stdout(io.StringIO()):
                omatrophy.set_option('icons', 'vector')
                omatrophy.set_hidden('steam', '20', True)
                omatrophy.set_hidden('steam', '10', True)
                omatrophy.set_hidden('steam', '20', False)
            with open(f'{home}/.config/omatrophy/config.json') as f:
                self.assertEqual(json.load(f), {'icons': 'vector', 'hidden': ['steam:10']})
            self.assertEqual(omatrophy.hidden_games(), {'steam:10'})
            with self.assertRaises(SystemExit):
                omatrophy.set_hidden('gog', '10', True)

    def test_hidden_games_leave_nearest_platinum(self):
        rows = [{'store': 'steam', 'app': '1', 'unlocked': 9, 'total': 10},
                {'store': 'steam', 'app': '2', 'unlocked': 5, 'total': 10}]
        self.assertEqual([r['app'] for r in omatrophy.nearest_platinum(rows, 4, {'steam:1'})], ['2'])


class Sounds(unittest.TestCase):
    def test_every_tier_has_a_sound(self):
        import wave
        root = os.path.join(os.path.dirname(__file__), '..', 'assets', 'sounds')
        for tier in ('bronze', 'silver', 'gold', 'platinum'):
            with wave.open(os.path.join(root, f'{tier}.wav')) as w:
                self.assertGreater(w.getnframes(), 0, tier)


class Qml(unittest.TestCase):
    """Rules the shell can't check until a card loads at runtime."""

    root = os.path.join(os.path.dirname(__file__), '..')

    def qml(self):
        for name in sorted(os.listdir(self.root)):
            if name.endswith('.qml'):
                with open(os.path.join(self.root, name)) as f:
                    yield name, f.read()

    def test_theme_colors_are_qualified(self):
        # Qt 6.12's QtQuick exports its own Color; a bare `Color.` resolves to
        # it (undefined members) in fresh-URL loads.
        import re
        for name, text in self.qml():
            for n, line in enumerate(text.splitlines(), 1):
                code = line.split('//')[0]
                self.assertIsNone(re.search(r'(?<![\w.])Color\.', code), f'{name}:{n}: use Commons.Color')

    def test_cards_load_standalone(self):
        # Cards are built from their text (FreshObject.qml, ADR 10) and stay
        # standalone so each reads on its own.
        siblings = {n[:-4] for n, _ in self.qml()}
        for name in ('TrophyToast.qml', 'PlatinumCard.qml', 'StylePicker.qml', 'TrackerView.qml'):
            text = dict(self.qml())[name]
            for other in siblings - {name[:-4]}:
                self.assertNotRegex(text, rf'\b{other}\s*\{{', f'{name} uses {other}')


if __name__ == '__main__':
    unittest.main()
