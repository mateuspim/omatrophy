# 100% guides

Status: **design**, with slice b (the reader) built. The slices below
build it in order, and each one updates this page to match the code. Why it works this way: [ADR 14](../adr/0014-generate-guides-through-the-users-agent.md).

## Slices

| Slice | Delivers |
| --- | --- |
| a | This spec, ADR 14, the stage contracts. |
| b (built) | Reader: `guide <store> <app>`, `guide import`, file parsing, tests, a made-up sample in `dev/samples/`. |
| c | Maker: gather, the four agent adapters, prompts, verify, `guide make/stop/status`, tests with a fake agent. |
| d | Tracker Guide view (`TrackerView.qml`, hot-reloads): route, phases, missables first, next up, Make guide button; `dev/render.sh guide`. |
| e | Now tab "Up next" from the plan. |
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
| `status.json` | The latest make job, like `steam-load/status.json`. |

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
      "tips": "One or two plain sentences.",
      "dlc": "End of Zoe",
      "cites": [{"source": "https://...", "quote": "verbatim snippet", "verified": true}],
      "unverified": ["time"],
      "details": {}
    }
  },
  "sections": {"overview": "...", "route": "...", "missables": "...", "combos": "..."},
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
  text the guide shows; either may be missing.
- `missable_note` says where the point of no return is; it's empty when
  that's unknown.
- `counter` is set only for a target of 2 or more; `null` otherwise.
- `cites`: a claim with no verified cite lists its fields in
  `unverified`, and the view marks them "(unverified)".
- `details` (per-achievement steps, facts, pitfalls) and `progress`/`steps`
  (the games app's hand state) pass through untouched. The games app's
  `usage`, without `stage`, reads as one whole-guide run.
- Format 1 is the games app's plan: no `format`, no `api`, no `minutes`,
  no `cites`. The reader accepts it.

## Command line (slice b: `guide`, `guide import`; the rest is slice c)

| Command | Does |
| --- | --- |
| `guide [store app]` | Prints the guide as JSON for the tracker: `{store, app, file, generated, order, items: {api: item}, sections, notes, ticks: [api], next: [api]}`, or `{}` when there is none. The reader is `guides.py`. `items` holds only the plan items that match a store achievement (by `api`, then name); `ticks` are the `api`s of hand ticks; `ticks` and the store's unlocks both count as done for `next`. `next` is the first three open items in `order`, missables first. Without arguments, the game running now, else the last one played. |
| `guide import <folder>` | Copies every `*-<app>.md` with its `.plan.json` and `.sources.json` from another folder (the games app's `games/`), skipping files we already have (`--replace` overwrites). Read-only on `<folder>`. Prints `imported N, skipped M`. |
| `guide agents` | Every agent with its models and picks (see Settings). |
| `guide model <agent> <model> [effort]`, `guide model <agent> default` | Sets or clears that agent's pick in `guide-models`. |
| `guide make <store> <app> [--no-web] [--agent a] [--model m] [--effort e]` | Runs the job below; the flags override the settings for this run only. One line per stage, then `done: N items, M verified`, or `stopped`/`failed: <what to do>`. Exits non-zero with no agent, an unsupported agent, or another job running. |
| `guide stop` | Stops the job; a stage cut short writes nothing. |
| `guide status` | `status.json`: `{state, store, app, stage, done, total, line, started, agent}`. |

## Settings (config.json, slice c)

| Key | Values | Default |
| --- | --- | --- |
| `guide-agent` | `""` (follow `omarchy-default-agent`) or any agent id in the adapter table | `""` |
| `guide-models` | Per agent, `{agent: {"model": "...", "effort": "..."}}`; a missing agent or `""` uses that agent's own default. Written by `guide model` and the panel. | `{}` |
| `guide-web` | `true`, `false`: let the agent search the web itself | `true` |

`guide agents` prints `[{agent, name, installed, supported, default,
web, models: [{id, name, efforts}], model, effort, source}]`. It lists
every agent in the adapter table. `default` marks the one
`omarchy-default-agent` names, and `model`/`effort` are the picks from
`guide-models`. `models` comes from the source named in the table and is
empty when the agent can't list them. The panel then offers free text:
any string the agent's model flag takes, such as a full model id, a
`provider/model` for a local endpoint, or an alias. `guide model <agent>
<model> [effort]` sets a pick, and `guide model <agent> default` clears
it.

## The make job (slice c)

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
   `<route>{order, sections}</route>`.
5. **Verify** (no model). Validates the shape. Drops names not in the
   game. Matches each quote against the source text after folding case,
   whitespace and quotes. Writes the files atomically.

Each model stage is checked as it lands: on a shape error it is asked once
more with the errors listed, then the valid part is kept. A cut-short
job leaves the old guide in place.

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
- The prompt text lives in `prompts/guide/<stage>.md`, with `{{name}}`
  placeholders.

### Agent adapters

One table row per agent `omarchy-default-agent` offers, except
openclaw, which only runs through its own gateway and terminal app.
Each runs in a fresh, empty temporary folder, with the prompt
on stdin or as an argument and a 25 min ceiling per stage. A row is
**supported** once slice c has checked, on a real run, that its lock keeps
shell and file tools off. Until then `guide agents` shows it as "not
supported yet". No row ever falls back to an auto-approve flag. Flags come
from each tool's `--help` on 2026-11-04; "unverified" means the help didn't
show it or timed out.

| Agent | Headless | Lock (no shell, no writes) | Web for research | Model / effort | Models listed from |
| --- | --- | --- | --- | --- | --- |
| claude | `-p --output-format stream-json --verbose --no-session-persistence` | `--disallowedTools Bash Edit Write NotebookEdit` | `--allowedTools WebSearch WebFetch` | `--model`, `--effort` | built-in aliases (`opus`, `sonnet`, `haiku`, `fable`, ...) plus `~/.claude.json` `additionalModelOptionsCache`; works with `ANTHROPIC_BASE_URL` for a local endpoint |
| codex | `exec --json --skip-git-repo-check -C <tmp>` | `--sandbox read-only` | `--search` | `-c model=`, `-c model_reasoning_effort=` | `$CODEX_HOME/models_cache.json` (`visibility: list`) |
| opencode | `run --format json` | through its permission config (unverified how, slice c) | its own websearch provider (unverified) | `-m provider/model#variant` | `opencode models` |
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
