#!/usr/bin/env python3
"""Watch game stores' achievement data and print new unlocks as JSON lines.

Usage:
  omatrophy.py watch                  print one JSON event per new unlock (the shell service runs this)
  omatrophy.py test [kind]            queue a fake event for a running watcher: bronze, silver, gold, platinum
  omatrophy.py status                 progress of every game with achievements, as JSON
  omatrophy.py cabinet                trophy totals and the games nearest platinum, as JSON
  omatrophy.py now                    what is playing, recent games, platinums and totals, as JSON (the bar panel)
  omatrophy.py games                  every game with achievements and its progress, as JSON (the panel's Games tab)
  omatrophy.py game [store app]       every achievement of one game with rarity, as JSON (the tracker);
                                      without arguments, the game running now or played last
  omatrophy.py set position <where>   top-center, top-left or top-right (applies live)
  omatrophy.py set sound on|off|omatrophy|classic
  omatrophy.py set icons omarchy|vector|painted
  omatrophy.py set tracker-sort recent|rarity|name|game
  omatrophy.py set community on|off   fill in games this machine never ran from your public Steam profile
  omatrophy.py sync                   run that backfill now, with progress
  omatrophy.py hide <store> <game>    keep a game you won't finish out of "closest to platinum"
  omatrophy.py unhide <store> <game>  bring it back

Each store (stores/) reads its launcher's own files; this file diffs them and
turns new unlocks into events. Steam is the only store so far.
"""
import json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

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
    # A remote unlock came through an online backfill: it happened on
    # another machine, so it isn't news here (ADR 11).
    fresh = [a for a in achs if a['api'] in new and not a.get('remote')
             and (not a['time'] or a['time'] >= cutoff)]
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


def warm_names(pairs, threads=8):
    """Look up every game's name once, so the panel's Games tab opens on a
    warm cache. Stores cache names themselves; a cached one costs a file read."""
    def lookup(pair):
        try:
            pair[0].game_name(pair[1])
        except Exception:
            pass
    with ThreadPoolExecutor(threads) as pool:
        list(pool.map(lookup, pairs))


# The backfill runs hourly, each run a small budget of pages. After a
# failed run (most often Steam's 429) it waits BACKFILL_LIMITED_WAIT, then
# doubles up to BACKFILL_MAX_WAIT: on 2026-10-27 a 429 lasted close to three
# hours, and asking sooner may only keep it going.
BACKFILL_WAIT = 3600
BACKFILL_LIMITED_WAIT = 4 * 3600
BACKFILL_MAX_WAIT = 8 * 3600


def next_backfill_wait(failed, previous):
    """Seconds until the next backfill run."""
    if not failed:
        return BACKFILL_WAIT
    return min(max(previous * 2, BACKFILL_LIMITED_WAIT), BACKFILL_MAX_WAIT)


def backfill_once(found):
    """One backfill run of every store; True when any of them failed."""
    failed = False
    for s in found:
        try:
            # Progress goes to the shell log; stdout is for events only.
            result = s.backfill(say=lambda line, s=s: print(f'omatrophy: {s.id} backfill: {line}', file=sys.stderr, flush=True))
        except Exception as e:
            print(f'omatrophy: {s.name} backfill failed: {e}', file=sys.stderr, flush=True)
            result = (0, True)
        failed = failed or bool(result and result[1])
    return failed


def background(found, pairs, sleep=time.sleep):
    """The watcher's slow chores, after `ready`: warm the name cache, then
    let each store backfill games it has no local data for, again and
    again for as long as the watcher runs."""
    warm_names(pairs)
    wait = BACKFILL_WAIT
    while True:
        wait = next_backfill_wait(backfill_once(found), wait)
        sleep(wait)


def sync():
    """Run every store's backfill now, printing progress."""
    found = found_stores()
    if not read_json(config_path(), {}).get('community'):
        raise SystemExit('The community backfill is off. Turn it on with: omatrophy.py set community on\n'
                         '(it needs a public Steam profile with public game details; see ADR 11)')
    for s in found:
        result = s.backfill(say=lambda line, s=s: print(f'{s.id}: {line}', flush=True))
        if result:
            fetched, failed = result
            print(f'{s.id}: fetched {fetched}' + (' (stopped early; run again later)' if failed else ''))


def watch(interval=1.0):
    found = found_stores()
    tokens = {s.id: s.games() for s in found}
    seen = {(s.id, g): unlocked_set(s, g)[1] for s in found for g in tokens[s.id]}
    inbox = os.path.getsize(INBOX) if os.path.exists(INBOX) else 0
    emit({'type': 'ready', 'stores': [s.id for s in found], 'games': len(seen)})
    # In the background, after `ready`: name lookups go to the network and
    # must never hold up an unlock.
    threading.Thread(target=background, args=(found, [(s, g) for s in found for g in tokens[s.id]]),
                     daemon=True).start()
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


def library(found=None):
    """(store, game, achievements) for every game with achievements."""
    out = []
    for s in found or found_stores():
        for game in s.games():
            try:
                achs = s.achievements(game)
            except Exception:
                continue
            if achs:
                out.append((s, game, achs))
    return out


def progress_row(store, game, achs):
    return {'store': store.id, 'app': game, 'unlocked': sum(a['unlocked'] for a in achs), 'total': len(achs)}


def progress():
    """(store, {store, app, unlocked, total}) for every game with achievements, most complete first."""
    out = [(s, progress_row(s, g, achs)) for s, g, achs in library()]
    return sorted(out, key=lambda r: -r[1]['unlocked'] / r[1]['total'])


def status():
    print(json.dumps([row for _, row in progress()]))


def nearest_platinum(rows, n, hidden=()):
    """The n started, unfinished games closest to 100%, ties to the one with fewer left;
    games in `hidden` ("store:game") never count."""
    open_rows = [r for r in rows if 0 < r['unlocked'] < r['total'] and game_key(r.get('store'), r['app']) not in hidden]
    return sorted(open_rows, key=lambda r: (-r['unlocked'] / r['total'], r['total'] - r['unlocked']))[:n]


def totals(rows):
    return {'games': len(rows), 'trophies': sum(r['unlocked'] for r in rows),
            'platinums': sum(r['unlocked'] == r['total'] for r in rows)}


def cabinet(n=4):
    """Totals plus the games nearest platinum, named and with art, for the bar panel.
    Names only the few games it shows, since a name can cost a request."""
    found = progress()
    stores = {(r['store'], r['app']): s for s, r in found}
    nearest = []
    for r in nearest_platinum([r for _, r in found], n, hidden_games()):
        s = stores[(r['store'], r['app'])]
        nearest.append(dict(r, game=s.game_name(r['app']), header=s.art(r['app'])['header']))
    print(json.dumps(dict(totals([r for _, r in found]), nearest=nearest)))


def platinum_time(achs):
    """When a complete game got its last achievement; 0 while any is locked."""
    if not achs or not all(a['unlocked'] for a in achs):
        return 0
    return max(a['time'] for a in achs)


def latest_unlocks(achs, n, since=0):
    """The n most recent unlocks (at or after `since`), newest first."""
    done = [a for a in achs if a['unlocked'] and a['time'] and a['time'] >= since]
    return sorted(done, key=lambda a: -a['time'])[:n]


def next_up(achs, pcts, n):
    """The n locked achievements most players have, the likeliest next unlocks."""
    locked = [a for a in achs if not a['unlocked']]
    return sorted(locked, key=lambda a: -(pcts.get(a['api']) or 0))[:n]


def recent_games(played, owned, skip, n):
    """The n most recently played games we hold achievements for, minus `skip`."""
    out = []
    for when, key in played:
        if key in owned and key != skip and key not in [k for _, k in out]:
            out.append((when, key))
    return out[:n]


def brief(a):
    return {'name': a['name'], 'icon': a['icon'], 'time': a['time']}


def game_card(store, game, achs, played=0):
    """One game as the panel draws it: art, progress, latest unlocks, platinum date."""
    return dict(progress_row(store, game, achs), game=store.game_name(game), header=store.art(game)['header'],
                played=played, platinum=platinum_time(achs), latest=[brief(a) for a in latest_unlocks(achs, 5)])


def playing_card(store, game, achs, since):
    """The game running now: its card, this session's unlocks and the likeliest next ones."""
    pcts = store.percents(game)
    card = game_card(store, game, achs, since)
    card.update(since=since, hero=store.art(game)['hero'])
    card['session'] = [brief(a) for a in latest_unlocks(achs, 12, since)]
    card['next'] = [dict(brief(a), icon=a.get('icon_locked') or a['icon'],
                         desc='' if a.get('hidden') else a['desc'], percent=pcts.get(a['api']),
                         progress=a.get('progress'))
                    for a in next_up(achs, pcts, 3)]
    return card


def now(recent_n=3):
    """Everything the panel's Now tab shows, in one read of every store."""
    found = found_stores()
    lib = library(found)
    by_key = {(s.id, g): (s, achs) for s, g, achs in lib}
    rows = [progress_row(s, g, achs) for s, g, achs in lib]
    playing, skip = None, None
    for s in found:
        run = s.running()
        if run and (s.id, run['game']) in by_key:
            skip = (s.id, run['game'])
            playing = playing_card(s, run['game'], by_key[skip][1], run['since'])
            break
    played = sorted(((t, (s.id, g)) for s in found for t, g in s.recent()), key=lambda r: -r[0])
    recent = []
    for when, key in recent_games(played, by_key, skip, recent_n):
        s, achs = by_key[key]
        recent.append(game_card(s, key[1], achs, when))
    shelf = sorted((dict(game_card(s, g, achs), latest=[]) for s, g, achs in lib if platinum_time(achs)),
                   key=lambda c: -c['platinum'])
    return dict(totals(rows), playing=playing, recent=recent, shelf=shelf)


def games():
    """Every game with achievements as a slim card, for the Games tab. Names
    not cached yet are looked up eight at a time, so a first open of a large
    library takes seconds, not minutes; later opens read the cache."""
    found = found_stores()
    lib = library(found)
    played = {(s.id, g): t for s in found for t, g in s.recent()}
    hidden = hidden_games()
    with ThreadPoolExecutor(8) as pool:
        names = list(pool.map(lambda item: item[0].game_name(item[1]), lib))
    return [dict(progress_row(s, g, achs), game=name, header=s.art(g)['header'],
                 platinum=platinum_time(achs), played=played.get((s.id, g), 0),
                 hidden=game_key(s.id, g) in hidden)
            for (s, g, achs), name in zip(lib, names)]


def detail(a, pcts):
    pct = pcts.get(a['api'])
    return {'api': a['api'], 'name': a['name'], 'desc': a['desc'], 'icon': a['icon'],
            'icon_locked': a.get('icon_locked', ''), 'hidden': bool(a.get('hidden')),
            'unlocked': a['unlocked'], 'time': a['time'], 'percent': pct, 'tier': tier(pct),
            'progress': a.get('progress')}


def pick_game(found):
    """(store, game) running now, else played last among games with achievements."""
    for s in found:
        run = s.running()
        if run and run['game'] in s.games():
            return s, run['game']
    played = sorted(((t, s, g) for s in found for t, g in s.recent() if g in s.games()), key=lambda r: -r[0])
    if played:
        return played[0][1], played[0][2]
    raise SystemExit('No game to show: play one, or name it: omatrophy.py game steam <appid>')


def game_detail(store, game):
    """Every achievement of one game with rarity, for the tracker."""
    achs = store.achievements(game)
    if not achs:
        raise SystemExit(f'{store.name} has no achievements cached for {game}; launch it once in {store.name}')
    pcts = store.percents(game)
    art = store.art(game)
    run = store.running()
    return dict(progress_row(store, game, achs), game=store.game_name(game), header=art['header'], hero=art['hero'],
                platinum=platinum_time(achs), playing=bool(run and run['game'] == game),
                achievements=[detail(a, pcts) for a in achs])


def game(args):
    found = found_stores()
    if not args:
        store, app = pick_game(found)
    elif len(args) == 2 and args[0] in [s.id for s in found]:
        store, app = next(s for s in found if s.id == args[0]), args[1]
    else:
        raise SystemExit(f'usage: omatrophy.py game [{"|".join(s.id for s in found)} <game id>]')
    print(json.dumps(game_detail(store, app)))


def config_path():
    # Resolved per call so tests can point HOME at a temporary folder.
    return os.path.expanduser('~/.config/omatrophy/config.json')


SETTINGS = {'position': ('top-center', 'top-left', 'top-right'),
            'sound': ('on', 'off', 'omatrophy', 'classic'),
            'icons': ('omarchy', 'vector', 'painted'),
            'tracker-sort': ('recent', 'rarity', 'name', 'game'),
            'community': ('on', 'off')}


def set_option(key, value):
    """Write one setting to ~/.config/omatrophy/config.json; the shell picks it up live.
    `sound` takes on/off, or a chime set, which also turns sound on."""
    if value not in SETTINGS.get(key, ()):
        raise SystemExit(f'usage: omatrophy.py set position {"|".join(SETTINGS["position"])}\n'
                         f'       omatrophy.py set sound {"|".join(SETTINGS["sound"])}\n'
                         f'       omatrophy.py set icons {"|".join(SETTINGS["icons"])}\n'
                         f'       omatrophy.py set tracker-sort {"|".join(SETTINGS["tracker-sort"])}\n'
                         f'       omatrophy.py set community on|off')
    path = config_path()
    cfg = read_json(path, {})
    if key == 'sound':
        cfg['sound'] = value != 'off'
        if value not in ('on', 'off'):
            cfg['chimes'] = value
    elif key == 'community':
        cfg['community'] = value == 'on'
    else:
        cfg[key] = value
    write_json(path, cfg, indent=2)
    print(f'{key} = {value}')


def game_key(store_id, game):
    return f'{store_id}:{game}'


def hidden_games():
    """{"store:game"} the owner hid from "closest to platinum"; a broken list reads as empty."""
    keys = read_json(config_path(), {}).get('hidden', [])
    return {k for k in keys if isinstance(k, str)} if isinstance(keys, list) else set()


def with_hidden(keys, key, hide):
    """The hidden list with `key` added or removed, sorted so the file diffs cleanly."""
    out = {k for k in keys if isinstance(k, str)} if isinstance(keys, list) else set()
    (out.add if hide else out.discard)(key)
    return sorted(out)


def set_hidden(store_id, game, hide):
    """Hide or unhide one game in config.json; the panel re-reads it live."""
    if store_id not in [cls.id for cls in stores.STORES] or not game or ':' in game:
        raise SystemExit(f'usage: omatrophy.py {"hide" if hide else "unhide"} '
                         f'{"|".join(cls.id for cls in stores.STORES)} <game id>')
    path = config_path()
    cfg = read_json(path, {})
    cfg['hidden'] = with_hidden(cfg.get('hidden', []), game_key(store_id, game), hide)
    write_json(path, cfg, indent=2)
    print(f'{"hidden" if hide else "shown"}: {game_key(store_id, game)}')


def main(argv):
    cmd = argv[1] if len(argv) > 1 else 'watch'
    if cmd == 'watch':
        watch()
    elif cmd == 'test':
        test(argv[2] if len(argv) > 2 else 'unlock')
    elif cmd == 'status':
        status()
    elif cmd == 'cabinet':
        cabinet()
    elif cmd == 'now':
        print(json.dumps(now()))
    elif cmd == 'games':
        print(json.dumps(games()))
    elif cmd == 'game':
        game(argv[2:])
    elif cmd == 'demo':
        demo(argv[2:] or ['unlock', 'rare', 'platinum'])
    elif cmd == 'set' and len(argv) == 4:
        set_option(argv[2], argv[3])
    elif cmd == 'sync':
        sync()
    elif cmd in ('hide', 'unhide') and len(argv) == 4:
        set_hidden(argv[2], argv[3], cmd == 'hide')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
