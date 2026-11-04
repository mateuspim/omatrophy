# 14. Make 100% guides through the user's own coding agent, on request

- Status: Accepted
- Date: 2026-11-04

## Context

The owner wants a guide per game in OmaTrophy: the path to 100%, what to do
next, which achievements are fastest, which are missable, which combine.
They already built this as a separate local web app. It writes a Markdown
guide plus a `- [ ]` checklist per game (`<slug>-<appid>.md`), a
`.plan.json` with per-achievement phase, difficulty, time, missable flag,
counter, combos and tips, and a `.sources.json` cache. It makes them with a
headless `claude` or `codex` run that does its own web research, then checks
each quote against the pages fetched. On 2026-11-04 it held 149 games;
11 had a plan, about 10 had real guide prose.

ADR 1 and ADR 7 keep OmaTrophy local and keyless. Its network calls time
out after 4 s so a toast never waits. A guide can't come from the
launcher's files, and it needs a language model. The owner asked for
generation inside OmaTrophy, grounded in trusted guide sites
(PowerPyx, TrueAchievements and the like), through "whichever harness
Omarchy installs or uses", with a choice of model in each one.

What we found on 2026-11-04:

- `omarchy-default-agent` offers 13 agents (pi, omp, opencode, claude,
  codex, grok, gemini, openclaw, hermes, copilot, crush, cursor-agent,
  muse) and records the user's pick in
  `~/.config/omarchy/defaults/agent`. Its `omarchy-agent` launcher only
  opens an interactive session with every permission approved. That's
  wrong for an unattended job that should only read the web.
- Each agent has its own headless mode, its own way to turn tools off,
  and its own list of models: a built-in set (claude's `opus`, `sonnet`,
  `fable` and any others its account offers), a local cache (codex's
  `models_cache.json`), or a command (`opencode models`, `crush models`,
  `pi --list-models`).
- Any of them may run a local model: opencode, crush or pi against an
  OpenAI-compatible endpoint, or claude through `ANTHROPIC_BASE_URL`. A
  run like that may have no web tools, weak ones, or little room for long
  pages.
- TrueAchievements, PlayStationTrophies and XboxAchievements answer a
  plain client with 403 (a bot check). Retrying with a browser user agent
  would dodge that check, and OmaTrophy won't do it. Steam's global
  percentages and individual Steam community guide pages answer a plain
  client. PowerPyx failed TLS verification that day (certificate
  expired), cause unverified.

## Decision

- **Generation is a job the owner starts.** It runs from
  `omatrophy.py guide make <store> <app>` or the tracker's button, never
  from the watcher, one game at a time, with a status file and a stop,
  like Load from Steam (ADR 13). The 4 s rule stays for everything a toast
  or panel read waits on. A guide job may take minutes and uses longer
  timeouts.
- **The agent and its model are the user's.** `guide-agent` in config.json
  picks the agent; empty means follow `omarchy-default-agent`. Every
  agent that `omarchy-default-agent` offers gets an adapter: a table row
  with its headless command, how to turn its tools off, how to allow web
  search, its model and effort flags, and where its models are listed.
  `guide agents` lists the installed agents with the models each one
  offers, read from that agent's own source. The panel offers the same
  list, plus free text for a model the list doesn't name. The pick is
  stored per agent (`guide-models`), so switching agents keeps each
  one's model. Our own adapter runs the agent, never `omarchy-agent`. It
  runs in an empty temporary folder with no shell and no file writes,
  and with web tools only when the job asks for research. OmaTrophy
  holds no API key; it uses the agent's own login or local endpoint.
- **Never an unlocked agent.** An adapter is enabled only once it has
  been checked to keep shell and file tools off in headless mode. An
  agent whose lock isn't confirmed is listed as "not supported yet", and
  it's never run with auto-approve as a fallback.
- **OmaTrophy gathers and checks; the agent writes.** OmaTrophy itself
  collects what it can fetch with an honest client: the store's
  achievement list, rarity and the player's progress; Steam community
  guides; pages the owner saved by hand into the game's sources folder;
  and pages the agent fetched, when its adapter reports them. It passes
  that text to the agent in short excerpts. The agent's own web search is
  an optional extra that local models can skip. Every claim the agent
  makes carries a source and a verbatim quote. OmaTrophy matches each
  quote against the text it holds, and a claim it can't match shows as
  "(unverified)". OmaTrophy never works around a site's bot check.
- **Small steps that a weak model can follow.** The job runs in stages:
  gather (no model), classify the achievements in batches of about 15
  (phase, time, difficulty, missable, combos, tips, as JSON), plan the
  route (order and prose from the compact table, not the pages), then
  verify (no model). Each model stage answers in one tagged JSON block that
  OmaTrophy validates. It retries once with the errors listed, then keeps
  what passed. The prompts are files in the repo, versioned with the
  format.
- **Guides are the owner's data, in OmaTrophy's own folder.** They live in
  `~/.local/share/omatrophy/guides/`, not the cache: each one cost time
  or money. The file layout follows the owner's existing app
  (`<slug>-<app>.md`, `.plan.json`, `.sources.json`). Steam is the
  default store, and other stores add their id (`<slug>-gog-<app>.md`), so
  `guide import <folder>` can copy the 149 existing files in unchanged.
  OmaTrophy never writes into the other app's folder.
- **Read-only for progress, for now.** Unlocks come from the store, as
  everywhere else. A checklist tick made by hand in an imported `.md` counts
  as done. OmaTrophy doesn't tick, count or take notes yet; ADR 9 leaves
  that as a separate decision (slice e).
- **No guide text in the repo.** Guides quote third-party sites, so the
  repo ships the reader, the prompts and a made-up sample for
  `dev/samples/` only.

## Consequences

- With a guide made, the tracker can show the route, missables first,
  what to do next and time per achievement. Toasts and the panel never
  wait on any of it.
- Guide quality depends on the agent. A local model gets the same
  excerpts and checks, so a weak run produces a shorter guide with more
  "(unverified)" marks, not made-up facts that pass as checked.
- Sites behind a bot check reach a guide only through the agent's own web
  tools or a page the owner saved; their quotes verify only when the
  adapter hands back the fetched text (claude's stream does) or the page
  is saved locally.
- Each supported agent's headless flags are its maker's to change. An
  adapter that breaks fails that job with the agent's own error and
  touches no guide.
- Cloud agents cost the owner money per guide; the job records what the
  agent reports (tokens, and $ when it says) in the plan file. A local
  model shares the GPU with any game running; the job doesn't stop for one
  (unverified how much a game notices).
- This changes ADR 1's "keyless, local" for this one job, and only when
  the owner starts it. Without a configured agent, the rest of OmaTrophy
  works as before and the guide view just offers to make one.
