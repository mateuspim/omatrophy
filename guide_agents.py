"""The coding agents a guide can be made with (ADR 14), one adapter each.

An adapter knows its agent's headless command, how to lock it down (no
shell, no file writes; web tools only when the job asks), how to pass a
model and effort, where its models are listed, and how to read its answer.
OmaTrophy never runs `omarchy-agent` (interactive, every permission
approved) and never falls back to an auto-approve flag. An adapter runs
only once its lock was checked on a real run (`checked`); the rest are
listed as "not supported yet". `dev/check-lock.py <agent>` repeats that
check after an agent update.
"""
import json, os, re, shutil, signal, subprocess, tempfile, time

from stores.base import CACHE, read_json, write_json

# A stage may research the web or classify a long batch; the spec's ceiling.
STAGE_SECONDS = 25 * 60
POLL_SECONDS = 0.5
# `guide agents` answers the panel, so a model list that has to run the
# agent itself (opencode, crush, pi) waits at most this, then uses the
# copy from its last answer.
MODELS_SECONDS = 4
MODELS_FRESH = 24 * 3600
# What an agent prints can be long (claude's stream holds every page it
# fetched); a cap keeps a runaway answer from filling memory.
MAX_OUTPUT = 16 * 1024 * 1024
# The ids omarchy-default-agent offers (its `omarchy:args`, 2026-11-04).
OMARCHY_AGENTS = ('pi', 'omp', 'opencode', 'claude', 'codex', 'grok', 'gemini', 'openclaw',
                  'hermes', 'copilot', 'crush', 'cursor-agent', 'muse')


def default_agent_path():
    # Resolved per call so tests can move HOME.
    return os.path.expanduser('~/.config/omarchy/defaults/agent')


def omarchy_default():
    """The agent `omarchy-default-agent` records, or '' when none is picked.
    Read from its file, not by running the command: the panel reads this."""
    try:
        with open(default_agent_path(), encoding='utf-8') as f:
            return f.readline().strip()
    except OSError:
        return ''


class Adapter:
    id = ''
    name = ''
    # True once a real headless run showed the lock keeps shell and file
    # tools off (ADR 14: never an unlocked agent).
    checked = False
    # Can search the web itself for the research stage.
    web = False
    # Where `models` comes from, as `guide agents` names it.
    models_source = 'none (type a model)'
    binary = ''

    def installed(self):
        return bool(self.binary) and shutil.which(self.binary) is not None

    def command(self, folder, web, model, effort):
        """(argv, stdin text or None, extra env) for one locked run in `folder`."""
        raise NotImplementedError

    def models(self):
        """[{id, name, efforts}] from the agent's own source; [] when it can't say."""
        return []

    def answer(self, stdout, folder):
        """{text, pages: [{url, text}], links: [url], usage: {input, output, cost_usd}, error}
        from what the run printed."""
        return {'text': stdout, 'pages': [], 'links': [], 'usage': {}, 'error': ''}


class Claude(Adapter):
    id, name, binary = 'claude', 'Claude Code', 'claude'
    # Checked 2026-11-04 (claude 2.1.318): with `--tools ""` the init event
    # listed no tools; with `--tools WebSearch WebFetch` only those two, and
    # a request to run `touch` found no Bash tool. No file appeared either way.
    checked = True
    web = True
    models_source = 'built-in aliases and ~/.claude.json'
    ALIASES = (('opus', 'Opus'), ('sonnet', 'Sonnet'), ('haiku', 'Haiku'), ('fable', 'Fable'))
    EFFORTS = ['low', 'medium', 'high', 'xhigh', 'max']

    def command(self, folder, web, model, effort):
        tools = ['WebSearch', 'WebFetch'] if web else ['']
        argv = ['claude', '-p', '--output-format', 'stream-json', '--verbose', '--no-session-persistence',
                # No MCP servers, no user or project settings: hooks and
                # plugins there could run commands of their own.
                '--strict-mcp-config', '--setting-sources', '',
                # Anything not allowed below is refused, never prompted for.
                '--permission-mode', 'dontAsk']
        if model:
            argv += ['--model', model]
        if effort:
            argv += ['--effort', effort]
        # `--tools` is an allowlist of built-in tools: "" is none at all.
        argv += ['--tools', *tools]
        if web:
            argv += ['--allowedTools', *tools]
        return argv, None, {}

    def models(self):
        out = [{'id': a, 'name': n, 'efforts': self.EFFORTS} for a, n in self.ALIASES]
        found = read_json(os.path.expanduser('~/.claude.json'), {})
        extra = found.get('additionalModelOptionsCache') if isinstance(found, dict) else None
        for m in extra if isinstance(extra, list) else []:
            if isinstance(m, dict) and isinstance(m.get('value'), str) and m['value'] not in [o['id'] for o in out]:
                out.append({'id': m['value'], 'name': str(m.get('label') or m['value']), 'efforts': self.EFFORTS})
        return out

    def answer(self, stdout, folder):
        """Claude's stream-json: the `result` event holds the answer and its
        cost; each WebFetch's tool_result is a page the agent read (its
        summary of the page, so a quote from it can verify); WebSearch
        results name links OmaTrophy may fetch itself."""
        calls, pages, links = {}, [], []
        out = {'text': '', 'pages': pages, 'links': links, 'usage': {}, 'error': ''}
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            kind = event.get('type')
            content = (event.get('message') or {}).get('content') if kind in ('assistant', 'user') else None
            for part in content if isinstance(content, list) else []:
                if not isinstance(part, dict):
                    continue
                if part.get('type') == 'tool_use':
                    calls[part.get('id')] = (part.get('name'), part.get('input') or {})
                elif part.get('type') == 'tool_result':
                    name, args = calls.get(part.get('tool_use_id'), ('', {}))
                    text = tool_text(part.get('content'))
                    if name == 'WebFetch' and isinstance(args.get('url'), str) and text:
                        pages.append({'url': args['url'], 'text': text})
                    elif name == 'WebSearch':
                        links.extend(u for u in re.findall(r'https://[^\s"\'<>)\]]+', text) if u not in links)
            if kind == 'result':
                usage = event.get('usage') or {}
                out['text'] = str(event.get('result') or '')
                out['usage'] = {'input': int(usage.get('input_tokens') or 0) + int(usage.get('cache_read_input_tokens') or 0)
                                + int(usage.get('cache_creation_input_tokens') or 0),
                                'output': int(usage.get('output_tokens') or 0),
                                'cost_usd': event.get('total_cost_usd')}
                if event.get('is_error'):
                    out['error'] = out['text'] or str(event.get('subtype') or 'error')
        return out


def tool_text(content):
    """A tool_result's text: a string, or a list of {type: text, text} parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(p.get('text', '') for p in content if isinstance(p, dict) and isinstance(p.get('text'), str))
    return ''


class Codex(Adapter):
    id, name, binary = 'codex', 'Codex', 'codex'
    # Flags from `codex exec --help` and `codex features list` (0.166.0,
    # 2026-11-04). Not checked on a real run yet: the session that wrote it
    # had no Codex sign-in. Run dev/check-lock.py codex, then set True.
    checked = False
    web = True
    models_source = '$CODEX_HOME/models_cache.json'

    def command(self, folder, web, model, effort):
        argv = ['codex', 'exec', '--json', '--skip-git-repo-check', '--ephemeral', '-C', folder,
                # read-only keeps writes off; the two features are its shell
                # tools, so no command runs at all.
                '--sandbox', 'read-only', '--disable', 'shell_tool', '--disable', 'unified_exec',
                '-c', 'approval_policy="never"',
                '-c', 'web_search="live"' if web else 'web_search="disabled"',
                '--output-last-message', os.path.join(folder, 'answer.txt')]
        if model:
            argv += ['-c', f'model={json.dumps(model)}']
        if effort:
            argv += ['-c', f'model_reasoning_effort={json.dumps(effort)}']
        return argv + ['-'], None, {}

    def models(self):
        home = os.environ.get('CODEX_HOME') or os.path.expanduser('~/.codex')
        found = read_json(os.path.join(home, 'models_cache.json'), {})
        rows = found.get('models') if isinstance(found, dict) else found
        out = []
        for m in rows if isinstance(rows, list) else []:
            if not isinstance(m, dict) or not isinstance(m.get('slug'), str) or m.get('visibility', 'list') != 'list':
                continue
            levels = m.get('supported_reasoning_levels') or []
            efforts = [lv.get('effort') if isinstance(lv, dict) else lv for lv in levels]
            out.append({'id': m['slug'], 'name': str(m.get('display_name') or m['slug']),
                        'efforts': [e for e in efforts if isinstance(e, str)]})
        return out

    def answer(self, stdout, folder):
        out = {'text': '', 'pages': [], 'links': [], 'usage': {}, 'error': ''}
        try:
            with open(os.path.join(folder, 'answer.txt'), encoding='utf-8') as f:
                out['text'] = f.read()
        except OSError:
            pass
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            if event.get('type') == 'turn.completed':
                usage = event.get('usage') or {}
                out['usage'] = {'input': int(usage.get('input_tokens') or 0),
                                'output': int(usage.get('output_tokens') or 0), 'cost_usd': None}
            elif event.get('type') in ('error', 'turn.failed'):
                err = event.get('message') or (event.get('error') or {}).get('message')
                out['error'] = str(err or 'codex failed')
            item = event.get('item') if event.get('type') == 'item.completed' else None
            if isinstance(item, dict) and item.get('type') == 'agent_message' and not out['text']:
                out['text'] = str(item.get('text') or '')
        return out


class ListedModels(Adapter):
    """An agent whose models come from a command of its own
    (`opencode models`, `crush models`, `pi --list-models`): one id per
    line, first word. Cached a day, and the cache answers when the command
    is slow."""
    models_command = ()

    def models(self):
        path = f'{CACHE}/guide/models-{self.id}.json'
        cached = read_json(path, {})
        if isinstance(cached, dict) and time.time() - cached.get('time', 0) < MODELS_FRESH:
            return cached.get('models', [])
        try:
            done = subprocess.run(list(self.models_command), capture_output=True, text=True,
                                  timeout=MODELS_SECONDS, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            return cached.get('models', []) if isinstance(cached, dict) else []
        ids = []
        for line in done.stdout.splitlines():
            word = line.strip().split(' ')[0] if line.strip() else ''
            if word and not word.startswith('#') and word not in ids:
                ids.append(word)
        models = [{'id': i, 'name': i, 'efforts': []} for i in ids]
        try:
            write_json(path, {'time': int(time.time()), 'models': models})
        except OSError:
            pass
        return models


class OpenCode(ListedModels):
    id, name, binary = 'opencode', 'OpenCode', 'opencode'
    # Lock through an inline config: every edit and shell permission denied,
    # those tools off. From opencode's config schema; `opencode run --help`
    # (2026-11-04) shows no tool flags. Not checked on a real run yet (no
    # provider set up in the session that wrote it): dev/check-lock.py opencode.
    checked = False
    web = True
    models_source = 'opencode models'
    models_command = ('opencode', 'models')

    def command(self, folder, web, model, effort):
        lock = {'permission': {'edit': 'deny', 'bash': 'deny', 'external_directory': 'deny',
                               'webfetch': 'allow' if web else 'deny'},
                'tools': {'bash': False, 'edit': False, 'write': False, 'patch': False,
                          'webfetch': web, 'websearch': web}}
        argv = ['opencode', 'run', '--format', 'json']
        if model:
            argv += ['-m', model + (f'#{effort}' if effort else '')]
        return argv, None, {'OPENCODE_CONFIG_CONTENT': json.dumps(lock)}

    def answer(self, stdout, folder):
        texts, out = [], {'text': '', 'pages': [], 'links': [], 'usage': {}, 'error': ''}
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            part = event.get('part') if isinstance(event, dict) else None
            if isinstance(part, dict) and part.get('type') == 'text' and isinstance(part.get('text'), str):
                texts.append(part['text'])
            if isinstance(event, dict) and event.get('type') == 'error':
                out['error'] = str((event.get('error') or {}).get('message') or event.get('error') or 'opencode failed')
        out['text'] = '\n'.join(texts) or stdout
        return out


class Unchecked(Adapter):
    """A row whose headless mode or lock isn't known well enough to run."""

    def __init__(self, id, name, binary=None, models_command=None, source=None):
        self.id, self.name, self.binary = id, name, binary or id
        self.models_command = models_command
        if source:
            self.models_source = source

    def models(self):
        if not self.models_command or not self.installed():
            return []
        lister = ListedModels()
        lister.id, lister.models_command = self.id, self.models_command
        return lister.models()


ADAPTERS = [Claude(), Codex(), OpenCode(),
            Unchecked('crush', 'Crush', models_command=('crush', 'models'), source='crush models'),
            Unchecked('pi', 'Pi', models_command=('pi', '--list-models'), source='pi --list-models'),
            Unchecked('gemini', 'Gemini'), Unchecked('grok', 'Grok'), Unchecked('hermes', 'Hermes'),
            Unchecked('copilot', 'GitHub Copilot'), Unchecked('cursor-agent', 'Cursor CLI'),
            Unchecked('omp', 'Oh My Pi'), Unchecked('muse', 'Muse Code')]
BY_ID = {a.id: a for a in ADAPTERS}


# Host variables an agent may need inside ai-jail, which passes only a
# safe allowlist: its endpoint and key when the user set them (a local
# model through ANTHROPIC_BASE_URL, say), and where codex keeps its state.
JAIL_ENV = ('ANTHROPIC_BASE_URL', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_MODEL',
            'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'CODEX_HOME', 'XDG_CONFIG_HOME', 'XDG_DATA_HOME')


def jail_installed():
    return shutil.which('ai-jail') is not None


def jailed(argv, extra_env):
    """`argv` run inside ai-jail (bubblewrap, Landlock, seccomp): the agent
    sees only the job's empty folder read-write, its own state dirs and
    the network, whatever its own flags let it do. A second fence around
    the adapter's lock, not a replacement: an agent still runs only when
    its own lock was checked. `--exec` runs it directly, stdin and stdout
    piped as without the jail; nothing is saved to a project .ai-jail."""
    out = ['ai-jail', '--exec', '--no-status-bar', '--no-save-config', '--no-display', '--no-gpu',
           '--no-audio', '--no-docker', '--no-ssh', '--network']
    for name in sorted(set(JAIL_ENV) | set(extra_env)):
        if name in os.environ or name in extra_env:
            out += ['--env', name]
    return out + ['--'] + list(argv)


def supported_ids():
    return [a.id for a in ADAPTERS if a.checked]


def resolve(picked):
    """The adapter for `picked` (an id, or '' for Omarchy's default).
    Raises SystemExit with what to do when there's none to run."""
    agent = picked or omarchy_default()
    names = ', '.join(supported_ids())
    if not agent:
        raise SystemExit(f'omatrophy: guide: no agent picked; pick one ({names}) in Settings > Guides, '
                         'or with: omatrophy.py set guide-agent claude')
    if agent == 'openclaw':
        raise SystemExit("omatrophy: guide: OpenClaw has no one-shot mode; pick another agent in Settings > Guides")
    adapter = BY_ID.get(agent)
    if adapter is None:
        raise SystemExit(f'omatrophy: guide: {agent} is not an agent OmaTrophy knows; pick {names} in Settings > Guides')
    if not adapter.installed():
        raise SystemExit(f'omatrophy: guide: {agent} not found; install it or pick another in Settings > Guides')
    if not adapter.checked:
        raise SystemExit(f"omatrophy: guide: {agent} can't run locked down yet; pick {names} in Settings > Guides")
    return adapter


def picks(cfg):
    """{agent: {model, effort}} from config.json's `guide-models`, cleaned."""
    found = cfg.get('guide-models') if isinstance(cfg, dict) else None
    out = {}
    for agent, pick in (found.items() if isinstance(found, dict) else []):
        if isinstance(pick, dict):
            out[agent] = {'model': str(pick.get('model') or ''), 'effort': str(pick.get('effort') or '')}
    return out


def listing(cfg):
    """`guide agents`: every row of the table, with its models and picks."""
    chosen, default, jail = picks(cfg), omarchy_default(), jail_installed()
    out = []
    for a in ADAPTERS:
        installed = a.installed()
        pick = chosen.get(a.id, {})
        out.append({'agent': a.id, 'name': a.name, 'installed': installed, 'supported': a.checked,
                    'default': a.id == default, 'web': a.web,
                    # Only agents that can run: a listing command can be slow
                    # (opencode's took over 20 s once), and the panel waits on it.
                    'models': a.models() if installed and a.checked else [],
                    'model': pick.get('model', ''), 'effort': pick.get('effort', ''), 'source': a.models_source,
                    'jail': jail})
    return out


def run(adapter, prompt, web=False, model='', effort='', stopped=lambda: False, timeout=STAGE_SECONDS,
        clock=time.monotonic, sleep=time.sleep, jail=False):
    """Run one locked stage in a fresh empty folder (inside ai-jail with
    `jail`). Returns the adapter's answer plus {seconds, ok, stopped}. A
    stop or the ceiling kills the agent's whole process group."""
    started = clock()
    with tempfile.TemporaryDirectory(prefix='omatrophy-guide-') as folder:
        argv, stdin_text, extra = adapter.command(folder, web, model, effort)
        env = dict(os.environ, **extra)
        if jail:
            argv = jailed(argv, extra)
        out_path, err_path = os.path.join(folder, '.stdout'), os.path.join(folder, '.stderr')
        with open(out_path, 'wb') as out, open(err_path, 'wb') as err:
            try:
                proc = subprocess.Popen(argv, cwd=folder, env=env, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                        start_new_session=True)
            except OSError as e:
                return dict(blank(), error=f'{adapter.id} did not start ({e})', seconds=0)
            try:
                proc.stdin.write((prompt if stdin_text is None else stdin_text).encode())
                proc.stdin.close()
            except OSError:
                pass
            state = 'ran'
            while proc.poll() is None:
                if stopped():
                    state = 'stopped'
                elif clock() - started > timeout:
                    state = 'timeout'
                if state != 'ran':
                    kill(proc)
                    break
                sleep(POLL_SECONDS)
        stdout = read_capped(out_path)
        stderr = read_capped(err_path)
        found = adapter.answer(stdout, folder)
    seconds = int(clock() - started)
    if state == 'stopped':
        return dict(found, ok=False, stopped=True, error='stopped', seconds=seconds)
    if state == 'timeout':
        return dict(found, ok=False, stopped=False, error=f'{adapter.id} took over {timeout // 60} min', seconds=seconds)
    if proc.returncode != 0 and not found['error']:
        last = [line for line in stderr.splitlines() if line.strip()][-1:] or [f'exit {proc.returncode}']
        found['error'] = f'{adapter.id}: {last[0][:300]}'
    return dict(found, ok=not found['error'], stopped=False, seconds=seconds)


def blank():
    return {'text': '', 'pages': [], 'links': [], 'usage': {}, 'error': '', 'ok': False, 'stopped': False}


def kill(proc):
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait()


def read_capped(path):
    try:
        with open(path, 'rb') as f:
            return f.read(MAX_OUTPUT).decode('utf-8', 'replace')
    except OSError:
        return ''
