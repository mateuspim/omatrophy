#!/usr/bin/env python3
"""Watch Steam's local achievement cache and print new unlocks as JSON lines.

Usage:
  omatrophy.py watch                  print one JSON event per new unlock (the shell service runs this)
  omatrophy.py test [kind]            queue a fake event for a running watcher: unlock, rare, platinum
  omatrophy.py status                 progress of every cached game, as JSON
  omatrophy.py set position <where>   top-center, top-left or top-right (applies live)
  omatrophy.py set sound on|off
  omatrophy.py set icons omarchy|vector|painted

Steam writes unlocks to <Steam>/appcache/stats/UserGameStats_<account>_<app>.bin,
so this needs no API key and works with a private profile.
"""
import json, os, struct, sys, time, urllib.request

STATE = os.path.expanduser('~/.local/state/omatrophy')
INBOX = f'{STATE}/inbox.jsonl'
CACHE = os.path.expanduser('~/.cache/omatrophy')
NAMES = f'{STATE}/names.json'
ICON_BASE = 'https://cdn.fastly.steamstatic.com/steamcommunity/public/images/apps'
ART_BASE = 'https://cdn.fastly.steamstatic.com/steam/apps'
# An unlock older than this when its file changes is a cache sync of past
# progress (first launch, a new machine), not something that just happened.
FRESH_SECONDS = 15 * 60
RARE_PERCENT = 10.0


def tier(pct):
    """Steam has no trophy grades, so rarity picks the metal: gold is the rare ones."""
    if pct is None or pct > 35:
        return 'bronze'
    return 'silver' if pct > RARE_PERCENT else 'gold'


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


def find_steam():
    env = os.environ.get('STEAM_DIR')
    cands = [env] if env else []
    cands += [os.path.expanduser(p) for p in (
        '~/.local/share/Steam', '~/.steam/steam',
        '~/.var/app/com.valvesoftware.Steam/.local/share/Steam')]
    for c in cands:
        if c and os.path.isdir(f'{c}/appcache/stats'):
            return c
    raise SystemExit('Steam folder not found. Set STEAM_DIR=/path/to/Steam')


def stats_dir():
    return f'{find_steam()}/appcache/stats'


def account_id(stats):
    """Steam account whose stats are cached (env STEAM_ACCOUNT overrides)."""
    if os.environ.get('STEAM_ACCOUNT'):
        return os.environ['STEAM_ACCOUNT']
    counts = {}
    for f in os.listdir(stats):
        p = f.split('_')
        if f.startswith('UserGameStats_') and len(p) == 3:
            counts[p[1]] = counts.get(p[1], 0) + 1
    if not counts:
        raise SystemExit(f'No UserGameStats files in {stats}')
    return max(counts, key=counts.get)


def read_achievements(stats, uid, app):
    """[{api, name, desc, icon, unlocked, time}] for one game, from the schema plus the user's cache."""
    sf = f'{stats}/UserGameStatsSchema_{app}.bin'
    uf = f'{stats}/UserGameStats_{uid}_{app}.bin'
    if not (os.path.exists(sf) and os.path.exists(uf)):
        return []
    sch, _ = parse_kv(open(sf, 'rb').read())
    us, _ = parse_kv(open(uf, 'rb').read())
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


def http_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'omatrophy'})
    with urllib.request.urlopen(req, timeout=4) as r:
        return json.load(r)


def game_name(app):
    """Store name, cached in the state folder; the appid when offline."""
    try:
        names = json.load(open(NAMES))
    except (OSError, ValueError):
        names = {}
    if app in names:
        return names[app]
    try:
        name = http_json(f'https://store.steampowered.com/api/appdetails?appids={app}&filters=basic')[app]['data']['name']
    except Exception:
        return f'App {app}'
    names[app] = name
    os.makedirs(STATE, exist_ok=True)
    json.dump(names, open(NAMES, 'w'))
    return name


def global_percent(app, api):
    """Share of players with this achievement, from Steam's public, keyless endpoint; None when unknown."""
    try:
        r = http_json(f'https://api.steampowered.com/ISteamUserStats/'
                      f'GetGlobalAchievementPercentagesForApp/v0002/?gameid={app}')
        for a in r['achievementpercentages']['achievements']:
            if a['name'] == api:
                return float(a['percent'])
    except Exception:
        pass
    return None


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


def library_art(app, name):
    """Art Steam already keeps for its library view, if any (newer clients nest it in a hashed folder)."""
    root = f'{find_steam()}/appcache/librarycache'
    for p in (f'{root}/{app}_{name}', f'{root}/{app}/{name}'):
        if os.path.exists(p):
            return 'file://' + p
    for dirpath, _, files in os.walk(f'{root}/{app}'):
        if name in files:
            return 'file://' + os.path.join(dirpath, name)
    return None


def unlock_event(app, ach, achs):
    """The JSON line the shell turns into a toast."""
    done = sum(a['unlocked'] for a in achs)
    pct = global_percent(app, ach['api'])
    return {'type': 'unlock', 'app': app, 'game': game_name(app),
            'name': ach['name'], 'desc': ach['desc'],
            'icon': cached(f"{ICON_BASE}/{app}/{ach['icon']}", f"icons/{app}/{ach['icon']}") if ach['icon'] else '',
            'percent': pct, 'rare': pct is not None and pct <= RARE_PERCENT, 'tier': tier(pct),
            'unlocked': done, 'total': len(achs), 'time': ach['time'] or int(time.time())}


def platinum_event(app, achs):
    times = [a['time'] for a in achs if a['time']]
    return {'type': 'platinum', 'app': app, 'game': game_name(app), 'total': len(achs),
            'first': min(times) if times else 0, 'last': max(times) if times else 0,
            'hero': library_art(app, 'library_hero.jpg') or cached(f'{ART_BASE}/{app}/library_hero.jpg', f'art/{app}_hero.jpg'),
            'header': f'{ART_BASE}/{app}/header.jpg'}


def emit(ev):
    print(json.dumps(ev), flush=True)


def user_files(stats, uid):
    """{appid: mtime} of the account's stats files."""
    pre, out = f'UserGameStats_{uid}_', {}
    for e in os.scandir(stats):
        if e.name.startswith(pre) and e.name.endswith('.bin'):
            out[e.name[len(pre):-4]] = e.stat().st_mtime
    return out


def unlocked_set(stats, uid, app):
    try:
        achs = read_achievements(stats, uid, app)
    except (OSError, ValueError, struct.error):
        return [], set()
    return achs, {a['api'] for a in achs if a['unlocked']}


def check_app(stats, uid, app, seen):
    """Emit what is newly unlocked in one game, and the platinum when it completes it."""
    achs, now = unlocked_set(stats, uid, app)
    new = now - seen.get(app, set())
    seen[app] = now
    cutoff = time.time() - FRESH_SECONDS
    fresh = [a for a in achs if a['api'] in new and (not a['time'] or a['time'] >= cutoff)]
    for a in sorted(fresh, key=lambda a: a['time']):
        emit(unlock_event(app, a, achs))
    if fresh and achs and len(now) == len(achs):
        emit(platinum_event(app, achs))


def drain_inbox(offset):
    """Forward events queued by `omatrophy.py test`; returns the new read offset."""
    try:
        size = os.path.getsize(INBOX)
    except OSError:
        return 0
    if size < offset:
        offset = 0
    if size == offset:
        return offset
    with open(INBOX) as f:
        f.seek(offset)
        for line in f:
            if line.strip():
                print(line.strip(), flush=True)
        return f.tell()


def watch(interval=1.0):
    stats = stats_dir()
    uid = account_id(stats)
    mtimes = user_files(stats, uid)
    seen = {app: unlocked_set(stats, uid, app)[1] for app in mtimes}
    inbox = os.path.getsize(INBOX) if os.path.exists(INBOX) else 0
    emit({'type': 'ready', 'games': len(seen), 'account': uid})
    while True:
        time.sleep(interval)
        inbox = drain_inbox(inbox)
        cur = user_files(stats, uid)
        for app, m in cur.items():
            if mtimes.get(app) != m:
                check_app(stats, uid, app, seen)
        mtimes = cur


def sample_game(stats, uid):
    """The most recently touched game with achievements, for realistic test toasts."""
    files = sorted(user_files(stats, uid).items(), key=lambda kv: -kv[1])
    for app, _ in files:
        achs = read_achievements(stats, uid, app)
        if achs:
            return app, achs
    raise SystemExit('No cached game with achievements to test with')


def test(kind):
    stats = stats_dir()
    app, achs = sample_game(stats, account_id(stats))
    ach = next((a for a in achs if a['unlocked']), achs[0])
    ev = unlock_event(app, ach, achs)
    if kind in ('rare', 'gold'):
        ev.update(rare=True, percent=ev['percent'] if ev['rare'] else 3.4, tier='gold')
    elif kind in ('silver', 'bronze'):
        ev.update(rare=False, percent=22.7 if kind == 'silver' else 64.0, tier=kind)
    if kind == 'platinum':
        ev = platinum_event(app, achs)
        ev['first'] = ev['first'] or int(time.time()) - 86400 * 12
        ev['last'] = ev['last'] or int(time.time())
    os.makedirs(STATE, exist_ok=True)
    with open(INBOX, 'a') as f:
        f.write(json.dumps(ev) + '\n')
    print(f"queued {kind}: {ev['game']}" + (f" / {ev['name']}" if 'name' in ev else ''))


def demo(kinds):
    """Print sample events straight to stdout (for dev/preview.sh), then idle so the shell doesn't restart us."""
    stats = stats_dir()
    app, achs = sample_game(stats, account_id(stats))
    ach = next((a for a in achs if a['unlocked']), achs[0])
    for kind in kinds:
        if kind == 'platinum':
            ev = platinum_event(app, achs)
            ev['first'] = ev['first'] or int(time.time()) - 86400 * 12
        else:
            ev = unlock_event(app, ach, achs)
            if kind in ('rare', 'gold'):
                ev.update(rare=True, percent=3.4, tier='gold')
            elif kind == 'silver':
                ev.update(rare=False, percent=22.7, tier='silver')
            elif kind == 'bronze':
                ev.update(rare=False, percent=64.0, tier='bronze')
        emit(ev)
    while True:
        time.sleep(3600)


def status():
    stats = stats_dir()
    uid = account_id(stats)
    out = []
    for app in user_files(stats, uid):
        achs = read_achievements(stats, uid, app)
        if achs:
            out.append({'app': app, 'unlocked': sum(a['unlocked'] for a in achs), 'total': len(achs)})
    print(json.dumps(sorted(out, key=lambda g: -g['unlocked'] / g['total'])))


SETTINGS = {'position': ('top-center', 'top-left', 'top-right'), 'sound': ('on', 'off'),
            'icons': ('omarchy', 'vector', 'painted')}


def set_option(key, value):
    """Write one setting to ~/.config/omatrophy/config.json; the shell picks it up live."""
    if value not in SETTINGS.get(key, ()):
        raise SystemExit(f'usage: omatrophy.py set position {"|".join(SETTINGS["position"])}\n'
                         f'       omatrophy.py set sound on|off\n'
                         f'       omatrophy.py set icons omarchy|vector|painted')
    path = os.path.expanduser('~/.config/omatrophy/config.json')
    try:
        cfg = json.load(open(path))
    except (OSError, ValueError):
        cfg = {}
    cfg[key] = value == 'on' if key == 'sound' else value
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(cfg, open(path, 'w'), indent=2)
    print(f'{key} = {value}')


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'watch'
    if cmd == 'watch':
        watch()
    elif cmd == 'test':
        test(argv[2] if len(argv) > 2 else 'unlock')
    elif cmd == 'status':
        status()
    elif cmd == 'demo':
        demo(argv[2:] or ['unlock', 'rare', 'platinum'])
    elif cmd == 'set' and len(argv) == 4:
        set_option(argv[2], argv[3])
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
