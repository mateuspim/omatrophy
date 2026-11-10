"""Reader for 100% guides: finds a game's guide file, parses it and matches
its items to the store's achievements. Format: docs/specs/guides.md.

Guides are the owner's data in ~/.local/share/omatrophy/guides/. This module
reads them and copies them in from another folder (`guide import`); it never
writes into the source folder, and never changes a guide it already holds.
"""
import json, os, re, shutil

PHASES = ('missable', 'story', 'quick', 'challenge', 'grind', 'collect', 'online')
NEXT_COUNT = 3
# A hand tick is "[x]" with no "_(unlocked ...)_" note: OmaTrophy writes that
# note itself when the store says the achievement is unlocked.
# Store ids other than Steam, which a Steam lookup must skip (extend with new stores).
OTHER_STORE_TAIL = re.compile(r'-(gog)$')
TICK = re.compile(r'^- \[(?P<mark>[ xX])\] \*\*(?P<name>.+?)\*\*(?P<rest>.*)$')


# The guide maker's revision, written to each plan it makes. Bump it when
# making a guide again gives a clearly better one (prompts, sources), so
# the tracker can say so. 3: route prose without `table` citations, fuller
# tips, full pages instead of the agent's summaries (2026-11-06). 4:
# `requires` per item and `actions` per walkthrough step (ADR 20).
MAKER = 4


def outdated(plan):
    """True for a guide OmaTrophy made with an older maker; an imported
    guide (no `generated`) never is."""
    rev = plan.get('maker')
    return bool(plan.get('generated')) and not (isinstance(rev, int) and rev >= MAKER)


def guides_dir():
    # Resolved per call so tests can point the environment elsewhere.
    base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return os.path.join(base, 'omatrophy', 'guides')


def find_guide(store, app, folder=None):
    """Path of the .md for one game, found by its trailing id, never by slug
    (a renamed game keeps its file). Steam is `<slug>-<app>.md`, any other
    store `<slug>-<store>-<app>.md`. None when there is none."""
    folder = folder or guides_dir()
    try:
        names = sorted(os.listdir(folder))
    except OSError:
        return None
    suffix = f'-{app}.md' if store == 'steam' else f'-{store}-{app}.md'
    for name in names:
        slug = name[:-len(suffix)]
        if name.endswith(suffix) and slug:
            # '<slug>-gog-5.md' also ends in '-5.md' but is not Steam app 5.
            if store == 'steam' and OTHER_STORE_TAIL.search(slug):
                continue
            return os.path.join(folder, name)
    return None


def parse_markdown(text):
    """(notes, [{name, done, hand}]) from a guide .md. `done` is any [x];
    `hand` is a tick made by the owner (no unlock note)."""
    lines = text.splitlines()
    notes, items, part = [], [], ''
    for line in lines:
        head = line.strip().lower()
        # Only these two headings switch parts: the notes keep their own
        # "## Overview", "## Recommended route" ... subsections.
        if head in ('## guide notes', '## achievements'):
            part = 'notes' if head == '## guide notes' else 'achievements'
            continue
        if part == 'notes':
            notes.append(line)
        elif part == 'achievements':
            m = TICK.match(line)
            if not m:
                continue
            done = m['mark'] in 'xX'
            items.append({'name': m['name'], 'done': done,
                          'hand': done and '_(unlocked' not in m['rest']})
    return '\n'.join(notes).strip(), items


def plan_path(md_path):
    return md_path[:-3] + '.plan.json'


def load_plan(md_path):
    """The .plan.json beside a guide, or {} when missing or broken (the
    prose and checklist still show)."""
    try:
        with open(plan_path(md_path), encoding='utf-8') as f:
            plan = json.load(f)
    except (OSError, ValueError):
        return {}
    return plan if isinstance(plan, dict) and isinstance(plan.get('items'), dict) else {}


def match_items(plan_items, achievements):
    """{api: item} matching plan items to the store's achievements: by `api`
    first, then by name. Two achievements with one name take the plan's items
    of that name in store order."""
    by_api = {i['api']: key for key, i in plan_items.items() if isinstance(i, dict) and i.get('api')}
    by_name, taken, out = {}, set(), {}
    for key, item in plan_items.items():
        if isinstance(item, dict):
            by_name.setdefault(item.get('name') or key, []).append(key)
    for a in achievements:
        key = by_api.get(a['api'])
        if key is None:
            queue = [k for k in by_name.get(a['name'], []) if k not in taken and not plan_items[k].get('api')]
            key = queue[0] if queue else None
        if key is not None and key not in taken:
            taken.add(key)
            out[a['api']] = dict(plan_items[key], name=plan_items[key].get('name') or key)
    return out


def phase_rank(item):
    phase = item.get('phase')
    return PHASES.index(phase) if phase in PHASES else len(PHASES)


def open_order(order, items, done):
    """The first NEXT_COUNT open apis in `order`, missables first. An item
    whose `requires` (apis) aren't all done waits: the game won't give it."""
    open_ = [api for api in order if api in items and api not in done
             and all(r in done for r in items[api].get('requires') or [])]
    open_.sort(key=lambda api: (not items[api].get('missable'),))  # stable: keeps the plan's order
    return open_[:NEXT_COUNT]


def guide_answer(store, app, achievements, folder=None):
    """The guide for one game as the tracker reads it, or {} when none."""
    path = find_guide(store, app, folder)
    if not path:
        return {}
    try:
        with open(path, encoding='utf-8') as f:
            notes, checklist = parse_markdown(f.read())
    except OSError:
        return {}
    plan = load_plan(path)
    items = match_items(plan.get('items', {}), achievements)
    by_name = {}
    for a in achievements:
        by_name.setdefault(a['name'], []).append(a['api'])
    ticks = []
    for row in checklist:
        apis = by_name.get(row['name'], [])
        if row['hand'] and apis:
            ticks.append(apis.pop(0))
        elif apis:
            apis.pop(0)
    done = {a['api'] for a in achievements if a.get('unlocked')} | set(ticks)
    name_to_api = {i['name']: api for api, i in items.items()}
    order = [name_to_api[n] for n in plan.get('order', []) if n in name_to_api]
    order += [api for api in items if api not in order]
    # A step names unlocked trophies too, which were never classified, so
    # it maps through every achievement of the game.
    every_api = {a['name']: a['api'] for a in achievements}
    every_api.update(name_to_api)
    for api, item in items.items():
        needs = item.get('requires') if isinstance(item.get('requires'), list) else []
        items[api] = dict(item, requires=[every_api[n] for n in needs if n in every_api and every_api[n] != api])
    steps = walkthrough_steps(plan, every_api, done)
    return {'store': store, 'app': str(app), 'file': os.path.basename(path),
            'generated': plan.get('generated', 0), 'order': order, 'items': items,
            'sections': plan.get('sections') or {}, 'notes': notes, 'ticks': ticks,
            'next': open_order(order, items, done),
            'agent': plan.get('agent') if isinstance(plan.get('agent'), dict) else {},
            'cost_usd': plan_cost(plan), 'outdated': outdated(plan),
            'walkthrough': steps, 'step': current_step(steps), 'tree': tree(order, items, steps)}


def tree(order, items, steps=()):
    """The guide as an outline (ADR 20): `story` the story items in play
    order (the steps', then the route's); `chains` rows {api, depth}, each
    item that needs others first with its prerequisites indented under it;
    `alone` the rest. Apis throughout; done ones stay, the view dims them."""
    placed = [a for s in steps for a in s.get('achievements') or []]
    ranked = [a for a in placed if a in items] + [a for a in order if a not in placed]
    ranked = list(dict.fromkeys(ranked))
    story = [a for a in ranked if items[a].get('phase') == 'story']
    needs = {a: [r for r in items[a].get('requires') or [] if r in items] for a in ranked}
    plain = [a for a in ranked if a not in story]
    needed = {r for a in plain if needs[a] for r in needs[a]}
    chains = []

    def walk(api, depth, path):
        chains.append({'api': api, 'depth': depth})
        # A cycle in an imported or older guide stops at its closing edge.
        for r in needs[api]:
            if r not in path:
                walk(r, depth + 1, path | {r})

    for a in plain:
        if needs[a] and a not in needed:
            walk(a, 0, {a})
    shown = {row['api'] for row in chains}
    return {'story': story, 'chains': chains, 'alone': [a for a in plain if a not in shown]}


def walkthrough_steps(plan, name_to_api, done):
    """The plan's walkthrough for the tracker: each step's achievements
    and missables as `api`s (names the store doesn't know are dropped),
    and `done` when none of its achievements is left open."""
    steps = []
    for s in plan.get('walkthrough') if isinstance(plan.get('walkthrough'), list) else []:
        if not isinstance(s, dict) or not isinstance(s.get('title'), str):
            continue
        apis = [name_to_api[n] for n in s.get('achievements') or [] if n in name_to_api]
        steps.append({'title': s['title'], 'text': s.get('text') if isinstance(s.get('text'), str) else '',
                      'achievements': apis,
                      'missables': [name_to_api[n] for n in s.get('missables') or [] if n in name_to_api],
                      'unverified': s.get('unverified') is True,
                      'started': any(a in done for a in apis),
                      'done': bool(apis) and all(a in done for a in apis)})
    return steps


def current_step(steps):
    """Where the player is: the first step with an achievement open, at or
    after the last step where they unlocked one (a horse bond left open in
    an early step mustn't pull a player back there); -1 when none is open."""
    last = max((i for i, s in enumerate(steps) if s.get('started')), default=0)
    open_at = [i for i, s in enumerate(steps) if s['achievements'] and not s['done']]
    return next((i for i in open_at if i >= last), open_at[0] if open_at else -1)


def plan_cost(plan):
    """What the agent reported the guide cost in all (every make), in
    dollars; 0 when it didn't say."""
    usage = plan.get('usage') if isinstance(plan.get('usage'), list) else []
    return round(sum(u['cost_usd'] for u in usage
                     if isinstance(u, dict) and isinstance(u.get('cost_usd'), (int, float))), 4)


def import_guides(source, replace=False, folder=None):
    """Copy every guide .md with its .plan.json and .sources.json from
    `source`. Returns (imported, skipped); `source` is only read."""
    folder = folder or guides_dir()
    if not os.path.isdir(source):
        raise SystemExit(f'omatrophy: guide import: {source} is not a folder; give the folder that holds the guide files')
    os.makedirs(folder, exist_ok=True)
    imported = skipped = 0
    for name in sorted(os.listdir(source)):
        if not name.endswith('.md') or not os.path.isfile(os.path.join(source, name)):
            continue
        target = os.path.join(folder, name)
        if os.path.exists(target) and not replace:
            skipped += 1
            continue
        base = name[:-3]
        for extra in (name, base + '.plan.json', base + '.sources.json'):
            src = os.path.join(source, extra)
            if os.path.isfile(src):
                shutil.copyfile(src, os.path.join(folder, extra))
        imported += 1
    return imported, skipped
