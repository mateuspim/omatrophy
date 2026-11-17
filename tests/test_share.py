"""The saved platinum image (share.py, `omatrophy.py share`): where it goes,
what the throwaway shell is told, and which games get one. Nothing here
starts Quickshell: the render runs a fake in its place, so CI needs none."""
import io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import omatrophy  # noqa: E402
import share  # noqa: E402
from stores import base as stores_base  # noqa: E402


def setUpModule():
    global NO_NETWORK
    NO_NETWORK = mock.patch.object(stores_base.OPENER, 'open', side_effect=AssertionError('network in a test'))
    NO_NETWORK.start()


def tearDownModule():
    NO_NETWORK.stop()


def ach(api, unlocked, t=0):
    return {'api': api, 'name': api, 'desc': '', 'icon': '', 'unlocked': unlocked, 'time': t}


class FakeStore:
    id = 'steam'
    name = 'Steam'

    def __init__(self, achs, art=None):
        self.achs = achs
        self.art_urls = art or {'hero': '', 'header': ''}

    def achievements(self, game):
        return self.achs

    def art(self, game):
        return dict(self.art_urls)

    def game_name(self, game):
        return 'Starfall Odyssey'

    def percent(self, game, api):
        return None


class Slug(unittest.TestCase):
    def test_words_lowercased_and_hyphenated(self):
        self.assertEqual(share.slug('Starfall Odyssey'), 'starfall-odyssey')
        self.assertEqual(share.slug("Baldur's Gate 3: Director's Cut"), 'baldur-s-gate-3-director-s-cut')

    def test_nothing_a_shell_trips_on(self):
        self.assertEqual(share.slug('../../etc/passwd; rm -rf ~'), 'etc-passwd-rm-rf')

    def test_a_name_without_letters_still_names_a_file(self):
        self.assertEqual(share.slug('★☆★'), 'game')
        self.assertEqual(share.slug(''), 'game')

    def test_long_names_are_cut(self):
        self.assertLessEqual(len(share.slug('word ' * 100)), 80)
        self.assertFalse(share.slug('word ' * 100).endswith('-'))


class PicturesDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, 'home')
        self.config = os.path.join(self.tmp.name, 'config')
        os.makedirs(self.config)

    def dirs(self, line):
        with open(os.path.join(self.config, 'user-dirs.dirs'), 'w') as f:
            f.write('# written by xdg-user-dirs-update\nXDG_DESKTOP_DIR="$HOME/Desktop"\n' + line + '\n')

    def test_reads_xdg_pictures_dir(self):
        self.dirs('XDG_PICTURES_DIR="$HOME/Bilder"')
        self.assertEqual(share.pictures_dir(self.home, self.config), f'{self.home}/Bilder')

    def test_absolute_folder_kept(self):
        self.dirs('XDG_PICTURES_DIR="/srv/pics"')
        self.assertEqual(share.pictures_dir(self.home, self.config), '/srv/pics')

    def test_home_itself_or_relative_means_pictures(self):
        # The spec's "$HOME/" is how a user switches a folder off.
        for line in ('XDG_PICTURES_DIR="$HOME/"', 'XDG_PICTURES_DIR="pics"'):
            with self.subTest(line=line):
                self.dirs(line)
                self.assertEqual(share.pictures_dir(self.home, self.config), f'{self.home}/Pictures')

    def test_no_file_means_pictures(self):
        self.assertEqual(share.pictures_dir(self.home, self.config), f'{self.home}/Pictures')

    def test_default_path(self):
        self.assertEqual(share.default_path('Starfall Odyssey', self.home, self.config),
                         f'{self.home}/Pictures/omatrophy/starfall-odyssey-platinum.png')


class LocalArt(unittest.TestCase):
    def test_only_local_files_that_exist(self):
        with tempfile.NamedTemporaryFile(suffix='.jpg') as f:
            self.assertEqual(share.local_art('file://' + f.name), 'file://' + f.name)
            self.assertEqual(share.local_art(f.name), 'file://' + f.name)
        self.assertEqual(share.local_art('file:///no/such/hero.jpg'), '')
        # The throwaway shell would fetch a web URL: no network in a save.
        self.assertEqual(share.local_art('https://cdn.example/hero.jpg'), '')
        self.assertEqual(share.local_art('relative/hero.jpg'), '')
        self.assertEqual(share.local_art(None), '')


class SceneQml(unittest.TestCase):
    def test_paths_go_in_as_string_literals(self):
        nasty = '/tmp/x"); Qt.quit(); ("'
        text = share.scene_qml('/repo/PlatinumShare.qml', nasty + '/event.json', nasty + '/out.png', nasty)
        self.assertNotIn(nasty, text)
        self.assertIn(json.dumps(nasty + '/out.png'), text)
        self.assertIn('"file:///repo/PlatinumShare.qml"', text)

    def test_grabs_at_twice_the_scene(self):
        text = share.scene_qml('/r/P.qml', '/e.json', '/o.png', '/theme')
        self.assertIn('Qt.size(2400, 1260)', text)


class Render(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.shell = os.path.join(self.tmp.name, 'shell')
        for part in ('Commons', 'Ui'):
            os.makedirs(os.path.join(self.shell, part))
        which = mock.patch.object(share.shutil, 'which', return_value='/usr/bin/quickshell')
        which.start()
        self.addCleanup(which.stop)
        self.calls = []

    def fake_quickshell(self, draw=True):
        def run(args, env=None, **kw):
            folder = args[args.index('-p') + 1]
            with open(os.path.join(folder, 'event.json')) as f:
                event = json.load(f)
            self.calls.append({'args': args, 'env': env, 'event': event,
                               'commons': os.path.realpath(os.path.join(folder, 'Commons'))})
            if draw:
                with open(os.path.join(folder, 'platinum.png'), 'wb') as f:
                    f.write(b'\x89PNG fake')
        return run

    def test_draws_offscreen_on_the_gpu_and_moves_the_image_in(self):
        out = os.path.join(self.tmp.name, 'Pictures', 'omatrophy', 'starfall-odyssey-platinum.png')
        ev = {'game': 'Starfall Odyssey', 'hero': 'https://cdn.example/h.jpg', 'header': ''}
        self.assertEqual(share.render(ev, out, run=self.fake_quickshell(), shell_dir=self.shell), out)
        with open(out, 'rb') as f:
            self.assertEqual(f.read(), b'\x89PNG fake')
        call = self.calls[0]
        self.assertEqual(call['env']['QT_QPA_PLATFORM'], 'offscreen')
        self.assertEqual(call['env']['QSG_RHI_BACKEND'], 'opengl')
        self.assertEqual(call['commons'], os.path.join(self.shell, 'Commons'))
        # A web URL is dropped, not handed to the shell to fetch.
        self.assertEqual(call['event']['hero'], '')

    def test_a_link_at_out_is_replaced_not_written_through(self):
        victim = os.path.join(self.tmp.name, 'victim')
        with open(victim, 'w') as f:
            f.write('precious')
        out = os.path.join(self.tmp.name, 'out.png')
        os.symlink(victim, out)
        share.render({'game': 'x'}, out, run=self.fake_quickshell(), shell_dir=self.shell)
        with open(victim) as f:
            self.assertEqual(f.read(), 'precious')
        self.assertFalse(os.path.islink(out))
        self.assertEqual(os.stat(out).st_mode & 0o777, 0o644)

    def test_a_swapped_temporary_file_never_gets_the_players_file_chmodded(self):
        # Marketplace review finding 11: another user who can write in the
        # output folder swaps the temporary name for a link to a private
        # file mid-copy; a chmod by path would make that file 0644.
        private = os.path.join(self.tmp.name, 'private')
        with open(private, 'w') as f:
            f.write('secret')
        os.chmod(private, 0o600)
        out = os.path.join(self.tmp.name, 'shared', 'out.png')
        os.makedirs(os.path.dirname(out))
        copy = share.shutil.copyfileobj

        def copy_then_swap(src, dst):
            copy(src, dst)
            folder = os.path.dirname(out)
            tmp = next(os.path.join(folder, n) for n in os.listdir(folder) if n.endswith('.tmp'))
            os.unlink(tmp)
            os.symlink(private, tmp)

        with mock.patch.object(share.shutil, 'copyfileobj', copy_then_swap):
            share.render({'game': 'x'}, out, run=self.fake_quickshell(), shell_dir=self.shell)
        self.assertEqual(os.stat(private).st_mode & 0o777, 0o600)

    def test_another_theme_gets_a_home_of_its_own(self):
        out = os.path.join(self.tmp.name, 'out.png')
        share.render({'game': 'x'}, out, run=self.fake_quickshell(), shell_dir=self.shell, theme='/themes/white')
        self.assertNotEqual(self.calls[0]['env']['HOME'], os.environ.get('HOME'))

    def test_no_image_says_what_to_try(self):
        out = os.path.join(self.tmp.name, 'out.png')
        with self.assertRaises(RuntimeError) as e:
            share.render({'game': 'x'}, out, run=self.fake_quickshell(draw=False), shell_dir=self.shell)
        self.assertIn('drew no image', str(e.exception))
        self.assertFalse(os.path.exists(out))

    def test_without_omarchys_shell(self):
        with self.assertRaises(RuntimeError) as e:
            share.render({'game': 'x'}, 'out.png', run=self.fake_quickshell(), shell_dir=self.tmp.name + '/none')
        self.assertIn("Omarchy's shell", str(e.exception))


class ShareEvent(unittest.TestCase):
    def test_a_finished_game(self):
        store = FakeStore([ach('A', True, 100), ach('B', True, 300)], {'hero': '', 'header': ''})
        ev = omatrophy.share_event(store, '1', store.achs, 'vector')
        self.assertEqual(ev['type'], 'platinum')
        self.assertEqual((ev['total'], ev['first'], ev['last'], ev['platinum']), (2, 100, 300, 300))
        self.assertEqual((ev['store_name'], ev['icon_set']), ('Steam', 'vector'))

    def test_not_finished_gets_none(self):
        store = FakeStore([ach('A', True, 100), ach('B', False)])
        self.assertIsNone(omatrophy.share_event(store, '1', store.achs))

    def test_unknown_icon_set_falls_back(self):
        store = FakeStore([ach('A', True, 100)])
        self.assertEqual(omatrophy.share_event(store, '1', store.achs, '../x')['icon_set'], 'omarchy')


class ShareArt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        cache = mock.patch.object(omatrophy, 'CACHE', self.tmp.name)
        cache.start()
        self.addCleanup(cache.stop)

    def test_missing_art_is_fetched_once_then_local(self):
        url = 'https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1/header.jpg'
        fetched = []

        def fetch(urls):
            fetched.extend(urls)
            for u in urls:
                path = f'{self.tmp.name}/{omatrophy.image_name(u)}'
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, 'wb') as f:
                    f.write(b'jpg')

        ev = omatrophy.share_art({'game': 'x', 'header': url, 'hero': ''}, fetch=fetch)
        self.assertEqual(fetched, [url])
        self.assertEqual(ev['header'], f'file://{self.tmp.name}/{omatrophy.image_name(url)}')

    def test_nothing_missing_fetches_nothing(self):
        ev = omatrophy.share_art({'game': 'x', 'header': '', 'hero': 'file:///a.jpg'},
                                 fetch=lambda urls: self.fail('fetched'))
        self.assertEqual(ev['hero'], 'file:///a.jpg')


class OutPath(unittest.TestCase):
    def test_default_and_file_and_folder(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(share.out_path('', 'Starfall Odyssey', home=home, config_home=home + '/c'),
                             f'{home}/Pictures/omatrophy/starfall-odyssey-platinum.png')
            self.assertEqual(share.out_path(f'{home}/x.png', 'Starfall'), f'{home}/x.png')
            self.assertEqual(share.out_path(home, 'Starfall Odyssey'), f'{home}/starfall-odyssey-platinum.png')


class Notify(unittest.TestCase):
    def test_options_end_before_the_text(self):
        with mock.patch.object(share.subprocess, 'run') as run:
            share.notify('-u critical', '--help', image='/x.png')
        args = run.call_args[0][0]
        self.assertEqual(args[-3:], ['--', '-u critical', '--help'])
        self.assertNotIn('shell', run.call_args[1])


class ShareArgs(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(omatrophy.share_args(['steam', '20']), ('steam', '20', '', False))
        self.assertEqual(omatrophy.share_args(['steam', '20', '--notify', '--out', '/x.png']),
                         ('steam', '20', '/x.png', True))
        for bad in ([], ['steam'], ['steam', '20', 'x'], ['steam', '20', '--out'], ['steam', '20', '--zip'],
                    ['steam', 'a:b']):
            with self.subTest(args=bad):
                self.assertIsNone(omatrophy.share_args(bad))


class ShareCommand(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        home = mock.patch.dict(os.environ, {'HOME': self.tmp.name, 'XDG_CONFIG_HOME': self.tmp.name + '/.config'})
        home.start()
        self.addCleanup(home.stop)

    def run_share(self, store, args):
        rendered = []
        with mock.patch.object(omatrophy, 'found_stores', return_value=[store]), \
                mock.patch.object(share, 'render', side_effect=lambda ev, out: rendered.append((ev, out))), \
                mock.patch.object(omatrophy, 'save_images', side_effect=AssertionError('fetched')), \
                redirect_stdout(io.StringIO()) as out:
            omatrophy.share_platinum(args)
        return rendered, out.getvalue().strip()

    def test_saves_to_pictures_and_prints_where(self):
        store = FakeStore([ach('A', True, 100)])
        rendered, printed = self.run_share(store, ['steam', '1'])
        path = f'{self.tmp.name}/Pictures/omatrophy/starfall-odyssey-platinum.png'
        self.assertEqual(printed, path)
        self.assertEqual(rendered[0][1], path)

    def test_refuses_an_unfinished_game(self):
        store = FakeStore([ach('A', True, 100), ach('B', False)])
        with self.assertRaises(SystemExit) as e:
            self.run_share(store, ['steam', '1'])
        self.assertIn('1 / 2', str(e.exception.code))

    def test_usage_names_the_stores(self):
        with self.assertRaises(SystemExit) as e:
            self.run_share(FakeStore([]), ['gog', '1'])
        self.assertIn('usage: omatrophy.py share steam', str(e.exception.code))


class ShareView(unittest.TestCase):
    def test_the_scene_loads_the_card_by_file(self):
        here = os.path.join(os.path.dirname(__file__), '..')
        with open(os.path.join(here, 'PlatinumShare.qml'), encoding='utf-8') as f:
            text = f.read()
        self.assertIn('Qt.resolvedUrl("PlatinumCard.qml")', text)
        self.assertIn('item.still = true', text)
        with open(os.path.join(here, 'PlatinumCard.qml'), encoding='utf-8') as f:
            self.assertIn('function hold()', f.read())


if __name__ == '__main__':
    unittest.main()
