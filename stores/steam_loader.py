"""Load from Steam: have the Steam client cache the stats of played games.

Steam writes appcache/stats/UserGameStats_<account>_<app>.bin only once its
client has loaded a game's stats: by playing it, or just by opening its
library page. Most played games are invisible to OmaTrophy only because
this machine never did either. Opening each page through a steam:// link
fills the cache locally, with no key and no rate limit (ADR 13). Steam's
window moves page to page while it runs, so only the owner starts it,
never the watcher.
"""
import os, subprocess, time

from .base import CACHE, read_json, write_json
from .steam_community import app_id

PAGE = 'steam://nav/games/details/{app}'
# On 2026-11-04 Fallout 4's stats files appeared within a second of its page
# opening; a game with no achievements never gets one, so the wait is a
# few seconds, not a minute, or a library of them would take hours.
WAIT_SECONDS = 8
POLL_SECONDS = 0.25
# A game that got no stats file is asked again after a month, in case it
# gained achievements or Steam was slow that once.
NONE_SECONDS = 30 * 86400


def cache_dir():
    return f'{CACHE}/steam-load'


def none_index():
    """{app: unix seconds} of games whose page opened without a stats file."""
    found = read_json(f'{cache_dir()}/none.json', {})
    return found if isinstance(found, dict) else {}


def status():
    """The latest run's progress, {time, line, done, total, loaded, none,
    state}; state is running, done, stopped or failed. {} before any run."""
    return read_json(f'{cache_dir()}/status.json', {})


def stop_path():
    return f'{cache_dir()}/stop'


def request_stop():
    """Ask a running load to stop after its current game."""
    os.makedirs(cache_dir(), exist_ok=True)
    with open(stop_path(), 'w'):
        pass


def stop_requested():
    return os.path.exists(stop_path())


def clear_stop():
    try:
        os.remove(stop_path())
    except FileNotFoundError:
        pass


def missing(playtimes, local, nones, now):
    """Played apps with no local stats file, most played first. A game
    tried in the last NONE_SECONDS without a file is skipped.
    `playtimes` is {app: {'total', ...}} in minutes, `local` the apps
    with a stats file, `nones` none_index()."""
    rows = [(p.get('total', 0), app) for app, p in playtimes.items()
            if app_id(app) and p.get('total', 0) > 0 and app not in local
            and (app not in nones or now - nones[app] > NONE_SECONDS)]
    return [app for _, app in sorted(rows, key=lambda r: (-r[0], int(r[1])))]


def steam_running(proc='/proc'):
    """True while the Steam client runs; a steam:// link would start it
    otherwise, and a start takes far longer than WAIT_SECONDS."""
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit()]
    except OSError:
        return False
    for pid in pids:
        try:
            with open(f'{proc}/{pid}/comm') as f:
                if f.read().strip() == 'steam':
                    return True
        except OSError:
            continue
    return False


def open_page(app):
    """Hand Steam a steam:// link to the game's library page. The `steam`
    command forwards it to the running client; xdg-open covers Flatpak."""
    url = PAGE.format(app=app)
    for cmd in (['steam', url], ['xdg-open', url]):
        try:
            subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
            return
        except FileNotFoundError:
            continue
    raise OSError('neither steam nor xdg-open is on PATH')


def wait_for(has_stats, app, wait, poll, clock, sleep):
    """True once has_stats(app), False after `wait` seconds."""
    end = clock() + wait
    while True:
        if has_stats(app):
            return True
        if clock() >= end:
            return False
        sleep(poll)


def load(todo, has_stats, busy, opener=open_page, running=steam_running, say=None,
         wait=WAIT_SECONDS, poll=POLL_SECONDS, clock=time.time, sleep=time.sleep):
    """Open each app's page in turn and wait for its stats file. Stops when
    Steam closes, a game starts (`busy()`: Steam's window must not jump
    over a game) or a stop is requested. Resumable: loaded games have a
    stats file next time, and empty ones wait in none.json.
    Returns {loaded, none, state}."""
    clear_stop()
    nones = none_index()
    counts = {'loaded': 0, 'none': 0}

    def report(line, state, done):
        write_json(f'{cache_dir()}/status.json', dict(
            counts, time=int(clock()), line=line, done=done, total=len(todo), state=state))
        if say:
            say(line)

    def end(line, state, done):
        report(line, state, done)
        return dict(counts, state=state)

    if not todo:
        return end('up to date', 'done', 0)
    for i, app in enumerate(todo):
        if stop_requested():
            clear_stop()
            return end(f'stopped: {i} of {len(todo)} done', 'stopped', i)
        if not running():
            return end('stopped: Steam is not running; start it and load again', 'failed', i)
        if busy():
            return end('stopped: a game is running; load again after it closes', 'failed', i)
        try:
            opener(app)
        except OSError as e:
            return end(f'stopped: could not open Steam ({e})', 'failed', i)
        if wait_for(has_stats, app, wait, poll, clock, sleep):
            counts['loaded'] += 1
            report(f'{i + 1}/{len(todo)} {app}: loaded', 'running', i + 1)
            continue
        counts['none'] += 1
        nones[app] = int(clock())
        write_json(f'{cache_dir()}/none.json', nones)
        report(f'{i + 1}/{len(todo)} {app}: no stats', 'running', i + 1)
    return end(f"done: {counts['loaded']} loaded, {counts['none']} without achievements", 'done', len(todo))
