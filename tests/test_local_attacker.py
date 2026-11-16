"""Another local user who can write in a folder OmaTrophy uses, or read
process command lines: findings 12-21 of docs/security-review-1.0.md
(12-19 from the follow-up review after the marketplace's, 20 and 21 from
the marketplace's re-checks of 1.0.2 and 1.0.3). Every file lives in a
temporary folder; nothing touches the owner's folders."""
import io, os, stat, sys, tempfile, threading, unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import guide_agents, guide_maker, guides, omatrophy, share  # noqa: E402
from stores import base, steam_loader  # noqa: E402


class Temp(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        self.tmp = d.name
        self.victim = os.path.join(self.tmp, 'victim')
        with open(self.victim, 'w') as f:
            f.write('precious')

    def assert_victim_whole(self):
        with open(self.victim) as f:
            self.assertEqual(f.read(), 'precious')


class StopFiles(Temp):
    # Finding 12: Stop wrote its marker with open(..., 'w').
    def test_guide_stop_does_not_truncate_through_a_link(self):
        jobs = guide_maker.jobs_dir(self.tmp)
        os.makedirs(jobs)
        os.symlink(self.victim, guide_maker.stop_path(self.tmp, 'steam', '1'))
        guide_maker.request_stop(self.tmp, 'steam', '1')
        self.assert_victim_whole()

    def test_steam_load_stop_does_not_truncate_through_a_link(self):
        with mock.patch.object(steam_loader, 'CACHE', self.tmp):
            os.makedirs(steam_loader.cache_dir())
            os.symlink(self.victim, steam_loader.stop_path())
            steam_loader.request_stop()
        self.assert_victim_whole()

    def test_a_stop_still_works(self):
        guide_maker.request_stop(self.tmp, 'steam', '1')
        self.assertTrue(os.path.isfile(guide_maker.stop_path(self.tmp, 'steam', '1')))


class Folders(Temp):
    # Finding 13: only by-hand's folder was checked.
    def setUp(self):
        super().setUp()
        self.home = os.path.join(self.tmp, 'home')
        os.mkdir(self.home, 0o700)
        env = mock.patch.dict(os.environ, {'HOME': self.home, 'XDG_STATE_HOME': '', 'XDG_DATA_HOME': ''})
        env.start()
        self.addCleanup(env.stop)
        for name, path in (('STATE', '.local/state/omatrophy'), ('CACHE', '.cache/omatrophy')):
            patch = mock.patch.object(base, name, os.path.join(self.home, path))
            patch.start()
            self.addCleanup(patch.stop)
        self.config = os.path.join(self.home, '.config', 'omatrophy')

    def test_no_folders_yet_is_fine(self):
        self.assertEqual(base.folder_problems(), [])

    def test_private_folders_are_fine(self):
        os.makedirs(os.path.join(self.config, 'sub'), mode=0o755)
        self.assertEqual(base.folder_problems(), [])

    def test_a_folder_others_can_write_is_named_with_the_fix(self):
        os.makedirs(self.config)
        os.chmod(self.config, 0o775)
        self.assertEqual(base.folder_problems(),
                         [f'{self.config} can be written by other users; run `chmod go-w {self.config}` and try again'])

    def test_a_loose_subfolder_is_found(self):
        sub = os.path.join(self.home, '.cache', 'omatrophy', 'art')
        os.makedirs(sub)
        os.chmod(sub, 0o777)
        self.assertEqual(len(base.folder_problems()), 1)
        self.assertIn(sub, base.folder_problems()[0])

    def test_a_parent_others_can_swap_it_in_is_refused_unless_sticky(self):
        parent = os.path.join(self.home, '.config')
        os.makedirs(parent)
        os.chmod(parent, 0o777)
        self.assertIn('could swap', base.folder_problems()[0])
        os.chmod(parent, 0o777 | stat.S_ISVTX)
        self.assertEqual(base.folder_problems(), [])

    def test_every_command_refuses_and_says_what_to_fix(self):
        os.makedirs(self.config)
        os.chmod(self.config, 0o777)
        with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
            omatrophy.main(['omatrophy.py', 'running'])
        self.assertIn(f'chmod go-w {self.config}', str(e.exception))


class LinkedFolders(Folders):
    # Finding 20: a linked folder passed when the link was ours, though
    # the real folder sat where others could swap it for their own.
    def link_cache(self, mode):
        shared = os.path.join(self.tmp, 'shared')
        os.mkdir(shared)
        os.chmod(shared, mode)
        real = os.path.join(shared, 'omatrophy')
        os.mkdir(real, 0o700)
        os.makedirs(os.path.join(self.home, '.cache'))
        os.symlink(real, base.CACHE)
        return shared

    def test_a_link_into_a_swappable_folder_is_refused(self):
        shared = self.link_cache(0o777)
        problems = base.folder_problems()
        self.assertEqual(len(problems), 1)
        self.assertIn(f'chmod go-w {shared}', problems[0])

    def test_a_link_into_a_sticky_or_private_folder_is_fine(self):
        shared = self.link_cache(0o777 | stat.S_ISVTX)
        self.assertEqual(base.folder_problems(), [])
        os.chmod(shared, 0o755)
        self.assertEqual(base.folder_problems(), [])


    # Finding 21: a real folder under another user's 0755 folder passed;
    # whoever owns a folder can rename in it whatever its mode.
    def owned_by_another(self, folder):
        real_stat = os.stat

        def fake(path, *a, **kw):
            st = real_stat(path, *a, **kw)
            if os.path.abspath(path) == folder:
                return os.stat_result((st.st_mode, st.st_ino, st.st_dev, st.st_nlink,
                                       os.getuid() + 1, st.st_gid, st.st_size,
                                       st.st_atime, st.st_mtime, st.st_ctime))
            return st
        patch = mock.patch.object(base.os, 'stat', fake)
        patch.start()
        self.addCleanup(patch.stop)

    def test_a_link_into_another_users_folder_is_refused_whatever_its_mode(self):
        shared = self.link_cache(0o755)
        self.owned_by_another(shared)
        problems = base.folder_problems()
        self.assertEqual(len(problems), 1)
        self.assertIn(f'{shared} belongs to another user', problems[0])

    def test_a_loose_folder_further_up_is_refused(self):
        os.chmod(self.tmp, 0o777)
        self.addCleanup(os.chmod, self.tmp, 0o700)
        problems = base.folder_problems()
        self.assertTrue(problems)
        self.assertIn(f'chmod go-w {self.tmp}', problems[0])

    def test_folders_of_root_are_fine(self):
        # The temporary folder sits in /tmp (root's, sticky) and / (root's).
        self.link_cache(0o755)
        self.assertEqual(base.folder_problems(), [])


class CachedArt(Temp):
    # Finding 20: a link in the cache was handed to the shell as art.
    def setUp(self):
        super().setUp()
        patch = mock.patch.object(base, 'CACHE', self.tmp)
        patch.start()
        self.addCleanup(patch.stop)
        os.mkdir(os.path.join(self.tmp, 'art'))
        self.url = 'https://cdn.akamai.steamstatic.com/steam/apps/1/header.jpg'

    def test_a_link_gives_the_url_not_the_file_it_points_at(self):
        os.symlink(self.victim, os.path.join(self.tmp, 'art', '1.jpg'))
        self.assertEqual(base.cached(self.url, 'art/1.jpg'), self.url)

    def test_a_second_name_for_a_file_is_not_used(self):
        os.link(self.victim, os.path.join(self.tmp, 'art', '1.jpg'))
        self.assertEqual(base.cached(self.url, 'art/1.jpg'), self.url)

    def test_a_plain_copy_of_ours_is_used(self):
        path = os.path.join(self.tmp, 'art', '1.jpg')
        with open(path, 'wb') as f:
            f.write(b'jpg')
        self.assertEqual(base.cached(self.url, 'art/1.jpg'), 'file://' + path)


class ShareArt(Temp):
    # Finding 20: the saved image drew art from its path, which could be
    # swapped between our check and the throwaway shell's load.
    def setUp(self):
        super().setUp()
        self.out = os.path.join(self.tmp, 'render')
        os.mkdir(self.out, 0o700)
        self.art = os.path.join(self.tmp, 'hero.jpg')
        with open(self.art, 'wb') as f:
            f.write(b'art')

    def test_art_is_copied_and_the_copy_drawn(self):
        url = share.art_copy('file://' + self.art, self.out, 'hero')
        self.assertEqual(url, 'file://' + os.path.join(self.out, 'hero'))
        # Swapping the original afterwards changes nothing drawn.
        os.unlink(self.art)
        os.symlink(self.victim, self.art)
        with open(url[len('file://'):], 'rb') as f:
            self.assertEqual(f.read(), b'art')

    def test_a_link_is_left_out(self):
        link = os.path.join(self.tmp, 'link.jpg')
        os.symlink(self.victim, link)
        self.assertEqual(share.art_copy(link, self.out, 'hero'), '')
        self.assertEqual(os.listdir(self.out), [])

    def test_a_second_name_is_left_out(self):
        other = os.path.join(self.tmp, 'other.jpg')
        os.link(self.victim, other)
        self.assertEqual(share.art_copy(other, self.out, 'hero'), '')

    def test_web_art_is_left_out(self):
        self.assertEqual(share.art_copy('https://cdn.example/h.jpg', self.out, 'hero'), '')


class Import(Temp):
    # Finding 14: `importable` looked at the name, then copy_in opened it.
    def test_a_link_swapped_in_after_the_check_is_not_copied(self):
        src = os.path.join(self.tmp, 'x.md')
        os.symlink(self.victim, src)
        target = os.path.join(self.tmp, 'guides', 'x.md')
        os.makedirs(os.path.dirname(target))
        with self.assertRaises(OSError):
            guides.copy_in(src, target)
        self.assertFalse(os.path.exists(target))

    def test_import_skips_it_and_carries_on(self):
        source, folder = os.path.join(self.tmp, 'shared'), os.path.join(self.tmp, 'guides')
        os.mkdir(source)
        with open(os.path.join(source, 'a-1.md'), 'w') as f:
            f.write('## Achievements\n')
        os.symlink(self.victim, os.path.join(source, 'a-1.plan.json'))
        with mock.patch.object(guides, 'importable', return_value=True):
            self.assertEqual(guides.import_guides(source, folder=folder), (1, 0))
        self.assertEqual(os.listdir(folder), ['a-1.md'])


class SavedSources(Temp):
    # Finding 15: a link among saved pages went into the agent's prompt.
    def test_a_link_is_skipped(self):
        folder = os.path.join(self.tmp, 'sources')
        os.mkdir(folder)
        os.symlink(self.victim, os.path.join(folder, 'notes.txt'))
        with open(os.path.join(folder, 'page.txt'), 'w') as f:
            f.write('a saved page')
        found = guide_maker.saved_sources(folder)
        self.assertEqual(list(found), ['file:page.txt'])
        self.assertNotIn('precious', repr(found))


class JailEnv(unittest.TestCase):
    # Finding 16: `--env NAME=VALUE` put a secret in ai-jail's command line.
    def test_a_value_is_refused_with_the_safe_forms(self):
        for words in (['--env', 'OPENAI_API_KEY=sk-x'], ['--env=OPENAI_API_KEY=sk-x']):
            with self.subTest(words=words), self.assertRaises(SystemExit) as e:
                guide_agents.jail_options(words)
            self.assertIn('--env-from-file', str(e.exception))
            self.assertNotIn('sk-x', str(e.exception))

    def test_a_name_alone_is_fine(self):
        self.assertEqual(guide_agents.jail_options(['--env', 'OPENAI_API_KEY']), ['--env', 'OPENAI_API_KEY'])


class Inbox(Temp):
    # Finding 17: the Try button appended through a link at the inbox.
    def setUp(self):
        super().setUp()
        self.inbox = os.path.join(self.tmp, 'inbox.jsonl')
        for name, value in (('STATE', self.tmp), ('INBOX', self.inbox)):
            patch = mock.patch.object(omatrophy, name, value)
            patch.start()
            self.addCleanup(patch.stop)

    def test_test_refuses_a_link(self):
        os.symlink(self.victim, self.inbox)
        # No launcher here (nor in CI): a made-up game, so the inbox is reached.
        with mock.patch.object(omatrophy, 'sample_game', return_value=()), \
                mock.patch.object(omatrophy, 'sample_event', return_value={'type': 'unlock', 'game': 'G'}), \
                self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
            omatrophy.test('gold')
        self.assertIn('is a link', str(e.exception))
        self.assert_victim_whole()

    def test_drain_does_not_read_through_a_link(self):
        with open(self.victim, 'w') as f:
            f.write('{"type": "unlock", "game": "Fake", "name": "Fake"}\n')
        os.symlink(self.victim, self.inbox)
        with mock.patch.object(omatrophy, 'emit_line') as emit:
            omatrophy.drain_inbox(0)
        emit.assert_not_called()


class Fifo(Temp):
    # Finding 18: a FIFO planted where we read or mark hung the process.
    def run_briefly(self, call):
        done = []
        t = threading.Thread(target=lambda: done.append(call()), daemon=True)
        t.start()
        t.join(3)
        self.assertTrue(done, 'blocked on a FIFO')
        return done[0]

    def test_read_json_on_a_fifo_gives_the_default(self):
        path = os.path.join(self.tmp, 'x.json')
        os.mkfifo(path)
        self.assertEqual(self.run_briefly(lambda: base.read_json(path, {'d': 1})), {'d': 1})

    def test_a_marker_on_a_fifo_is_left_alone(self):
        path = os.path.join(self.tmp, 'stop')
        os.mkfifo(path)
        self.assertFalse(self.run_briefly(lambda: base.touch_marker(path)))


class Notify(unittest.TestCase):
    # Finding 19: text starting with '-' read as a notify-send option.
    def test_text_comes_after_a_double_dash(self):
        with mock.patch.object(guide_maker.subprocess, 'run') as run:
            guide_maker.notify('Guide failed', '--help')
        argv = run.call_args[0][0]
        self.assertLess(argv.index('--'), argv.index('Guide failed'))


if __name__ == '__main__':
    unittest.main()
