"""Tests for the GOG store: Comet's gameplay databases and Heroic's files,
built in a temporary folder. No Heroic install, no Comet, no network, no
real config; every id here is made up.

Run from the repo root: python3 -m unittest discover -s tests
"""
import io, json, os, sqlite3, sys, tempfile, time, unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import omatrophy  # noqa: E402
from stores import base, gog  # noqa: E402

PRODUCT = '1000000001'
CLIENT = '50000000000000001'
USER = '40000000000000001'

# The achievement table as Comet creates it, trimmed of CHECK clauses.
SCHEMA = '''CREATE TABLE achievement (id INTEGER PRIMARY KEY NOT NULL, key TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL, description TEXT NOT NULL, visible_while_locked INTEGER NOT NULL,
  unlock_time TEXT, image_url_locked TEXT NOT NULL, image_url_unlocked TEXT NOT NULL,
  changed INTEGER NOT NULL, rarity REAL NOT NULL DEFAULT 0.0,
  rarity_level_description TEXT NOT NULL DEFAULT "", rarity_level_slug TEXT NOT NULL DEFAULT "")'''


def row(key, unlock=None, visible=1, rarity=50.0, changed=0):
    return {'key': key, 'name': f'Name {key}', 'description': f'Do {key}', 'visible_while_locked': visible,
            'unlock_time': unlock, 'image_url_locked': f'https://images.gog.com/{key}_l.jpg',
            'image_url_unlocked': f'https://images.gog.com/{key}_u.jpg', 'changed': changed, 'rarity': rarity}


class HeroicDir:
    """A throwaway Heroic config folder, Comet gameplay folder and game
    install, patched in through HEROIC_DIR and COMET_DIR."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.heroic, self.comet, self.home = f'{t}/heroic', f'{t}/comet/gameplay', f'{t}/home'
        for d in (f'{self.heroic}/gog_store', f'{self.heroic}/store_cache', f'{self.heroic}/store',
                  self.comet, f'{self.home}/.config/omatrophy'):
            os.makedirs(d)
        self.clients = f'{t}/state/gog-clients.json'
        self.patches = [mock.patch.dict(os.environ, {'HEROIC_DIR': self.heroic, 'COMET_DIR': self.comet,
                                                     'HOME': self.home, 'STEAM_DIR': f'{t}/none'}),
                        mock.patch.object(gog, 'CLIENTS', self.clients),
                        # Art goes through base.cached, which would download it.
                        mock.patch.object(gog, 'cached', lambda url, name: url),
                        mock.patch.object(base, 'fetch_bytes', side_effect=AssertionError('network in a test'))]

    def database(self, rows, client=CLIENT, user=USER):
        folder = f'{self.comet}/{client}/{user}'
        os.makedirs(folder, exist_ok=True)
        path = f'{folder}/gameplay.db'
        conn = sqlite3.connect(path)
        conn.execute('DROP TABLE IF EXISTS achievement')
        conn.execute(SCHEMA)
        conn.executemany('INSERT INTO achievement (key, name, description, visible_while_locked, unlock_time,'
                         ' image_url_locked, image_url_unlocked, changed, rarity) VALUES'
                         ' (:key, :name, :description, :visible_while_locked, :unlock_time,'
                         ' :image_url_locked, :image_url_unlocked, :changed, :rarity)', rows)
        conn.commit()
        conn.close()
        return path

    def install(self, product=PRODUCT, client=CLIENT, name='Info Name'):
        """An install folder with its goggame-<product>.info, listed in installed.json."""
        path = f'{self.tmp.name}/games/{product}'
        os.makedirs(path, exist_ok=True)
        with open(f'{path}/goggame-{product}.info', 'w') as f:
            json.dump({'gameId': product, 'rootGameId': product, 'clientId': client, 'name': name}, f)
        self.installed([(product, path)])
        return path

    def installed(self, pairs):
        self.write('gog_store/installed.json',
                   {'installed': [{'appName': p, 'install_path': path, 'platform': 'windows'} for p, path in pairs]})

    def library(self, games):
        self.write('store_cache/gog_library.json', {'games': games})

    def write(self, name, value):
        with open(f'{self.heroic}/{name}', 'w') as f:
            json.dump(value, f)
        # A distinct mtime, so caches keyed on it notice the change.
        os.utime(f'{self.heroic}/{name}', (time.time() + 1, time.time() + len(json.dumps(value))))

    def __enter__(self):
        for p in self.patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in reversed(self.patches):
            p.stop()
        self.tmp.cleanup()


class Discovery(unittest.TestCase):
    def test_no_comet_folder_is_unavailable(self):
        with HeroicDir() as h:
            os.rmdir(h.comet)
            self.assertFalse(gog.Gog().available())

    def test_an_empty_comet_folder_is_unavailable(self):
        with HeroicDir():
            self.assertFalse(gog.Gog().available())

    def test_an_installed_game_is_known_by_its_product_id(self):
        with HeroicDir() as h:
            h.database([row('A')])
            h.install()
            store = gog.Gog()
            self.assertTrue(store.available())
            self.assertEqual(list(store.games()), [PRODUCT])

    def test_folders_that_are_not_ids_are_ignored(self):
        with HeroicDir() as h:
            h.database([row('A')], client='../x')
            h.database([row('A')], user='me')
            self.assertEqual(gog.find_databases([h.comet]), {})

    def test_the_newest_user_folder_wins(self):
        with HeroicDir() as h:
            h.database([row('A')], user='1')
            newer = h.database([row('A'), row('B')], user='2')
            old = f'{h.comet}/{CLIENT}/1/gameplay.db'
            os.utime(old, (1000, 1000))
            self.assertEqual(gog.find_databases([h.comet]), {CLIENT: newer})

    def test_a_game_never_seen_installed_keeps_its_client_id(self):
        with HeroicDir() as h:
            h.database([row('A')])
            store = gog.Gog()
            self.assertEqual(list(store.games()), [CLIENT])
            self.assertEqual(store.game_name(CLIENT), f'GOG {CLIENT}')

    def test_an_uninstalled_game_keeps_its_product_id_and_name(self):
        with HeroicDir() as h:
            h.database([row('A')])
            h.install(name='Info Name')
            self.assertEqual(list(gog.Gog().games()), [PRODUCT])
            h.installed([])
            store = gog.Gog()
            self.assertEqual(list(store.games()), [PRODUCT])
            self.assertEqual(store.game_name(PRODUCT), 'Info Name')

    def test_an_unreadable_install_folder_falls_back_to_the_client_id(self):
        with HeroicDir() as h:
            h.database([row('A')])
            h.installed([(PRODUCT, f'{h.tmp.name}/unmounted')])
            self.assertEqual(list(gog.Gog().games()), [CLIENT])


class Achievements(unittest.TestCase):
    def test_rows_become_the_store_contract(self):
        with HeroicDir() as h:
            h.database([row('A', unlock='2026-11-03T23:59:46+00:00'), row('B', visible=0)])
            h.install()
            a, b = gog.Gog().achievements(PRODUCT)
        self.assertEqual(a, {'api': 'A', 'name': 'Name A', 'desc': 'Do A',
                             'icon': 'https://images.gog.com/A_u.jpg', 'icon_locked': 'https://images.gog.com/A_l.jpg',
                             'hidden': False, 'unlocked': True, 'time': 1793750386})
        self.assertTrue(b['hidden'])
        self.assertFalse(b['unlocked'])
        self.assertEqual(b['time'], 0)

    def test_an_unlock_not_yet_synced_to_gog_counts(self):
        with HeroicDir() as h:
            h.database([row('A', unlock='2026-11-03T23:59:46+00:00', changed=1)])
            h.install()
            self.assertTrue(gog.Gog().achievements(PRODUCT)[0]['unlocked'])

    def test_unknown_or_unsafe_game_ids_have_nothing(self):
        with HeroicDir() as h:
            h.database([row('A')])
            store = gog.Gog()
            self.assertEqual(store.achievements('../../etc'), [])
            self.assertEqual(store.achievements('999'), [])

    def test_rarity_is_rounded_and_zero_is_unknown(self):
        with HeroicDir() as h:
            h.database([row('A', rarity=54.099998474121094), row('B', rarity=0.0), row('C', rarity=3.0)])
            h.install()
            store = gog.Gog()
            self.assertEqual(store.percents(PRODUCT), {'A': 54.1, 'C': 3.0})
            self.assertEqual(store.percent(PRODUCT, 'C'), 3.0)
            self.assertIsNone(store.percent(PRODUCT, 'B'))
            pcts = store.percents(PRODUCT)
            tiers = [omatrophy.detail(a, pcts)['tier'] for a in store.achievements(PRODUCT)]
        self.assertEqual(tiers, ['bronze', 'bronze', 'gold'])


class UnlockTime(unittest.TestCase):
    def test_rfc3339_with_offset_or_z(self):
        self.assertEqual(gog.unix_time('2026-11-03T23:59:46+00:00'), 1793750386)
        self.assertEqual(gog.unix_time('2026-11-03T23:59:46Z'), 1793750386)
        self.assertEqual(gog.unix_time('2026-11-03T20:59:46-03:00'), 1793750386)

    def test_no_zone_reads_as_utc(self):
        self.assertEqual(gog.unix_time('2026-11-03T23:59:46'), 1793750386)

    def test_missing_or_garbage_is_zero(self):
        for text in (None, '', 'yesterday', 12):
            self.assertEqual(gog.unix_time(text), 0)

    def test_heroic_last_played(self):
        self.assertEqual(gog.played_at('2026-11-03T23:18:17.957Z'), 1793747897)
        self.assertEqual(gog.played_at(''), 0)
        self.assertEqual(gog.played_at(None), 0)


class Caching(unittest.TestCase):
    def test_an_unchanged_database_is_read_once(self):
        with HeroicDir() as h:
            db = h.database([row('A')])
            h.install()
            store = gog.Gog()
            with mock.patch.object(gog, 'read_rows', wraps=gog.read_rows) as reads:
                store.achievements(PRODUCT)
                store.percents(PRODUCT)
                self.assertEqual(reads.call_count, 1)
                os.utime(db, (time.time() + 5, time.time() + 5))
                store.achievements(PRODUCT)
                self.assertEqual(reads.call_count, 2)

    def test_the_token_follows_the_wal_file(self):
        with HeroicDir() as h:
            db = h.database([row('A')])
            os.utime(db, (1000, 1000))
            self.assertEqual(gog.db_token(db), 1000)
            open(db + '-wal', 'w').close()
            os.utime(db + '-wal', (2000, 2000))
            self.assertEqual(gog.db_token(db), 2000)

    def test_installed_json_is_read_again_only_when_it_changes(self):
        with HeroicDir() as h:
            h.database([row('A')])
            h.install()
            store = gog.Gog()
            store.games()
            with mock.patch.object(gog, 'client_of', wraps=gog.client_of) as reads:
                store.games()
                self.assertEqual(reads.call_count, 0)
                h.install()
                store.games()
                self.assertEqual(reads.call_count, 1)


class LockedDatabase(unittest.TestCase):
    def lock(self, db):
        """Hold Comet's write lock: in rollback-journal mode an exclusive
        transaction keeps readers out until it ends."""
        conn = sqlite3.connect(db, isolation_level=None)
        conn.execute('BEGIN EXCLUSIVE')
        self.addCleanup(conn.close)
        return conn

    def test_a_locked_database_answers_the_last_copy_and_retries(self):
        with HeroicDir() as h, mock.patch.object(gog, 'DB_TIMEOUT', 0.01):
            db = h.database([row('A')])
            h.install()
            store = gog.Gog()
            self.assertEqual(len(store.achievements(PRODUCT)), 1)
            conn = self.lock(db)
            os.utime(db, (time.time() + 5, time.time() + 5))
            self.assertEqual(len(store.achievements(PRODUCT)), 1)
            # A fresh token every tick while it fails, so the watcher
            # doesn't wait for the next unlock to read it again.
            with mock.patch.object(gog.time, 'time', return_value=111):
                self.assertEqual(store.games()[PRODUCT], 111)
            conn.execute('ROLLBACK')
            store.achievements(PRODUCT)
            self.assertNotEqual(store.games()[PRODUCT], 111)

    def test_a_first_read_of_a_locked_database_is_not_readable_yet(self):
        with HeroicDir() as h, mock.patch.object(gog, 'DB_TIMEOUT', 0.01):
            db = h.database([row('A', unlock='2026-11-03T23:59:46+00:00')])
            h.install()
            self.lock(db)
            store = gog.Gog()
            self.assertEqual(omatrophy.unlocked_set(store, PRODUCT), ([], set()))
            self.assertEqual(store.percents(PRODUCT), {})

    def test_a_file_that_is_not_a_database_is_not_readable_yet(self):
        with HeroicDir() as h:
            os.makedirs(f'{h.comet}/{CLIENT}/{USER}')
            with open(f'{h.comet}/{CLIENT}/{USER}/gameplay.db', 'w') as f:
                f.write('not sqlite')
            store = gog.Gog()
            self.assertEqual(omatrophy.unlocked_set(store, CLIENT), ([], set()))
            self.assertNotIn(CLIENT, store.retry)

    def test_another_layout_has_no_achievements_and_is_not_retried(self):
        with HeroicDir() as h:
            db = h.database([row('A')])
            conn = sqlite3.connect(db)
            conn.execute('ALTER TABLE achievement RENAME TO trophies')
            conn.commit()
            conn.close()
            store = gog.Gog()
            with mock.patch.object(gog, 'read_rows', wraps=gog.read_rows) as reads:
                self.assertEqual(store.achievements(CLIENT), [])
                self.assertEqual(store.achievements(CLIENT), [])
                self.assertEqual(reads.call_count, 1)
            self.assertNotIn(CLIENT, store.retry)

    def test_a_hot_journal_keeps_the_last_copy(self):
        with HeroicDir() as h:
            db = h.database([row('A', unlock='2026-11-03T23:59:46+00:00')])
            h.install()
            store = gog.Gog()
            self.assertEqual(len(store.achievements(PRODUCT)), 1)
            # What a read-only open says after Comet died mid-transaction.
            hot = sqlite3.OperationalError('attempt to write a readonly database')
            os.utime(db, (time.time() + 5, time.time() + 5))
            with mock.patch.object(gog, 'read_rows', side_effect=hot):
                self.assertEqual([a['api'] for a in store.achievements(PRODUCT) if a['unlocked']], ['A'])
            self.assertNotIn(PRODUCT, store.retry)

    def test_only_a_lock_is_busy(self):
        self.assertTrue(gog.busy(sqlite3.OperationalError('database is locked')))
        self.assertFalse(gog.busy(sqlite3.OperationalError('no such table: achievement')))
        self.assertFalse(gog.busy(sqlite3.DatabaseError('file is not a database')))


class Watcher(unittest.TestCase):
    def test_a_new_unlock_becomes_a_gog_event_with_gogs_rarity(self):
        with HeroicDir() as h:
            h.database([row('A', rarity=20.0), row('B')])
            h.install()
            h.library([{'app_name': PRODUCT, 'title': 'Library Title'}])
            store = gog.Gog()
            seen = {('gog', PRODUCT): omatrophy.unlocked_set(store, PRODUCT)[1]}
            now = time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())
            h.database([row('A', unlock=now, rarity=20.0), row('B')])
            out = io.StringIO()
            with redirect_stdout(out):
                omatrophy.check_game(store, PRODUCT, seen)
        ev = json.loads(out.getvalue())
        self.assertEqual((ev['store'], ev['app'], ev['game'], ev['name']), ('gog', PRODUCT, 'Library Title', 'Name A'))
        self.assertEqual((ev['tier'], ev['percent'], ev['unlocked'], ev['total']), ('silver', 20.0, 1, 2))
        self.assertTrue(ev['icon'].endswith('A_u.jpg'))


class Library(unittest.TestCase):
    def test_title_and_art_come_from_heroics_library(self):
        with HeroicDir() as h:
            h.database([row('A')])
            h.install(name='Info Name')
            h.library([{'app_name': PRODUCT, 'title': 'Library Title',
                        'art_cover': 'https://images.gog.com/c.jpg', 'art_background': 'https://images.gog.com/b.webp'}])
            store = gog.Gog()
            self.assertEqual(store.game_name(PRODUCT), 'Library Title')
            self.assertEqual(store.art(PRODUCT), {'hero': 'https://images.gog.com/b.webp',
                                                  'header': 'https://images.gog.com/c.jpg'})

    def test_no_library_entry_means_no_art_and_the_info_name(self):
        with HeroicDir() as h:
            h.database([row('A')])
            h.install(name='Info Name')
            store = gog.Gog()
            self.assertEqual(store.game_name(PRODUCT), 'Info Name')
            self.assertEqual(store.art(PRODUCT), {'hero': '', 'header': ''})

    def test_recent_takes_heroics_last_played_or_the_databases_last_write(self):
        with HeroicDir() as h:
            os.utime(h.database([row('A')]), (1000, 1000))
            os.utime(h.database([row('A')], client='50000000000000002'), (3000, 3000))
            h.install()
            h.write('store/timestamp.json', {PRODUCT: {'lastPlayed': '2026-11-03T23:18:17.957Z'},
                                             '50000000000000002': {'lastPlayed': ''}, 'x/y': {}})
            self.assertEqual(gog.Gog().recent(), [(1793747897, PRODUCT), (3000, '50000000000000002')])

    def test_playtime_is_heroics_total_with_no_two_week_figure(self):
        with HeroicDir() as h:
            h.database([row('A')])
            h.install()
            h.write('store/timestamp.json', {PRODUCT: {'totalPlayed': 56}, 'x/y': {'totalPlayed': 9},
                                             '50000000000000002': {'totalPlayed': 'lots'}})
            self.assertEqual(gog.Gog().playtime(), {PRODUCT: {'total': 56, 'recent': None}})

    def test_gogs_image_hosts_are_trusted(self):
        self.assertTrue(base.trusted_url('https://images.gog.com/a_gac_60.jpg'))
        self.assertTrue(base.trusted_url('https://images.gog-statics.com/a.jpg'))
        self.assertFalse(base.trusted_url('https://evilgog.com/a.jpg'))
        self.assertFalse(base.trusted_url('http://images.gog.com/a.jpg'))


class Running(unittest.TestCase):
    def fake_proc(self, proc, commands):
        with open(f'{proc}/stat', 'w') as f:
            f.write('cpu 1 2 3\nbtime 1000\n')
        for pid, (cmd, seconds) in commands.items():
            os.makedirs(f'{proc}/{pid}')
            with open(f'{proc}/{pid}/cmdline', 'wb') as f:
                f.write(cmd)
            with open(f'{proc}/{pid}/stat', 'w') as f:
                f.write(f'{pid} (x) S ' + ' '.join(['0'] * 18) + f' {os.sysconf("SC_CLK_TCK") * seconds} 0')

    def test_the_earliest_process_in_an_install_folder_is_the_game(self):
        with tempfile.TemporaryDirectory() as proc:
            self.fake_proc(proc, {'7': (b'bash\0', 1),
                                  '8': (b'/games/Doom Two/doom.exe\0-skill\0', 50),
                                  '9': (b'wine\0Z:\\games\\Doom Two\\launcher.exe\0', 30)})
            self.assertEqual(gog.running_install([(PRODUCT, '/games/Doom Two')], proc),
                             {'game': PRODUCT, 'since': 1030})

    def test_a_sibling_folder_with_the_same_prefix_is_not_the_game(self):
        with tempfile.TemporaryDirectory() as proc:
            self.fake_proc(proc, {'8': (b'/games/Doom Two Extra/x.exe\0', 50)})
            self.assertIsNone(gog.running_install([(PRODUCT, '/games/Doom Two')], proc))


if __name__ == '__main__':
    unittest.main()
