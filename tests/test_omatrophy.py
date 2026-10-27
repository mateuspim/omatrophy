"""Tests for omatrophy.py and the Steam store: Steam's binary KeyValues, the
stats cache, unlock diffing, the test inbox and settings. Everything runs against temporary
folders built here; no Steam install, no network, no real config.

Run from the repo root: python3 -m unittest discover -s tests
"""
import io, json, os, struct, sys, tempfile, time, unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import omatrophy  # noqa: E402
from stores import steam  # noqa: E402

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
            with self.assertRaises(SystemExit):
                omatrophy.set_option('icons', 'neon')


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
        # Cards load by fresh URL, where sibling QML types don't resolve.
        siblings = {n[:-4] for n, _ in self.qml()}
        for name in ('TrophyToast.qml', 'PlatinumCard.qml'):
            text = dict(self.qml())[name]
            for other in siblings - {name[:-4]}:
                self.assertNotRegex(text, rf'\b{other}\s*\{{', f'{name} uses {other}')


if __name__ == '__main__':
    unittest.main()
