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
  omatrophy.py set glass <look>       clear, frosted or solid toast background
  omatrophy.py set sound on|off|omatrophy|classic
  omatrophy.py set icons omarchy|vector|painted
  omatrophy.py set tracker-sort recent|rarity|name|game
  omatrophy.py set games-sort recent|closest|name
  omatrophy.py set rarest ever|month|platinum
  omatrophy.py set community on|off   fill in games this machine never ran from your public Steam profile
  omatrophy.py sync                   run that backfill now, with progress
  omatrophy.py hide <store> <game>    keep a game you won't finish out of "closest to platinum"
  omatrophy.py unhide <store> <game>  bring it back
  omatrophy.py showcase add|remove <store> <game> [api]
                                      pin a trophy (or, with no api, the game's platinum) to the Profile showcase

Each store (stores/) reads its launcher's own files; this file diffs them and
turns new unlocks into events. Steam and GOG (through Heroic) so far.
"""
import hashlib, json, os, sys, threading, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor

import stores
from stores.base import CACHE, STATE, cached, read_json, trusted_url, write_json

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
            event = inbox_event(line)
            if event:
                print(event, flush=True)
        return f.tell()


# A real event line is a few hundred bytes; the shell parses every line.
MAX_INBOX_LINE = 64 * 1024


def inbox_event(line):
    """The line itself when it is one toast event (`unlock` or `platinum`),
    else None: the inbox is a file any of the user's processes can append to."""
    line = line.strip()
    if not line or len(line) > MAX_INBOX_LINE:
        return None
    try:
        event = json.loads(line)
    except ValueError:
        return None
    if not isinstance(event, dict) or event.get('type') not in ('unlock', 'platinum'):
        return None
    return line


def found_stores():
    found = stores.available()
    if not found:
        raise SystemExit('No game store with achievement data found. For Steam, set STEAM_DIR=/path/to/Steam; '
                         'for GOG, play a game once through Heroic (or set COMET_DIR)')
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


def warm_rarity(pairs, threads=8):
    """Fetch rarity once for games that have none cached yet, so the
    panel's rarest unlocks can read every game from the cache."""
    def lookup(pair):
        try:
            if not pair[0].known_percents(pair[1]):
                pair[0].percents(pair[1])
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
    """The watcher's slow chores, after `ready`: warm the name and rarity caches, then
    let each store backfill games it has no local data for, again and
    again for as long as the watcher runs."""
    warm_names(pairs)
    warm_rarity(pairs)
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


def average_completion(rows):
    """Mean share unlocked, in whole percent, over the games you've started
    (Steam's "average game completion rate" counts the same games)."""
    started = [r['unlocked'] / r['total'] for r in rows if r['unlocked'] and r['total']]
    # Half up, not Python's round-half-to-even, so 62.5 shows as 63.
    return int(100 * sum(started) / len(started) + 0.5) if started else 0


def metal_tally(lib):
    """Every unlock counted by the metal its toast would have, from cached
    rarity (no network); an unlock with no known rarity counts as bronze,
    as its toast would."""
    tally = {'bronze': 0, 'silver': 0, 'gold': 0}
    for s, g, achs in lib:
        pcts = None
        for a in achs:
            if not a['unlocked']:
                continue
            if pcts is None:
                pcts = s.known_percents(g)
            tally[tier(pcts.get(a['api']))] += 1
    return tally


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


def month_start(now):
    """Unix time the local calendar month of `now` began."""
    t = time.localtime(now)
    return int(time.mktime((t.tm_year, t.tm_mon, 1, 0, 0, 0, 0, 0, -1)))


def rarest_unlocks(unlocks, n, since=0):
    """The n unlocks fewest players have (at or after `since`), rarest
    first, ties to the newest. Each unlock is a dict with `percent` and
    `time`; one with no known rarity can't rank and is left out."""
    ranked = [u for u in unlocks if u['percent'] is not None and u['time'] >= since]
    return sorted(ranked, key=lambda u: (u['percent'], -u['time']))[:n]


def library_unlocks(lib, hidden=()):
    """Every unlock with a date across the library, with its rarity from
    the cache (no network) and where it came from; games in `hidden`
    ("store:game") are set aside, so they stay out."""
    out = []
    for s, g, achs in lib:
        if game_key(s.id, g) in hidden:
            continue
        pcts = None
        for a in achs:
            if not (a['unlocked'] and a['time']):
                continue
            if pcts is None:
                pcts = s.known_percents(g)
            out.append(dict(brief(a), api=a['api'], percent=pcts.get(a['api']), store=s.id, app=g))
    return out


def rarest_cards(lib, n, now_time, hidden=()):
    """The panel's rarest unlocks, ever, this month and from finished games only,
    each named with its game."""
    unlocks = library_unlocks(lib, hidden)
    stores_by_id = {s.id: s for s, _, _ in lib}
    def card(u):
        return dict(u, tier=tier(u['percent']), game=stores_by_id[u['store']].game_name(u['app']))
    finished = {(s.id, g) for s, g, achs in lib if platinum_time(achs)}
    platinum = [u for u in unlocks if (u['store'], u['app']) in finished]
    return {'ever': [card(u) for u in rarest_unlocks(unlocks, n)],
            'month': [card(u) for u in rarest_unlocks(unlocks, n, month_start(now_time))],
            'platinum': [card(u) for u in rarest_unlocks(platinum, n)]}


def store_rows(classes, found, lib):
    """Every store OmaTrophy knows, for Settings: whether it was found here
    and how many of its games have achievements."""
    counts = {}
    for s, _, _ in lib:
        counts[s.id] = counts.get(s.id, 0) + 1
    found_ids = {s.id for s in found}
    return [{'id': c.id, 'name': c.name, 'found': c.id in found_ids, 'games': counts.get(c.id, 0)} for c in classes]


def library_playtime(found):
    """{(store id, game): {'total', 'recent'}} minutes for every game a store
    keeps playtime for, achievements or not."""
    out = {}
    for s in found:
        try:
            out.update({(s.id, g): v for g, v in s.playtime().items()})
        except Exception:
            continue
    return out


def playtime_totals(playtime):
    """Minutes played in all and in the past two weeks, over every game; a
    store that keeps no two-week figure adds nothing to `recent`."""
    return {'total': sum(v['total'] for v in playtime.values()),
            'recent': sum(v['recent'] or 0 for v in playtime.values())}


def favorite_game(lib, playtime, hidden=()):
    """(store, game, achievements) of the most played game with
    achievements, hidden ones aside; None when no store keeps playtime."""
    best, most = None, 0
    for s, g, achs in lib:
        minutes = playtime.get((s.id, g), {}).get('total', 0)
        if minutes > most and game_key(s.id, g) not in hidden:
            best, most = (s, g, achs), minutes
    return best


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


def now(recent_n=3, rarest_n=8, nearest_n=4):
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
    playtime = library_playtime(found)
    def minutes(key):
        return playtime.get(key, {}).get('total', 0)
    recent = []
    for when, key in recent_games(played, by_key, skip, recent_n):
        s, achs = by_key[key]
        recent.append(dict(game_card(s, key[1], achs, when), minutes=minutes(key)))
    shelf = sorted((dict(game_card(s, g, achs), latest=[]) for s, g, achs in lib if platinum_time(achs)),
                   key=lambda c: -c['platinum'])
    # The panel hides games live, before the next read: a few extra rarest
    # unlocks and nearest games let it drop a hidden one and still fill.
    # The rarest list shows three and the Profile showcase six.
    hidden = hidden_games()
    favorite = None
    best = favorite_game(lib, playtime, hidden)
    if best:
        s, g, achs = best
        pcts = s.known_percents(g)
        rare = sum(1 for a in achs if a['unlocked'] and tier(pcts.get(a['api'])) == 'gold')
        favorite = dict(game_card(s, g, achs), minutes=minutes((s.id, g)), rare=rare)
    nearest = []
    for r in nearest_platinum(rows, nearest_n + 2, hidden):
        s, achs = by_key[(r['store'], r['app'])]
        nearest.append(dict(game_card(s, r['app'], achs), latest=[]))
    return dict(totals(rows), metals=metal_tally(lib), completion=average_completion(rows),
                started=sum(1 for r in rows if r['unlocked']), playtime=playtime_totals(playtime),
                favorite=favorite, showcase=showcase_items(showcase_keys(), by_key),
                playing=playing, recent=recent, shelf=shelf, nearest=nearest,
                stores=store_rows(stores.STORES, found, lib),
                rarest=rarest_cards(lib, rarest_n, time.time(), hidden))


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


# Fields of a panel or tracker answer that hold an image URL.
IMAGE_KEYS = ('header', 'hero', 'icon', 'icon_locked')
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
# Images fetched after one answer; the rest wait for the next read.
IMAGE_BATCH = 600


def image_name(url):
    """Where an image's local copy lives under the cache, named by a hash of
    its URL so any store's art and icons share one folder."""
    ext = os.path.splitext(urllib.parse.urlsplit(url).path)[1].lower()
    return f'images/{hashlib.sha1(url.encode()).hexdigest()}{ext if ext in IMAGE_EXTS else ""}'


def local_images(value, missing):
    """`value` with every store image URL in it swapped for its local copy
    when there is one; URLs without a copy yet are added to `missing`. The
    panel is rebuilt on every open and Quickshell keeps no disk cache, so a
    URL is a fresh download each time."""
    if isinstance(value, list):
        return [local_images(v, missing) for v in value]
    if not isinstance(value, dict):
        return value
    out = {}
    for key, v in value.items():
        if key in IMAGE_KEYS and isinstance(v, str) and trusted_url(v):
            path = f'{CACHE}/{image_name(v)}'
            if os.path.exists(path):
                v = 'file://' + path
            elif v not in missing:
                missing.append(v)
        out[key] = local_images(v, missing)
    return out


def save_images(urls, threads=8):
    """Fetch images into the cache, eight at a time; a failed one is retried
    by the next read that names it."""
    with ThreadPoolExecutor(threads) as pool:
        list(pool.map(lambda url: cached(url, image_name(url)), urls[:IMAGE_BATCH]))


def save_images_later(urls):
    """Fetch the missing images after the answer is out, in a detached child:
    the panel reads until this process exits, and shouldn't wait on the CDN."""
    if not urls:
        return
    sys.stdout.flush()
    if os.fork():
        return
    try:
        os.setsid()
        quiet = os.open(os.devnull, os.O_RDWR)
        for fd in (0, 1, 2):
            os.dup2(quiet, fd)
        save_images(urls)
    finally:
        os._exit(0)


def print_with_images(value):
    """Print an answer with local images where cached, then fetch the rest."""
    missing = []
    print(json.dumps(local_images(value, missing)))
    save_images_later(missing)


def panel_answer(name, value):
    """Print a read for the bar panel and keep a copy: the panel is rebuilt on
    every open, and shows the copy at once while this fresh read runs. A copy
    that can't be written only costs the next open its head start."""
    missing = []
    value = local_images(value, missing)
    try:
        write_json(f'{CACHE}/panel/{name}.json', value)
    except OSError:
        pass
    print(json.dumps(value))
    save_images_later(missing)


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
    print_with_images(game_detail(store, app))


def config_path():
    # Resolved per call so tests can point HOME at a temporary folder.
    return os.path.expanduser('~/.config/omatrophy/config.json')


SETTINGS = {'position': ('top-center', 'top-left', 'top-right'),
            'sound': ('on', 'off', 'omatrophy', 'classic'),
            'icons': ('omarchy', 'vector', 'painted'),
            'glass': ('clear', 'frosted', 'solid'),
            'tracker-sort': ('recent', 'rarity', 'name', 'game'),
            # The panel's last picks, so the next open shows the same view.
            'games-sort': ('recent', 'closest', 'name'),
            'rarest': ('ever', 'month', 'platinum'),
            'community': ('on', 'off')}
# The Now tab's sections, each shown unless switched off in Settings.
NOW_SECTIONS = ('metals', 'recent', 'rarest', 'shelf')
SETTINGS.update({f'now-{name}': ('on', 'off') for name in NOW_SECTIONS})
# Settings stored as true/false rather than the word given.
SWITCHES = {'community'} | {f'now-{name}' for name in NOW_SECTIONS}


def set_option(key, value):
    """Write one setting to ~/.config/omatrophy/config.json; the shell picks it up live.
    `sound` takes on/off, or a chime set, which also turns sound on."""
    if value not in SETTINGS.get(key, ()):
        raise SystemExit(f'usage: omatrophy.py set position {"|".join(SETTINGS["position"])}\n'
                         f'       omatrophy.py set sound {"|".join(SETTINGS["sound"])}\n'
                         f'       omatrophy.py set icons {"|".join(SETTINGS["icons"])}\n'
                         f'       omatrophy.py set glass {"|".join(SETTINGS["glass"])}\n'
                         f'       omatrophy.py set tracker-sort {"|".join(SETTINGS["tracker-sort"])}\n'
                         f'       omatrophy.py set games-sort {"|".join(SETTINGS["games-sort"])}\n'
                         f'       omatrophy.py set rarest {"|".join(SETTINGS["rarest"])}\n'
                         f'       omatrophy.py set community on|off\n'
                         f'       omatrophy.py set now-{{{",".join(NOW_SECTIONS)}}} on|off')
    path = config_path()
    cfg = read_json(path, {})
    if key == 'sound':
        cfg['sound'] = value != 'off'
        if value not in ('on', 'off'):
            cfg['chimes'] = value
    elif key in SWITCHES:
        cfg[key] = value == 'on'
    else:
        cfg[key] = value
    write_json(path, cfg, indent=2)
    print(f'{key} = {value}')


def game_key(store_id, game):
    return f'{store_id}:{game}'


def hidden_games():
    """{"store:game"} the owner hid from "closest to platinum" and the platinum shelf; a broken list reads as empty."""
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


# The Profile tab's showcase holds as many picks as one row of tiles.
SHOWCASE_MAX = 6


def showcase_keys():
    """The owner's showcase picks, in the order picked: "store:game:api" for
    one achievement, "store:game" for a game's platinum."""
    keys = read_json(config_path(), {}).get('showcase', [])
    return [k for k in keys if isinstance(k, str)] if isinstance(keys, list) else []


def with_showcase(keys, key, add):
    """The showcase list with `key` added at the end or removed; None when
    adding to a full showcase, so the caller can say so."""
    # A hand-edited list can be anything; a string would read letter by letter.
    out = [k for k in keys if isinstance(k, str) and k != key] if isinstance(keys, list) else []
    if not add:
        return out
    if len(out) >= SHOWCASE_MAX:
        return None
    return out + [key]


def set_showcase(store_id, game, api, add):
    """Pin or unpin one achievement (or, with no api, a game's platinum)."""
    if store_id not in [cls.id for cls in stores.STORES] or not game or ':' in game:
        raise SystemExit('usage: omatrophy.py showcase add|remove '
                         f'{"|".join(cls.id for cls in stores.STORES)} <game id> [achievement api]')
    key = game_key(store_id, game) + (f':{api}' if api else '')
    path = config_path()
    cfg = read_json(path, {})
    keys = with_showcase(cfg.get('showcase', []), key, add)
    if keys is None:
        raise SystemExit(f'The showcase is full ({SHOWCASE_MAX}); remove one first: omatrophy.py showcase remove ...')
    cfg['showcase'] = keys
    write_json(path, cfg, indent=2)
    print(f'{"pinned" if add else "unpinned"}: {key}')


def showcase_items(keys, by_key):
    """The picks still earned, as tiles: an unlocked achievement with its
    rarity, or a finished game's platinum with its art. Picks whose game
    or unlock is gone are skipped, not shown broken."""
    out = []
    for key in keys:
        store_id, _, rest = key.partition(':')
        game, _, api = rest.partition(':')
        found = by_key.get((store_id, game))
        if not found:
            continue
        s, achs = found
        if not api:
            when = platinum_time(achs)
            if when:
                out.append({'key': key, 'store': store_id, 'app': game, 'api': '', 'name': 'Platinum',
                            'icon': s.art(game)['header'], 'time': when, 'percent': None, 'tier': 'platinum',
                            'game': s.game_name(game)})
            continue
        a = next((a for a in achs if a['api'] == api and a['unlocked']), None)
        if a:
            pct = s.known_percents(game).get(api)
            out.append(dict(brief(a), key=key, store=store_id, app=game, api=api, percent=pct,
                            tier=tier(pct), game=s.game_name(game)))
    return out


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
        panel_answer('now', now())
    elif cmd == 'games':
        panel_answer('games', games())
    elif cmd == 'game':
        game(argv[2:])
    elif cmd == 'demo':
        demo(argv[2:] or ['unlock', 'rare', 'platinum'])
    elif cmd == 'set' and len(argv) == 4:
        set_option(argv[2], argv[3])
    elif cmd == 'sync':
        sync()
    elif cmd == 'showcase' and len(argv) in (5, 6) and argv[2] in ('add', 'remove'):
        set_showcase(argv[3], argv[4], argv[5] if len(argv) == 6 else '', argv[2] == 'add')
    elif cmd in ('hide', 'unhide') and len(argv) == 4:
        set_hidden(argv[2], argv[3], cmd == 'hide')
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    try:
        main(sys.argv)
    except KeyboardInterrupt:
        pass
