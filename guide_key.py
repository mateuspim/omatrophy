"""The Guide key: a Hyprland bind that opens the running game's guide over
it (ADR 16, ADR 18). Nothing is bound until the owner installs a key in
Settings > Guides (`guide-key` in config.json); OmaTrophy then binds it at
runtime with `hyprctl eval` and never writes the owner's Hyprland config.
A key another bind already uses is refused, with the reason."""
import json, os, re, subprocess

DEFAULT = 'SUPER + CTRL + G'
DESCRIPTION = 'OmaTrophy: the guide over your game'
COMMAND = """omarchy-shell shell toggle pym.omatrophy '{"view":"guide"}'"""
# Hyprland's modifier names and mask bits.
MODIFIERS = {'SHIFT': 1, 'CAPS': 2, 'CTRL': 4, 'CONTROL': 4, 'ALT': 8, 'MOD2': 16, 'MOD3': 32,
             'SUPER': 64, 'WIN': 64, 'LOGO': 64, 'MOD4': 64, 'MOD5': 128}
# Key names Hyprland knows (xkb keysyms) that Settings > Guides can record,
# besides a letter, a digit, F1-F35 and code:N. Anything else is refused
# here: "dsadsadsa" once reached hl.bind and the owner saw its Lua error.
NAMED = {'SPACE', 'TAB', 'RETURN', 'BACKSPACE', 'DELETE', 'INSERT', 'HOME', 'END', 'PRIOR', 'NEXT',
         'LEFT', 'RIGHT', 'UP', 'DOWN', 'COMMA', 'PERIOD', 'SLASH', 'BACKSLASH', 'SEMICOLON', 'APOSTROPHE',
         'MINUS', 'EQUAL', 'GRAVE', 'BRACKETLEFT', 'BRACKETRIGHT', 'PRINT', 'PAUSE', 'SCROLL_LOCK'}
KEY = re.compile(r'^(code:\d{1,3}|[A-Za-z0-9]|F([1-9]|[12]\d|3[0-5]))$', re.I)
HYPRCTL_SECONDS = 4


def parse(text):
    """{spec, modmask, key} with the spec written as Hyprland's config
    writes it ("SUPER + CTRL + G"); spec "" for an empty setting (no key);
    None when it isn't a key. The spec goes into Lua, so only modifier
    names and a plain key name (or code:N) pass."""
    value = str(text or '').strip()
    if not value:
        return {'spec': '', 'modmask': 0, 'key': ''}
    parts = [p.strip() for p in value.split('+')]
    key = parts.pop()
    if not (KEY.match(key) or key.upper() in NAMED):
        return None
    # A bare key would take it from every app and game (an F-key alone is
    # allowed: few apps use F13-F35, and the owner chose it).
    if not parts and not re.match(r'^F\d+$', key, re.I):
        return None
    mask, names = 0, []
    for p in parts:
        name = p.upper()
        if name not in MODIFIERS:
            return None
        mask |= MODIFIERS[name]
        names.append(name)
    key = key.upper() if (len(key) == 1 or key.upper() in NAMED or re.match(r'^F\d+$', key, re.I)) else key
    return {'spec': ' + '.join(names + [key]), 'modmask': mask, 'key': key}


def same_key(bind, parsed):
    return (isinstance(bind, dict) and bind.get('submap', '') == '' and bind.get('modmask') == parsed['modmask']
            and str(bind.get('key', '')).lower() == parsed['key'].lower())


# One name per bit, for writing a bind Hyprland reports back as a spec.
MASK_NAMES = (('SUPER', 64), ('CTRL', 4), ('ALT', 8), ('SHIFT', 1), ('CAPS', 2), ('MOD2', 16), ('MOD3', 32), ('MOD5', 128))


def ours(binds):
    """Where our bind sits now (after a shell restart or an old setting),
    from `hyprctl -j binds` output: [{spec, modmask, key}]."""
    out = []
    for b in binds:
        if isinstance(b, dict) and b.get('description') == DESCRIPTION and b.get('submap', '') == '':
            mask, key = b.get('modmask', 0), str(b.get('key', ''))
            names = [n for n, bit in MASK_NAMES if mask & bit]
            out.append({'spec': ' + '.join(names + [key]), 'modmask': mask, 'key': key})
    return out


def conflict(binds, parsed):
    """What else is bound on the key, or "" when it is free (or ours)."""
    for b in binds:
        if same_key(b, parsed) and b.get('description') != DESCRIPTION:
            return str(b.get('description') or b.get('dispatcher') or 'another binding')
    return ''


def bind_lua(spec):
    # Both are constants or a spec parse() made; json.dumps quotes for Lua.
    return f'hl.bind({json.dumps(spec)}, hl.dsp.exec_cmd({json.dumps(COMMAND)}), {{ description = {json.dumps(DESCRIPTION)} }})'


def unbind_lua(spec):
    return f'hl.unbind({json.dumps(spec)})'


def plan(text, binds):
    """(steps, result) to make the bound key match the setting `text`:
    steps are Lua for `hyprctl eval`, in order; result is {key, bound,
    error} as it will be once they ran."""
    parsed = parse(text)
    if parsed is None:
        return [], {'key': str(text), 'bound': '',
                    'error': f'"{text}" is not a key: a modifier (SUPER, CTRL, ALT, SHIFT) and a key, like {DEFAULT}.'}
    held = ours(binds)
    here = [h for h in held if same_key({'modmask': h['modmask'], 'key': h['key']}, parsed)]
    steps = [unbind_lua(h['spec']) for h in held if h not in here]
    if not parsed['spec']:
        return steps, {'key': '', 'bound': '', 'error': ''}
    taken = conflict(binds, parsed)
    if taken:
        return steps, {'key': parsed['spec'], 'bound': '',
                       'error': f'{parsed["spec"]} is already bound to {taken}. Pick another Guide key in '
                                f'Omarchy\'s plugin settings for OmaTrophy, or leave it empty and bind {COMMAND} yourself.'}
    if not here:
        steps.append(bind_lua(parsed['spec']))
    return steps, {'key': parsed['spec'], 'bound': parsed['spec'], 'error': ''}


def check(text, run=None):
    """Whether a key can be installed, without binding it: {key, valid,
    taken} (`taken`: what else uses it, "" when free or ours)."""
    parsed = parse(text)
    if not parsed or not parsed['spec']:
        return {'key': str(text or ''), 'valid': False, 'taken': ''}
    raw = (run or hyprctl)('-j', 'binds')
    try:
        binds = json.loads(raw) if raw else []
    except ValueError:
        binds = []
    return {'key': parsed['spec'], 'valid': True, 'taken': conflict(binds if isinstance(binds, list) else [], parsed)}


# Where free keys are looked for, in order: G for guide first, then the
# rest of the alphabet under each modifier pair Omarchy leaves room in.
FREE_MODS = ('SUPER + CTRL', 'SUPER + ALT', 'SUPER + CTRL + ALT', 'SUPER + SHIFT + ALT')
FREE_KEYS = 'GJMQUXYZHKNOPRTVWBCDEFILSA'


def free(binds, n=6):
    """Up to `n` keys no bind uses (ours counts as free), to offer when the
    recorder can't hear a taken one: Hyprland handles a bound key before
    any app, so Super+Ctrl+F (Omarchy's tiled full screen) never reached
    Settings > Guides."""
    out = []
    for mods in FREE_MODS:
        for key in FREE_KEYS:
            parsed = parse(f'{mods} + {key}')
            if not conflict(binds, parsed):
                out.append(parsed['spec'])
                if len(out) >= n:
                    return out
    return out


def hyprctl(*args):
    try:
        done = subprocess.run(['hyprctl', *args], capture_output=True, text=True, timeout=HYPRCTL_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout


def state_path():
    base = os.environ.get('XDG_STATE_HOME') or os.path.expanduser('~/.local/state')
    return os.path.join(base, 'omatrophy', 'guide-key.json')


def sync(text, run=hyprctl):
    """Binds the Guide key the setting asks for; returns and saves {key,
    bound, error} for Settings > Guides."""
    raw = run('-j', 'binds')
    try:
        binds = json.loads(raw) if raw else None
    except ValueError:
        binds = None
    if not isinstance(binds, list):
        result = {'key': str(text or ''), 'bound': '', 'error': 'Hyprland did not answer; the Guide key is not bound.'}
    else:
        steps, result = plan(text, binds)
        for lua in steps:
            reply = (run('eval', lua) or '').strip()
            if reply != 'ok' and 'hl.bind(' in lua:
                # Hyprland's reply quotes the Lua; the owner needs only this.
                result = dict(result, bound='', error=f'Hyprland did not accept {result["key"]} as a key; pick another.')
    path = state_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(result, f)
    return result
