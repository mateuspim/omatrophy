"""The repo is public: tracked files must not carry anything private.

Two layers. Patterns that are never fine in a tracked file (a path inside
someone's home folder, a LAN address, an email address) are checked
everywhere, CI included. The owner's own ids (Steam account, SteamID64, GOG
user and client ids, mount points) can't be told from made-up ones by shape,
so they live one per line in `.private-strings` at the repo root, which is
gitignored: local runs check them, CI (which never has the file) skips it.

Run from the repo root: python3 -m unittest discover -s tests
"""
import os, re, subprocess, unittest

ROOT = os.path.join(os.path.dirname(__file__), '..')
PRIVATE_LIST = os.path.join(ROOT, '.private-strings')
# Binary assets carry no text worth scanning; this file holds the patterns.
SKIP = re.compile(r'\.(png|jpg|jpeg|webp|ogg|wav|ttf|otf)$')
FORBIDDEN = {
    'a path inside a home folder': re.compile(r'/home/[a-z_][a-z0-9_-]*/'),
    'a LAN address': re.compile(r'\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b'),
    'an email address': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[a-z]{2,}\b'),
}


def tracked_files():
    """Tracked text files, relative to the repo root; [] outside a git checkout."""
    try:
        out = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    names = [n for n in out.decode().split('\0') if n and not SKIP.search(n)]
    return [n for n in names if os.path.isfile(os.path.join(ROOT, n)) and not n.endswith('test_hygiene.py')]


def read_text(name):
    with open(os.path.join(ROOT, name), 'rb') as f:
        return f.read().decode('utf8', 'replace')


def private_strings(path=PRIVATE_LIST):
    """The owner's private strings, one per line, '#' comments; [] without the file."""
    try:
        with open(path, encoding='utf8') as f:
            return [s.strip() for s in f if s.strip() and not s.lstrip().startswith('#')]
    except OSError:
        return []


def findings(files, read=read_text, secrets=()):
    """[(file, what)] for every forbidden pattern or private string found."""
    found = []
    for name in files:
        text = read(name)
        found += [(name, what) for what, pattern in FORBIDDEN.items() if pattern.search(text)]
        found += [(name, 'a string from .private-strings') for s in secrets if s in text]
    return found


class Hygiene(unittest.TestCase):
    def test_patterns_catch_what_they_should(self):
        texts = {'a': 'cache in /home/someone/.cache', 'b': 'server 192.168.1.20', 'c': 'mail me@example.com',
                 'd': 'file:///home/a.png and 10.5 seconds and noreply', 'e': 'id 1234 here'}
        got = findings(texts, read=texts.get, secrets=['1234'])
        self.assertEqual(got, [('a', 'a path inside a home folder'), ('b', 'a LAN address'),
                               ('c', 'an email address'), ('e', 'a string from .private-strings')])

    def test_private_list_skips_comments_and_blanks(self):
        import tempfile
        with tempfile.NamedTemporaryFile('w', delete=False) as f:
            f.write('# mine\n\n 42 \n')
        self.addCleanup(os.unlink, f.name)
        self.assertEqual(private_strings(f.name), ['42'])
        self.assertEqual(private_strings(f.name + '.missing'), [])

    def test_tracked_files_carry_nothing_private(self):
        files = tracked_files()
        if not files:
            self.skipTest('not a git checkout')
        self.assertEqual(findings(files, secrets=private_strings()), [],
                         'Remove these before committing; the repo is public (AGENTS.md, Public-repo hygiene).')


if __name__ == '__main__':
    unittest.main()
