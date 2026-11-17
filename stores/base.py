"""What a game store gives OmaTrophy, and the helpers every store shares.

A store reads achievements from the launcher's local files (or an API) and
answers in plain dicts; omatrophy.py does the diffing, events and toasts.
To add one, subclass Store in stores/<id>.py and list it in stores/__init__.py.
"""
import errno, json, os, secrets, stat, urllib.error, urllib.parse, urllib.request

STATE = os.path.expanduser('~/.local/state/omatrophy')
CACHE = os.path.expanduser('~/.cache/omatrophy')
# A store page or a rarity list is well under a megabyte; a cap keeps a
# hostile or broken server from filling memory.
MAX_RESPONSE = 8 * 1024 * 1024
# Every network call goes to the store's own HTTPS hosts; a redirect
# elsewhere (or down to http) is refused. GOG's achievement icons and
# Heroic's cached store art live on images.gog.com and images.gog-statics.com.
TRUSTED_HOSTS = ('steamcommunity.com', 'steampowered.com', 'steamstatic.com',
                 'gog.com', 'gog-statics.com')


def config():
    """The user's settings; resolved per call so tests can point HOME elsewhere."""
    cfg = read_json(os.path.expanduser('~/.config/omatrophy/config.json'), {})
    return cfg if isinstance(cfg, dict) else {}


class Store:
    """One launcher. Game ids are the store's own, as strings."""

    id = ''      # short and stable: it namespaces game ids and cache files
    name = ''    # shown to people

    def available(self):
        """True when this store is installed and has achievement data to read."""
        return False

    def games(self):
        """{game id: change token} for games with achievement data. The token
        (an mtime, a hash) changes whenever that game's unlocks might have."""
        return {}

    def achievements(self, game):
        """[{api, name, desc, icon, unlocked, time}] for one game: `api` a
        stable key, `icon` an image URL or '' (fetched only
        when that unlock is shown), `time` unix seconds or 0 when unknown.
        Optional keys: `hidden` (the store keeps it secret until unlocked),
        `icon_locked` (the greyed-out icon), on locked counter
        achievements `progress: {value, max}` ("12 of 15"), and `remote`
        (read from an online backfill, not this machine: never toasted)."""
        return []

    def running(self):
        """{'game': id, 'since': unix seconds} for the game being played now, or None."""
        return None

    def recent(self):
        """[(unix seconds, game id)] last played, newest first; [] when the store doesn't say."""
        return []

    def playtime(self):
        """{game id: {'total': minutes played, 'recent': minutes in the past
        two weeks, or None when the store doesn't say}}; {} when it keeps
        no playtime. Optional; the panel's Profile tab sums it."""
        return {}

    def game_name(self, game):
        return f'{self.name} {game}'

    def percents(self, game):
        """{api: share of players} for one game; {} when the store doesn't say."""
        return {}

    def known_percents(self, game):
        """Rarity this machine already holds, with no network call: what
        library-wide views use, since asking for every game would make the
        panel wait. Stores whose rarity is local answer `percents`."""
        return self.percents(game)

    def percent(self, game, api):
        """Share of players with this achievement, or None when the store doesn't say."""
        return self.percents(game).get(api)

    def backfill(self, say=None):
        """Slowly fill in games this machine has no local data for, from an
        online source, when the user opted in. Optional; runs in the
        watcher's background thread and by `omatrophy.py sync`."""
        return None

    def art(self, game):
        """{'hero': wide art URL or '', 'header': banner URL or ''} for the platinum card."""
        return {'hero': '', 'header': ''}


def started_at(stat, boot, ticks):
    """Unix start time of a process from its /proc/<pid>/stat line."""
    # The command name (field 2) may hold spaces and parentheses; count from the last ')'.
    fields = stat[stat.rindex(')') + 2:].split()
    return boot + int(fields[19]) / ticks


def boot_time(proc='/proc'):
    """Unix time the machine booted, from /proc/stat; 0 when it doesn't say."""
    with open(f'{proc}/stat') as f:
        for line in f:
            if line.startswith('btime '):
                return int(line.split()[1])
    return 0


def read_json(path, default):
    try:
        with open_regular(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


# Safe file access. The marketplace review (findings 9-11, and the
# follow-up review in docs/security-review-1.0.md) assumes another local
# user may be able to write in a loosely permissioned folder we use and
# race us: plant links, FIFOs or hard links, swap names between calls.

def open_regular(path, binary=False):
    """Open `path` to read, only if it is a regular file. Follows a link
    (a dotfiles manager may link config.json), but O_NONBLOCK means a FIFO
    planted there can't hang us, and the type is checked on what opened."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError(f'{path} is not a plain file')
    return os.fdopen(fd, 'rb' if binary else 'r', **({} if binary else {'encoding': 'utf-8', 'errors': 'replace'}))


def read_plain(path, limit):
    """Up to `limit` bytes of `path`, only when `path` itself is a plain
    file: no link followed, checked on the file that opened (no gap
    between a check and the open). OSError otherwise."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as f:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError(f'{path} is not a plain file')
        return f.read(limit)


def open_own(path, flags):
    """Open (creating, 0600) a file we write in place, such as a lock or
    an append-only log: never through a link, never truncated by the open,
    and refused unless it is a plain file of ours with no other name."""
    try:
        fd = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, 0o600)
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise OSError(f'{path} is a link; remove it and try again') from None
        raise
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1:
        os.close(fd)
        raise OSError(f'{path} is not a plain file of yours; remove it and try again')
    return fd


def own_plain(path):
    """`path` itself (no link followed) is a plain file of ours with no
    other name."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and st.st_uid == os.getuid() and st.st_nlink == 1


def touch_marker(path):
    """Create or refresh an empty marker file (a stop request, a "looked,
    none" note); only its existence and time matter. True when done; a
    link, FIFO or someone else's file there is left alone."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = open_own(path, os.O_WRONLY | os.O_CREAT)
    except OSError:
        return False
    try:
        os.utime(fd)
    finally:
        os.close(fd)
    return True


def roots():
    """Every folder OmaTrophy keeps files in; resolved per call so tests
    can point the environment elsewhere."""
    state = os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state')
    data = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return sorted({os.path.expanduser('~/.config/omatrophy'), STATE, CACHE,
                   os.path.join(state, 'omatrophy'), os.path.join(data, 'omatrophy')})


def loose(st):
    """Group or others may create, rename or remove entries in it."""
    return bool(st.st_mode & 0o022)


def private_folder(folder, create=True):
    """Check (and with `create`, make 0700) a folder we keep files in.
    Refused: one not ours, or one others can write in, where another user
    could plant a link, a file or a FIFO for us to use. A link to a folder
    is fine when the link is ours too (only we can have made it). Never
    chmods: the player decides (AGENTS.md: never change their files on load)."""
    odd = odd_root(folder)
    if odd:
        raise OSError(odd)
    if create:
        os.makedirs(folder, mode=0o700, exist_ok=True)
    link = os.lstat(folder)
    st = os.stat(folder) if stat.S_ISLNK(link.st_mode) else link
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or link.st_uid != os.getuid():
        raise OSError(f'{folder} is not a folder owned by you; move it aside and try again')
    if loose(st):
        raise OSError(f'{folder} can be written by other users; run `chmod go-w {folder}` and try again')
    if stat.S_ISLNK(link.st_mode):
        risk = swap_risk(folder)
        if risk:
            raise OSError(risk)


# Linux's own limit on links followed while resolving one path.
MAX_HOPS = 40


def consulted_folders(path):
    """Every folder whose entries are read while resolving `path`, link by
    link, as the kernel does: the folders above it and, for each link on
    the way (a link to a link too), the folders above where it leads.
    Whoever can rename in any of them can redirect `path`; realpath would
    collapse an intermediate link and hide its folder (finding 22). Stops
    at the first missing name: the rest doesn't exist yet and is made by
    us under a folder already listed."""
    found = ['/']
    # Never abspath: it drops `link/..` as text, while the kernel follows
    # the link first and `..` leaves where it leads (finding 23). getcwd
    # is already link-free.
    start = path if path.startswith('/') else os.path.join(os.getcwd(), path)
    pending = [p for p in start.split('/') if p]
    here = '/'
    hops = 0
    while pending:
        name = pending.pop(0)
        if name == '.':
            continue
        if name == '..':
            here = os.path.dirname(here)
            continue
        if here not in found:
            found.append(here)
        step = os.path.join(here, name)
        try:
            st = os.lstat(step)
        except OSError:
            break
        if not stat.S_ISLNK(st.st_mode):
            here = step
            continue
        hops += 1
        if hops > MAX_HOPS:
            raise OSError(f'{path} goes through too many links')
        target = os.readlink(step)
        if target.startswith('/'):
            here = '/'
        pending[:0] = [p for p in target.split('/') if p]
    return found


def odd_root(path):
    """Why `path` can't be one of OmaTrophy's folders, as a message; ''
    when fine. It must be absolute with no `.` or `..` in it: Python's
    path helpers (abspath, and mkstemp through it) read those as text,
    the kernel after following links, so the two could name different
    folders (finding 23). The XDG spec ignores relative paths too."""
    if not path.startswith('/'):
        return f'{path} is not an absolute path; set it to one (or unset it) and try again'
    if any(p in ('.', '..') for p in path.split('/')):
        return f'{path} has `.` or `..` in it; set it to a plain absolute path and try again'
    return ''


def temp_beside(path):
    """(fd, name) of a new 0600 file in `path`'s folder to write and then
    rename over `path`. Like mkstemp, but the folder is named exactly as
    `path` names it: mkstemp abspaths it, so with a `link/..` in the path
    the temporary file and the rename could land in different folders
    (finding 23). O_EXCL|O_NOFOLLOW: never an existing file or a link."""
    folder, base = os.path.split(path)
    for _ in range(100):
        tmp = os.path.join(folder, f'.{base}.{secrets.token_hex(6)}.tmp')
        try:
            fd = os.open(tmp, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        except FileExistsError:
            continue
        return fd, tmp
    raise FileExistsError(f'no free temporary name beside {path}')


def swap_risk(path):
    """Why another user could swap `path` (or what it leads to) for a
    folder of theirs, as a message; '' when nobody can. Every folder read
    while resolving it (consulted_folders) must belong to us or root
    (whoever owns a folder can rename anything in it, whatever its mode),
    and one others can write in needs the sticky bit. Marketplace review
    findings 20 to 22: checking only the nearest parent, only others'
    write bits, or only the realpath left a folder out."""
    try:
        chain = consulted_folders(path)
    except OSError as e:
        return f'{e}; point it at a folder of yours directly and try again'
    for folder in chain:
        try:
            st = os.stat(folder)
        except OSError:
            continue  # not made yet: makedirs creates it as ours
        if st.st_uid not in (os.getuid(), 0):
            return (f'{folder} belongs to another user, who could swap {path}; '
                    f'keep OmaTrophy\'s folders under folders of yours and try again')
        if loose(st) and not st.st_mode & stat.S_ISVTX:
            return (f'{folder} can be written by other users, who could swap {path}; '
                    f'run `chmod go-w {folder}` and try again')
    return ''


def folder_problems():
    """What is unsafe about OmaTrophy's folders, as messages; [] when all
    is well. No root may sit where another user could swap it (swap_risk),
    and each existing root and every folder in it must pass
    private_folder. Read only: changes nothing."""
    problems = []
    for root in roots():
        risk = odd_root(root) or swap_risk(root)
        if risk:
            problems.append(risk)
            continue
        if not os.path.lexists(root):
            continue
        try:
            private_folder(root, create=False)
        except OSError as e:
            problems.append(str(e))
            continue
        for here, dirs, _ in os.walk(root):
            for name in dirs:
                try:
                    private_folder(os.path.join(here, name), create=False)
                except OSError as e:
                    problems.append(str(e))
    return problems


def write_json(path, value, **kw):
    """Write to a fresh temporary file beside `path`, then rename it over:
    a crash leaves the old file whole, and a symlink at `path` is replaced,
    not followed."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = temp_beside(path)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(value, f, **kw)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def trusted_url(url):
    """True for an https URL on one of the stores' own hosts."""
    try:
        u = urllib.parse.urlsplit(str(url))
    except ValueError:
        return False
    host = (u.hostname or '').lower()
    return u.scheme == 'https' and any(host == h or host.endswith('.' + h) for h in TRUSTED_HOSTS)


class TrustedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not trusted_url(newurl):
            raise urllib.error.HTTPError(newurl, code, f'refused redirect to {newurl}', headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


OPENER = urllib.request.build_opener(TrustedRedirects)


def fetch_bytes(url):
    """The body at a trusted URL, at most MAX_RESPONSE bytes, with a 4 s
    socket timeout; raises on anything else. Returns (body, final URL)."""
    if not trusted_url(url):
        raise ValueError(f'refused untrusted URL {url}')
    req = urllib.request.Request(url, headers={'User-Agent': 'omatrophy'})
    with OPENER.open(req, timeout=4) as r:
        body = r.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            raise ValueError(f'response from {url} is over {MAX_RESPONSE} bytes')
        return body, r.geturl()


def http_json(url):
    return json.loads(fetch_bytes(url)[0])


def shown_image(value):
    """An image the shell may load: a local file:// one or an https URL on a
    store's host; '' for anything else. The shell's Image fetches any URL it
    is given (plain http too), and some come from files other programs
    write (Comet's database, Heroic's library cache)."""
    value = value if isinstance(value, str) else ''
    return value if value.startswith('file://') or trusted_url(value) else ''


def cached(url, name):
    """A local file:// copy of an image, so a card shows complete the moment
    it slides in; the URL if offline; '' for a URL off the stores' hosts,
    which the shell would otherwise load itself."""
    if not trusted_url(url):
        return ''
    path = f'{CACHE}/{name}'
    if os.path.lexists(path):
        # Only a plain file of ours with no other name: a link here could
        # point the card (and a saved image) at any file we can read.
        return 'file://' + path if own_plain(path) else url
    try:
        body = fetch_bytes(url)[0]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd, tmp = temp_beside(path)
        with os.fdopen(fd, 'wb') as f:
            f.write(body)
        os.replace(tmp, path)
    except Exception:
        return url
    return 'file://' + path
