"""Steam, from its local stats cache.

Steam writes unlocks to <Steam>/appcache/stats/UserGameStats_<account>_<app>.bin,
so this needs no API key and works with a private profile. Rarity comes from
Steam's public, keyless global-percentages endpoint. What is running comes
from /proc (Steam starts every game through `reaper SteamLaunch AppId=N`),
what was played last from userdata/<account>/config/localconfig.vdf.
"""
import os, re, struct, threading, time

from . import steam_community
from .base import CACHE, STATE, Store, cached, config, http_json, read_json, write_json
from .steam_community import app_id

ICON_BASE = 'https://cdn.fastly.steamstatic.com/steamcommunity/public/images/apps'
ART_BASE = 'https://cdn.fastly.steamstatic.com/steam/apps'
NAMES = f'{STATE}/names.json'
# Global rarity drifts slowly; a day-old copy keeps the panel and the tracker
# from asking Steam on every open.
RARITY_SECONDS = 24 * 3600
# A delisted game's store page answers success: false, every time; without
# remembering that, `games` asked again on each open and waited on it.
NAME_MISS_SECONDS = 24 * 3600
# `omatrophy.py games` looks names up from several threads; the cache file is
# read and rewritten whole, so one writer at a time.
NAMES_LOCK = threading.Lock()
# The largest schema seen is a few megabytes; anything far past that is a
# broken or planted file, not stats.
MAX_KV_BYTES = 64 * 1024 * 1024
# Binary KeyValues nest a handful of levels; a deeper file is corrupt and
# would otherwise end in a RecursionError deep inside the parser.
MAX_KV_DEPTH = 32


def parse_kv(b, pos=0, depth=0):
    """Parse Steam's binary KeyValues format. A truncated or malformed file
    raises ValueError (or struct.error), never loops."""
    if depth > MAX_KV_DEPTH:
        raise ValueError('KeyValues nested too deep')
    d = {}
    while pos < len(b):
        t = b[pos]; pos += 1
        if t == 8:
            return d, pos
        e = b.index(b'\0', pos); k = b[pos:e].decode('utf8', 'replace'); pos = e + 1
        if t == 0:
            v, pos = parse_kv(b, pos, depth + 1)
        elif t == 1:
            e = b.index(b'\0', pos); v = b[pos:e].decode('utf8', 'replace'); pos = e + 1
        elif t in (2, 4, 6):
            v = struct.unpack_from('<i', b, pos)[0]; pos += 4
        elif t == 3:
            v = struct.unpack_from('<f', b, pos)[0]; pos += 4
        elif t == 7:
            v = struct.unpack_from('<Q', b, pos)[0]; pos += 8
        elif t == 5:
            # UTF-16 runs to a two-byte NUL on an even offset; stop at the
            # end of the buffer, or a truncated file spins forever.
            e = pos
            while e + 1 < len(b) and b[e:e + 2] != b'\0\0':
                e += 2
            if e + 1 >= len(b):
                raise ValueError('unterminated UTF-16 value')
            v = b[pos:e].decode('utf-16le', 'replace'); pos = e + 2
        else:
            raise ValueError(f'unknown type {t}')
        d[k] = v
    return d, pos


def parse_text_vdf(text):
    """Parse Steam's text KeyValues (localconfig.vdf, appmanifest)."""
    root, stack, key = {}, [], None
    cur = root
    for quoted, brace in re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text):
        if brace == '{':
            child = {}
            cur[key] = child
            stack.append(cur)
            cur, key = child, None
        elif brace == '}':
            if not stack:
                break
            cur, key = stack.pop(), None
        elif key is None:
            key = quoted
        else:
            cur[key], key = quoted, None
    return root


def find_apps(tree):
    """The `apps` block that carries LastPlayed; Steam nests it under
    UserLocalConfigStore/Software/Valve/Steam, with varying key case."""
    for k, v in tree.items():
        if not isinstance(v, dict):
            continue
        if k.lower() == 'apps' and any(isinstance(x, dict) and 'LastPlayed' in x for x in v.values()):
            return v
        found = find_apps(v)
        if found:
            return found
    return None


def last_played(text):
    """[(unix seconds, appid)] newest first, from localconfig.vdf's text."""
    apps = find_apps(parse_text_vdf(text)) or {}
    rows = [(int(v['LastPlayed']), k) for k, v in apps.items()
            if app_id(k) and isinstance(v, dict) and str(v.get('LastPlayed', '')).isdigit() and int(v['LastPlayed']) > 0]
    return sorted(rows, reverse=True)


def launched_app(cmdline):
    """The appid in a `reaper SteamLaunch AppId=N -- ...` command line (NUL-separated), or None.
    Matches whole arguments so a shell that merely mentions SteamLaunch doesn't count."""
    args = cmdline.split(b'\0')
    if b'SteamLaunch' not in args:
        return None
    for a in args:
        if a.startswith(b'AppId=') and a[6:].isdigit():
            return a[6:].decode()
    return None


def started_at(stat, boot, ticks):
    """Unix start time of a process from its /proc/<pid>/stat line."""
    # The command name (field 2) may hold spaces and parentheses; count from the last ')'.
    fields = stat[stat.rindex(')') + 2:].split()
    return boot + int(fields[19]) / ticks


def boot_time(proc='/proc'):
    with open(f'{proc}/stat') as f:
        for line in f:
            if line.startswith('btime '):
                return int(line.split()[1])
    return 0


def running_game(proc='/proc'):
    """{'game': appid, 'since': unix seconds} for the Steam game running now, or None."""
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return None
    for pid in pids:
        try:
            with open(f'{proc}/{pid}/cmdline', 'rb') as f:
                app = launched_app(f.read())
            if not app:
                continue
            with open(f'{proc}/{pid}/stat') as f:
                since = started_at(f.read(), boot_time(proc), os.sysconf('SC_CLK_TCK'))
            return {'game': app, 'since': int(since)}
        except (OSError, ValueError, IndexError):
            continue
    return None


def read_kv(path):
    with open(path, 'rb') as f:
        body = f.read(MAX_KV_BYTES + 1)
    if len(body) > MAX_KV_BYTES:
        raise ValueError(f'{path} is over {MAX_KV_BYTES} bytes')
    return parse_kv(body)[0]


def find_steam():
    """The Steam folder (env STEAM_DIR overrides), or None."""
    env = os.environ.get('STEAM_DIR')
    cands = [env] if env else []
    cands += [os.path.expanduser(p) for p in (
        '~/.local/share/Steam', '~/.steam/steam',
        '~/.var/app/com.valvesoftware.Steam/.local/share/Steam')]
    for c in cands:
        if c and os.path.isdir(f'{c}/appcache/stats'):
            return c
    return None


def account_id(stats):
    """Steam account whose stats are cached (env STEAM_ACCOUNT overrides), or None."""
    if os.environ.get('STEAM_ACCOUNT'):
        return os.environ['STEAM_ACCOUNT'] if app_id(os.environ['STEAM_ACCOUNT']) else None
    counts = {}
    for f in os.listdir(stats):
        p = f.split('_')
        if f.startswith('UserGameStats_') and len(p) == 3 and app_id(p[1]):
            counts[p[1]] = counts.get(p[1], 0) + 1
    return max(counts, key=counts.get) if counts else None


def number(v):
    """A schema or stats value as a float, or None; Steam writes numbers as ints, floats or strings."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def stat_values(stats_schema, cache):
    """{stat name: value} for every INT or FLOAT stat; a stat the game hasn't
    written yet holds its schema default."""
    out = {}
    for sid, s in stats_schema.items():
        if not isinstance(s, dict) or 'name' not in s or s.get('type') not in ('INT', 'FLOAT', 'AVGRATE'):
            continue
        c = cache.get(sid)
        v = number(c.get('data')) if isinstance(c, dict) else None
        out[s['name']] = v if v is not None else (number(s.get('default')) or 0.0)
    return out


def progress(spec, values):
    """{value, max} for a counter achievement ("12 of 15 relics"), or None.
    The schema ties the achievement to a stat: progress.value.operand1 names
    it, min_val and max_val bound it. A span of 1 is a done/not-done flag
    many games wire up as a stat (on a real library: "0 / 1" on dozens of games),
    not a counter, so it gets no bar."""
    if not isinstance(spec, dict):
        return None
    value = spec.get('value')
    if not isinstance(value, dict) or value.get('operation', 'statvalue') != 'statvalue':
        return None
    lo, hi = number(spec.get('min_val')) or 0.0, number(spec.get('max_val'))
    have = values.get(value.get('operand1'))
    if hi is None or have is None or hi - lo <= 1:
        return None
    have = min(max(have, lo), hi)
    return {'value': whole(have - lo), 'max': whole(hi - lo)}


def whole(x):
    """An int when the count is whole, so the views print "12 / 15", not "12.0 / 15.0"."""
    return int(x) if x == int(x) else round(x, 2)


def read_achievements(stats, uid, app):
    """[{api, name, desc, icon, unlocked, time}] for one game, from the schema
    plus the user's cache; locked counter achievements add `progress`."""
    sf = f'{stats}/UserGameStatsSchema_{app}.bin'
    uf = f'{stats}/UserGameStats_{uid}_{app}.bin'
    if not (os.path.exists(sf) and os.path.exists(uf)):
        return []
    try:
        sch, us = read_kv(sf), read_kv(uf)
    except (OSError, ValueError, struct.error, IndexError):
        # One broken cache file must not stop the watcher before `ready`.
        return []
    cache = us.get('cache', {})
    stats_schema = sch.get(app, {}).get('stats', {})
    values = stat_values(stats_schema, cache)
    out = []
    for sid, s in stats_schema.items():
        if not isinstance(s, dict) or 'bits' not in s:
            continue
        c = cache.get(sid)
        times = c.get('AchievementTimes', {}) if isinstance(c, dict) else {}
        data = c.get('data', 0) if isinstance(c, dict) else 0
        data = data if isinstance(data, int) else 0  # bitfield: Steam sometimes sets the bit but stores no unlock time
        for bit, a in s['bits'].items():
            d = a.get('display', {})
            nm, ds = d.get('name', {}), d.get('desc', {})
            name = nm.get('english') if isinstance(nm, dict) else nm
            desc = ds.get('english', '') if isinstance(ds, dict) else ds
            t = times.get(bit, 0)
            ach = {'api': str(a.get('name', f'{sid}_{bit}')),
                   'name': str(name if name is not None else a.get('name')),
                   'desc': str(desc or ''), 'icon': d.get('icon', ''),
                   'icon_locked': d.get('icon_gray', ''),
                   # Steam writes hidden as an int or a string, depending on the schema's age.
                   'hidden': str(d.get('hidden', 0)) == '1',
                   'unlocked': t > 0 or bool(data >> int(bit) & 1), 'time': t}
            prog = None if ach['unlocked'] else progress(a.get('progress'), values)
            if prog:
                ach['progress'] = prog
            out.append(ach)
    return out


class Steam(Store):
    id = 'steam'
    name = 'Steam'

    def __init__(self):
        self.root = find_steam()
        self.stats = f'{self.root}/appcache/stats' if self.root else None
        self.uid = account_id(self.stats) if self.stats else None

    def available(self):
        return self.uid is not None

    def local_games(self):
        """{appid: mtime} of the account's stats files."""
        pre, out = f'UserGameStats_{self.uid}_', {}
        for e in os.scandir(self.stats):
            if e.name.startswith(pre) and e.name.endswith('.bin') and app_id(e.name[len(pre):-4]):
                out[e.name[len(pre):-4]] = e.stat().st_mtime
        return out

    def games(self):
        """Local stats files, plus, with `community` on, cached profile pages
        of games that never ran here (ADR 11). Local data wins."""
        local = self.local_games()
        if not config().get('community'):
            return local
        # An mtime, like the local tokens: `test` sorts games by it.
        remote = {app: t for app, t in steam_community.cached_games().items() if app not in local}
        return dict(remote, **local)

    def achievements(self, app):
        if not app_id(app):
            return []
        achs = read_achievements(self.stats, self.uid, app)
        if not achs and not os.path.exists(f'{self.stats}/UserGameStats_{self.uid}_{app}.bin') \
                and config().get('community'):
            return [dict(a, remote=True) for a in steam_community.cached(app).get('achievements', [])]
        for a in achs:
            a['icon'] = f"{ICON_BASE}/{app}/{a['icon']}" if a['icon'] else ''
            a['icon_locked'] = f"{ICON_BASE}/{app}/{a['icon_locked']}" if a['icon_locked'] else ''
        return achs

    def backfill(self, say=None):
        """Fetch profile pages for played games with no local stats, when
        `community` is on. Names from the pages go into the name cache."""
        if not config().get('community'):
            return None
        result = steam_community.backfill(self.uid, self.recent(), set(self.local_games()), say=say)
        self.remember_names()
        return result

    def remember_names(self):
        """Copy game names from cached profile pages into the name cache,
        so delisted or offline games keep a name."""
        found = {app: steam_community.cached(app).get('name') for app in steam_community.cached_games()}
        found = {app: n for app, n in found.items() if n}
        if not found:
            return
        with NAMES_LOCK:
            names = read_json(NAMES, {})
            if all(names.get(a) == n for a, n in found.items()):
                return
            names.update(found)
            write_json(NAMES, names)

    def running(self):
        return running_game()

    def recent(self):
        try:
            with open(f'{self.root}/userdata/{self.uid}/config/localconfig.vdf', encoding='utf8', errors='replace') as f:
                return last_played(f.read())
        except OSError:
            return []

    def game_name(self, app):
        """Store name, cached in the state folder; the appid when offline."""
        if not app_id(app):
            return f'App {app}'
        with NAMES_LOCK:
            names = read_json(NAMES, {})
        if app in names:
            return names[app]
        misses_path = f'{CACHE}/name-misses.json'
        if time.time() - read_json(misses_path, {}).get(app, 0) < NAME_MISS_SECONDS:
            return f'App {app}'
        try:
            answer = http_json(f'https://store.steampowered.com/api/appdetails?appids={app}&filters=basic')[app]
        except Exception:
            # Offline or a hiccup: ask again next time.
            return f'App {app}'
        if not answer.get('success'):
            with NAMES_LOCK:
                misses = read_json(misses_path, {})
                misses[app] = int(time.time())
                write_json(misses_path, misses)
            return f'App {app}'
        name = answer['data']['name']
        with NAMES_LOCK:
            names = read_json(NAMES, {})
            names[app] = name
            write_json(NAMES, names)
        return name

    def percents(self, app):
        """Global rarity for every achievement, cached a day; a stale copy when offline."""
        if not app_id(app):
            return {}
        path = f'{CACHE}/rarity/{app}.json'
        old = read_json(path, {})
        if old.get('time', 0) > time.time() - RARITY_SECONDS:
            return old['percents']
        try:
            r = http_json(f'https://api.steampowered.com/ISteamUserStats/'
                          f'GetGlobalAchievementPercentagesForApp/v0002/?gameid={app}')
            pcts = {a['name']: float(a['percent']) for a in r['achievementpercentages']['achievements']}
        except Exception:
            return old.get('percents', {})
        write_json(path, {'time': int(time.time()), 'percents': pcts})
        return pcts

    def library_art(self, app, name):
        """Art Steam already keeps for its library view, if any (newer clients nest it in a hashed folder)."""
        root = f'{self.root}/appcache/librarycache'
        for p in (f'{root}/{app}_{name}', f'{root}/{app}/{name}'):
            if os.path.exists(p):
                return 'file://' + p
        for dirpath, _, files in os.walk(f'{root}/{app}'):
            if name in files:
                return 'file://' + os.path.join(dirpath, name)
        return None

    def art(self, app):
        if not app_id(app):
            return {'hero': '', 'header': ''}
        return {'hero': self.library_art(app, 'library_hero.jpg')
                or cached(f'{ART_BASE}/{app}/library_hero.jpg', f'art/{app}_hero.jpg'),
                'header': self.library_art(app, 'library_header.jpg') or f'{ART_BASE}/{app}/header.jpg'}
