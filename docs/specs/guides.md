# 100% guides

Status: slices b to e built; f (manual ticks) waits on its own ADR. The slices below
build it in order, and each one updates this page to match the code. Why it works this way: [ADR 14](../adr/0014-generate-guides-through-the-users-agent.md).

## Slices

| Slice | Delivers |
| --- | --- |
| a | This spec, ADR 14, the stage contracts. |
| b (built) | Reader: `guide <store> <app>`, `guide import`, file parsing, tests, a made-up sample in `dev/samples/`. |
| c (built) | Maker: gather, the four agent adapters, prompts, verify, `guide make/stop/status`, tests with a fake agent. |
| d (built) | Tracker Guide view (`TrackerView.qml`, hot-reloads): route, phases, missables first, next up, Make guide button; `dev/render.sh guide`. |
| e (built) | Now tab "Up next" from the plan. |
| f | Manual ticks, counters, notes: needs its own ADR (ADR 9's open question). |

## Files

Folder: `~/.local/share/omatrophy/guides/` (`$XDG_DATA_HOME` respected).
OmaTrophy writes only here.

| File | Holds |
| --- | --- |
| `<slug>-<app>.md` | Steam game `<app>`: guide prose plus the checklist. |
| `<slug>-<store>-<app>.md` | Any other store (`doom-gog-1435827232.md`). |
| `<name>.plan.json` | The structured guide, next to its `.md`. |
| `<name>.sources.json` | Every source the guide quotes: `{url: {kind, fetched, text}}`. |
| `sources/<name>/` | Pages the owner saved by hand (`.html`, `.txt`, `.md`), read as sources on the next make. |
| `jobs/<store>-<app>.json` | One make job per game, like `steam-load/status.json`; ended ones older than 7 days are removed. Guides are made in parallel, up to 3 at once (`MAX_JOBS`). |
| `jobs/<store>-<app>.stop` | A stop request for that game's job, removed when the job sees it. |
| `<name>.md.prev`, `<name>.plan.json.prev` | The guide as it was before the last make, so a worse new one never costs the old. |

`<slug>` is the game name lowercased, with runs of anything but `a-z0-9`
turned into `-`. A game is found by its trailing `-<app>` (Steam) or
`-<store>-<app>`, never by the slug, so a rename keeps the file. Exactly the
games app's layout, so `guide import` copies its files unchanged.

### `.md`

```markdown
# <Game name>

- Steam AppID: 418370
- Progress: 47/58 (81%)

## Guide notes

<Markdown prose: Overview, Recommended route, Missable warning,
per-DLC sections, Efficiency combos. Links are the citations.>

## Achievements

- [ ] **Name** — Description.
- [ ] **Name** 🔒hidden — (hidden)
- [x] **Name** — Description. _(unlocked 2017-04-07)_
- [x] **Name** — Description. _(unlocked, date unknown)_
```

The reader takes the prose between `## Guide notes` and `## Achievements`.
A `[x]` line without `_(unlocked ...)_` is a hand tick and counts as done
(slice b). OmaTrophy rewrites the checklist from the store when it makes a
guide; it never changes a hand tick.

### `.plan.json`

A superset of the games app's plan, so both read each other's. Keys
OmaTrophy doesn't know survive a rewrite.

```json
{
  "format": 2,
  "maker": 3,
  "generated": 1793059700,
  "agent": {"name": "claude", "model": "", "stages": {"classify": 4, "route": 1}},
  "order": ["Name", "..."],
  "items": {
    "Name": {
      "name": "Name",
      "api": "ACH_ID",
      "phase": "missable",
      "difficulty": 2,
      "time": "~10-30 min",
      "minutes": [10, 30],
      "missable": true,
      "missable_note": "Before leaving the Baker house in chapter 3",
      "counter": {"target": 50, "label": "kills"},
      "combine_with": ["Other name"],
      "tips": "Two to four plain sentences: where, how, what to watch out for.",
      "dlc": "End of Zoe",
      "cites": [{"source": "https://...", "quote": "verbatim snippet", "verified": true}],
      "unverified": ["time"],
      "details": {}
    }
  },
  "sections": {"overview": "...", "route": "...", "missables": "...", "combos": "..."},
  "walkthrough": [{"title": "Chapter 2: The Veil", "text": "...", "achievements": ["Name"],
                   "missables": ["Name"], "cites": [{"source": "https://...", "quote": "...", "verified": true}],
                   "unverified": false}],
  "usage": [{"engine": "claude", "stage": "classify", "input": 0, "output": 0,
             "cost_usd": 0.17, "seconds": 43, "ok": true, "ts": 1793059700}],
  "progress": {},
  "steps": {}
}
```

- `items` is keyed by the achievement's display name (the games app's
  key). `api` (new in format 2) is the store id, and the reader matches by
  `api` first, then by name. Names shared by two achievements are matched
  in store order.
- `phase`: `missable`, `story`, `quick`, `challenge`, `grind`, `collect`,
  `online`. The tracker groups by phase in that order, missables first.
- `difficulty` 1-5; `minutes` is `[low, high]` and comes with `time`, the
  text the guide shows; either may be missing. With no source giving a
  time, classify estimates one (`"time_estimate": true` in its answer,
  not stored) and `time` is always in `unverified`, even when another
  quote verifies the item.
- `missable_note` says where the point of no return is; it's empty when
  that's unknown.
- `counter` is set only for a target of 2 or more; `null` otherwise.
- `cites`: a claim with no verified cite lists its fields in
  `unverified`, and the view marks them "(unverified)".
- `details` (per-achievement steps, facts, pitfalls) and `progress`/`steps`
  (the games app's hand state) pass through untouched. The games app's
  `usage`, without `stage`, reads as one whole-guide run.
- A `usage` entry whose answer failed the checks holds `errors` (up to
  five), the reasons the stage asked again.
- Format 1 is the games app's plan: no `format`, no `api`, no `minutes`,
  no `cites`. The reader accepts it.

## Command line

| Command | Does |
| --- | --- |
| `guide [store app]` | Prints the guide as JSON for the tracker: `{store, app, file, generated, order, items: {api: item}, sections, notes, ticks: [api], next: [api], agent, cost_usd, outdated, walkthrough, step}` (`agent` is the plan's, `cost_usd` the sum of its `usage`, `walkthrough` the plan's steps with `achievements` and `missables` as `api`s and `done` when none is left open, `step` the index of the first step with one open or -1, `outdated` true when OmaTrophy made it with a `maker` older than `guides.MAKER`, so the tracker says "older maker" and lights Make again), or `{}` when there is none. The reader is `guides.py`. `items` holds only the plan items that match a store achievement (by `api`, then name); `ticks` are the `api`s of hand ticks; `ticks` and the store's unlocks both count as done for `next`. `next` is the first three open items in `order`, missables first. Without arguments, the game running now, else the last one played. |
| `guide import <folder>` | Copies every `*-<app>.md` with its `.plan.json` and `.sources.json` from another folder (the games app's `games/`), skipping files we already have (`--replace` overwrites). Read-only on `<folder>`. Prints `imported N, skipped M`. |
| `guide agents` | Every agent with its models and picks (see Settings). |
| `guide model <agent> <model> [effort] [@http://endpoint]`, `guide model <agent> default` | Sets or clears that agent's pick in `guide-models`; `@endpoint` points claude at a local Anthropic-compatible server (`ANTHROPIC_BASE_URL`) for that model. |
| `guide jail` | Prints the installed ai-jail's version and path, whether the sandbox is on, and each agent's jail options; exits non-zero when ai-jail isn't installed. |
| `guide jail-options <agent> [options...]` | Sets that agent's extra ai-jail options in `guide-jail-options`; none (or `""`) clears them. One argument with spaces (the panel's) is split like a shell would. Only `--map`, `--rw-map`, `--env`, `--env-from-file` (each with a value; `--opt=value` works) and `--allow-loopback-listen`; anything else fails with the list. `--forward-port`, `--allow-host`, `--allow-private-host` and `--publish-port` fail with why: ai-jail refuses them next to the `--network` we pass, and with it the host's `127.0.0.1` (a local model's server) is reachable already. Prints `<agent> in ai-jail: <options>`. |
| `guide bench <store> <app> <agent:model[:effort][@endpoint]>... [--no-web] [--jail\|--no-jail] [--pick] [--keep]` | [Compares](#benchmark) agents and models on one game. |
| `guide check <agent> [model] [--jail]` | The lock check on a real run (below); prints a line per run and `PASS`/`FAIL`, exits non-zero on a fail. Progress in `~/.cache/omatrophy/guide/check.json` (`{agent, jail, state: running\|passed\|failed, lines, time, runs}`; `jail`: a `--jail` check, which Settings shows under Sandbox) for Settings > Guides' Check. |
| `guide make <store> <app> [--no-web] [--notify] [--jail\|--no-jail] [--agent a] [--model m] [--effort e]` | Runs the job below; the flags override the settings for this run only. `--notify` (the tracker passes it) sends a desktop notification when the job is done or failed. `--jail` runs the agent inside ai-jail (see Settings). One line per stage, then `done: N items, M verified`, or `stopped`/`failed: <what to do>`. Exits non-zero with no agent, an unsupported agent, this game's guide already being made, 3 guides being made already, or a game already at 100% (nothing open to plan; the tracker says so instead of offering a make). A saved sandbox setting without ai-jail installed runs without it and prints a `note:`; an explicit `--jail` fails. |
| `guide stop [store app]` | Stops that game's job, or every running one without a game, within half a second (the agent's process group is killed); nothing is written, so the old guide stays. |
| `guide jobs` | `{jobs: [status...], max}`: every kept job, newest first, and how many may run at once. The tracker and the panel read it. |
| `guide status [store app]` | That game's job, or the newest of any without a game: `{state, store, app, game, stage, done, total, line, started, time, agent, model, pid, web, jail, header, open}` (`web`: the research stage runs; `jail`: inside ai-jail; `header`: the game's poster URL, `""` when unknown; `open`: achievements the guide covers); `state` is `running`, `done`, `stopped` or `failed`, and a `running` job whose `pid` is gone reads as `failed`. `{}` before any job. `done`/`total` count steps: gather, research (with web), one per classify batch, route, walkthrough, verify. |

## Settings (config.json)

| Key | Values | Default |
| --- | --- | --- |
| `guide-agent` | `""` (follow `omarchy-default-agent`) or any agent id in the adapter table. `set guide-agent default\|<id>`. | `""` |
| `guide-models` | Per agent, `{agent: {"model": "...", "effort": "...", "endpoint": "..."}}`; a missing agent or `""` uses that agent's own default. Written by `guide model` and the panel. | `{}` |
| `guide-web` | `true`, `false`: let the agent search the web itself. `set guide-web on\|off`. | `true` |
| `guide-jail` | `true`, `false`: run the agent inside [ai-jail](https://github.com/akitaonrails/ai-jail) (`ai-jail --exec ... --network -- <agent command>`): the job's empty folder read-write, the agent's own state dirs, the network, and only the environment variables it needs (its endpoint and key, when set). A second fence around the adapter's lock; an unchecked agent still never runs. Checked with `guide check <agent> [model] --jail` (Settings > Guides: Check in ai-jail): passed for OpenCode with a local model on 2026-11-05 (ai-jail 2.15.0, its key file let in with `--map`); Claude Code passed in the jail on 2026-11-05 once mise shims were resolved (mise itself fails in the jail with "Read-only file system", so OmaTrophy starts the tool `mise which` names); Codex in the jail is unverified there. On ai-jail 3.x (`jail_version` major 3 or more) the argv also has `--clean --agent-state --harness <agent>` (the harness only for agents ai-jail knows: claude, codex, opencode, crush, gemini, grok, pi): with no terminal, 3.x applies its first-run preset in a new folder, whose filtered egress it won't combine with `--network`, and leaves the agent logged out. `--clean` ignores that and any saved policy for the job's temp folder, so the flags alone decide and nothing needs approving with `ai-jail configure`. Claude Code (haiku), Codex (GPT-6.1 Terra) and OpenCode with a local model passed `guide check --jail` on ai-jail 3.1.0, 2026-11-06. `set guide-jail on\|off`. | `false` |
| `guide-jail-options` | Per agent, `{agent: ["--map", "~/path/to/key", ...]}`: ai-jail options added before `--` when that agent runs in the jail (the lock check too), `~` expanded. What a local model may need: its key file (`--map`); its server on the host's `127.0.0.1` is reachable already. Checked against the list under `guide jail-options` when written and when read: a saved filtered-network option is dropped with its value, and an entry that still fails reads as none. Written by `guide jail-options` and the panel. | `{}` |

`guide agents` prints `[{agent, name, installed, supported, default,
web, models: [{id, name, efforts}], model, effort, endpoint, source, jail, jail_version, jail_options, headless, relocked, suggested}]` (`supported`: its lock is checked, here or when written; `headless`: OmaTrophy has a command for it, so it can be checked; `relocked`: a check passed for an earlier binary; `jail`: ai-jail is installed; `jail_version`: its version, `""` when unknown; `jail_options`: that agent's `guide-jail-options`; `suggested`: `{model, effort, why}`, the best model for that agent in the [guide bench](../guide/guide-models.md) when it lists it, `{}` otherwise; the panel offers it, nothing picks it). It lists
every agent in the adapter table. `default` marks the one
`omarchy-default-agent` names, and `model`/`effort` are the picks from
`guide-models`. `models` comes from the source named in the table and is
empty when the agent can't list them, isn't installed, or isn't supported yet. The panel then offers free text:
any string the agent's model flag takes, such as a full model id, a
`provider/model` for a local endpoint, or an alias. `guide model <agent>
<model> [effort]` sets a pick, and `guide model <agent> default` clears
it.

## The make job

1. **Gather** (no model). The store's achievements (name, description,
   hidden, rarity, unlocked, counter) and playtime. Sources, each cut into
   numbered chunks of about 1,500 characters:
   - Steam community guides for the app, top rated, with achievement
     tags; at most 3 pages (unverified: the guide list page answered
     without links on 2026-11-04, so links may have to come from the
     agent).
   - Files in `sources/<name>/`.
   - Earlier `.sources.json`, kept 30 days.
   - Fetches use the client name `omatrophy-guide/<version>` and an 8 s
     timeout, 10 pages a job at most. A 403, 429 or captcha page counts
     as "not fetchable" and is skipped, never retried with another
     client.
2. **Research** (model, web tools, only with `guide-web` and an agent that
   has them). The agent gets the game, the open achievements and the
   trusted sites (list below) and answers with links plus a quote per
   achievement. The adapter hands back the pages it fetched where the agent
   reports them (claude's `stream-json`). OmaTrophy fetches the rest
   itself when they're fetchable.
3. **Classify** (model, no tools). Batches of about 15 open achievements,
   each with the top excerpts for it (picked by matching words from its
   name and description), about 12,000 characters a batch. Answers
   `<items>[...]</items>`.
4. **Route** (model, no tools). The compact table of every item (no
   excerpts), the player's progress, DLC. Answers
   `<route>{order, sections}</route>`. Plain prose for the player: no
   quotes, no citations, no talk about its input ("the provided table",
   "`table`", "chunk ids"). Such talk is an error that asks again; what
   is left after the second answer is cut (the citation, else the
   sentence).
5. **Walkthrough** (model, no tools; [ADR 17](../adr/0017-walkthrough-is-a-maker-stage.md)).
   The items in the route's order, their best excerpts, then chunks that
   read like a walkthrough (chapter, mission, act...), trusted sites
   first, up to 16,000 characters. Answers
   `<walkthrough>{"steps": [{title, text, achievements, missables, cites}]}</walkthrough>`,
   5 to 30 steps in play order (40 kept at most). Unknown names, talk
   about the input and open achievements in no step are errors that ask
   again. An achievement named in several steps stays in the first. Each
   step's `missables` gain its items that classify marked missable, and
   its quotes must say more than the store's text for its achievements,
   as items' do. A failure here keeps the rest of the guide and the
   earlier walkthrough.
6. **Verify** (no model). Validates the shape. Drops names not in the
   game. Matches each quote against the source text after folding case,
   whitespace and quotes. Writes the files atomically.

Pages come from, in this order: the earlier `.sources.json`, files in
`sources/<name>/` (named `file:<name>`), Steam guides, then pages the
agent read (Claude's WebFetch results, OpenCode's webfetch results, kind
`agent`), the pages it cites, and trusted-site links its searches turned
up (Claude's and OpenCode's search results; Codex's `web_search` items:
result URLs and pages it opened), best site first, fetched by OmaTrophy
within the budget. A Steam player's own page (`/profiles/...`, `/id/...`)
is never fetched: it lists achievements, not how to get them. Search engines' result pages
(Bing, DuckDuckGo, Google, any `/search?q=`) are never kept as sources. A
cite verifies when its quote (folded, 12-400 characters) is in the source
it names, or failing that in any source held, and says more than the
store's own text: with the achievement's name, description and DLC name
taken out, at least 10 letters or digits remain. The cite then names that
source.

Each model stage is checked as it lands: on a shape error it is asked once
more with the errors listed, then the valid part is kept. A cut-short
job leaves the old guide in place.

### Benchmark

`guide bench` makes the guide once per entry, each in its own folder
`guides/bench/<yyyymmdd-hhmmss>/<n>-<entry>/`, reading the owner's saved
pages and earlier sources so every entry starts from the same text; the
owner's guide is untouched. It prints a line per stage, then a table, and
writes `results.json` there: `{store, app, game, web, jail, weights,
results: [{entry, agent, model, effort, endpoint, state, error, score,
metrics, seconds, cost_usd, tokens, calls, folder, name}]}`, best first;
`metrics` holds each measure (0..1) and the counts `items`, `cited`,
`unverified` and `steps`.

The score (0-100) uses only what OmaTrophy checks: `verified` (share of
covered items with a verified quote) 35, `coverage` (share of open
achievements classified) 25, `complete` (phase, difficulty, time and tip
filled) 15, `route` (open achievements placed in the order) 10,
`walkthrough` (half the open achievements placed in a step, half the
steps with a verified quote) 10, `sections` (overview, route, missables,
combos written) 5. The play order of the steps isn't checked, so it
isn't scored. Benches before 0.6.4 had no `walkthrough` measure and gave
`complete` 20 and `sections` 10. Ties go to
the cheaper (unknown cost last), then the faster. A failed or stopped
entry scores 0. `--pick` saves the best as `guide-agent` and its
`guide-models` pick (endpoint included); `--keep` copies its guide over
the game's (the old one kept as `.prev`). Ctrl-C skips the entry running;
`guide stop` doesn't reach a bench. Results of a first bench on three
games: [docs/guide/guide-models.md](../guide/guide-models.md).

### Trusted sites

Passed to the research stage as preferred, in this order: PowerPyx,
TrueAchievements, PlayStationTrophies, XboxAchievements, Steam community
guides, the game's official wiki or Fandom wiki. Other pages may be cited
but rank lower in excerpts.

### Prompt rules (every stage)

- Use the excerpts first. State only what a source says, and quote it
  (12-200 characters, verbatim) with its URL or chunk id.
- Write "(unverified)" for anything you can't quote. Never invent codes,
  locations, counts or times.
- Skip achievements already unlocked, except as combo partners.
- Hidden achievements: tips stay spoiler-light; the view hides them until
  revealed.
- Plain, short sentences. One JSON block between the stage's tags, nothing
  else needed outside it.
- The prompt text lives in `prompts/guide/<stage>.md` (`research`,
  `classify`, `route`, `walkthrough`), with `{{name}}` placeholders;
  `rules.md` holds these rules and fills `{{rules}}` (research, classify
  and walkthrough; route has its own, as it has nothing to quote).

### Agent adapters

One table row per agent `omarchy-default-agent` offers, except
openclaw, which only runs through its own gateway and terminal app.
Each runs in a fresh, empty temporary folder, with the prompt
on stdin or as an argument and a 25 min ceiling per stage. A row is
**supported** once a real run has shown that its lock keeps shell and file
tools off: `guide check <agent>` (Settings > Guides' Check, or
`dev/check-lock.py`) asks the agent, through the job's own command, to write
a file and run a shell command, with no tools and with web tools, and
passes when every run answered and neither happened. Claude's check was
made when its adapter was written (`checked` in `guide_agents.py`); any
other passes on the owner's machine ([ADR 15](../adr/0015-check-an-agents-lock-on-the-owners-machine.md)) and is recorded in
`~/.local/state/omatrophy/guide-locks.json` as `{agent: {passed, binary,
time, model}}`, where `binary` is the agent's real path, size and mtime: an
update of the agent turns it off again until checked. A check inside
ai-jail is never recorded (the agent's /tmp is its own there). Only rows
with a headless command can be checked. Until then `guide agents` shows it as "not
supported yet". No row ever falls back to an auto-approve flag. Flags come
from each tool's `--help` on 2026-11-04; "unverified" means the help didn't
show it or timed out.

| Agent | Headless | Lock (no shell, no writes) | Web for research | Model / effort | Models listed from |
| --- | --- | --- | --- | --- | --- |
| claude (**supported**, checked 2026-11-04 on 2.1.318) | `-p --output-format stream-json --verbose --no-session-persistence --strict-mcp-config --setting-sources "" --permission-mode dontAsk` | `--tools ""` (an allowlist of built-in tools: none) | `--tools WebSearch WebFetch --allowedTools WebSearch WebFetch` | `--model`, `--effort` | built-in aliases (`opus`, `sonnet`, `haiku`, `fable`, ...) plus `~/.claude.json` `additionalModelOptionsCache`; works with `ANTHROPIC_BASE_URL` for a local endpoint |
| codex (written, not checked yet) | `exec --json --skip-git-repo-check --ephemeral -C <tmp> --output-last-message <tmp>/answer.txt -c approval_policy="never"` | `--sandbox read-only --disable shell_tool --disable unified_exec` | `-c web_search="live"` (`"disabled"` otherwise) | `-c model=`, `-c model_reasoning_effort=` | `$CODEX_HOME/models_cache.json` (`visibility: list`) |
| opencode (off until `guide check` passes) | `run --standalone --format json` (its own server: without it, `run` uses OpenCode's shared background service and that service's config) | `OPENCODE_CONFIG_CONTENT` with `permission` edit/bash/external_directory `deny` and those tools off | `webfetch`/`websearch` on in that config | `-m provider/model#variant` | `opencode models --standalone` |
| crush | `run --quiet` | unverified (`--yolo` only on the interactive command) | unverified | `-m`, `--reasoning-effort` | `crush models` |
| pi | `-p --mode json` | `--no-tools`, or `--tools` allowlist | `--tools` with its web tool, if one is installed (unverified) | `--model provider/id:thinking` | `pi --list-models` |
| gemini | `-p --output-format json` | `--approval-mode plan` | unverified whether plan mode allows search | `-m` (unverified) | none (free text) |
| grok | unverified (`[PROMPT]` starts an interactive session) | `--disallowed-tools`, `--deny` | default on; `--disable-web-search` for no-tools stages | unverified | none (free text) |
| hermes | `chat --query-file <f> --oneshot` | `-t <toolsets>` with only web | `-t` | `-m` | none (free text) |
| copilot | unverified | unverified | unverified | unverified | none |
| cursor-agent | unverified | unverified | unverified | unverified | none |
| omp | unverified | unverified | unverified | unverified | none |
| muse | unverified | unverified | unverified | unverified | none |

A missing agent fails with `omatrophy: guide: <agent> not found; install
it or pick another in Settings > Guides`. An unsupported one fails with
`omatrophy: guide: <agent> can't run locked down yet; pick claude, codex,
... in Settings > Guides` (the supported ones at that time).
