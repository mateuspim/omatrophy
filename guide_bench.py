"""Compare agents and models at making one game's guide (`guide bench`).

Each entry makes the guide on its own, into its own folder under
guides/bench/<time>/, so the owner's guide stays as it is. The score uses
only what OmaTrophy can check, never a model's opinion of another: quotes
verified against their source, open achievements covered, fields filled,
the route's reach, the notes written, and the walkthrough's actions,
prerequisites and markers. Time and cost are reported and
break ties. `--pick` makes the winner the default agent and model, and
`--keep` adopts its guide for the game. Format: docs/specs/guides.md.
"""
import json, os, re, time

import guide_agents, guide_maker, guides
from stores.base import write_json

# Weights of the score, out of 100: grounded claims count most, then
# covering every open achievement. The walkthrough (ADR 17) took its 10
# from fields and sections, the cheapest parts to fill; benches before
# 0.6.4 scored without it. Actions, prerequisites and markers (maker 4-5)
# were only counted until the owner asked for them scored (2026-11-11);
# their 15 came from verified, coverage and fields, which every good
# entry fills alike, so the parts that tell entries apart weigh more.
WEIGHTS = {'verified': 30, 'coverage': 20, 'complete': 10, 'route': 10, 'sections': 5, 'walkthrough': 10,
           'useful_actions': 5, 'prerequisites': 5, 'story_markers': 5}
FIELDS = ('phase', 'difficulty', 'time', 'tips')
SECTIONS = ('overview', 'route', 'missables', 'combos')
# agent:model[:effort][@endpoint]; a model may hold '/' (provider/model) and
# ':' only before the effort, so the effort is the last part when it names one.
ENTRY = re.compile(r'^(?P<agent>[a-z][a-z0-9-]*)(?::(?P<model>[^@]*?))?(?::(?P<effort>low|medium|high|xhigh|max|minimal))?'
                   r'(?:@(?P<endpoint>https?://\S+))?$')


def parse_entry(text):
    """{agent, model, effort, endpoint} from `agent:model[:effort][@url]`;
    raises SystemExit saying the shape when it isn't one."""
    m = ENTRY.match(text.strip())
    if not m:
        raise SystemExit(f'omatrophy: guide bench: {text!r} is not agent:model[:effort][@http://endpoint]')
    return {k: m[k] or '' for k in ('agent', 'model', 'effort', 'endpoint')}


def label(entry):
    return (entry['agent'] + (':' + entry['model'] if entry['model'] else '')
            + (':' + entry['effort'] if entry['effort'] else '') + ('@' + entry['endpoint'] if entry['endpoint'] else ''))


def walkthrough_measure(plan, open_apis):
    """0..1: half for the open achievements placed in a step, half for the
    steps holding a verified quote. Both are checked the way items are; the
    play order of a game's chapters isn't, so it isn't scored."""
    steps = [s for s in plan.get('walkthrough') or [] if isinstance(s, dict)]
    if not steps or not open_apis:
        return 0.0
    api_of = {i.get('name'): i.get('api') for i in (plan.get('items') or {}).values() if isinstance(i, dict)}
    placed = {api_of.get(n) for s in steps for n in s.get('achievements') or []} & set(open_apis)
    grounded = sum(1 for s in steps if any(c.get('verified') for c in s.get('cites') or []))
    return round(0.5 * len(placed) / len(open_apis) + 0.5 * grounded / len(steps), 3)


def plan_measure(plan, open_apis):
    """Counts beside the scored measures: `needs` the covered items that
    require another, `needs_cited` those whose requires a verified quote
    backs, `actions` the steps' actions, `where` the share naming a place
    and `markers` the share of steps with a marker. Raw counts aren't
    scored: more `requires` or markers isn't better (a game may have
    none), and a place is easy to fill with words no check reads; the
    scored `prerequisites` and `story_markers` judge them instead."""
    items = [i for i in (plan.get('items') or {}).values() if isinstance(i, dict) and i.get('api') in open_apis]
    needs = [i for i in items if i.get('requires')]
    cited = [i for i in needs if 'requires' not in (i.get('unverified') or [])]
    actions = [a for s in plan.get('walkthrough') or [] if isinstance(s, dict)
               for a in s.get('actions') or [] if isinstance(a, dict)]
    placed = [a for a in actions if isinstance(a.get('where'), str) and a['where'].strip()]
    steps = [s for s in plan.get('walkthrough') or [] if isinstance(s, dict)]
    marked = [s for s in steps if isinstance(s.get('marker'), str) and s['marker']]
    return {'needs': len(needs), 'needs_cited': len(cited), 'actions': len(actions),
            'where': round(len(placed) / len(actions), 3) if actions else 0.0,
            'markers': round(len(marked) / len(steps), 3) if steps else 0.0}


# An action that only says to play on ("Play through to the end of the
# chapter", "Finish the mission", "Continue the story to unlock X"): the
# step already lists its story trophy (8888c7c), so it tells the player
# nothing.
FILLER = re.compile(r"(?:simply\s+|just\s+)?(?:play(?:\s+on)?|continue|progress|proceed|keep\s+playing|finish|complete"
                    r"|beat|clear|reach\s+the\s+end\s+of)(?:\s+through)?(?:\s+(?:to\s+)?the\s+end\s+of)?"
                    r"(?:\s+(?:the|this))?\s+(?:story|game|chapter|mission|level|episode|act|stage|campaign)"
                    r"(?:\s+[\w-]+)?", re.I)
TRAILING_GOAL = re.compile(r"[\s,]+(?:(?:to|and)\s+(?:get|earn|unlock)\b|for\s+(?:the\s+)?[\w' -]*(?:trophy|achievement)).*$"
                           r"|[.!]+$", re.I)


def filler(what):
    """True when an action's `what` only says to play on."""
    return bool(FILLER.fullmatch(TRAILING_GOAL.sub('', (what or '').strip())))


def useful_measure(plan):
    """0..1: the share of the steps' actions that say more than "play on";
    0 when there are none, as every step has somewhere to go."""
    actions = [a for s in plan.get('walkthrough') or [] if isinstance(s, dict)
               for a in s.get('actions') or [] if isinstance(a, dict)]
    if not actions:
        return 0.0
    return round(sum(1 for a in actions if not filler(a.get('what'))) / len(actions), 3)


def share(part, whole):
    """part/whole, or 1.0 when there is nothing to get wrong."""
    return part / whole if whole else 1.0


def prerequisite_measure(items, achievements):
    """0..1, half each: the items whose verified quotes state a
    prerequisite (guide_maker.prerequisite_said) that have `requires`, and
    the items with `requires` that a verified quote backs. A game with no
    prerequisites scores 1: more `requires` isn't better."""
    words = guide_maker.prerequisite_words(list(achievements) or
                                           [{'name': i.get('name') or ''} for i in items.values()])
    stated = [i for i in items.values() if i.get('name') in words and guide_maker.prerequisite_said(
        [c.get('quote') or '' for c in i.get('cites') or [] if c.get('verified')], *words[i['name']])[0]]
    needs = [i for i in items.values() if i.get('requires')]
    cited = [i for i in needs if 'requires' not in (i.get('unverified') or [])]
    return round(0.5 * share(sum(1 for i in stated if i.get('requires')), len(stated))
                 + 0.5 * share(len(cited), len(needs)), 3)


def marker_measure(plan):
    """0..1, half each: the markers that are story items (a chapter clear,
    not a side trophy), and the steps holding a story item that name a
    marker. A game with no story items and no markers scores 1."""
    phase = {i.get('name'): i.get('phase') for i in (plan.get('items') or {}).values() if isinstance(i, dict)}
    steps = [s for s in plan.get('walkthrough') or [] if isinstance(s, dict)]
    # A marker that is no item (an unlocked one, not classified) says nothing.
    marks = [s['marker'] for s in steps if isinstance(s.get('marker'), str) and s['marker'] in phase]
    story = [s for s in steps if any(phase.get(n) == 'story' for n in s.get('achievements') or [])]
    return round(0.5 * share(sum(1 for m in marks if phase[m] == 'story'), len(marks))
                 + 0.5 * share(sum(1 for s in story if s.get('marker')), len(story)), 3)


def metrics(plan, open_apis, achievements=()):
    """The checkable measures of one made plan, each 0..1. `achievements`
    (the store's, with descriptions) name the difficulty settings a
    prerequisite may be quoted by; without them, item names only."""
    items = {i['api']: i for i in (plan.get('items') or {}).values() if isinstance(i, dict) and i.get('api') in open_apis}
    n = len(open_apis) or 1
    with_cite = sum(1 for i in items.values() if any(c.get('verified') for c in i.get('cites', [])))
    filled = [sum(1 for f in FIELDS if i.get(f) not in (None, '', [])) / len(FIELDS) for i in items.values()]
    names = {i.get('name') for i in items.values()}
    routed = len([o for o in plan.get('order') or [] if o in names])
    sections = plan.get('sections') or {}
    return {'coverage': round(len(items) / n, 3),
            'verified': round(with_cite / len(items), 3) if items else 0.0,
            'complete': round(sum(filled) / len(filled), 3) if filled else 0.0,
            'route': round(min(1.0, routed / n), 3),
            'sections': round(sum(1 for k in SECTIONS if sections.get(k)) / len(SECTIONS), 3),
            'walkthrough': walkthrough_measure(plan, open_apis),
            'useful_actions': useful_measure(plan),
            'prerequisites': prerequisite_measure(items, achievements),
            'story_markers': marker_measure(plan),
            'steps': len(plan.get('walkthrough') or []),
            'items': len(items), 'cited': with_cite,
            'unverified': sum(len(i.get('unverified') or []) for i in items.values()),
            **plan_measure(plan, open_apis)}


def score(m):
    return round(sum(WEIGHTS[k] * m[k] for k in WEIGHTS), 1)


def usage_totals(plan):
    usage = [u for u in plan.get('usage') or [] if isinstance(u, dict)]
    costs = [u['cost_usd'] for u in usage if isinstance(u.get('cost_usd'), (int, float))]
    return {'cost_usd': round(sum(costs), 4) if costs else None,
            'tokens': sum(int(u.get('input') or 0) + int(u.get('output') or 0) for u in usage),
            'calls': len(usage)}


def ranked(results):
    """Best first: score, then cheaper (unknown cost last), then faster."""
    def key(r):
        cost = r.get('cost_usd')
        return (-r['score'], cost if isinstance(cost, (int, float)) else float('inf'), r.get('seconds', 0))
    return sorted(results, key=key)


def table(results):
    rows = [('', 'entry', 'score', 'verified', 'covered', 'fields', 'walk', 'acts', 'needs', 'marker', 'where', 'time',
             'cost', 'state')]
    for n, r in enumerate(ranked(results), 1):
        m = r.get('metrics') or {}
        cost = r.get('cost_usd')
        rows.append((str(n), r['entry'], f"{r['score']:.1f}", f"{m.get('cited', 0)}/{m.get('items', 0)}",
                     f"{int(100 * m.get('coverage', 0))}%", f"{int(100 * m.get('complete', 0))}%",
                     f"{int(100 * m.get('walkthrough', 0))}%",
                     f"{int(100 * m.get('useful_actions', 0))}%" if m.get('actions') else '-',
                     f"{int(100 * m.get('prerequisites', 0))}% {m.get('needs_cited', 0)}/{m.get('needs', 0)}",
                     f"{int(100 * m.get('story_markers', 0))}%" if m.get('steps') else '-',
                     f"{int(100 * m.get('where', 0))}%" if m.get('actions') else '-',
                     f"{r.get('seconds', 0) // 60}m{r.get('seconds', 0) % 60:02d}s",
                     f'${cost:.2f}' if isinstance(cost, (int, float)) else '-', r['state']))
    widths = [max(len(row[i]) for row in rows) for i in range(len(rows[0]))]
    return '\n'.join('  '.join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in rows)


def bench(store, app, game, achievements, entries, web=True, jail=False, folder=None, say=print,
          clock=time.time, adapters=None, minutes=0, **job_kw):
    """Make the guide once per entry, each in its own folder; returns the
    results ranked, and writes them to results.json beside the runs."""
    folder = folder or guides.guides_dir()
    run_dir = os.path.join(folder, 'bench', time.strftime('%Y%m%d-%H%M%S', time.localtime(clock())))
    os.makedirs(run_dir, exist_ok=True)
    open_apis = {a['api'] for a in achievements if not a.get('unlocked')}
    lookup = adapters or {}
    results = []
    for n, entry in enumerate(entries, 1):
        name = label(entry)
        here = os.path.join(run_dir, f'{n:02d}-' + re.sub(r'[^A-Za-z0-9._-]+', '_', name)[:60])
        say(f'--- {n}/{len(entries)} {name}')
        adapter = lookup.get(entry['agent']) or guide_agents.resolve(entry['agent'])
        env = guide_agents.endpoint_env(adapter, entry['endpoint'])
        started = clock()
        job = guide_maker.Job(store, app, game, [dict(a) for a in achievements], adapter, model=entry['model'],
                              effort=entry['effort'], web=web, folder=here, say=lambda line: say('    ' + line),
                              clock=clock, minutes=minutes, jail=jail, env=env,
                              source_root=folder, **job_kw)
        try:
            end = guide_maker.make(job)
        except KeyboardInterrupt:
            say('    skipped (interrupted); Ctrl-C again to end the bench')
            end = {'state': 'stopped'}
        plan = getattr(job, 'plan', None) or {}
        m = metrics(plan, open_apis, achievements) if end['state'] == 'done' else {}
        totals = usage_totals(dict(plan, usage=job.usage))
        results.append({'entry': name, **entry, 'state': end['state'], 'error': end.get('error', ''),
                        'score': score(m) if m else 0.0, 'metrics': m, 'seconds': int(clock() - started),
                        'cost_usd': totals['cost_usd'], 'tokens': totals['tokens'], 'calls': totals['calls'],
                        'folder': here, 'name': end.get('name', '')})
        write_json(os.path.join(run_dir, 'results.json'),
                   {'store': store, 'app': str(app), 'game': game, 'web': web, 'jail': jail,
                    'weights': WEIGHTS, 'results': ranked(results)}, indent=1)
    return run_dir, ranked(results)


def keep(winner, folder=None):
    """Adopt the winner's guide for the game: its files replace the owner's
    (the old ones kept as .prev)."""
    folder = folder or guides.guides_dir()
    src = winner['folder']
    for ext in ('.md', '.plan.json', '.sources.json'):
        path = os.path.join(src, winner['name'] + ext)
        if not os.path.isfile(path):
            continue
        target = os.path.join(folder, winner['name'] + ext)
        if os.path.isfile(target) and ext != '.sources.json':
            guide_maker.keep_previous(target)
        guides.copy_in(path, target)  # a link at target is replaced, not written through
