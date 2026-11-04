"""Make a 100% guide for one game through the user's agent (ADR 14).

The job runs in stages: gather (no model), research (the agent's own web
search, optional), classify (batches of about 15 achievements), route
(order and prose from the compact table) and verify (no model). OmaTrophy
gathers the sources and checks every quote against them; the agent only
writes. Files and shapes: docs/specs/guides.md.

Only the owner starts a job (`guide make` or the tracker's button), never
the watcher. Nothing is written until the last stage passes, so a stopped
or failed job leaves the old guide as it was.
"""
import html, html.parser, json, os, re, signal, sys, tempfile, time, urllib.error, urllib.parse, urllib.request

import guide_agents, guides
from stores.base import read_json, write_json

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(HERE, 'prompts', 'guide')
CHUNK_CHARS = 1500
BATCH_SIZE = 15
BATCH_CHARS = 12000
# Fetches made by OmaTrophy itself: an honest client name, a long-ish
# timeout (a job, not a toast), a page budget, and a size cap.
FETCH_SECONDS = 8
FETCH_PAGES = 10
FETCH_BYTES = 4 * 1024 * 1024
STEAM_GUIDE_PAGES = 3
SOURCES_KEPT = 30 * 86400
QUOTE_MIN, QUOTE_MAX = 12, 200
# The trusted sites, preferred in this order (spec "Trusted sites").
SITES = ('PowerPyx (powerpyx.com)', 'TrueAchievements (trueachievements.com)',
         'PlayStationTrophies (playstationtrophies.org)', 'XboxAchievements (xboxachievements.com)',
         'Steam community guides (steamcommunity.com/sharedfiles)', "the game's official wiki or Fandom wiki")
SITE_HOSTS = ('powerpyx.com', 'trueachievements.com', 'playstationtrophies.org', 'xboxachievements.com',
              'steamcommunity.com', 'fandom.com')
# Item fields the view marks "(unverified)" when no quote backs the item.
CLAIMS = ('time', 'missable', 'counter', 'tips', 'combine_with')
WORD = re.compile(r"[a-z0-9']+")
STOPWORDS = set('the and for with that this from your you are all any one into over have has its not but get '
                'got can will each every than then them they their what when where which while who also out '
                'complete completed achievement unlock unlocked game'.split())
# A page that is really a bot check, whatever its status code.
BOT_CHECK = re.compile(r'captcha|cf-challenge|just a moment\.\.\.|are you a robot|access denied', re.I)


def version():
    found = read_json(os.path.join(HERE, 'manifest.json'), {})
    return str(found.get('version') or '0') if isinstance(found, dict) else '0'


# ------------------------------------------------------------ status, stop

def status_path(folder=None):
    return os.path.join(folder or guides.guides_dir(), 'status.json')


def stop_path(folder=None):
    return os.path.join(folder or guides.guides_dir(), '.stop')


def status(folder=None):
    """The latest job, or {} before any. A job that died without saying so
    (killed, a crash) reads as failed rather than running forever."""
    found = read_json(status_path(folder), {})
    if not isinstance(found, dict):
        return {}
    if found.get('state') == 'running' and not alive(found.get('pid')):
        found = dict(found, state='failed', line='failed: the job ended without finishing; make it again')
    return found


def alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def busy(folder=None):
    return status(folder).get('state') == 'running'


def request_stop(folder=None):
    folder = folder or guides.guides_dir()
    os.makedirs(folder, exist_ok=True)
    with open(stop_path(folder), 'w'):
        pass


def stop_requested(folder=None):
    return os.path.exists(stop_path(folder))


def clear_stop(folder=None):
    try:
        os.remove(stop_path(folder))
    except FileNotFoundError:
        pass


# ------------------------------------------------------------ text helpers

def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', str(name).lower()).strip('-') or 'game'


def fold(text):
    """Text as quotes are compared: case, whitespace, quote marks and
    dashes folded, so a quote copied from a page still matches."""
    text = html.unescape(str(text)).lower()
    text = re.sub(r'[‘’‚‛′´`]', "'", text)
    text = re.sub(r'[“”„‟″]', '"', text)
    text = re.sub(r'[‐-―−]', '-', text)
    text = text.replace('…', '...')
    return re.sub(r'\s+', ' ', text).strip()


class TextOnly(html.parser.HTMLParser):
    """A page's readable text: scripts, styles and navigation dropped, a
    newline at each block."""
    SKIP = {'script', 'style', 'noscript', 'svg', 'nav', 'footer', 'header', 'form', 'iframe', 'template'}
    BLOCK = {'p', 'div', 'br', 'li', 'tr', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section', 'article', 'table', 'ul', 'ol'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skipping = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.BLOCK:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.skipping:
            self.parts.append(data)


def html_text(page):
    parser = TextOnly()
    try:
        parser.feed(page)
        parser.close()
    except Exception:
        pass
    lines = [re.sub(r'[ \t\r\f\v]+', ' ', line).strip() for line in ''.join(parser.parts).splitlines()]
    return '\n'.join(line for line in lines if line)


def chunk_text(text, size=CHUNK_CHARS):
    """Pieces of about `size` characters, cut at paragraph, then sentence,
    then word ends."""
    text = text.strip()
    out = []
    while len(text) > size:
        cut = max(text.rfind('\n', 0, size), text.rfind('. ', 0, size) + 1, size // 2)
        if cut <= size // 2:
            space = text.rfind(' ', 0, size)
            cut = space if space > size // 2 else size
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


def chunks(sources):
    """[{id: 'S<n>.<m>', url, text}] over every source, in order."""
    out = []
    for n, (url, source) in enumerate(sources.items(), 1):
        for m, piece in enumerate(chunk_text(source.get('text', '')), 1):
            out.append({'id': f'S{n}.{m}', 'url': url, 'text': piece, 'fold': fold(piece)})
    return out


def words(text):
    return {w for w in WORD.findall(fold(text)) if len(w) >= 3 and w not in STOPWORDS}


def site_rank(url):
    host = (urllib.parse.urlsplit(url).hostname or '').lower()
    for i, site in enumerate(SITE_HOSTS):
        if host == site or host.endswith('.' + site):
            return i
    return len(SITE_HOSTS)


def excerpts_for(ach, pieces, hints=(), n=3):
    """The chunks that best match one achievement: its name as a phrase
    scores most, then words of its name and description; a research quote
    for it pins its chunk first. Trusted sites win ties."""
    name = fold(ach['name'])
    want = words(ach['name']) | words(ach.get('desc', ''))
    hinted = [fold(h) for h in hints if h]
    scored = []
    for p in pieces:
        score = sum(1 for w in want if w in p['fold'])
        if name and name in p['fold']:
            score += 10
        if any(h and h in p['fold'] for h in hinted):
            score += 100
        if score:
            scored.append((-score, site_rank(p['url']), p['id'], p))
    scored.sort(key=lambda r: r[:3])
    return [r[3] for r in scored[:n]]


# ------------------------------------------------------------ fetching

class HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).scheme != 'https':
            raise urllib.error.HTTPError(newurl, code, f'refused redirect to {newurl}', headers, fp)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_page(url):
    """A page's text, or None when it isn't fetchable: not https, an error,
    a 403/429, or a bot check. Never retried with another client (ADR 14)."""
    if urllib.parse.urlsplit(str(url)).scheme != 'https':
        return None
    req = urllib.request.Request(url, headers={'User-Agent': f'omatrophy-guide/{version()}'})
    try:
        with urllib.request.build_opener(HttpsOnly).open(req, timeout=FETCH_SECONDS) as r:
            body = r.read(FETCH_BYTES).decode(r.headers.get_content_charset() or 'utf-8', 'replace')
            kind = r.headers.get_content_type()
    except Exception:
        return None
    if BOT_CHECK.search(body[:20000]) and len(body) < 200000:
        return None
    return html_text(body) if 'html' in kind else body


STEAM_GUIDE_LIST = 'https://steamcommunity.com/app/{app}/guides/?browsefilter=toprated&requiredtags%5B%5D=Achievements'
STEAM_GUIDE_ID = re.compile(r'sharedfiles/filedetails/\?id=(\d+)')


def steam_guide_urls(app, get=None):
    """Up to STEAM_GUIDE_PAGES top-rated Steam guides tagged Achievements.
    (2026-11-04: the list page answered without links once; then there are
    none, and the research stage may still find some.)"""
    get = get or raw_page
    page = get(STEAM_GUIDE_LIST.format(app=urllib.parse.quote(str(app)))) or ''
    ids = []
    for gid in STEAM_GUIDE_ID.findall(page):
        if gid not in ids:
            ids.append(gid)
    return [f'https://steamcommunity.com/sharedfiles/filedetails/?id={gid}' for gid in ids[:STEAM_GUIDE_PAGES]]


def raw_page(url):
    req = urllib.request.Request(url, headers={'User-Agent': f'omatrophy-guide/{version()}'})
    try:
        with urllib.request.build_opener(HttpsOnly).open(req, timeout=FETCH_SECONDS) as r:
            return r.read(FETCH_BYTES).decode('utf-8', 'replace')
    except Exception:
        return None


def saved_sources(folder):
    """Pages the owner saved into sources/<name>/: .html, .htm, .txt, .md."""
    out = {}
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return out
    for name in names:
        path = os.path.join(folder, name)
        ext = os.path.splitext(name)[1].lower()
        if ext not in ('.html', '.htm', '.txt', '.md') or not os.path.isfile(path):
            continue
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                text = f.read(FETCH_BYTES)
        except OSError:
            continue
        out[f'file:{name}'] = {'kind': 'saved', 'fetched': int(os.path.getmtime(path)),
                               'text': html_text(text) if ext in ('.html', '.htm') else text}
    return out


def kept_sources(path, now):
    """An earlier .sources.json, minus what is older than SOURCES_KEPT."""
    found = read_json(path, {})
    if not isinstance(found, dict):
        return {}
    return {url: s for url, s in found.items()
            if isinstance(s, dict) and isinstance(s.get('text'), str) and now - (s.get('fetched') or 0) < SOURCES_KEPT}


# ------------------------------------------------------------ answers

def tagged(text, tag):
    """The JSON between <tag> and </tag> (the last such block), or raises
    ValueError saying what is wrong."""
    found = re.findall(rf'<{tag}>\s*(.*?)\s*</{tag}>', text or '', re.S)
    if not found:
        raise ValueError(f'no <{tag}>...</{tag}> block in the answer')
    body = found[-1].strip()
    # A model may wrap the JSON in a Markdown fence inside the tags.
    body = re.sub(r'^```[a-z]*\s*|\s*```$', '', body)
    try:
        return json.loads(body)
    except ValueError as e:
        raise ValueError(f'the <{tag}> block is not valid JSON ({e})')


def check_cites(raw):
    out = []
    for c in raw if isinstance(raw, list) else []:
        if isinstance(c, dict) and isinstance(c.get('quote'), str) and isinstance(c.get('source'), str):
            out.append({'source': c['source'].strip(), 'quote': c['quote'].strip()})
    return out


def check_item(raw, names):
    """(item, errors) for one classified achievement; bad fields are
    dropped, not guessed."""
    errors, item = [], {}
    name = raw.get('name') if isinstance(raw, dict) else None
    if name not in names:
        return None, [f'unknown achievement name {name!r}; use the names exactly as listed']
    item['name'] = name
    phase = raw.get('phase')
    if phase in guides.PHASES:
        item['phase'] = phase
    else:
        errors.append(f'{name}: phase must be one of {", ".join(guides.PHASES)}')
    diff = raw.get('difficulty')
    if isinstance(diff, (int, float)) and not isinstance(diff, bool) and 1 <= diff <= 5:
        item['difficulty'] = int(round(diff))
    elif diff is not None:
        errors.append(f'{name}: difficulty must be 1-5')
    if isinstance(raw.get('time'), str) and raw['time'].strip():
        item['time'] = raw['time'].strip()
    mins = raw.get('minutes')
    if isinstance(mins, list) and len(mins) == 2 and all(isinstance(m, (int, float)) and not isinstance(m, bool) and m >= 0 for m in mins):
        item['minutes'] = sorted(int(m) for m in mins)
    elif mins is not None:
        errors.append(f'{name}: minutes must be [low, high]')
    item['missable'] = raw.get('missable') is True
    item['missable_note'] = raw.get('missable_note').strip() if isinstance(raw.get('missable_note'), str) else ''
    counter = raw.get('counter')
    if isinstance(counter, dict) and isinstance(counter.get('target'), (int, float)) and counter['target'] >= 2:
        item['counter'] = {'target': int(counter['target']), 'label': str(counter.get('label') or '')}
    else:
        item['counter'] = None
    combos = raw.get('combine_with')
    item['combine_with'] = [c for c in combos if c in names and c != name] if isinstance(combos, list) else []
    item['tips'] = raw.get('tips').strip() if isinstance(raw.get('tips'), str) else ''
    item['dlc'] = raw.get('dlc').strip() if isinstance(raw.get('dlc'), str) else ''
    item['cites'] = check_cites(raw.get('cites'))
    unver = raw.get('unverified')
    item['unverified'] = [f for f in unver if isinstance(f, str)] if isinstance(unver, list) else []
    return item, errors


def check_items(text, batch, every):
    """(items by name, errors) from a classify answer for `batch` (names)."""
    try:
        raw = tagged(text, 'items')
    except ValueError as e:
        return {}, [str(e)]
    if not isinstance(raw, list):
        return {}, ['the <items> block must be a JSON list']
    items, errors = {}, []
    for entry in raw:
        item, errs = check_item(entry, set(every))
        errors += errs
        if item and item['name'] in batch:
            items[item['name']] = item
    missing = [n for n in batch if n not in items]
    if missing:
        errors.append('no entry for: ' + ', '.join(missing))
    return items, errors


def check_route(text, names):
    try:
        raw = tagged(text, 'route')
    except ValueError as e:
        return {}, [str(e)]
    if not isinstance(raw, dict):
        return {}, ['the <route> block must be a JSON object']
    errors = []
    order = []
    for n in raw.get('order') if isinstance(raw.get('order'), list) else []:
        if n in names and n not in order:
            order.append(n)
        elif n not in names:
            errors.append(f'order names {n!r}, which is not an achievement here')
    sections = {}
    found = raw.get('sections') if isinstance(raw.get('sections'), dict) else {}
    for key in ('overview', 'route', 'missables', 'combos'):
        if isinstance(found.get(key), str):
            sections[key] = found[key].strip()
    if not order:
        errors.append('order is empty')
    if not sections.get('overview'):
        errors.append('sections.overview is missing')
    return {'order': order, 'sections': sections}, errors


def check_research(text, names):
    try:
        raw = tagged(text, 'research')
    except ValueError as e:
        return {'pages': [], 'notes': []}, [str(e)]
    raw = raw if isinstance(raw, dict) else {}
    pages = [u for u in raw.get('pages', []) if isinstance(u, str) and u.startswith('https://')]
    notes = [n for n in raw.get('notes', []) if isinstance(n, dict) and n.get('name') in names
             and isinstance(n.get('quote'), str) and isinstance(n.get('url'), str)]
    return {'pages': pages, 'notes': notes}, []


# ------------------------------------------------------------ verify

def verify_cites(item, sources, pieces):
    """Mark each cite verified when its quote is in the source it names (a
    URL or a chunk id), or else in any source we hold; then list the
    item's claims as unverified when none verified."""
    by_chunk = {p['id']: p['url'] for p in pieces}
    folded = {url: fold(s.get('text', '')) for url, s in sources.items()}
    cites = []
    for c in item.get('cites', []):
        quote = fold(c['quote'])
        url = by_chunk.get(c['source'], c['source'])
        # The prompt asks for 12-200 characters; a little over still checks.
        ok = False
        if QUOTE_MIN <= len(quote) <= QUOTE_MAX * 2:
            ok = quote in folded.get(url, '')
            if not ok:
                hit = next((u for u, t in folded.items() if quote in t), None)
                url, ok = (hit, True) if hit else (url, False)
        cites.append({'source': url, 'quote': c['quote'][:QUOTE_MAX * 2], 'verified': bool(ok)})
    item = dict(item, cites=cites)
    if not any(c['verified'] for c in cites):
        claimed = [f for f in CLAIMS if item.get(f) not in (None, '', [], False)]
        item['unverified'] = sorted(set(item.get('unverified', [])) | set(claimed))
    return item


# ------------------------------------------------------------ prompts

def prompt(stage, **values):
    with open(os.path.join(PROMPTS, f'{stage}.md'), encoding='utf-8') as f:
        text = f.read()
    with open(os.path.join(PROMPTS, 'rules.md'), encoding='utf-8') as f:
        values.setdefault('rules', f.read().strip())
    return re.sub(r'\{\{(\w+)\}\}', lambda m: str(values.get(m.group(1), m.group(0))), text)


def ach_line(a):
    desc = '(hidden)' if a.get('hidden') and not a.get('unlocked') and not a.get('desc') else a.get('desc', '')
    flags = ' [hidden]' if a.get('hidden') else ''
    flags += ' [unlocked]' if a.get('unlocked') else ''
    pct = f' ({a["percent"]:.1f}% of players)' if isinstance(a.get('percent'), (int, float)) else ''
    return f'- {a["name"]}{flags}: {desc}{pct}'


def table_line(name, item, unlocked):
    parts = [item.get('phase', '?'), f'difficulty {item.get("difficulty", "?")}', item.get('time') or 'time ?']
    if item.get('missable'):
        parts.append('MISSABLE' + (f' ({item["missable_note"]})' if item.get('missable_note') else ''))
    if item.get('counter'):
        parts.append(f'counter {item["counter"]["target"]} {item["counter"].get("label", "")}'.strip())
    if item.get('combine_with'):
        parts.append('combines with ' + ', '.join(item['combine_with']))
    if item.get('dlc'):
        parts.append(f'DLC {item["dlc"]}')
    return f'- {name}{" [unlocked]" if unlocked else ""}: ' + '; '.join(parts)


def excerpt_block(pieces):
    return '\n\n'.join(f'[{p["id"]}] {p["url"]}\n{p["text"]}' for p in pieces) or '(no excerpts: write "(unverified)")'


# ------------------------------------------------------------ files

def guide_name(store, app, game, folder):
    """The file stem: the existing guide's when there is one (a rename
    keeps it), else <slug>-<app> (Steam) or <slug>-<store>-<app>."""
    path = guides.find_guide(store, app, folder)
    if path:
        return os.path.basename(path)[:-3]
    return f'{slug(game)}-{app}' if store == 'steam' else f'{slug(game)}-{store}-{app}'


def markdown(store, app, game, achievements, sections, hand_ticks):
    done = sum(1 for a in achievements if a.get('unlocked'))
    total = len(achievements)
    lines = [f'# {game}', '',
             f'- Steam AppID: {app}' if store == 'steam' else f'- {store.upper()} ID: {app}',
             f'- Progress: {done}/{total} ({int(100 * done / total) if total else 0}%)', '',
             '## Guide notes', '']
    titles = (('overview', 'Overview'), ('route', 'Recommended route'), ('missables', 'Missable warning'),
              ('combos', 'Efficiency combos'))
    for key, title in titles:
        if sections.get(key):
            lines += [f'## {title}', '', sections[key].strip(), '']
    lines += ['## Achievements', '']
    hand = list(hand_ticks)
    for a in achievements:
        name = a['name'].replace('**', '')
        desc = '(hidden)' if a.get('hidden') and not a.get('desc') else a.get('desc', '')
        hidden = ' 🔒hidden' if a.get('hidden') else ''
        if a.get('unlocked'):
            when = time.strftime('%Y-%m-%d', time.localtime(a['time'])) if a.get('time') else ''
            note = f'_(unlocked {when})_' if when else '_(unlocked, date unknown)_'
            lines.append(f'- [x] **{name}**{hidden} — {desc} {note}')
        elif a['name'] in hand:
            hand.remove(a['name'])
            lines.append(f'- [x] **{name}**{hidden} — {desc}')
        else:
            lines.append(f'- [ ] **{name}**{hidden} — {desc}')
    return '\n'.join(lines) + '\n'


def write_text(path, text):
    folder = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.' + os.path.basename(path), suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def keep_previous(path):
    """One earlier copy, `<file>.prev`, so a worse new guide never costs
    the owner the old one (each cost time or money)."""
    if os.path.isfile(path):
        with open(path, 'rb') as f:
            body = f.read()
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
        with os.fdopen(fd, 'wb') as f:
            f.write(body)
        os.replace(tmp, path + '.prev')


def item_key(name, api, taken):
    """Items are keyed by display name (the games app's key); a second
    achievement with the same name gets its api added."""
    return name if name not in taken else f'{name} ({api})'


# ------------------------------------------------------------ the job

class Stopped(Exception):
    pass


class Job:
    """One make: holds the status, the usage and the sources as it goes."""

    def __init__(self, store, app, game, achievements, adapter, model='', effort='', web=True, folder=None,
                 fetch=None, list_guides=None, say=None, clock=time.time, minutes=0):
        self.store, self.app, self.game, self.achs = store, str(app), game, achievements
        self.adapter, self.model, self.effort = adapter, model, effort
        self.web = web and adapter.web
        self.folder = folder or guides.guides_dir()
        self.fetch = fetch or fetch_page
        self.list_guides = list_guides or steam_guide_urls
        self.say = say or (lambda line: None)
        self.clock = clock
        self.minutes = minutes
        self.usage, self.sources, self.fetched, self.links = [], {}, 0, []
        self.done, self.total, self.stage = 0, 0, ''
        self.started = int(clock())

    # status
    def report(self, line, state='running'):
        write_json(status_path(self.folder), {
            'state': state, 'store': self.store, 'app': self.app, 'game': self.game, 'stage': self.stage,
            'done': self.done, 'total': self.total, 'line': line, 'started': self.started,
            'time': int(self.clock()), 'agent': self.adapter.id, 'model': self.model, 'pid': os.getpid()})
        if line:
            self.say(line)

    def step(self, stage, line=''):
        if stop_requested(self.folder):
            raise Stopped()
        self.stage = stage
        self.report(line or stage)

    # stages
    def ask(self, stage, text, check, merge):
        """Run one model stage, check its answer, and ask once more with the
        errors listed; returns (value, errors), `merge` keeping the valid
        part of both tries."""
        best, errors = None, []
        for attempt in (1, 2):
            if attempt == 2:
                text = (text + '\n\nYour last answer had these problems:\n' + '\n'.join(f'- {e}' for e in errors[:20])
                        + '\nAnswer again in full, inside the tags.')
            found = guide_agents.run(self.adapter, text, web=self.web and stage == 'research', model=self.model,
                                     effort=self.effort, stopped=lambda: stop_requested(self.folder))
            self.usage.append({'engine': self.adapter.id, 'model': self.model, 'stage': stage,
                               'input': found['usage'].get('input', 0), 'output': found['usage'].get('output', 0),
                               'cost_usd': found['usage'].get('cost_usd'), 'seconds': found['seconds'],
                               'ok': found['ok'], 'ts': int(self.clock())})
            if found['stopped']:
                raise Stopped()
            for page in found['pages']:
                self.add_source(page['url'], page['text'], 'agent')
            self.links += [u for u in found['links'] if u not in self.links]
            if not found['ok']:
                raise RuntimeError(f"{stage}: {found['error']}; the old guide is unchanged")
            value, errors = check(found['text'])
            best = value if best is None else merge(best, value)
            if not errors:
                break
        return best, errors

    def add_source(self, url, text, kind):
        if text and text.strip():
            self.sources[url] = {'kind': kind, 'fetched': int(self.clock()), 'text': text}

    def fetch_into(self, url, kind):
        if url in self.sources or self.fetched >= FETCH_PAGES:
            return
        self.fetched += 1
        text = self.fetch(url)
        if text:
            self.add_source(url, text, kind)

    def gather(self, name):
        self.sources.update(kept_sources(os.path.join(self.folder, name + '.sources.json'), self.clock()))
        self.sources.update(saved_sources(os.path.join(self.folder, 'sources', name)))
        if self.store == 'steam':
            for url in self.list_guides(self.app):
                self.fetch_into(url, 'steam-guide')

    def research(self, open_achs):
        names = [a['name'] for a in self.achs]
        text = prompt('research', game=self.game, store=self.store, app=self.app,
                      sites='\n'.join(f'{i}. {s}' for i, s in enumerate(SITES, 1)),
                      achievements='\n'.join(ach_line(a) for a in open_achs))
        found, _ = self.ask('research', text, lambda t: check_research(t, set(names)),
                            lambda a, b: b if b['notes'] or b['pages'] else a)
        found = found or {'pages': [], 'notes': []}
        # Pages the agent cites first, then trusted sites its searches named.
        trusted = [u for u in self.links if site_rank(u) < len(SITE_HOSTS)]
        for url in found['pages'] + [n['url'] for n in found['notes']] + trusted:
            self.fetch_into(url, 'research')
        hints = {}
        for n in found['notes']:
            hints.setdefault(n['name'], []).append(n['quote'])
        return hints

    def classify(self, open_achs, pieces, hints):
        every = [a['name'] for a in self.achs]
        items, problems = {}, []
        for i in range(0, len(open_achs), BATCH_SIZE):
            batch = open_achs[i:i + BATCH_SIZE]
            self.step('classify', f'classify: {i + len(batch)}/{len(open_achs)} achievements')
            picked, size = [], 0
            for a in batch:
                for p in excerpts_for(a, pieces, hints.get(a['name'], ())):
                    if p not in picked and size + len(p['text']) <= BATCH_CHARS:
                        picked.append(p)
                        size += len(p['text'])
            text = prompt('classify', game=self.game, excerpts=excerpt_block(picked),
                          achievements='\n'.join(ach_line(a) for a in batch),
                          all_names='\n'.join(f'- {n}' for n in every), phases=', '.join(guides.PHASES))
            found, errors = self.ask('classify', text, lambda t, b=[a['name'] for a in batch]: check_items(t, b, every),
                                     lambda a, b: dict(a, **b))
            items.update(found or {})
            problems += errors
            self.done += 1
        return items, problems

    def route(self, items):
        done = sum(1 for a in self.achs if a.get('unlocked'))
        rows = []
        for a in self.achs:
            if a['name'] in items:
                rows.append(table_line(a['name'], items[a['name']], a.get('unlocked')))
        played = f', {self.minutes // 60} h played' if self.minutes else ''
        text = prompt('route', game=self.game, progress=f'{done} of {len(self.achs)} unlocked{played}',
                      table='\n'.join(rows))
        found, errors = self.ask('route', text, lambda t: check_route(t, set(items)),
                                 lambda a, b: b if b.get('order') else a)
        return found or {'order': [], 'sections': {}}, errors

    def run(self):
        os.makedirs(self.folder, exist_ok=True)
        clear_stop(self.folder)
        name = guide_name(self.store, self.app, self.game, self.folder)
        open_achs = [a for a in self.achs if not a.get('unlocked')]
        batches = (len(open_achs) + BATCH_SIZE - 1) // BATCH_SIZE
        self.total = 1 + int(self.web) + batches + 2
        self.step('gather', f'gather: sources for {self.game}')
        self.gather(name)
        self.done += 1
        hints = {}
        if self.web and open_achs:
            self.step('research', 'research: the agent searches the web')
            hints = self.research(open_achs)
            self.done += 1
        pieces = chunks(self.sources)
        self.say(f'sources: {len(self.sources)} ({len(pieces)} excerpts)')
        items, problems = self.classify(open_achs, pieces, hints)
        if open_achs and not items:
            raise RuntimeError("the agent's answers didn't parse (" + '; '.join(problems[:3]) +
                               '); make it again, or pick another model')
        self.step('route', 'route: order and notes')
        old = read_json(guides.plan_path(os.path.join(self.folder, name + '.md')), {})
        old = old if isinstance(old, dict) else {}
        old_items = old.get('items') if isinstance(old.get('items'), dict) else {}
        # Unlocked achievements were not classified; their old entries
        # stay, so the route still knows them as combo partners.
        table = {n: i for n, i in old_items.items() if isinstance(i, dict)}
        table.update(items)
        route, route_errors = self.route(table)
        self.done += 1
        self.step('verify', 'verify: checking every quote')
        self.write(name, old, items, route, pieces)
        self.done += 1
        return name, problems + route_errors

    def write(self, name, old, items, route, pieces):
        md = os.path.join(self.folder, name + '.md')
        hand = []
        try:
            with open(md, encoding='utf-8') as f:
                hand = [r['name'] for r in guides.parse_markdown(f.read())[1] if r['hand']]
        except OSError:
            pass
        old_items = old.get('items') if isinstance(old.get('items'), dict) else {}
        by_name = {}
        for k, i in old_items.items():
            if isinstance(i, dict):
                by_name.setdefault(i.get('name') or k, []).append(k)
        plan_items, taken = {}, set()
        for a in self.achs:
            prev_keys = [k for k in by_name.get(a['name'], []) if k not in taken]
            prev_key = next((k for k in prev_keys if old_items[k].get('api') in (None, a['api'])), None)
            prev = old_items.get(prev_key, {}) if prev_key else {}
            new = items.get(a['name'])
            if not new and not prev:
                continue
            key = prev_key or item_key(a['name'], a['api'], plan_items)
            taken.add(key)
            entry = dict(prev)
            if new:
                entry.update(verify_cites(new, self.sources, pieces))
            entry.update(name=a['name'], api=a['api'])
            plan_items[key] = entry
        plan = dict(old)
        plan.update({'format': 2, 'generated': int(self.clock()),
                     'agent': {'name': self.adapter.id, 'model': self.model, 'effort': self.effort,
                               'stages': stage_counts(self.usage)},
                     'order': route['order'] or list(items), 'items': plan_items,
                     'sections': route['sections'] or old.get('sections') or {},
                     'usage': (old.get('usage') if isinstance(old.get('usage'), list) else []) + self.usage})
        keep_previous(md)
        keep_previous(guides.plan_path(md))
        write_text(md, markdown(self.store, self.app, self.game, self.achs, plan['sections'], hand))
        write_json(guides.plan_path(md), plan, indent=1, ensure_ascii=False)
        write_json(md[:-3] + '.sources.json', self.sources, ensure_ascii=False)
        self.plan = plan


def stage_counts(usage):
    out = {}
    for u in usage:
        out[u['stage']] = out.get(u['stage'], 0) + 1
    return out


def make(job):
    """Run a Job to its end and report how it ended: {state, line}."""
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: sys.exit(1))
    try:
        name, problems = job.run()
    except Stopped:
        clear_stop(job.folder)
        job.report('stopped: the old guide is unchanged', 'stopped')
        return {'state': 'stopped'}
    except (RuntimeError, OSError) as e:
        job.report(f'failed: {e}', 'failed')
        return {'state': 'failed', 'error': str(e)}
    except BaseException:
        job.report('failed: the job was interrupted; the old guide is unchanged', 'failed')
        raise
    items = job.plan['items']
    verified = sum(1 for i in items.values() if any(c.get('verified') for c in i.get('cites', [])))
    cost = sum(u['cost_usd'] or 0 for u in job.usage if isinstance(u.get('cost_usd'), (int, float)))
    tail = f' (${cost:.2f})' if cost else ''
    job.report(f'done: {len(items)} items, {verified} verified{tail}', 'done')
    for p in problems[:5]:
        job.say(f'note: {p}')
    return {'state': 'done', 'name': name}
