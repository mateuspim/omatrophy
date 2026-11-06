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
  omatrophy.py guide [store app]      the 100% guide of one game, as JSON ({} when none; docs/specs/guides.md)
  omatrophy.py guide import <folder> [--replace]
                                      copy guide files in from another folder (read-only on it)
  omatrophy.py guide make <store> <app> [--no-web] [--agent a] [--model m] [--effort e]
                                      make a guide through your agent (ADR 14); guide stop|status|agents
  omatrophy.py guide model <agent> <model> [effort] [@http://endpoint]|default
  omatrophy.py guide jail             is ai-jail installed, is the sandbox on, each agent's jail options
  omatrophy.py guide jail-options <agent> [--map <file> --env NAME ...]
                                      extra ai-jail options for that agent (a local model's key file); none clears
  omatrophy.py guide check <agent> [model] [--jail]
                                      check on a real run that the agent stays locked down; a pass enables it
  omatrophy.py guide bench <store> <app> <agent:model[:effort][@endpoint]>... [--no-web] [--jail|--no-jail] [--pick] [--keep]
                                      make one game's guide with each, side by side, and rank them
  omatrophy.py set guide-agent default|claude|...   set guide-web on|off   set guide-jail on|off
  omatrophy.py set position <where>   top-center, top-left or top-right (applies live)
  omatrophy.py set glass <look>       clear, frosted or solid toast background
  omatrophy.py set sound on|off|omatrophy|classic
  omatrophy.py set icons omarchy|vector|painted
  omatrophy.py set tracker-sort recent|rarity|name|game
  omatrophy.py set games-sort recent|closest|name
  omatrophy.py set rarest ever|month|platinum
  omatrophy.py set community on|off   fill in games this machine never ran from your public Steam profile
  omatrophy.py sync                   run that backfill now, with progress
  omatrophy.py steam-load [all]       have Steam cache the stats of played games not tried yet (ADR 13);
                                      `all` tries every played game without stats again
  omatrophy.py steam-load stop|status stop a running load; or its progress, as JSON
  omatrophy.py hide <store> <game>    keep a game you won't finish out of "closest to platinum"
  omatrophy.py unhide <store> <game>  bring it back
  omatrophy.py favorite <store> <game>|clear
                                      the Profile tab's favorite game
  omatrophy.py completionist add|remove <store> <game>
                                      pin a finished game to the Profile's completionist tile
  omatrophy.py showcase|completionist order <key>...
                                      save a new order for the pins (every key once)
  omatrophy.py showcase add|remove <store> <game> [api]
                                      pin a trophy (or, with no api, the game's platinum) to the Profile showcase

Each store (stores/) reads its launcher's own files; this file diffs them and
turns new unlocks into events. Steam and GOG (through Heroic) so far.
"""
import hashlib, json, os, signal, sys, threading, time, urllib.parse
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
    # A game with no baseline only just appeared (first played, or cached
    # by Load from Steam): all its unlocks look new.
    known = key in seen
    achs, now = unlocked_set(store, game)
    new = now - seen.get(key, set())
    seen[key] = now
    cutoff = time.time() - FRESH_SECONDS
    # A remote unlock came through an online backfill: it happened on
    # another machine, so it isn't news here (ADR 11). An unlock with no
    # time (Steam set the bit but stored none) is news only against a
    # baseline; in a game just appeared it is as old as any other.
    fresh = [a for a in achs if a['api'] in new and not a.get('remote')
             and (a['time'] >= cutoff if a['time'] else known)]
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


def backfill_schedule_path():
    # Read at call time, not import time, so tests can move HOME.
    return os.path.expanduser('~/.local/state/omatrophy/backfill.json')


def saved_backfill_schedule():
    """{next: unix seconds, wait: seconds} from the last run; {} if none."""
    found = read_json(backfill_schedule_path(), {})
    return found if isinstance(found, dict) else {}


def save_backfill_schedule(failed, now):
    """Work out the wait after a run and keep it on disk, so a watcher
    restart (every shell restart) waits it out instead of asking Steam
    again inside a rate limit. Returns the wait in seconds."""
    previous = saved_backfill_schedule().get('wait')
    if not isinstance(previous, int) or previous <= 0:
        previous = BACKFILL_WAIT
    wait = next_backfill_wait(failed, previous)
    write_json(backfill_schedule_path(), {'next': int(now) + wait, 'wait': wait})
    return wait


def pending_backfill_wait(now):
    """Seconds the watcher still waits before its next run: what is left
    of the saved wait. Capped at BACKFILL_MAX_WAIT, so a clock jump or a
    hand-edited file can't stop the backfill for good."""
    due = saved_backfill_schedule().get('next')
    if not isinstance(due, (int, float)):
        return 0
    return int(min(max(due - now, 0), BACKFILL_MAX_WAIT))


def backfill_once(found, say=None):
    """One backfill run of every store: True when any of them failed,
    False when they all ran cleanly, None when none ran (all off)."""
    if say is None:
        # Progress goes to the shell log; stdout is for events only.
        say = lambda s, line: print(f'omatrophy: {s.id} backfill: {line}', file=sys.stderr, flush=True)
    failed = None
    for s in found:
        try:
            result = s.backfill(say=lambda line, s=s: say(s, line))
        except Exception as e:
            print(f'omatrophy: {s.name} backfill failed: {e}', file=sys.stderr, flush=True)
            result = (0, True)
        if result is not None:
            failed = bool(failed) or bool(result[1])
    return failed


def background(found, pairs, sleep=time.sleep, clock=time.time):
    """The watcher's slow chores, after `ready`: warm the name and rarity caches, then
    let each store backfill games it has no local data for, again and
    again for as long as the watcher runs."""
    warm_names(pairs)
    warm_rarity(pairs)
    while True:
        # Checked before every run, not only at start: the saved time may
        # have moved since (a restart, or a `sync` that met a 429).
        pending = pending_backfill_wait(clock())
        if pending:
            sleep(pending)
            continue
        failed = backfill_once(found)
        # A pass where every backfill is off says nothing about the limit,
        # and saving it would delay the first run after one is turned on.
        sleep(BACKFILL_WAIT if failed is None else save_backfill_schedule(failed, clock()))


def sync():
    """Run every store's backfill now, printing progress."""
    found = found_stores()
    if not read_json(config_path(), {}).get('community'):
        raise SystemExit('The community backfill is off. Turn it on with: omatrophy.py set community on\n'
                         '(it needs a public Steam profile with public game details; see ADR 11)')

    def say(s, line):
        print(f'{s.id}: {line}', flush=True)

    failed = backfill_once(found, say=say)
    if failed is None:
        return
    # A manual run counts like the watcher's: after a 429 here the
    # watcher waits too.
    wait = save_backfill_schedule(failed, time.time())
    print(('stopped early; ' if failed else '') + f'next automatic run in {wait // 60} min')


# A running load rewrites its status at least every WAIT_SECONDS; one quiet
# for longer than this died without saying so (killed, logged out).
STEAM_LOAD_STALE = 60


def steam_store(found=None):
    steam = next((s for s in (found or stores.available()) if s.id == 'steam'), None)
    if not steam:
        raise SystemExit('Steam was not found. Install it and sign in, or set STEAM_DIR=/path/to/Steam')
    return steam


def steam_load_busy(state, now):
    """True when another load is still running."""
    return state.get('state') == 'running' and now - state.get('time', 0) < STEAM_LOAD_STALE


def steam_load_status():
    """{missing, unchecked, status} for the panel: played games without
    stats here, those no load has tried yet, and the latest run."""
    from stores import steam_loader
    steam = steam_store()
    played = steam.missing(everything=True)
    tried = steam_loader.checked()
    print(json.dumps({'missing': len(played), 'unchecked': len([a for a in played if not steam_loader.settled(tried, a)]),
                      'status': steam_loader.status()}))


def steam_load(everything=False):
    """Load missing games' stats through the Steam client, printing progress."""
    from stores import steam_loader
    others = stores.available()
    steam = steam_store(others)
    if steam_load_busy(steam_loader.status(), time.time()):
        raise SystemExit('A load from Steam is already running. Stop it with: omatrophy.py steam-load stop')
    # A kill (or a closed terminal) must still run the loader's cleanup,
    # or Steam's window stays on the hidden workspace.
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: sys.exit(1))
    # Steam's window must not jump over a game from any store.
    busy = lambda: any(s.running() for s in others)
    result = steam.load_from_steam(busy, say=lambda line: print(f'steam: {line}', flush=True), everything=everything)
    if result['state'] == 'failed':
        raise SystemExit(1)


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


def favorite_card(s, game, achs, minutes, n=6):
    """The Profile tab's favorite game: its card, hours, how many of its
    unlocks are rare (gold), and its n rarest unlocks, rarest first."""
    pcts = s.known_percents(game)
    unlocked = [dict(brief(a), api=a['api'], percent=pcts.get(a['api']), tier=tier(pcts.get(a['api'])),
                     store=s.id, app=game) for a in achs if a['unlocked']]
    ranked = sorted((u for u in unlocked if u['percent'] is not None), key=lambda u: (u['percent'], -u['time']))
    return dict(game_card(s, game, achs), minutes=minutes, rarest=ranked[:n],
                rare=sum(1 for u in unlocked if u['tier'] == 'gold'))


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
    # With a guide, Up next follows its route (missables first); without
    # one, the locked achievements most players have.
    plan = guide_next(store.id, game, achs)
    by_api = {a['api']: a for a in achs}
    upcoming = [by_api[api] for api in plan] if plan else next_up(achs, pcts, 3)
    card['guide'] = bool(plan)
    card['next'] = [dict(brief(a), api=a['api'], icon=a.get('icon_locked') or a['icon'],
                         desc='' if a.get('hidden') else a['desc'], percent=pcts.get(a['api']),
                         progress=a.get('progress'), **guide_hint(plan.get(a['api']), a.get('hidden')))
                    for a in upcoming]
    return card


def guide_next(store_id, game, achs):
    """{api: plan item} for the guide's next three open achievements, in
    its order; {} with no guide. A broken guide only costs the hints."""
    import guides
    try:
        answer = guides.guide_answer(store_id, game, achs)
    except Exception:
        return {}
    by_api = {a['api']: a for a in achs}
    return {api: dict(answer['items'][api], api=api) for api in answer.get('next', []) if api in by_api}


def guide_hint(item, hidden=False):
    """The few plan fields the Now tab's Up next shows: time, missable and
    one tip (`guide_time`, not `time`: that is the unlock time); a hidden achievement's tip stays out (spoilers)."""
    if not item:
        return {'guide_time': '', 'missable': False, 'missable_note': '', 'tip': ''}
    return {'guide_time': item.get('time') or '', 'missable': bool(item.get('missable')),
            'missable_note': item.get('missable_note') or '', 'tip': '' if hidden else item.get('tips') or ''}


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
    store_id, _, game = favorite_key().partition(':')
    if (store_id, game) in by_key:
        s, achs = by_key[(store_id, game)]
        favorite = favorite_card(s, game, achs, minutes((store_id, game)))
    nearest = []
    for r in nearest_platinum(rows, nearest_n + 2, hidden):
        s, achs = by_key[(r['store'], r['app'])]
        nearest.append(dict(game_card(s, r['app'], achs), latest=[]))
    return dict(totals(rows), metals=metal_tally(lib), completion=average_completion(rows),
                started=sum(1 for r in rows if r['unlocked']), playtime=playtime_totals(playtime),
                favorite=favorite, showcase=showcase_items(showcase_keys(), by_key),
                completionist=completionist_cards(completionist_keys(), by_key),
                playing=playing, recent=recent, shelf=shelf, nearest=nearest,
                stores=store_rows(stores.STORES, found, lib),
                rarest=rarest_cards(lib, rarest_n, time.time(), hidden))


def games():
    """Every game with achievements as a slim card, for the Games tab. Names
    and store headers not cached yet are looked up eight at a time, so a
    first open of a large library takes seconds, not minutes; later opens
    read the cache."""
    found = found_stores()
    lib = library(found)
    played = {(s.id, g): t for s in found for t, g in s.recent()}
    hidden = hidden_games()
    with ThreadPoolExecutor(8) as pool:
        names = list(pool.map(lambda item: item[0].game_name(item[1]), lib))
        headers = list(pool.map(lambda item: item[0].art(item[1])['header'], lib))
    return [dict(progress_row(s, g, achs), game=name, header=header,
                 platinum=platinum_time(achs), played=played.get((s.id, g), 0),
                 hidden=game_key(s.id, g) in hidden)
            for (s, g, achs), name, header in zip(lib, names, headers)]


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


def guide(args):
    """`guide [store app]` prints the guide as JSON; `guide import <folder> [--replace]` copies guides in."""
    import guides
    if args[:1] == ['import'] and len(args) in (2, 3) and args[2:] in ([], ['--replace']):
        imported, skipped = guides.import_guides(args[1], replace=len(args) == 3)
        print(f'imported {imported}, skipped {skipped}')
        return
    if args[:1] in (['make'], ['stop'], ['status'], ['agents'], ['model'], ['jail'], ['jail-options'], ['bench'], ['check']):
        return guide_job(args)
    found = found_stores()
    if not args:
        store, app = pick_game(found)
    elif len(args) == 2 and args[0] in [s.id for s in found]:
        store, app = next(s for s in found if s.id == args[0]), args[1]
    else:
        raise SystemExit(f'usage: omatrophy.py guide [{"|".join(s.id for s in found)} <game id>]\n'
                         '       omatrophy.py guide import <folder> [--replace]\n'
                         '       omatrophy.py guide make <store> <app> [--no-web] [--notify] [--jail|--no-jail] [--agent a] [--model m] [--effort e]\n'
                         '       omatrophy.py guide stop|status|agents\n'
                         '       omatrophy.py guide model <agent> <model> [effort] [@http://endpoint] | default\n'
                         '       omatrophy.py guide jail | jail-options <agent> [ai-jail options...]')
    print(json.dumps(guides.guide_answer(store.id, app, store.achievements(app))))


def guide_job(args):
    """`guide make/stop/status/agents/model` (docs/specs/guides.md, ADR 14)."""
    import guide_agents, guide_maker
    cmd = args[0]
    cfg = read_json(config_path(), {})
    cfg = cfg if isinstance(cfg, dict) else {}
    game_args = args[1:3] if len(args) == 3 else ['', '']
    if cmd == 'stop' and len(args) in (1, 3):
        n = guide_maker.request_stop(None, *game_args)
        print('stop requested' if n else 'no guide is being made')
    elif cmd == 'status' and len(args) in (1, 3):
        print(json.dumps(guide_maker.status(None, *game_args)))
    elif cmd == 'jobs':
        print(json.dumps({'jobs': guide_maker.jobs(), 'max': guide_maker.MAX_JOBS}))
    elif cmd == 'agents':
        print(json.dumps(guide_agents.listing(cfg)))
    elif cmd == 'model' and 3 <= len(args) <= 5 and args[1] in guide_agents.BY_ID:
        models = guide_agents.picks(cfg)
        # `@http://...` names a local endpoint (claude: ANTHROPIC_BASE_URL).
        endpoint = next((a[1:] for a in args[3:] if a.startswith('@')), '')
        effort = next((a for a in args[3:] if not a.startswith('@')), '')
        if endpoint:
            guide_agents.endpoint_env(guide_agents.BY_ID[args[1]], endpoint)
        if args[2] == 'default':
            models.pop(args[1], None)
        else:
            models[args[1]] = {'model': args[2], 'effort': effort, 'endpoint': endpoint}
        cfg['guide-models'] = models
        write_json(config_path(), cfg, indent=2)
        print(f'{args[1]}: {args[2]}' + (f' ({effort})' if effort else '') + (f' at {endpoint}' if endpoint else ''))
    elif cmd == 'jail' and len(args) == 1:
        guide_jail(cfg)
    elif cmd == 'jail-options' and len(args) >= 2 and args[1] in guide_agents.BY_ID:
        guide_jail_options(args[1], args[2:], cfg)
    elif cmd == 'make' and len(args) >= 3:
        guide_make(args[1], args[2], args[3:], cfg)
    elif cmd == 'bench' and len(args) >= 4:
        guide_bench(args[1], args[2], args[3:], cfg)
    elif cmd == 'check' and 2 <= len(args) <= 4 and args[1] in guide_agents.BY_ID:
        guide_check(args[1], args[2:])
    else:
        raise SystemExit('usage: omatrophy.py guide make <store> <app> [--no-web] [--agent a] [--model m] [--effort e]\n'
                         '       omatrophy.py guide model <agent> <model> [effort] [@http://endpoint] | default\n'
                         '       omatrophy.py guide jail | jail-options <agent> [ai-jail options...]\n'
                         '       omatrophy.py guide bench <store> <app> <agent:model[:effort][@endpoint]>... '
                         '[--no-web] [--jail|--no-jail] [--pick] [--keep]\n'
                         '       omatrophy.py guide check <agent> [model] [--jail]')


def use_jail(asked, cfg, say=print):
    """Whether a guide job runs inside ai-jail. `asked` is the run's
    --jail/--no-jail (None: the setting). An explicit --jail without
    ai-jail fails; the saved setting with ai-jail gone (removed, or a
    config copied from another machine) counts as off and says so, so a
    make still runs behind the agent's own lock."""
    import guide_agents
    jail = cfg.get('guide-jail') is True if asked is None else asked
    if not jail or guide_agents.jail_installed():
        return jail
    if asked:
        raise SystemExit(f'omatrophy: guide: ai-jail not found; install it ({guide_agents.JAIL_HOME}), '
                         'or leave out --jail')
    say(f'note: sandbox is on but ai-jail is not installed, so the agent runs without it '
        f'(its own lock still applies); get it at {guide_agents.JAIL_HOME}')
    return False


def guide_jail(cfg):
    """`guide jail`: is ai-jail here, is the sandbox on, and what each agent
    adds to it; exits non-zero when ai-jail isn't installed."""
    import shlex, shutil, guide_agents
    version = guide_agents.jail_version()
    if not guide_agents.jail_installed():
        raise SystemExit(f'omatrophy: guide: ai-jail not found; install it ({guide_agents.JAIL_HOME}) '
                         'to run the agent inside it')
    print(f'ai-jail {version or "(version unknown)"} at {shutil.which("ai-jail")}, by Akita: {guide_agents.JAIL_HOME}')
    print('sandbox: ' + ('on' if cfg.get('guide-jail') is True else 'off (omatrophy.py set guide-jail on)'))
    for a in guide_agents.ADAPTERS:
        options = guide_agents.saved_jail_options(a.id, cfg)
        if options:
            print(f'{a.id}: ' + ' '.join(shlex.quote(o) for o in options))
    print('check an agent in it: omatrophy.py guide check <agent> [model] --jail')


def guide_jail_options(agent, words, cfg):
    """`guide jail-options <agent> [options...]`: the extra ai-jail options
    that agent runs with when the sandbox is on, such as a local model's
    `--map` of its key file; none clears them. One string from the panel is
    split like a shell would."""
    import shlex, guide_agents
    if len(words) == 1 and ' ' in words[0].strip():
        try:
            words = shlex.split(words[0])
        except ValueError as e:
            raise SystemExit(f'omatrophy: guide jail-options: could not read {words[0]!r} ({e}); check the quotes')
    words = [w for w in words if w.strip()]
    options = guide_agents.jail_options(words)
    found = cfg.get('guide-jail-options')
    saved = dict(found) if isinstance(found, dict) else {}
    if options:
        saved[agent] = options
    else:
        saved.pop(agent, None)
    cfg['guide-jail-options'] = saved
    write_json(config_path(), cfg, indent=2)
    print(f'{agent} in ai-jail: ' + (' '.join(shlex.quote(o) for o in options) if options else 'no extra options'))


def guide_check(agent, words):
    """`guide check <agent> [model] [--jail]`: the lock check on a real run;
    a pass (without --jail) lets that agent make guides. The panel follows
    it through guide/check.json."""
    import guide_agents
    adapter = guide_agents.BY_ID[agent]
    jail = '--jail' in words
    model = next((w for w in words if not w.startswith('--')), '')
    if not adapter.installed():
        raise SystemExit(f'omatrophy: guide check: {agent} not found; install it first')
    if not guide_agents.headless(adapter):
        raise SystemExit(f'omatrophy: guide check: OmaTrophy has no headless command for {agent} yet, so there is '
                         'nothing to check (docs/specs/guides.md, Agent adapters)')
    if jail and not guide_agents.jail_installed():
        raise SystemExit('omatrophy: guide check: ai-jail not found')
    path = guide_agents.check_status_path()
    lines = []

    def say(line):
        lines.append(line)
        print(line, flush=True)
        write_json(path, {'agent': agent, 'jail': jail, 'state': 'running', 'lines': lines, 'time': int(time.time()),
                          'pid': os.getpid()})

    say(f'checking {agent}' + (f' ({model})' if model else '') + ': asking it to write a file and run a command')
    try:
        result = guide_agents.check_lock(adapter, model=model, jail=jail, say=say)
    except BaseException:
        write_json(path, {'agent': agent, 'jail': jail, 'state': 'failed', 'lines': lines + ['interrupted'],
                          'time': int(time.time())})
        raise
    verdict = ('PASS: ' + (f'{agent} runs inside ai-jail' if jail else f'{agent} can make guides now')) if result['passed'] \
        else f'FAIL: {agent} stays off'
    say(verdict)
    write_json(path, {'agent': agent, 'jail': jail, 'state': 'passed' if result['passed'] else 'failed', 'lines': lines,
                      'time': int(time.time()), 'runs': result['runs']})
    if not result['passed']:
        raise SystemExit(1)


def guide_target(store_id, app):
    """(store, achievements with rarity, minutes played) for a guide job."""
    found = found_stores()
    store = next((s for s in found if s.id == store_id), None)
    if not store:
        raise SystemExit(f'usage: omatrophy.py guide make|bench {"|".join(s.id for s in found)} <game id> ...')
    pcts = store.percents(app)
    achs = [dict(a, percent=pcts.get(a['api'])) for a in store.achievements(app)]
    if not achs:
        raise SystemExit(f'{store.name} has no achievements cached for {app}; launch it once in {store.name}')
    return store, achs, library_playtime([store]).get((store.id, app), {}).get('total', 0)


def guide_bench(store_id, app, words, cfg):
    """`guide bench`: make one game's guide with each agent:model given,
    side by side, and rank them (guide_bench.py)."""
    import guide_agents, guide_bench as bench
    flags = {w for w in words if w.startswith('--')}
    unknown = flags - {'--no-web', '--jail', '--no-jail', '--pick', '--keep'}
    if unknown:
        raise SystemExit(f'omatrophy: guide bench: unknown option {sorted(unknown)[0]}')
    entries = [bench.parse_entry(w) for w in words if not w.startswith('--')]
    if not entries:
        raise SystemExit('omatrophy: guide bench: name at least one agent:model, e.g. claude:sonnet claude:opus:high')
    for e in entries:
        guide_agents.resolve(e['agent'])
    jail = use_jail(True if '--jail' in flags else False if '--no-jail' in flags else None, cfg)
    web = '--no-web' not in flags and cfg.get('guide-web', True) is not False
    store, achs, minutes = guide_target(store_id, app)
    run_dir, results = bench.bench(store.id, app, store.game_name(app), achs, entries, web=web, jail=jail,
                                   minutes=minutes)
    print()
    print(bench.table(results))
    print(f'\nresults: {run_dir}/results.json')
    best = next((r for r in results if r['state'] == 'done'), None)
    if not best:
        raise SystemExit('omatrophy: guide bench: no entry made a guide; see the lines above')
    if '--pick' in flags:
        cfg['guide-agent'] = best['agent']
        models = guide_agents.picks(cfg)
        models[best['agent']] = {'model': best['model'], 'effort': best['effort'], 'endpoint': best['endpoint']}
        cfg['guide-models'] = models
        write_json(config_path(), cfg, indent=2)
        print(f'default now: {best["entry"]}')
    if '--keep' in flags:
        bench.keep(best)
        print(f'kept {best["entry"]}\'s guide for this game (the old one is .prev)')


def guide_make(store_id, app, flags, cfg):
    import guide_agents, guide_maker
    opts, web, i = {}, cfg.get('guide-web', True) is not False, 0
    while i < len(flags):
        if flags[i] == '--no-web':
            web, i = False, i + 1
        elif flags[i] == '--notify':
            opts['notify'], i = True, i + 1
        elif flags[i] in ('--jail', '--no-jail'):
            opts['jail'], i = flags[i] == '--jail', i + 1
        elif flags[i] in ('--agent', '--model', '--effort') and i + 1 < len(flags):
            opts[flags[i][2:]], i = flags[i + 1], i + 2
        else:
            raise SystemExit(f'omatrophy: guide make: unknown option {flags[i]}')
    adapter = guide_agents.resolve(opts.get('agent', cfg.get('guide-agent') or ''))
    jail = use_jail(opts.get('jail'), cfg)
    pick = guide_agents.picks(cfg).get(adapter.id, {})
    if guide_maker.busy(None, store_id, app):
        raise SystemExit(f'omatrophy: guide: this game\'s guide is being made; stop it with: omatrophy.py guide stop {store_id} {app}')
    if len(guide_maker.running()) >= guide_maker.MAX_JOBS:
        raise SystemExit(f'omatrophy: guide: {guide_maker.MAX_JOBS} guides are being made already; make this one when one ends, '
                         'or stop one with: omatrophy.py guide stop <store> <app>')
    store, achs, minutes = guide_target(store_id, app)
    # Nothing open: a make only spent the agent's tokens on filler.
    if all(a.get('unlocked') for a in achs):
        raise SystemExit(f'omatrophy: guide: {store.game_name(app)} is already at 100%; there is nothing left for '
                         'a guide to plan')
    job = guide_maker.Job(store.id, app, store.game_name(app), achs, adapter, model=opts.get('model', pick.get('model', '')),
                          effort=opts.get('effort', pick.get('effort', '')), web=web, minutes=minutes, jail=jail,
                          header=store.art(app)['header'],
                          # The saved endpoint goes with the saved model (the tracker
                          # passes --model too); another model is a cloud one.
                          env=guide_agents.endpoint_env(adapter, pick.get('endpoint', '')
                                                        if opts.get('model', pick.get('model')) == pick.get('model') else ''),
                          say=lambda line: print(line, flush=True))
    if guide_maker.make(job, announce=opts.get('notify', False))['state'] == 'failed':
        raise SystemExit(1)


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
            'settings-section': ('overview', 'toasts', 'now', 'guides', 'stores'),
            'community': ('on', 'off'),
            'guide-web': ('on', 'off'),
            'guide-jail': ('on', 'off'),
            # The tracker's Reveal all, kept across opens and games.
            'reveal-hidden': ('on', 'off')}
# The Now tab's sections, each shown unless switched off in Settings.
NOW_SECTIONS = ('metals', 'recent', 'rarest', 'shelf')
SETTINGS.update({f'now-{name}': ('on', 'off') for name in NOW_SECTIONS})
# Settings stored as true/false rather than the word given.
SWITCHES = {'community', 'guide-web', 'guide-jail', 'reveal-hidden'} | {f'now-{name}' for name in NOW_SECTIONS}


def set_option(key, value):
    """Write one setting to ~/.config/omatrophy/config.json; the shell picks it up live.
    `sound` takes on/off, or a chime set, which also turns sound on."""
    if key == 'guide-key':
        # Installed from Settings > Guides only when the owner asks (ADR 18);
        # `none` removes it.
        import guide_key
        parsed = guide_key.parse('' if value == 'none' else value)
        if parsed is None:
            raise SystemExit(f'omatrophy: set guide-key: "{value}" is not a key; write it like {guide_key.DEFAULT}, or none')
        value = parsed['spec']
        path = config_path()
        cfg = read_json(path, {})
        cfg = cfg if isinstance(cfg, dict) else {}
        cfg[key] = value
        write_json(path, cfg, indent=2)
        print(f'guide-key = {value or "none"}')
        return
    if key == 'guide-agent':
        import guide_agents
        if value != 'default' and value not in guide_agents.BY_ID:
            raise SystemExit(f'usage: omatrophy.py set guide-agent default|{"|".join(guide_agents.BY_ID)}')
        value = '' if value == 'default' else value
    elif value not in SETTINGS.get(key, ()):
        raise SystemExit(f'usage: omatrophy.py set position {"|".join(SETTINGS["position"])}\n'
                         f'       omatrophy.py set sound {"|".join(SETTINGS["sound"])}\n'
                         f'       omatrophy.py set icons {"|".join(SETTINGS["icons"])}\n'
                         f'       omatrophy.py set glass {"|".join(SETTINGS["glass"])}\n'
                         f'       omatrophy.py set tracker-sort {"|".join(SETTINGS["tracker-sort"])}\n'
                         f'       omatrophy.py set games-sort {"|".join(SETTINGS["games-sort"])}\n'
                         f'       omatrophy.py set rarest {"|".join(SETTINGS["rarest"])}\n'
                         f'       omatrophy.py set community on|off\n'
                         f'       omatrophy.py set reveal-hidden on|off\n'
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


def favorite_key():
    """The owner's favorite game as "store:game", or "" when none is set."""
    key = read_json(config_path(), {}).get('favorite', '')
    return key if isinstance(key, str) else ''


def set_favorite(store_id, game):
    """Make one game the Profile tab's favorite; no game clears it."""
    if store_id == 'clear' and not game:
        key = ''
    elif store_id in [cls.id for cls in stores.STORES] and game and ':' not in game:
        key = game_key(store_id, game)
    else:
        raise SystemExit('usage: omatrophy.py favorite '
                         f'{"|".join(cls.id for cls in stores.STORES)} <game id>\n'
                         '       omatrophy.py favorite clear')
    path = config_path()
    cfg = read_json(path, {})
    cfg['favorite'] = key
    write_json(path, cfg, indent=2)
    print(f'favorite: {key or "none"}')


# The Profile tab's showcase holds as many picks as one row of tiles.
SHOWCASE_MAX = 6


def showcase_keys():
    """The owner's showcase picks, in the order picked: "store:game:api" for
    one achievement, "store:game" for a game's platinum."""
    keys = read_json(config_path(), {}).get('showcase', [])
    return [k for k in keys if isinstance(k, str)] if isinstance(keys, list) else []


def with_showcase(keys, key, add, limit=SHOWCASE_MAX):
    """A pin list (showcase, completionist) with `key` added at the end or
    removed; None when adding to a full list, so the caller can say so."""
    # A hand-edited list can be anything; a string would read letter by letter.
    out = [k for k in keys if isinstance(k, str) and k != key] if isinstance(keys, list) else []
    if not add:
        return out
    if len(out) >= limit:
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


# The completionist tile shows finished games two to a row, two rows.
COMPLETIONIST_MAX = 4


def completionist_keys():
    """The finished games the owner pinned to the completionist tile, as
    "store:game", in the order pinned."""
    keys = read_json(config_path(), {}).get('completionist', [])
    return [k for k in keys if isinstance(k, str)] if isinstance(keys, list) else []


def set_completionist(store_id, game, add):
    """Pin or unpin one finished game on the completionist tile."""
    if store_id not in [cls.id for cls in stores.STORES] or not game or ':' in game:
        raise SystemExit('usage: omatrophy.py completionist add|remove '
                         f'{"|".join(cls.id for cls in stores.STORES)} <game id>')
    key = game_key(store_id, game)
    path = config_path()
    cfg = read_json(path, {})
    keys = with_showcase(cfg.get('completionist', []), key, add, COMPLETIONIST_MAX)
    if keys is None:
        raise SystemExit(f'The completionist tile is full ({COMPLETIONIST_MAX}); remove one first: '
                         'omatrophy.py completionist remove ...')
    cfg['completionist'] = keys
    write_json(path, cfg, indent=2)
    print(f'{"pinned" if add else "unpinned"}: {key}')


def completionist_cards(keys, by_key):
    """The pinned games still at 100%, as shelf cards; others are skipped."""
    out = []
    for key in keys:
        store_id, _, game = key.partition(':')
        found = by_key.get((store_id, game))
        if found and platinum_time(found[1]):
            out.append(dict(game_card(found[0], game, found[1]), key=key, latest=[]))
    return out


def reordered(keys, order):
    """`order` when it holds exactly the pins in `keys`, else None: a
    reorder never adds or drops one."""
    current = [k for k in keys if isinstance(k, str)] if isinstance(keys, list) else []
    return list(order) if sorted(order) == sorted(current) and len(set(order)) == len(order) else None


def set_pin_order(name, order):
    """Save a new order for the `showcase` or `completionist` pins."""
    path = config_path()
    cfg = read_json(path, {})
    keys = reordered(cfg.get(name, []), order)
    if keys is None:
        raise SystemExit(f'omatrophy.py {name} order: give every pinned key once, in the new order '
                         f'(now: {" ".join(cfg.get(name, [])) or "none"})')
    cfg[name] = keys
    write_json(path, cfg, indent=2)
    print(f'{name}: {" ".join(keys)}')


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
    elif cmd == 'guide':
        guide(argv[2:])
    elif cmd == 'demo':
        demo(argv[2:] or ['unlock', 'rare', 'platinum'])
    elif cmd == 'set' and len(argv) == 4:
        set_option(argv[2], argv[3])
    elif cmd == 'guide-key' and argv[2:] == ['free']:
        import guide_key
        raw = guide_key.hyprctl('-j', 'binds')
        try:
            binds = json.loads(raw) if raw else []
        except ValueError:
            binds = []
        print(json.dumps(guide_key.free(binds if isinstance(binds, list) else [])))
    elif cmd == 'guide-key' and len(argv) == 4 and argv[2] == 'check':
        import guide_key
        print(json.dumps(guide_key.check(argv[3])))
    elif cmd == 'guide-key' and len(argv) == 3:
        # Called by Service.qml with config.json's `guide-key` (ADR 18).
        import guide_key
        print(json.dumps(guide_key.sync(argv[2])))
    elif cmd == 'sync':
        sync()
    elif cmd == 'steam-load' and argv[2:] in ([], ['all']):
        steam_load(everything=argv[2:] == ['all'])
    elif cmd == 'steam-load' and argv[2:] == ['stop']:
        from stores import steam_loader
        steam_loader.request_stop()
    elif cmd == 'steam-load' and argv[2:] == ['status']:
        steam_load_status()
    elif cmd == 'favorite' and len(argv) in (3, 4):
        set_favorite(argv[2], argv[3] if len(argv) == 4 else '')
    elif cmd in ('showcase', 'completionist') and len(argv) >= 3 and argv[2] == 'order':
        set_pin_order(cmd, argv[3:])
    elif cmd == 'completionist' and len(argv) == 5 and argv[2] in ('add', 'remove'):
        set_completionist(argv[3], argv[4], argv[2] == 'add')
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
