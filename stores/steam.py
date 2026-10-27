"""Steam, from its local stats cache.

Steam writes unlocks to <Steam>/appcache/stats/UserGameStats_<account>_<app>.bin,
so this needs no API key and works with a private profile. Rarity comes from
Steam's public, keyless global-percentages endpoint.
"""
import os, struct

from .base import STATE, Store, cached, http_json, read_json, write_json

ICON_BASE = 'https://cdn.fastly.steamstatic.com/steamcommunity/public/images/apps'
ART_BASE = 'https://cdn.fastly.steamstatic.com/steam/apps'
NAMES = f'{STATE}/names.json'


def parse_kv(b, pos=0):
    """Parse Steam's binary KeyValues format."""
    d = {}
    while pos < len(b):
        t = b[pos]; pos += 1
        if t == 8:
            return d, pos
        e = b.index(b'\0', pos); k = b[pos:e].decode('utf8', 'replace'); pos = e + 1
        if t == 0:
            v, pos = parse_kv(b, pos)
        elif t == 1:
            e = b.index(b'\0', pos); v = b[pos:e].decode('utf8', 'replace'); pos = e + 1
        elif t in (2, 4, 6):
            v = struct.unpack_from('<i', b, pos)[0]; pos += 4
        elif t == 3:
            v = struct.unpack_from('<f', b, pos)[0]; pos += 4
        elif t == 7:
            v = struct.unpack_from('<Q', b, pos)[0]; pos += 8
        elif t == 5:
            e = pos
            while b[e:e + 2] != b'\0\0':
                e += 2
            v = b[pos:e].decode('utf-16le'); pos = e + 2
        else:
            raise ValueError(f'unknown type {t}')
        d[k] = v
    return d, pos


def read_kv(path):
    with open(path, 'rb') as f:
        return parse_kv(f.read())[0]


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
        return os.environ['STEAM_ACCOUNT']
    counts = {}
    for f in os.listdir(stats):
        p = f.split('_')
        if f.startswith('UserGameStats_') and len(p) == 3:
            counts[p[1]] = counts.get(p[1], 0) + 1
    return max(counts, key=counts.get) if counts else None


def read_achievements(stats, uid, app):
    """[{api, name, desc, icon, unlocked, time}] for one game, from the schema plus the user's cache."""
    sf = f'{stats}/UserGameStatsSchema_{app}.bin'
    uf = f'{stats}/UserGameStats_{uid}_{app}.bin'
    if not (os.path.exists(sf) and os.path.exists(uf)):
        return []
    sch, us = read_kv(sf), read_kv(uf)
    cache = us.get('cache', {})
    out = []
    for sid, s in sch.get(app, {}).get('stats', {}).items():
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
            out.append({'api': str(a.get('name', f'{sid}_{bit}')),
                        'name': str(name if name is not None else a.get('name')),
                        'desc': str(desc or ''), 'icon': d.get('icon', ''),
                        'unlocked': t > 0 or bool(data >> int(bit) & 1), 'time': t})
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

    def games(self):
        """{appid: mtime} of the account's stats files."""
        pre, out = f'UserGameStats_{self.uid}_', {}
        for e in os.scandir(self.stats):
            if e.name.startswith(pre) and e.name.endswith('.bin'):
                out[e.name[len(pre):-4]] = e.stat().st_mtime
        return out

    def achievements(self, app):
        achs = read_achievements(self.stats, self.uid, app)
        for a in achs:
            a['icon'] = f"{ICON_BASE}/{app}/{a['icon']}" if a['icon'] else ''
        return achs

    def game_name(self, app):
        """Store name, cached in the state folder; the appid when offline."""
        names = read_json(NAMES, {})
        if app in names:
            return names[app]
        try:
            name = http_json(f'https://store.steampowered.com/api/appdetails?appids={app}&filters=basic')[app]['data']['name']
        except Exception:
            return f'App {app}'
        names[app] = name
        write_json(NAMES, names)
        return name

    def percent(self, app, api):
        try:
            r = http_json(f'https://api.steampowered.com/ISteamUserStats/'
                          f'GetGlobalAchievementPercentagesForApp/v0002/?gameid={app}')
            for a in r['achievementpercentages']['achievements']:
                if a['name'] == api:
                    return float(a['percent'])
        except Exception:
            pass
        return None

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
        return {'hero': self.library_art(app, 'library_hero.jpg')
                or cached(f'{ART_BASE}/{app}/library_hero.jpg', f'art/{app}_hero.jpg'),
                'header': f'{ART_BASE}/{app}/header.jpg'}
