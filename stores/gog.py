"""GOG, from the database Comet keeps while a game runs through Heroic.

Heroic Games Launcher starts Comet (an open-source GOG Galaxy service,
github.com/imLinguin/comet) beside every GOG game. Comet answers the game's
Galaxy SDK calls and keeps one SQLite database per game and GOG user:
$XDG_DATA_HOME/comet/gameplay/<client id>/<user id>/gameplay.db, rewritten on
each unlock, with names, icons, unlock times and GOG's own rarity (ADR 12).

The database is keyed by the game's Galaxy client id; Heroic knows games by
product id. Each install folder's goggame-<product>.info names both, so the
pair is read from there and remembered, and a game uninstalled since still
shows under its product id. Titles and art come from Heroic's library cache,
last-played times from Heroic's timestamp.json. Nothing here goes online
and Heroic's GOG login (gog_store/auth.json) is never read.
"""
import os, sqlite3, time
from datetime import datetime, timezone

from .base import STATE, Store, boot_time, cached, read_json, started_at, write_json

CLIENTS = f'{STATE}/gog-clients.json'
FLATPAK = '~/.var/app/com.heroicgameslauncher.hgl'
# Comet holds a write lock for a moment per unlock; waiting this long rides
# that out without stalling the watcher's one-second tick.
DB_TIMEOUT = 0.5
# GOG's product and client ids are decimal; a client id has 17 digits. Ids
# end up in file paths, so anything else is ignored.
MAX_ID_DIGITS = 20


def gog_id(value):
    """True for a GOG product or client id: ASCII digits only."""
    value = str(value)
    return value.isascii() and value.isdigit() and len(value) <= MAX_ID_DIGITS


def heroic_dirs():
    """Heroic's config folders that exist, native first (env HEROIC_DIR overrides)."""
    env = os.environ.get('HEROIC_DIR')
    if env:
        cands = [env]
    else:
        config_home = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
        cands = [f'{config_home}/heroic', os.path.expanduser(f'{FLATPAK}/config/heroic')]
    return [c for c in cands if os.path.isdir(c)]


def comet_dirs():
    """Comet's gameplay folders that exist (env COMET_DIR overrides). Inside
    the Heroic Flatpak, XDG_DATA_HOME is the app's own data folder (unverified)."""
    env = os.environ.get('COMET_DIR')
    if env:
        cands = [env]
    else:
        data_home = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
        cands = [f'{data_home}/comet/gameplay', os.path.expanduser(f'{FLATPAK}/data/comet/gameplay')]
    return [c for c in cands if os.path.isdir(c)]


def mtime(path):
    try:
        return os.stat(path).st_mtime
    except OSError:
        return 0.0


def db_token(db):
    """When a database last changed, counting its -wal and -journal files:
    with WAL on, an unlock lands in the -wal file and the main file keeps its
    time until a checkpoint. Comet 0.x uses the default rollback journal."""
    return max(mtime(db), mtime(db + '-wal'), mtime(db + '-journal'))


def find_databases(roots):
    """{client id: gameplay.db path}, picking the most recently written user
    folder when more than one GOG account has played a game here."""
    out, best = {}, {}
    for root in roots:
        try:
            clients = list(os.scandir(root))
        except OSError:
            continue
        for client in clients:
            if not gog_id(client.name) or not client.is_dir():
                continue
            try:
                users = list(os.scandir(client.path))
            except OSError:
                continue
            for user in users:
                db = os.path.join(user.path, 'gameplay.db')
                if not gog_id(user.name) or not os.path.isfile(db):
                    continue
                token = db_token(db)
                if token > best.get(client.name, -1):
                    out[client.name], best[client.name] = db, token
    return out


def installed_games(heroic):
    """[(product id, install path)] from Heroic's gog_store/installed.json."""
    rows = read_json(f'{heroic}/gog_store/installed.json', {})
    rows = rows.get('installed', []) if isinstance(rows, dict) else []
    return [(str(r['appName']), str(r['install_path'])) for r in rows
            if isinstance(r, dict) and gog_id(r.get('appName')) and r.get('install_path')]


def client_of(install_path, product):
    """(client id, name) from an install's goggame-<product>.info, or None."""
    info = read_json(os.path.join(install_path, f'goggame-{product}.info'), {})
    if not isinstance(info, dict) or not gog_id(info.get('clientId')):
        return None
    return str(info['clientId']), str(info.get('name') or '')


def library(heroic):
    """{product id: library entry} from Heroic's GOG store cache."""
    games = read_json(f'{heroic}/store_cache/gog_library.json', {})
    games = games.get('games', []) if isinstance(games, dict) else []
    return {str(g['app_name']): g for g in games if isinstance(g, dict) and gog_id(g.get('app_name'))}


def unix_time(text):
    """Unix seconds from Comet's RFC 3339 unlock time, or 0. A time without a
    zone is read as UTC, which is what Comet writes."""
    if not text:
        return 0
    try:
        when = datetime.fromisoformat(str(text).replace('Z', '+00:00'))
    except ValueError:
        return 0
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return int(when.timestamp())


def read_rows(db):
    """Every row of Comet's achievement table, read-only. Raises
    sqlite3.Error while Comet holds the lock or mid-write."""
    # mode=ro, never immutable=1: Comet rewrites this file while the game runs.
    conn = sqlite3.connect(f'file:{db}?mode=ro', uri=True, timeout=DB_TIMEOUT)
    try:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            'SELECT key, name, description, visible_while_locked, unlock_time,'
            ' image_url_locked, image_url_unlocked, rarity FROM achievement ORDER BY id')]
    finally:
        conn.close()


def busy(error):
    """True when Comet holds the database's lock, the one failure worth
    retrying next second; SQLite says so only in the message."""
    text = str(error).lower()
    return isinstance(error, sqlite3.OperationalError) and ('locked' in text or 'busy' in text)


def achievement(row):
    """One Comet row as the store contract's dict. An unlock not yet synced
    to GOG (`changed` = 1) has its unlock_time already, so it counts."""
    when = unix_time(row.get('unlock_time'))
    return {'api': str(row['key']), 'name': str(row.get('name') or row['key']),
            'desc': str(row.get('description') or ''),
            'icon': str(row.get('image_url_unlocked') or ''),
            'icon_locked': str(row.get('image_url_locked') or ''),
            'hidden': not row.get('visible_while_locked'),
            'unlocked': bool(row.get('unlock_time')), 'time': when}


def rarity(rows):
    """{key: percent of GOG players}. Comet's column defaults to 0.0 until it
    has fetched GOG's numbers, so 0 reads as unknown, not as the rarest."""
    out = {}
    for r in rows:
        try:
            pct = float(r.get('rarity') or 0)
        except (TypeError, ValueError):
            continue
        if pct > 0:
            # Comet stores a float32: 54.099998 is GOG's 54.1.
            out[str(r['key'])] = round(pct, 2)
    return out


def played_at(text):
    """Unix seconds from Heroic's lastPlayed (`2026-11-03T23:18:17.957Z`), or 0."""
    return unix_time(text) if isinstance(text, str) else 0


def path_args(install_path):
    """How a process's arguments name a file in this install: the Linux path,
    or the Wine `Z:` drive path Proton and Wine pass to a Windows game
    (unverified on a running GOG game)."""
    base = install_path.rstrip('/')
    return (base + '/').encode(), ('z:' + base.replace('/', '\\') + '\\').lower().encode()


def running_install(installs, proc='/proc'):
    """{'game': product id, 'since': unix seconds} for the earliest process
    whose arguments point into a GOG install folder, or None."""
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return None
    prefixes = [(product, path_args(path)) for product, path in installs]
    found = None
    for pid in pids:
        try:
            with open(f'{proc}/{pid}/cmdline', 'rb') as f:
                args = f.read().split(b'\0')
            product = next((p for p, (unix, wine) in prefixes
                            if any(a.startswith(unix) or a.lower().startswith(wine) for a in args)), None)
            if not product:
                continue
            with open(f'{proc}/{pid}/stat') as f:
                since = int(started_at(f.read(), boot_time(proc), os.sysconf('SC_CLK_TCK')))
        except (OSError, ValueError, IndexError):
            continue
        if found is None or since < found['since']:
            found = {'game': product, 'since': since}
    return found


class Gog(Store):
    id = 'gog'
    name = 'GOG'

    def __init__(self):
        self.heroic = heroic_dirs()
        self.comet = comet_dirs()
        # {game id: (token, rows)}: the panel and the tracker ask for the
        # same game's achievements and rarity several times per read.
        self.rows = {}
        # Games whose last read failed (Comet held the lock): games() hands
        # them a fresh token each tick so the watcher reads them again.
        self.retry = set()
        self.installed_token = None
        self.clients = {}

    def available(self):
        return bool(self.comet and find_databases(self.comet))

    def client_map(self):
        """{client id: {'product', 'name'}} for every GOG game ever seen
        installed. Read again only when installed.json changes; pairs are
        remembered in the state folder so they outlive an uninstall or an
        unmounted game drive."""
        token = tuple(mtime(f'{h}/gog_store/installed.json') for h in self.heroic)
        if token == self.installed_token:
            return self.clients
        known = read_json(CLIENTS, {})
        known = {c: v for c, v in known.items() if gog_id(c) and isinstance(v, dict)
                 and gog_id(v.get('product'))} if isinstance(known, dict) else {}
        found = {}
        for heroic in self.heroic:
            for product, path in installed_games(heroic):
                pair = client_of(path, product)
                if pair:
                    found[pair[0]] = {'product': product, 'name': pair[1]}
        if any(known.get(c) != v for c, v in found.items()):
            known.update(found)
            try:
                write_json(CLIENTS, known)
            except OSError:
                pass
        self.installed_token, self.clients = token, known
        return known

    def databases(self):
        """{game id: gameplay.db}: the product id where known, else the client id."""
        clients = self.client_map()
        return {clients.get(c, {}).get('product', c): db for c, db in find_databases(self.comet).items()}

    def games(self):
        now = time.time()
        return {game: now if game in self.retry else db_token(db) for game, db in self.databases().items()}

    def read(self, game):
        """Comet's rows for one game, reread only when its database changed;
        the last good copy while Comet holds the lock."""
        db = self.databases().get(game) if gog_id(game) else None
        if not db:
            return []
        token = db_token(db)
        old = self.rows.get(game)
        if old and old[0] == token:
            return old[1]
        try:
            rows = read_rows(db)
        except sqlite3.Error as e:
            if not busy(e):
                # Not Comet's layout, or not a database: nothing to read
                # until the file changes again. A Comet killed mid-write
                # leaves a hot journal that only a writer may roll back
                # (SQLITE_READONLY_ROLLBACK) until Comet opens the file
                # again, so the last good copy stands in until then.
                rows = old[1] if old else []
            else:
                self.retry.add(game)
                if old:
                    return old[1]
                raise
        self.retry.discard(game)
        self.rows[game] = (token, rows)
        return rows

    def achievements(self, game):
        return [achievement(r) for r in self.read(game)]

    def percents(self, game):
        try:
            return rarity(self.read(game))
        except sqlite3.Error:
            return {}

    def entry(self, game):
        """Heroic's library entry for a product id, or {}."""
        for heroic in self.heroic:
            found = library(heroic).get(game)
            if found:
                return found
        return {}

    def game_name(self, game):
        """Heroic's title, else the name from goggame-*.info, else the id."""
        title = self.entry(game).get('title')
        if title:
            return str(title)
        named = next((v.get('name') for v in self.client_map().values() if v.get('product') == game), '')
        return named or f'GOG {game}'

    def art(self, game):
        """Heroic's cached store art: the wide background for the platinum
        card, the cover for the panel's header frames."""
        g = self.entry(game)
        cover, wide = str(g.get('art_cover') or ''), str(g.get('art_background') or g.get('art_cover') or '')
        hero = cached(wide, f'art/gog_{game}_hero{os.path.splitext(wide.split("?")[0])[1]}') if wide else ''
        return {'hero': hero, 'header': cover}

    def recent(self):
        """[(unix seconds, game id)] from Heroic's lastPlayed, or the
        database's last write when Heroic left that empty."""
        played = {}
        for heroic in self.heroic:
            stamps = read_json(f'{heroic}/store/timestamp.json', {})
            for game, row in (stamps.items() if isinstance(stamps, dict) else ()):
                if gog_id(game) and isinstance(row, dict):
                    played[game] = max(played.get(game, 0), played_at(row.get('lastPlayed')))
        rows = {game: max(played.get(game, 0), int(db_token(db))) for game, db in self.databases().items()}
        return sorted(((t, g) for g, t in rows.items() if t > 0), reverse=True)

    def playtime(self):
        """Heroic's totalPlayed (minutes) per game; Heroic keeps no
        two-week figure, so `recent` is None."""
        out = {}
        for heroic in self.heroic:
            stamps = read_json(f'{heroic}/store/timestamp.json', {})
            for game, row in (stamps.items() if isinstance(stamps, dict) else ()):
                minutes = row.get('totalPlayed') if isinstance(row, dict) else None
                if gog_id(game) and isinstance(minutes, int) and minutes >= 0:
                    out[game] = {'total': max(minutes, out.get(game, {}).get('total', 0)), 'recent': None}
        return out

    def running(self):
        installs = [pair for heroic in self.heroic for pair in installed_games(heroic)]
        return running_install(installs) if installs else None
