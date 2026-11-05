# 15. Check an agent's lock on the owner's machine, per installed binary

- Status: Accepted
- Date: 2026-11-04
- Builds on [ADR 14](0014-generate-guides-through-the-users-agent.md)

## Context

ADR 14 lets an agent make guides only once a real headless run has shown
that its lock keeps shell and file tools off. Claude Code was checked when
its adapter was written. Codex and OpenCode adapters were written from
their `--help`, in a session that had no login for either, so they stayed
"not supported yet" until someone edited `checked = True` in the code.
The owner has both installed, and runs OpenCode against a local model the
code's author can't reach.

Two things showed on 2026-11-04 that a lock is only as good as the
binary it was checked on:

- `opencode run` talks to OpenCode's shared background service unless
  given `--standalone`; that service keeps its own config, so the lock
  passed inline may never reach the agent. The first check failed because
  the service's port was taken, not because the lock held.
- Agents update often, and each maker can change its headless flags.

## Decision

- **The check runs on the owner's machine.** `omatrophy.py guide check
  <agent>` (and Settings > Guides' Check) asks the agent, through the
  exact command a guide job uses, to write a file and run a shell command
  aimed at a fresh folder, once with no tools and once with web tools. It
  passes when every run answered and neither happened.
- **A pass is recorded per installed binary.** It goes to
  `~/.local/state/omatrophy/guide-locks.json` with the agent's real path,
  size and mtime. An adapter runs when it was checked in the code or a
  recorded pass matches the binary installed now; an update turns the
  agent off again until checked. No subprocess is needed to tell.
- **A failed or unanswered run never enables.** A run that errors (no
  login, a rate limit, a busy port) is a fail, not a pass by default.
- **A check inside ai-jail is never recorded.** The agent has its own
  /tmp there, so a write would not show; that run only checks the agent
  works inside the jail.
- Agents without a headless command in OmaTrophy can't be checked; they
  stay listed as "no headless mode yet".

## Consequences

- The owner can turn Codex or OpenCode on from the panel, on their own
  login and models, without editing code.
- The check trusts what it can observe: a model that politely declines to
  write still passes, which is the lock's job to make impossible, not the
  model's. Claude's check also saw its tool list; others have no such
  listing (unverified whether codex's or opencode's JSON events would show
  a blocked tool call).
- Each check costs two short agent runs.
