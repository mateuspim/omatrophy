"""Tests for Load from Steam (stores/steam_loader.py, ADR 13): which played
games lack stats, and the page-by-page loop, with a fake opener and clock.
Nothing here opens Steam or touches a real cache.

Run from the repo root: python3 -m unittest discover -s tests
"""
import os, sys, tempfile, unittest
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


class LoaderCache(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patch = mock.patch.object(steam_loader, 'CACHE', tmp.name)
        patch.start()
        self.addCleanup(patch.stop)


class Missing(unittest.TestCase):
    def test_played_without_stats_most_played_first(self):
        played = {'10': {'total': 5}, '20': {'total': 500}, '30': {'total': 50}, '40': {'total': 0}}
        self.assertEqual(steam_loader.missing(played, {'30'}, {}, 0), ['20', '10'])

    def test_a_recent_none_waits_a_month(self):
        now = 100 * DAY
        played = {'10': {'total': 5}, '20': {'total': 9}}
        nones = {'10': now - DAY, '20': now - 31 * DAY}
        self.assertEqual(steam_loader.missing(played, set(), nones, now), ['20'])

    def test_bad_ids_are_skipped(self):
        self.assertEqual(steam_loader.missing({'../x': {'total': 9}, '7': {'total': 1}}, set(), {}, 0), ['7'])


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
        real_sleep = clock.sleep
        result = steam_loader.load(todo, has_stats, busy, opener=opener, running=running,
                                   clock=clock.time, sleep=real_sleep)
        return result, opened, clock

    def test_loads_and_remembers_games_without_stats(self):
        result, opened, _ = self.run_load(['1', '2', '3'], ready={'1', '3'})
        self.assertEqual(opened, ['1', '2', '3'])
        self.assertEqual(result, {'loaded': 2, 'none': 1, 'state': 'done'})
        self.assertEqual(set(steam_loader.none_index()), {'2'})
        status = steam_loader.status()
        self.assertEqual((status['done'], status['total'], status['state']), (3, 3, 'done'))

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

    def test_stop_request_ends_after_the_current_game(self):
        result, opened, _ = self.run_load(['1', '2', '3'], ready={'1', '2', '3'},
                                          after=lambda app: steam_loader.request_stop())
        self.assertEqual(opened, ['1'])
        self.assertEqual(result, {'loaded': 1, 'none': 0, 'state': 'stopped'})
        self.assertFalse(steam_loader.stop_requested())

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
                                   running=lambda: True, clock=FakeClock().time, sleep=FakeClock().sleep)
        self.assertEqual(result['state'], 'failed')


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
