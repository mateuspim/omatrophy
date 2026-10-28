"""What a game store gives OmaTrophy, and the helpers every store shares.

A store reads achievements from the launcher's local files (or an API) and
answers in plain dicts; omatrophy.py does the diffing, events and toasts.
To add one, subclass Store in stores/<id>.py and list it in stores/__init__.py.
"""
import json, os, tempfile, urllib.error, urllib.parse, urllib.request

STATE = os.path.expanduser('~/.local/state/omatrophy')
CACHE = os.path.expanduser('~/.cache/omatrophy')
# A store page or a rarity list is well under a megabyte; a cap keeps a
# hostile or broken server from filling memory.
MAX_RESPONSE = 8 * 1024 * 1024
# Every network call goes to the store's own HTTPS hosts; a redirect
# elsewhere (or down to http) is refused.
TRUSTED_HOSTS = ('steamcommunity.com', 'steampowered.com', 'steamstatic.com')


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

    def game_name(self, game):
        return f'{self.name} {game}'

    def percents(self, game):
        """{api: share of players} for one game; {} when the store doesn't say."""
        return {}

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


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, value, **kw):
    """Write to a fresh temporary file beside `path`, then rename it over:
    a crash leaves the old file whole, and a symlink at `path` is replaced,
    not followed."""
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.' + os.path.basename(path), suffix='.tmp')
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


def cached(url, name):
    """A local file:// copy of an image, so a card shows complete the moment it slides in; the URL if offline."""
    path = f'{CACHE}/{name}'
    if not os.path.exists(path):
        try:
            body = fetch_bytes(url)[0]
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
            with os.fdopen(fd, 'wb') as f:
                f.write(body)
            os.replace(tmp, path)
        except Exception:
            return url
    return 'file://' + path
