"""What a game store gives OmaTrophy, and the helpers every store shares.

A store reads achievements from the launcher's local files (or an API) and
answers in plain dicts; omatrophy.py does the diffing, events and toasts.
To add one, subclass Store in stores/<id>.py and list it in stores/__init__.py.
"""
import json, os, urllib.request

STATE = os.path.expanduser('~/.local/state/omatrophy')
CACHE = os.path.expanduser('~/.cache/omatrophy')


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
        when that unlock is shown), `time` unix seconds or 0 when unknown."""
        return []

    def game_name(self, game):
        return f'{self.name} {game}'

    def percent(self, game, api):
        """Share of players with this achievement, or None when the store doesn't say."""
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
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(value, f, **kw)


def http_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'omatrophy'})
    with urllib.request.urlopen(req, timeout=4) as r:
        return json.load(r)


def cached(url, name):
    """A local file:// copy of an image, so a card shows complete the moment it slides in; the URL if offline."""
    path = f'{CACHE}/{name}'
    if not os.path.exists(path):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'omatrophy'})
            with urllib.request.urlopen(req, timeout=4) as r:
                body = r.read()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(body)
        except Exception:
            return url
    return 'file://' + path
