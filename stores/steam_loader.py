"""Load from Steam: have the Steam client cache the stats of played games.

Steam writes appcache/stats/UserGameStats_<account>_<app>.bin only once its
client has loaded a game's stats: by playing it, or just by opening its
library page. Most played games are invisible to OmaTrophy only because
this machine never did either. Opening each page through a steam:// link
fills the cache locally, with no key and no rate limit (ADR 13). Steam's
window moves page to page while it runs, so only the owner starts it,
never the watcher.
"""
import json, os, shutil, subprocess, time

from .base import CACHE, read_json, write_json
from .steam_community import app_id

PAGE = 'steam://nav/games/details/{app}'
# On 2026-11-04 Fallout 4's stats files appeared within a second of its page
# opening; a game with no achievements never gets one, so the wait is a
# few seconds, not a minute, or a library of them would take hours.
WAIT_SECONDS = 8
POLL_SECONDS = 0.25
# Steam's window waits here while a load runs. Hyprland draws a special
# workspace only when someone toggles it, so the pages open out of sight.
HIDDEN_WORKSPACE = 'special:omatrophy'
# hyprctl answers in milliseconds; a hung compositor shouldn't hang a load.
HYPRCTL_SECONDS = 4
# The client's main window. A load closes it again only when it appeared
# during the load (Steam sat in the tray); any other new window (Friends,
# a sign-in dialog) is the user's and comes back to their workspace.
MAIN_TITLE = 'Steam'
# Steam offline or still signing in loads nothing, and every game would
# time out and pass for one without achievements. After this many
# timeouts in a row the load stops and keeps those games unsure, to try
# first next time. Most played go first, so a real run that long is rare
# (180 of 313 games had none on the owner's library, and 0.57^15 is about
# 1 in 4500 per position); an unsure game that times out again is
# settled as none and doesn't count toward a new streak, so a library
# that has one can't stop every load.
TIMEOUT_STREAK = 15
# The panel's progress strip shows this many of the latest results.
RECENT_KEPT = 6


def cache_dir():
    return f'{CACHE}/steam-load'


def checked():
    """{app: {time, found}} of every game a load has tried: the checkpoint.
    A tried game is never tried again unless the owner asks for the whole
    library (`steam-load all`), so a later load only sees games played
    since, and a stopped one picks up where it ended. `found` is None for
    a game left unsure by a timeout streak, tried again by the next load."""
    found = read_json(f'{cache_dir()}/checked.json', {})
    return found if isinstance(found, dict) else {}


def settled(tried, app):
    """True when a load has tried `app` and its answer stands."""
    entry = tried.get(app)
    return isinstance(entry, dict) and entry.get('found') is not None


def unsure(tried, app):
    entry = tried.get(app)
    return isinstance(entry, dict) and 'found' in entry and entry['found'] is None


def status():
    """The latest run's progress, {time, line, done, total, loaded, none,
    app, everything, state}; state is running, done, stopped or failed.
    {} before any run."""
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


def missing(playtimes, local, tried, everything=False):
    """Played apps with no local stats file, most played first, leaving
    out those a load already tried unless `everything`.
    `playtimes` is {app: {'total', ...}} in minutes, `local` the apps
    with a stats file, `tried` checked()."""
    rows = [(p.get('total', 0), app) for app, p in playtimes.items()
            if app_id(app) and p.get('total', 0) > 0 and app not in local
            and (everything or not settled(tried, app))]
    # Unsure games first: they were next in line when the streak stopped.
    return [app for _, _, app in sorted(((not unsure(tried, app), -t, app) for t, app in rows),
                                        key=lambda r: (r[0], r[1], int(r[2])))]


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


def lua_string(text):
    """A Lua string literal for hyprctl's Lua dispatch (Hyprland 0.56+)."""
    return '"' + str(text).replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def hyprctl(*args):
    """hyprctl's answer, or None when it fails or isn't there."""
    try:
        done = subprocess.run(['hyprctl', *args], capture_output=True, text=True, timeout=HYPRCTL_SECONDS)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return done.stdout if done.returncode == 0 else None


class SteamWindow:
    """Keeps Steam's window out of sight while pages open, on Hyprland.

    A steam:// link activates the client's window, and with
    misc:focus_on_activate on Hyprland jumps to it. So each Steam window
    moves to HIDDEN_WORKSPACE, with focus_on_activate off for that window
    only (Omarchy turns it off the same way for Telegram), and goes back
    where it was afterwards. Hyprland's config is never touched. A main
    window that only appeared during the load (Steam sat in the tray) is
    closed again, which puts Steam back in the tray; other new windows
    come to the active workspace. Without Hyprland nothing happens and
    Steam's window comes forward as before."""

    def __init__(self, ctl=None):
        # Looked up now, not at import, so tests can swap the module's hyprctl.
        self.ctl = ctl or hyprctl
        self.enabled = bool(os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')) and \
            (ctl is not None or shutil.which('hyprctl') is not None)
        self.before = None   # addresses of Steam windows when the load began
        self.moved = {}      # address -> workspace it came from

    def windows(self):
        """Steam's windows, or None when hyprctl didn't answer: no answer
        is not "no windows", or the user's own window would count as one
        the load opened and be closed at the end."""
        answer = self.ctl('clients', '-j')
        if answer is None:
            return None
        try:
            clients = json.loads(answer)
        except ValueError:
            return None
        if not isinstance(clients, list):
            return None
        return [c for c in clients if isinstance(c, dict) and c.get('class') == 'steam' and c.get('address')]

    def dispatch(self, lua):
        self.ctl('dispatch', lua)

    def set_focus_on_activate(self, address, value):
        # A Lua `false` reads as a missing value to set_prop; 0 and 1 work,
        # and "unset" drops the window's override (checked on Hyprland
        # 0.56.2: border_size 7 went back to the global 2; other strings
        # are ignored).
        value = lua_string(value) if isinstance(value, str) else int(value)
        self.dispatch(f'hl.dsp.window.set_prop({{ window = {lua_string("address:" + address)}, '
                      f'prop = "focus_on_activate", value = {value} }})')

    def move(self, address, workspace):
        self.dispatch(f'hl.dsp.window.move({{ window = {lua_string("address:" + address)}, '
                      f'workspace = {lua_string(workspace)}, follow = false }})')

    def hide(self):
        if not self.enabled:
            return
        found = self.windows()
        if found is None:
            return
        if self.before is None:
            self.before = {c['address'] for c in found}
        for c in found:
            name = (c.get('workspace') or {}).get('name', '')
            if name == HIDDEN_WORKSPACE:
                continue
            self.moved.setdefault(c['address'], name)
            self.set_focus_on_activate(c['address'], 0)
            self.move(c['address'], HIDDEN_WORKSPACE)

    def active_workspace(self):
        """The workspace the user is on, or None when hyprctl didn't say."""
        try:
            name = json.loads(self.ctl('activeworkspace', '-j') or '{}').get('name')
        except (ValueError, AttributeError):
            return None
        return name if isinstance(name, str) and name else None

    def restore(self):
        if not self.enabled or not self.moved:
            return
        # Titles as they are now; unknown (hyprctl silent) is never "main",
        # so a window is moved rather than closed when in doubt.
        titles = {c['address']: c.get('title') for c in self.windows() or []}
        active = None
        for address, workspace in self.moved.items():
            # Unset, not the global value: a window rule of the user's
            # (or a later config change) applies again.
            self.set_focus_on_activate(address, 'unset')
            if address in (self.before or set()):
                self.move(address, workspace)
            elif titles.get(address) == MAIN_TITLE:
                self.dispatch(f'hl.dsp.window.close({{ window = {lua_string("address:" + address)} }})')
            else:
                active = active or self.active_workspace()
                if active:
                    self.move(address, active)
        self.moved = {}


def wait_for(has_stats, app, wait, poll, clock, sleep):
    """'loaded' once has_stats(app), 'none' after `wait` seconds, and
    'stopped' as soon as a stop is requested: Stop shouldn't wait out a
    game with no achievements."""
    end = clock() + wait
    while True:
        if has_stats(app):
            return 'loaded'
        if stop_requested():
            return 'stopped'
        if clock() >= end:
            return 'none'
        sleep(poll)


def load(todo, has_stats, busy, opener=open_page, running=steam_running, say=None,
         wait=WAIT_SECONDS, poll=POLL_SECONDS, clock=time.time, sleep=time.sleep, window=None,
         everything=False, describe=None, prepare=None):
    """Open each app's page in turn and wait for its stats file. Stops when
    Steam closes, a game starts (`busy()`: Steam's window must not jump
    over a game) or a stop is requested. Each tried game goes into
    checked.json at once, so a stopped run resumes at the next game.
    `describe(app)` gives {name, art} for the panel's progress strip,
    from what is already on disk; `prepare(app)` is told the next game
    while the current one loads (the store warms its name). Returns
    {loaded, none, state}."""
    clear_stop()
    tried = checked()
    counts = {'loaded': 0, 'none': 0}
    describe = describe or (lambda app: {'name': '', 'art': ''})
    started = int(clock())
    recent = []
    # Whether Steam's window waits out of sight, so the panel can say so.
    hidden = [False]

    def report(line, state, done, app='', found=None):
        if found is not None:
            recent.insert(0, dict(describe(app), app=app, found=found))
            del recent[RECENT_KEPT:]
            app = ''
        write_json(f'{cache_dir()}/status.json', dict(
            counts, time=int(clock()), started=started, line=line, done=done, total=len(todo), app=app,
            current=dict(describe(app), app=app) if app else None, recent=recent,
            everything=everything, hidden=hidden[0], state=state))
        if say and line:
            say(line)

    def end(line, state, done):
        report(line, state, done)
        return dict(counts, state=state)

    if not todo:
        return end('up to date', 'done', 0)
    window = window or SteamWindow()
    # Before the first page, so a window already open never shows it.
    window.hide()
    hidden[0] = bool(getattr(window, 'enabled', False))
    # The panel's bar shows up before the first game is done.
    report('', 'running', 0)
    try:
        return run(todo, has_stats, busy, opener, running, wait, poll, clock, sleep, window, tried, counts, report, end,
                   prepare or (lambda app: None))
    except BaseException:
        # A kill or a bug: the panel would show a live run until the status
        # went stale; say it ended.
        end('stopped: the load was interrupted; load again', 'failed', sum(counts.values()))
        raise
    finally:
        window.restore()


def run(todo, has_stats, busy, opener, running, wait, poll, clock, sleep, window, tried, counts, report, end, prepare):
    """load()'s loop, with Steam's window kept out of sight."""
    retried = {app for app in todo if unsure(tried, app)}
    streak = []
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
        # After the open: a Steam that sat in the tray only now has a window.
        window.hide()
        # The panel's progress bar names the game being tried.
        report('', 'running', i, app)
        if i + 1 < len(todo):
            prepare(todo[i + 1])
        found = wait_for(has_stats, app, wait, poll, clock, sleep)
        if found == 'stopped':
            clear_stop()
            return end(f'stopped: {i} of {len(todo)} done', 'stopped', i)
        counts['loaded' if found == 'loaded' else 'none'] += 1
        tried[app] = {'time': int(clock()), 'found': found == 'loaded'}
        if found == 'loaded':
            streak.clear()
        elif app not in retried:
            streak.append(app)
        if len(streak) >= TIMEOUT_STREAK:
            for a in streak:
                tried[a]['found'] = None
            write_json(f'{cache_dir()}/checked.json', tried)
            counts['none'] -= len(streak)
            return end(f'stopped: {len(streak)} games in a row gave no stats; Steam may be offline or still '
                       'signing in. Load again once it is online', 'failed', i + 1)
        write_json(f'{cache_dir()}/checked.json', tried)
        report(f"{i + 1}/{len(todo)} {app}: " + ('loaded' if found == 'loaded' else 'no stats'), 'running', i + 1,
               app, found == 'loaded')
    return end(f"done: {counts['loaded']} loaded, {counts['none']} without achievements", 'done', len(todo))
