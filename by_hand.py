"""Ticks, counts and notes by hand (ADR 21): the player's own word on
achievements the store doesn't see. Format: docs/specs/by-hand.md.

One file, `~/.local/share/omatrophy/by-hand.json`, keyed "store:app" then
by achievement api. Only `omatrophy.py hand ...` writes it; the tracker
runs that command and never writes a file itself. A tick is never an
unlock: it counts as done for the guide (`guides.guide_answer`'s `ticks`)
and nowhere else.
"""
import errno, fcntl, json, os, shutil, stat, tempfile, time

from stores.base import write_json

FORMAT = 1
NOTE_MAX = 1000
GAME_NOTE_MAX = 4000
GAME_NOTE_KEY = 'game'
SECTIONS = ('ticks', 'counts', 'notes')


def hand_path():
    # Resolved per call so tests can point the environment elsewhere. Data,
    # not state: a note is the player's writing, kept with the guides.
    base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, 'omatrophy', 'by-hand.json')


def read_file(path=None):
    """(whole file, broken). Missing reads as empty and not broken; a file
    that isn't the expected JSON reads as empty and broken."""
    path = path or hand_path()
    try:
        with open(path, encoding='utf-8') as f:
            whole = json.load(f)
    except FileNotFoundError:
        return {'format': FORMAT, 'games': {}}, False
    except (OSError, ValueError):
        return {'format': FORMAT, 'games': {}}, True
    if not isinstance(whole, dict) or not isinstance(whole.get('games'), dict):
        return {'format': FORMAT, 'games': {}}, True
    return whole, False


def game_entry(store, app, path=None):
    entry = read_file(path)[0]['games'].get(f'{store}:{app}')
    return entry if isinstance(entry, dict) else {}


def section(entry, name):
    value = entry.get(name)
    return value if isinstance(value, dict) else {}


def game_hand(store, app, achievements, path=None):
    """The `hand` block `game` gives: ticks (not unlocked since), unticks,
    counts and notes for achievements the game still has, and the game's
    note. Hand-edited junk is skipped, not fixed: reads never write."""
    entry = game_entry(store, app, path)
    unlocked = {a['api'] for a in achievements if a.get('unlocked')}
    order = [a['api'] for a in achievements]
    ticks = section(entry, 'ticks')

    def done(api, value):
        return isinstance(ticks.get(api), dict) and ticks[api].get('done') is value

    counts = {}
    for api, c in section(entry, 'counts').items():
        value = c.get('value') if isinstance(c, dict) else None
        if api in order and isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            counts[api] = value
    notes = {}
    for api, n in section(entry, 'notes').items():
        text = n.get('text') if isinstance(n, dict) else None
        if api in order and isinstance(text, str) and text:
            notes[api] = text
    note = entry.get('note')
    note = note.get('text') if isinstance(note, dict) and isinstance(note.get('text'), str) else ''
    return {'ticks': [api for api in order if done(api, True) and api not in unlocked],
            'unticks': [api for api in order if done(api, False)],
            'counts': counts, 'notes': notes, 'note': note}


def merged_ticks(md_ticks, hand, achievements):
    """`guide`'s `ticks`: the guide .md's hand ticks plus the file's,
    minus the file's unticks, in the store's order."""
    want = (set(md_ticks) | set(hand.get('ticks') or [])) - set(hand.get('unticks') or [])
    return [a['api'] for a in achievements if a['api'] in want]


def clean_note(text, limit):
    """A note as saved: control characters other than newline dropped
    (they'd show as boxes, or move the cursor in a terminal), ends
    trimmed. ValueError over `limit` characters."""
    text = ''.join(' ' if ch == '\t' else ch for ch in text.replace('\r\n', '\n') if ch in '\n\t' or not control(ch)).strip()
    if len(text) > limit:
        raise ValueError(f'a note holds at most {limit} characters; this one has {len(text)}')
    return text


def control(ch):
    # C0, DEL and C1: none is text a note means to keep.
    return ord(ch) < 32 or 0x7f <= ord(ch) <= 0x9f


def parse_count(word, current, target):
    """The new count for `count <n|+n|-n|clear>`, clamped to 0..target;
    None for `clear`. ValueError for anything else."""
    if word == 'clear':
        return None
    sign = word[:1] if word[:1] in '+-' else ''
    digits = word[len(sign):]
    if not digits.isdigit():
        raise ValueError('give a count (12), a change (+1, -1) or clear')
    n = int(digits)
    value = current + n if sign == '+' else current - n if sign == '-' else n
    return max(0, min(target, value))


def set_tick(entry, api, done, now):
    entry.setdefault('ticks', {})[api] = {'done': done, 'time': now}


def set_count(entry, api, value, now):
    if value is None:
        section(entry, 'counts').pop(api, None)
    else:
        entry.setdefault('counts', {})[api] = {'value': value, 'time': now}


def set_note(entry, api, text, now):
    """Saves a note on `api`, or on the game for GAME_NOTE_KEY; "" removes it."""
    if api == GAME_NOTE_KEY:
        if text:
            entry['note'] = {'text': text, 'time': now}
        else:
            entry.pop('note', None)
    elif text:
        entry.setdefault('notes', {})[api] = {'text': text, 'time': now}
    else:
        section(entry, 'notes').pop(api, None)


def tidy(entry):
    """Drop sections left empty, so a game with nothing by hand leaves no trace."""
    for name in SECTIONS:
        if name in entry and not entry[name]:
            del entry[name]
    return entry


def update(store, app, change, path=None, clock=time.time):
    """Read, `change(entry, now)` one game's entry, write it back. An
    fcntl lock beside the file keeps two quick clicks (two processes) from
    losing one. A broken file is kept as `.bad` before starting anew.
    OSError (with a message saying what to fix) when the folder or the
    lock isn't safely ours."""
    path = path or hand_path()
    own_folder(os.path.dirname(path))
    with open_lock(path + '.lock') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        whole, broken = read_file(path)
        if broken:
            keep_bad(path)
        key = f'{store}:{app}'
        entry = whole['games'].get(key)
        entry = entry if isinstance(entry, dict) else {}
        for name in SECTIONS:
            if name in entry and not isinstance(entry[name], dict):
                del entry[name]
        change(entry, int(clock()))
        if tidy(entry):
            whole['games'][key] = entry
        else:
            whole['games'].pop(key, None)
        whole['format'] = FORMAT
        write_json(path, whole, indent=1, sort_keys=True)


def own_folder(folder):
    """Make the data folder private (0700) if new; refuse one that isn't a
    real folder of ours, or that others can write in: there another user
    could plant a link where we open a file (marketplace review, finding 9).
    Never chmods an existing folder: the player decides."""
    os.makedirs(folder, mode=0o700, exist_ok=True)
    st = os.lstat(folder)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise OSError(f'{folder} is not a folder owned by you; move it aside and try again')
    if st.st_mode & 0o022:
        raise OSError(f'{folder} can be written by other users; run `chmod go-w {folder}` and try again')


def open_lock(lock_path):
    """The lock file, opened without following a link and without
    truncating: a link planted at `lock_path` must not let us clobber the
    file it points at (finding 9). Refused unless a plain file of ours."""
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(lock_path, flags, 0o600)
    except OSError as e:
        if e.errno == errno.ELOOP:
            raise OSError(f'{lock_path} is a link; remove it and try again') from None
        raise
    st = os.fstat(fd)
    if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_nlink != 1:
        os.close(fd)
        raise OSError(f'{lock_path} is not a plain file of yours; remove it and try again')
    return os.fdopen(fd, 'r+')


def keep_bad(path):
    """Copy a broken file to `<file>.bad` through a temporary file and a
    rename, so a link already at `.bad` is replaced, not written through."""
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.' + os.path.basename(path), suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as out, open(path, 'rb') as f:
            shutil.copyfileobj(f, out)
        os.replace(tmp, path + '.bad')
    except BaseException:
        os.unlink(tmp)
        raise
