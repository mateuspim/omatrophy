"""Steam's public Community profile, as a backfill for games this machine never ran.

Steam keeps a game's stats file only once the game has run here (ADR 1), so
a fresh install knows a handful of games. A public profile's achievement
page has the rest without a key: it embeds its data as JSON in
<script id="valve-ssr-data">, whose renderContext.queryData holds the
react-query cache (schema, the user's unlocks, the store item). Only that
JSON is read, never the markup (ADR 11). Opt-in with `set community on`.
"""
import json, os, re, time, urllib.request

from .base import CACHE, read_json, write_json

STEAMID64_BASE = 76561197960265728
PAGE = 'https://steamcommunity.com/profiles/{id64}/stats/{app}/achievements/'
SSR = re.compile(r'<script[^>]*id="valve-ssr-data"[^>]*>(.*?)</script>', re.S)
# A page is refetched when the game was played since; otherwise after a
# week for games played in the last 60 days and after 60 days for the rest,
# whose unlocks rarely move: a full refresh of a few hundred pages takes
# hours under Steam's rate limit. A dormant game with nothing unlocked
# waits half a year, and a finished one only refreshes when played, since
# unlocks need play. "No achievements" holds for a month.
FRESH_SECONDS = 7 * 86400
ACTIVE_SECONDS = 60 * 86400
DORMANT_SECONDS = 60 * 86400
UNTOUCHED_SECONDS = 180 * 86400
NONE_SECONDS = 30 * 86400
# Valve doesn't publish a rate. On 2026-10-27 it answered 429 after about
# 20 pages in two and a half minutes, and once limited it kept answering
# 429 for over two hours. So a run fetches at most PAGES_PER_RUN pages,
# gently paced, and a 429 ends it; the watcher runs it again later
# (omatrophy.py's background loop) instead of waiting minutes in a run.
PAUSE_SECONDS = 3
PAGES_PER_RUN = 15

def cache_dir():
    return f'{CACHE}/community'


def steamid64(account):
    return STEAMID64_BASE + int(account)


def queries(html):
    """{queryKey as a tuple: data} from the page's embedded react-query cache, or None."""
    m = SSR.search(html)
    if not m:
        return None
    try:
        q = json.loads(json.loads(m.group(1))['renderContext']['queryData'])
        return {tuple(x['queryKey']): x['state'].get('data') for x in q['queries']}
    except (ValueError, KeyError, TypeError):
        return None


def parse_page(html, app):
    """{'name', 'achievements': [...]} for one game, in the shape the Steam
    store answers, or None when the page has no achievement data (a game
    without achievements redirects to the profile, which has none)."""
    found = queries(html)
    if not found:
        return None
    schema, user, info = None, None, None
    for key, data in found.items():
        if len(key) >= 3 and key[0] == 'achievements' and str(key[1]) == str(app):
            if key[2] == 'schema':
                schema = data
            elif key[2] == 'user_achievements':
                user = data
        elif len(key) >= 3 and key[0] == 'StoreItem' and key[1] == f'app_{app}' and key[2] == 'default_info':
            info = data
    if not isinstance(schema, dict) or not isinstance(user, dict):
        return None
    got = user.get('achievements') or {}
    out = []
    for group in schema.get('groups') or []:
        for a in group.get('achievements') or []:
            if a.get('archived') or a.get('developeronly'):
                continue
            mine = got.get(str(a.get('internal_key'))) or {}
            unlocked = bool(mine.get('unlocked'))
            out.append({'api': str(a.get('api_name', '')), 'name': str(a.get('name', '')),
                        'desc': str(a.get('description') or ''),
                        'icon': a.get('icon_achieved', ''), 'icon_locked': a.get('icon_unachieved', ''),
                        'hidden': bool(a.get('hidden')), 'unlocked': unlocked,
                        'time': int(mine.get('unlock_time') or 0) if unlocked else 0})
    if not out:
        return None
    name = info.get('name') if isinstance(info, dict) else None
    return {'name': name, 'achievements': out}


def fetch(account, app):
    """The parsed page for one game, None for a game without achievements.
    Raises on network errors so the caller can stop the run."""
    url = PAGE.format(id64=steamid64(account), app=app)
    req = urllib.request.Request(url, headers={'User-Agent': 'omatrophy'})
    with urllib.request.urlopen(req, timeout=4) as r:
        return page_or_none(r.read().decode('utf8', 'replace'), app, r.geturl())


def page_or_none(html, app, final_url):
    """A game without achievements redirects off its achievements page; a
    page that stays there yet carries no data is an error (throttled, a
    changed layout), not "none", or the game would be skipped for a month."""
    page = parse_page(html, app)
    path = final_url.split('?')[0].rstrip('/')
    if page is None and (path.endswith(f'/achievements/{app}') or path.endswith(f'/stats/{app}/achievements')):
        raise ValueError(f'achievement page for {app} had no data')
    return page


def cached(app):
    """The cached page for one game, {'time', 'name', 'achievements'}; {} when none."""
    return read_json(f'{cache_dir()}/games/{app}.json', {})


def cached_games():
    """{app: mtime} of games with a cached page. A folder listing, no
    parsing: the watcher asks every second."""
    try:
        return {e.name[:-5]: e.stat().st_mtime for e in os.scandir(f'{cache_dir()}/games')
                if e.name.endswith('.json')}
    except OSError:
        return {}


def none_index():
    """{app: unix seconds} of games found to have no achievements."""
    return read_json(f'{cache_dir()}/none.json', {})


def due(app, played, now, nones):
    """True when a game's page should be fetched: never fetched, played
    since the last fetch, or stale for how recently it was played."""
    if app in nones:
        return now - nones[app] > NONE_SECONDS
    c = cached(app)
    if not c:
        return True
    fetched = c.get('time', 0)
    if played > fetched:
        return True
    achievements = c.get('achievements') or []
    unlocked = sum(1 for a in achievements if a.get('unlocked'))
    if achievements and unlocked == len(achievements):
        return False
    if now - played < ACTIVE_SECONDS:
        limit = FRESH_SECONDS
    else:
        limit = UNTOUCHED_SECONDS if unlocked == 0 else DORMANT_SECONDS
    return now - fetched > limit

def write_atomic(path, value):
    """Write then rename, so the watcher never reads half a file."""
    write_json(path + '.tmp', value)
    os.replace(path + '.tmp', path)


def status():
    """The backfill's latest line, {time, line, done, total}; {} before the first run."""
    return read_json(f'{cache_dir()}/status.json', {})


def backfill(account, played, local, fetch_page=fetch, pause=PAUSE_SECONDS, say=None, sleep=time.sleep,
             budget=PAGES_PER_RUN):
    """Fetch the pages of played games with no local stats file, most recent
    first, at most `budget` of them. Any error (a rate limit, offline, a
    private profile) ends the run, and the next one resumes where it stopped.
    `played` is [(unix seconds, app)], `local` the apps with local stats.
    Returns (fetched, failed: bool)."""
    now = time.time()
    nones = none_index()
    todo = [(t, app) for t, app in played if app not in local and due(app, t, now, nones)]
    fetched = 0
    shout = say

    def say(line):
        # Also kept in status.json, so progress is visible without the
        # shell log (and the panel can show it).
        write_atomic(f'{cache_dir()}/status.json',
                     {'time': int(time.time()), 'line': line, 'done': fetched, 'total': len(todo)})
        if shout:
            shout(line)

    for i, (_, app) in enumerate(todo[:budget]):
        if i:
            sleep(pause)
        try:
            page = fetch_page(account, app)
        except Exception as e:
            say(f'stopped at {app}: {e}')
            return fetched, True
        if page:
            write_atomic(f'{cache_dir()}/games/{app}.json', dict(page, time=int(time.time())))
        else:
            nones[app] = int(time.time())
            write_atomic(f'{cache_dir()}/none.json', nones)
        fetched += 1
        say(f'{i + 1}/{len(todo)} {app}: ' + (f"{len(page['achievements'])} achievements" if page else 'none'))
    if not todo:
        say('up to date')
    elif len(todo) > budget:
        say(f'paused: {fetched} fetched, {len(todo) - fetched} left for later runs')
    else:
        say(f'done: {fetched} fetched')
    return fetched, False
