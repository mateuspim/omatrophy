#!/usr/bin/env python3
"""Watch game stores' achievement data and print new unlocks as JSON lines.

Usage:
  omatrophy.py watch                  print one JSON event per new unlock (the shell service runs this)
  omatrophy.py test [kind]            queue a fake event for a running watcher: bronze, silver, gold, platinum
  omatrophy.py status                 progress of every game with achievements, as JSON
  omatrophy.py set position <where>   top-center, top-left or top-right (applies live)
  omatrophy.py set sound on|off|omatrophy|classic
  omatrophy.py set icons omarchy|vector|painted

Each store (stores/) reads its launcher's own files; this file diffs them and
turns new unlocks into events. Steam is the only store so far.
"""
import json, os, sys, time

import stores
from stores.base import STATE, cached, read_json, write_json

INBOX = f'{STATE}/inbox.jsonl'
# An unlock older than this when its file changes is a cache sync of past
# progress (first launch, a new machine), not something that just happened.
FRESH_SECONDS = 15 * 60
RARE_PERCENT = 10.0


def tier(pct):
    """Stores have no trophy grades, so rarity picks the metal: gold is the rare ones."""
    if pct is None or pct > 35:
        return 'bronze'
    return 'silver' if pct > RARE_PERCENT else 'gold'


def icon(store, game, url):
    """A local copy of an achievement icon, cached per store and game."""
    return cached(url, f'icons/{store.id}/{game}/{os.path.basename(url)}') if url else ''


def unlock_event(store, game, ach, achs):
    """The JSON line the shell turns into a toast."""
    done = sum(a['unlocked'] for a in achs)
    pct = store.percent(game, ach['api'])
    return {'type': 'unlock', 'store': store.id, 'app': game, 'game': store.game_name(game),
            'name': ach['name'], 'desc': ach['desc'], 'icon': icon(store, game, ach['icon']),
            'percent': pct, 'rare': pct is not None and pct <= RARE_PERCENT, 'tier': tier(pct),
            'unlocked': done, 'total': len(achs), 'time': ach['time'] or int(time.time())}


def platinum_event(store, game, achs):
    times = [a['time'] for a in achs if a['time']]
    art = store.art(game)
    return {'type': 'platinum', 'store': store.id, 'app': game, 'game': store.game_name(game),
            'total': len(achs), 'first': min(times) if times else 0, 'last': max(times) if times else 0,
            'hero': art['hero'], 'header': art['header']}


def emit(ev):
    print(json.dumps(ev), flush=True)


def unlocked_set(store, game):
    """A game's achievements and the keys unlocked; nothing when its files are mid-write or unreadable."""
    try:
        achs = store.achievements(game)
    except Exception:
        return [], set()
    return achs, {a['api'] for a in achs if a['unlocked']}


def check_game(store, game, seen):
    """Emit what is newly unlocked in one game, and the platinum when it completes it."""
    key = (store.id, game)
    achs, now = unlocked_set(store, game)
    new = now - seen.get(key, set())
    seen[key] = now
    cutoff = time.time() - FRESH_SECONDS
    fresh = [a for a in achs if a['api'] in new and (not a['time'] or a['time'] >= cutoff)]
    for a in sorted(fresh, key=lambda a: a['time']):
        emit(unlock_event(store, game, a, achs))
    if fresh and achs and len(now) == len(achs):
        emit(platinum_event(store, game, achs))


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


def found_stores():
    found = stores.available()
    if not found:
        raise SystemExit('No game store with achievement data found. For Steam, set STEAM_DIR=/path/to/Steam')
    return found


def watch(interval=1.0):
    found = found_stores()
    tokens = {s.id: s.games() for s in found}
    seen = {(s.id, g): unlocked_set(s, g)[1] for s in found for g in tokens[s.id]}
    inbox = os.path.getsize(INBOX) if os.path.exists(INBOX) else 0
    emit({'type': 'ready', 'stores': [s.id for s in found], 'games': len(seen)})
    while True:
        time.sleep(interval)
        inbox = drain_inbox(inbox)
        for s in found:
            cur = s.games()
            for game, token in cur.items():
                if tokens[s.id].get(game) != token:
                    check_game(s, game, seen)
            tokens[s.id] = cur


def sample_game():
    """The most recently touched game with achievements, for realistic test toasts."""
    for s in found_stores():
        for game, _ in sorted(s.games().items(), key=lambda kv: -kv[1]):
            achs = s.achievements(game)
            if achs:
                return s, game, achs
    raise SystemExit('No game with achievements to test with')


def sample_event(kind, store, game, achs):
    """A realistic event of one kind from a real game, with made-up rarity."""
    if kind == 'platinum':
        ev = platinum_event(store, game, achs)
        ev['first'] = ev['first'] or int(time.time()) - 86400 * 12
        ev['last'] = ev['last'] or int(time.time())
        return ev
    ach = next((a for a in achs if a['unlocked']), achs[0])
    ev = unlock_event(store, game, ach, achs)
    if kind in ('rare', 'gold'):
        ev.update(rare=True, percent=3.4, tier='gold')
    elif kind in ('silver', 'bronze'):
        ev.update(rare=False, percent=22.7 if kind == 'silver' else 64.0, tier=kind)
    return ev


def test(kind):
    ev = sample_event(kind, *sample_game())
    os.makedirs(STATE, exist_ok=True)
    with open(INBOX, 'a') as f:
        f.write(json.dumps(ev) + '\n')
    print(f"queued {kind}: {ev['game']}" + (f" / {ev['name']}" if 'name' in ev else ''))


def demo(kinds):
    """Print sample events straight to stdout (for dev/preview.sh), then idle so the shell doesn't restart us."""
    game = sample_game()
    for kind in kinds:
        emit(sample_event(kind, *game))
    while True:
        time.sleep(3600)


def status():
    out = []
    for s in found_stores():
        for game in s.games():
            achs = s.achievements(game)
            if achs:
                out.append({'store': s.id, 'app': game, 'unlocked': sum(a['unlocked'] for a in achs), 'total': len(achs)})
    print(json.dumps(sorted(out, key=lambda g: -g['unlocked'] / g['total'])))


SETTINGS = {'position': ('top-center', 'top-left', 'top-right'),
            'sound': ('on', 'off', 'omatrophy', 'classic'),
            'icons': ('omarchy', 'vector', 'painted')}


def set_option(key, value):
    """Write one setting to ~/.config/omatrophy/config.json; the shell picks it up live.
    `sound` takes on/off, or a chime set, which also turns sound on."""
    if value not in SETTINGS.get(key, ()):
        raise SystemExit(f'usage: omatrophy.py set position {"|".join(SETTINGS["position"])}\n'
                         f'       omatrophy.py set sound {"|".join(SETTINGS["sound"])}\n'
                         f'       omatrophy.py set icons {"|".join(SETTINGS["icons"])}')
    path = os.path.expanduser('~/.config/omatrophy/config.json')
    cfg = read_json(path, {})
    if key == 'sound':
        cfg['sound'] = value != 'off'
        if value not in ('on', 'off'):
            cfg['chimes'] = value
    else:
        cfg[key] = value
    write_json(path, cfg, indent=2)
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
