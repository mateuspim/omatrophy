"""Tests for Load from Steam (stores/steam_loader.py, ADR 13): which played
games lack stats, and the page-by-page loop, with a fake opener and clock.
Nothing here opens Steam or touches a real cache.

Run from the repo root: python3 -m unittest discover -s tests
"""
import json, os, sys, tempfile, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.dirname(__file__))
import omatrophy  # noqa: E402
from stores import steam, steam_loader  # noqa: E402
from test_omatrophy import UID, FakeLibrary  # noqa: E402

DAY = 86400


class FakeClock:
    """time() and sleep() that only move when slept."""

    def __init__(self, now=1_800_000_000):
        self.now = now

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class NoWindow:
    """A SteamWindow stand-in that records calls."""

    def __init__(self):
        self.calls = []

    def hide(self):
        self.calls.append('hide')

    def restore(self):
        self.calls.append('restore')


class LoaderCache(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # A test on a Hyprland desktop must never move the real Steam window.
        for name, value in (('CACHE', tmp.name),
                            ('hyprctl', mock.Mock(side_effect=AssertionError('hyprctl in a test')))):
            patch = mock.patch.object(steam_loader, name, value)
            patch.start()
            self.addCleanup(patch.stop)


class Missing(unittest.TestCase):
    def test_played_without_stats_most_played_first(self):
        played = {'10': {'total': 5}, '20': {'total': 500}, '30': {'total': 50}, '40': {'total': 0}}
        self.assertEqual(steam_loader.missing(played, {'30'}, {}), ['20', '10'])

    def test_a_tried_game_is_never_tried_again(self):
        played = {'10': {'total': 5}, '20': {'total': 9}, '30': {'total': 1}}
        tried = {'10': {'time': 1, 'found': False}, '20': {'time': 1, 'found': True}}
        self.assertEqual(steam_loader.missing(played, set(), tried), ['30'])

    def test_everything_tries_them_all_again(self):
        played = {'10': {'total': 5}, '20': {'total': 9}}
        tried = {'10': {'time': 1, 'found': False}}
        self.assertEqual(steam_loader.missing(played, {'20'}, tried, everything=True), ['10'])

    def test_unsure_games_are_queued_first_and_not_settled(self):
        played = {'10': {'total': 5}, '20': {'total': 9}, '30': {'total': 1}}
        tried = {'30': {'time': 1, 'found': None}, '20': {'time': 1, 'found': False}}
        self.assertEqual(steam_loader.missing(played, set(), tried), ['30', '10'])
        self.assertTrue(steam_loader.unsure(tried, '30'))
        self.assertFalse(steam_loader.settled(tried, '30'))
        self.assertTrue(steam_loader.settled(tried, '20'))
        self.assertFalse(steam_loader.settled(tried, '10'))
        self.assertFalse(steam_loader.unsure(tried, '10'))

    def test_bad_ids_are_skipped(self):
        self.assertEqual(steam_loader.missing({'../x': {'total': 9}, '7': {'total': 1}}, set(), {}), ['7'])


class Load(LoaderCache):
    def run_load(self, todo, ready=(), running=lambda: True, busy=lambda: False, after=None):
        """Load `todo`; apps in `ready` get a stats file one poll after
        their page opens. `after(app)` runs after each open."""
        clock, files, opened = FakeClock(), set(), []

        def opener(app):
            opened.append(app)
            if after:
                after(app)

        def has_stats(app):
            if app in ready and opened and opened[-1] == app and clock.now > start[0]:
                files.add(app)
            return app in files

        start = [clock.now]
        self.window = NoWindow()
        result = steam_loader.load(todo, has_stats, busy, opener=opener, running=running,
                                   clock=clock.time, sleep=clock.sleep, window=self.window)
        return result, opened, clock

    def test_loads_and_remembers_games_without_stats(self):
        result, opened, _ = self.run_load(['1', '2', '3'], ready={'1', '3'})
        self.assertEqual(opened, ['1', '2', '3'])
        self.assertEqual(result, {'loaded': 2, 'none': 1, 'state': 'done'})
        self.assertEqual(steam_loader.checked(), {'1': {'time': 1_800_000_000, 'found': True},
                                                  '2': {'time': 1_800_000_008, 'found': False},
                                                  '3': {'time': 1_800_000_008, 'found': True}})
        status = steam_loader.status()
        self.assertEqual((status['done'], status['total'], status['state']), (3, 3, 'done'))

    def test_stops_when_steam_is_not_signed_in(self):
        states = iter([True, False])
        clock = FakeClock()
        result = steam_loader.load(['1', '2'], lambda app: False, lambda: False, opener=lambda app: None,
                                   running=lambda: True, clock=clock.time, sleep=clock.sleep, window=NoWindow(),
                                   online=lambda: next(states))
        self.assertEqual(result, {'loaded': 0, 'none': 1, 'state': 'failed'})
        self.assertIn('not signed in', steam_loader.status()['line'])
        # The game it didn't get to stays untried.
        self.assertNotIn('2', steam_loader.checked())

    def test_reads_the_last_connection_state(self):
        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, 'connection_log.txt')
            self.assertIsNone(steam_loader.signed_in(log))
            with open(log, 'w') as f:
                f.write('[2026-11-03 20:01:01] [Logging On, 4, 23] [U:1:1] Using JWT\n'
                        '[2026-11-03 20:01:14] [Logged On, 4, 23] [U:1:1] processing complete\n'
                        '[2026-11-03 20:31:43] CClientJobGetClientUpdateHosts: cached version not expired\n')
            self.assertTrue(steam_loader.signed_in(log))
            with open(log, 'a') as f:
                f.write('[2026-11-03 21:00:00] [Logged Off, 4, 0] [U:1:1] lost connection\n')
            self.assertFalse(steam_loader.signed_in(log))
            with open(log, 'w') as f:
                f.write('a format we have never seen\n')
            self.assertIsNone(steam_loader.signed_in(log))

    def test_a_timeout_streak_stops_and_keeps_those_games_unsure(self):
        # Steam offline: every game times out. Before, all of them were
        # filed as "no achievements" and never tried again.
        n = steam_loader.TIMEOUT_STREAK
        todo = [str(i) for i in range(1, n + 3)]
        result, opened, _ = self.run_load(todo)
        self.assertEqual(len(opened), n)
        self.assertEqual(result, {'loaded': 0, 'none': 0, 'state': 'failed'})
        self.assertIn('Steam may be offline', steam_loader.status()['line'])
        tried = steam_loader.checked()
        self.assertTrue(all(tried[a]['found'] is None for a in todo[:n]))
        playtimes = {a: {'total': 100 - int(a)} for a in todo}
        playtimes['99'] = {'total': 1000}
        # Unsure games come back first, ahead of a more played new one.
        self.assertEqual(steam_loader.missing(playtimes, set(), tried), todo[:n] + ['99'] + todo[n:])

    def test_unsure_games_that_time_out_again_are_settled(self):
        n = steam_loader.TIMEOUT_STREAK
        todo = [str(i) for i in range(1, n + 1)]
        self.run_load(todo)
        result, opened, _ = self.run_load(todo + ['50'], ready={'50'})
        self.assertEqual(result, {'loaded': 1, 'none': n, 'state': 'done'})
        tried = steam_loader.checked()
        self.assertTrue(all(tried[a]['found'] is False for a in todo))
        self.assertTrue(steam_loader.settled(tried, '50'))

    def test_a_loaded_game_breaks_the_streak(self):
        n = steam_loader.TIMEOUT_STREAK
        todo = [str(i) for i in range(1, 2 * n)]
        result, _, _ = self.run_load(todo, ready={str(n)})
        self.assertEqual(result['state'], 'done')

    def test_a_game_without_stats_waits_only_the_timeout(self):
        _, _, clock = self.run_load(['2'])
        self.assertLessEqual(clock.now - 1_800_000_000, steam_loader.WAIT_SECONDS + steam_loader.POLL_SECONDS)

    def test_stops_when_steam_closes(self):
        alive = iter([True, False])
        result, opened, _ = self.run_load(['1', '2'], ready={'1', '2'}, running=lambda: next(alive))
        self.assertEqual(opened, ['1'])
        self.assertEqual(result['state'], 'failed')
        self.assertIn('Steam is not running', steam_loader.status()['line'])

    def test_stops_when_a_game_starts(self):
        result, opened, _ = self.run_load(['1', '2'], busy=lambda: True)
        self.assertEqual(opened, [])
        self.assertEqual(result['state'], 'failed')

    def test_stop_acts_mid_wait(self):
        result, opened, clock = self.run_load(['1', '2', '3'], after=lambda app: steam_loader.request_stop())
        self.assertEqual(opened, ['1'])
        self.assertEqual(result, {'loaded': 0, 'none': 0, 'state': 'stopped'})
        self.assertLess(clock.now - 1_800_000_000, 1)
        self.assertFalse(steam_loader.stop_requested())
        self.assertEqual(steam_loader.status()['state'], 'stopped')

    def test_the_window_is_hidden_then_put_back(self):
        self.run_load(['1', '2'], ready={'1', '2'})
        self.assertEqual(self.window.calls, ['hide', 'hide', 'hide', 'restore'])

    def test_status_lists_the_latest_results_newest_first(self):
        describe = lambda app: {'name': f'Game {app}', 'art': f'file:///art/{app}.jpg'}
        clock = FakeClock()
        steam_loader.load([str(a) for a in range(1, 9)], lambda app: app != '8', lambda: False,
                          opener=lambda app: None, running=lambda: True, window=NoWindow(),
                          clock=clock.time, sleep=clock.sleep, describe=describe)
        status = steam_loader.status()
        self.assertEqual([r['app'] for r in status['recent']], ['8', '7', '6', '5', '4', '3'])
        self.assertEqual(status['recent'][0], {'name': 'Game 8', 'art': 'file:///art/8.jpg', 'app': '8', 'found': False})
        self.assertIsNone(status['current'])
        self.assertIn('started', status)
        self.assertFalse(status['hidden'])

    def test_the_next_game_is_prepared_while_one_loads(self):
        told = []
        steam_loader.load(['1', '2', '3'], lambda app: True, lambda: False, opener=lambda app: None,
                          running=lambda: True, window=NoWindow(), prepare=told.append)
        self.assertEqual(told, ['2', '3'])

    def test_status_says_which_kind_of_run(self):
        steam_loader.load(['1'], lambda app: True, lambda: False, opener=lambda app: None,
                          running=lambda: True, window=NoWindow(), everything=True)
        self.assertTrue(steam_loader.status()['everything'])

    def test_the_window_comes_back_after_a_failure(self):
        self.run_load(['1'], busy=lambda: True)
        self.assertEqual(self.window.calls[-1], 'restore')

    def test_a_killed_run_says_so_and_restores_the_window(self):
        def killed(app):
            raise SystemExit(1)
        with self.assertRaises(SystemExit):
            self.run_load(['1'], after=killed)
        self.assertEqual(self.window.calls[-1], 'restore')
        self.assertEqual(steam_loader.status()['state'], 'failed')

    def test_a_stopped_run_resumes_at_the_next_game(self):
        self.run_load(['1', '2', '3'], ready={'1', '2', '3'},
                      after=lambda app: app == '2' and steam_loader.request_stop())
        # 2's file came before the stop took effect, so it counts.
        self.assertEqual(set(steam_loader.checked()), {'1', '2'})
        played = {a: {'total': 10 - int(a)} for a in ('1', '2', '3')}
        self.assertEqual(steam_loader.missing(played, set(), steam_loader.checked()), ['3'])

    def test_progress_names_the_game_being_tried(self):
        seen = []
        real = steam_loader.write_json
        with mock.patch.object(steam_loader, 'write_json',
                               side_effect=lambda path, v: (seen.append(dict(v)) if path.endswith('status.json') else None, real(path, v))):
            self.run_load(['1'], ready={'1'})
        self.assertEqual([(v['state'], v['done'], v['app']) for v in seen],
                         [('running', 0, ''), ('running', 0, '1'), ('running', 1, ''), ('done', 1, '')])

    def test_a_stale_stop_does_not_cancel_the_next_run(self):
        steam_loader.request_stop()
        result, opened, _ = self.run_load(['1'], ready={'1'})
        self.assertEqual((opened, result['state']), (['1'], 'done'))

    def test_nothing_to_do(self):
        result, opened, _ = self.run_load([])
        self.assertEqual((opened, result['state'], steam_loader.status()['line']), ([], 'done', 'up to date'))

    def test_no_launcher_on_path(self):
        def opener(app):
            raise OSError('neither steam nor xdg-open is on PATH')
        result = steam_loader.load(['1'], lambda app: False, lambda: False, opener=opener,
                                   running=lambda: True, clock=FakeClock().time, sleep=FakeClock().sleep,
                                   window=NoWindow())
        self.assertEqual(result['state'], 'failed')


class FakeHyprctl:
    """hyprctl with a fixed client list; records dispatches."""

    def __init__(self, clients):
        self.clients = clients
        self.dispatched = []

    def __call__(self, *args):
        if args[0] == 'clients':
            return json.dumps(self.clients)
        if args[0] == 'activeworkspace':
            return json.dumps({'name': '3'})
        self.dispatched.append(args[1])
        return 'ok'


def client(address, workspace, cls='steam', title='Steam'):
    return {'address': address, 'class': cls, 'title': title, 'workspace': {'name': workspace}}


class SteamWindowOnHyprland(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': 'test'})
        patch.start()
        self.addCleanup(patch.stop)

    def test_hides_steam_windows_and_puts_them_back(self):
        ctl = FakeHyprctl([client('0x1', '4'), client('0x2', '2', cls='kitty')])
        w = steam_loader.SteamWindow(ctl)
        w.hide()
        self.assertEqual(len(ctl.dispatched), 2)
        self.assertIn('prop = "focus_on_activate", value = 0', ctl.dispatched[0])
        self.assertIn('workspace = "special:omatrophy", follow = false', ctl.dispatched[1])
        self.assertNotIn('0x2', ''.join(ctl.dispatched))
        ctl.clients = [client('0x1', 'special:omatrophy')]
        w.hide()
        self.assertEqual(len(ctl.dispatched), 2)
        w.restore()
        self.assertIn('value = "unset"', ctl.dispatched[2])
        self.assertIn('workspace = "4"', ctl.dispatched[3])

    def test_drops_the_per_window_override_instead_of_copying_the_global(self):
        # Regression: restore wrote the global value back as an override,
        # which outlived any later change to the user's config.
        ctl = FakeHyprctl([client('0x1', '4')])
        w = steam_loader.SteamWindow(ctl)
        w.hide()
        w.restore()
        self.assertIn('prop = "focus_on_activate", value = "unset"', ctl.dispatched[2])

    def test_a_new_window_that_is_not_the_main_one_comes_back_instead_of_closing(self):
        # Regression: a Friends list or sign-in dialog opened mid-load was
        # closed with the main window.
        ctl = FakeHyprctl([client('0x1', '4')])
        w = steam_loader.SteamWindow(ctl)
        w.hide()
        ctl.clients = [client('0x1', 'special:omatrophy'), client('0x7', '2', title='Friends List')]
        w.hide()
        ctl.clients[1]['workspace']['name'] = 'special:omatrophy'
        w.restore()
        sent = ''.join(ctl.dispatched)
        self.assertNotIn('window.close', sent)
        self.assertIn('window = "address:0x7", workspace = "3"', sent)
        self.assertIn('window = "address:0x1", workspace = "4"', sent)

    def test_a_window_the_load_opened_is_closed_again(self):
        ctl = FakeHyprctl([])
        w = steam_loader.SteamWindow(ctl)
        w.hide()
        ctl.clients = [client('0x9', '1')]
        w.hide()
        w.restore()
        self.assertIn('hl.dsp.window.close({ window = "address:0x9" })', ctl.dispatched[-1])

    def test_a_silent_hyprctl_does_not_make_the_users_window_the_loads(self):
        ctl = FakeHyprctl([client('0x1', '4')])
        answer = ctl.__call__
        ctl_silent = lambda *args: None if args[0] == 'clients' and not ctl.clients_ok else answer(*args)
        ctl.clients_ok = False
        w = steam_loader.SteamWindow(ctl_silent)
        w.hide()
        self.assertIsNone(w.before)
        ctl.clients_ok = True
        w.hide()
        w.restore()
        self.assertNotIn('window.close', ''.join(ctl.dispatched))
        self.assertIn('workspace = "4"', ctl.dispatched[-1])

    def test_nothing_without_hyprland(self):
        ctl = FakeHyprctl([client('0x1', '4')])
        with mock.patch.dict(os.environ, {'HYPRLAND_INSTANCE_SIGNATURE': ''}):
            w = steam_loader.SteamWindow(ctl)
        w.hide()
        w.restore()
        self.assertEqual(ctl.dispatched, [])


class SteamRunning(unittest.TestCase):
    def test_finds_the_client_by_process_name(self):
        with tempfile.TemporaryDirectory() as proc:
            for pid, comm in (('1', 'bash'), ('2', 'steamwebhelper')):
                os.makedirs(f'{proc}/{pid}')
                with open(f'{proc}/{pid}/comm', 'w') as f:
                    f.write(comm + '\n')
            self.assertFalse(steam_loader.steam_running(proc))
            os.makedirs(f'{proc}/3')
            with open(f'{proc}/3/comm', 'w') as f:
                f.write('steam\n')
            self.assertTrue(steam_loader.steam_running(proc))


class StoreMissing(LoaderCache):
    def test_store_lists_played_games_without_stats(self):
        with FakeLibrary() as lib:
            apps = ''.join(f'"{a}" {{ "LastPlayed" "1700000000" "Playtime" "{m}" }}'
                           for a, m in (('10', 90), ('50', 10), ('60', 300), ('70', 0)))
            with open(f'{lib.root}/userdata/{UID}/config/localconfig.vdf', 'w') as f:
                f.write(f'"UserLocalConfigStore" {{ "Software" {{ "Valve" {{ "Steam" {{ "apps" {{ {apps} }} }} }} }} }}')
            self.assertEqual(steam.Steam().missing(), ['60', '50'])


class AlreadyRunning(unittest.TestCase):
    def test_a_fresh_running_status_blocks_a_second_load(self):
        self.assertTrue(omatrophy.steam_load_busy({'state': 'running', 'time': 100}, 110))

    def test_a_quiet_one_died(self):
        self.assertFalse(omatrophy.steam_load_busy({'state': 'running', 'time': 100}, 100 + omatrophy.STEAM_LOAD_STALE))
        self.assertFalse(omatrophy.steam_load_busy({'state': 'done', 'time': 100}, 101))


if __name__ == '__main__':
    unittest.main()
