# Which model makes the best guide

Results of `omatrophy.py guide bench` on three Steam games, measured
2026-11-05 with the unreleased 100% guides build (after OmaTrophy 0.5.2).
How the score works: [docs/specs/guides.md](../specs/guides.md#benchmark).
Results vary per game, per run and, for a local model, per machine; treat
them as one sample, not a ranking to trust blindly. Run your own with your
games.

## Setup

- Entries: Claude Code with Sonnet (effort medium) and with Haiku (default
  effort), and OpenCode with Qwen3.8 Flash Next at a 2-bit quant on a local
  server. All inside ai-jail, web research on, nothing picked or kept.
- Games, only their open achievements:
  - METAL GEAR SOLID V: GROUND ZEROES, 13 open (small)
  - Resident Evil 7 Biohazard, 11 open, all of them DLC (DLC test)
  - Rise of the Tomb Raider, 81 open, many in DLC or Endurance (big)
- The local model's web search tool was unavailable during the run (its
  search server didn't answer), so it fetched pages it knew or guessed.
  OmaTrophy's own Steam guide fetch worked for every entry.
- Scores below use the stricter quote check (a quote must say more than
  the achievement's own name, description or DLC name; search result pages
  are no source). The first scoring counted name-only quotes and put the
  local model first everywhere.

## Summary

| Agent · model | Where it runs | Score (MGS V GZ / RE7 / RotTR) | Verified quotes | Coverage | Time (small / DLC / big) | Cost (3 games) |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Code · Haiku | cloud | 86.9 / 69.6 / 94.1 | 92 of 105 (88%) | 100% | 2m52 / 3m07 / 9m57 | $0.30 |
| Claude Code · Sonnet, medium | cloud | 87.1 / 70.2 / 81.7 | 72 of 105 (69%) | 100% | 1m32 / 1m37 / 3m48 | $1.14 |
| OpenCode · Qwen3.8 Flash Next, Q2 | local | 95.0 / 82.3 / 77.8 | 63 of 105 (60%) | 100% | 8m29 / 5m11 / 23m59 | $0 |

## Per game

Score, verified items, filled fields (phase, difficulty, time, tip),
sections written, wall time, cost as the agent reported it, tokens, items
tagged with a DLC, items marked missable.

### METAL GEAR SOLID V: GROUND ZEROES (13 open)

| Entry | Score | Verified | Fields | Sections | Time | Cost | Tokens | DLC | Missable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenCode · Qwen3.8 Flash Next Q2 | 95.0 | 13/13 | 75% | 4/4 | 8m29s | $0 | 658k | 2 | 1 |
| Claude · Sonnet medium | 87.1 | 11/13 | 75% | 3/4 | 1m32s | $0.20 | 48k | 0 | 0 |
| Claude · Haiku | 86.9 | 10/13 | 75% | 4/4 | 2m52s | $0.07 | 99k | 0 | 0 |

### Resident Evil 7 Biohazard (11 open, all DLC)

| Entry | Score | Verified | Fields | Sections | Time | Cost | Tokens | DLC | Missable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| OpenCode · Qwen3.8 Flash Next Q2 | 82.3 | 7/11 | 75% | 4/4 | 5m11s | $0 | 711k | 11 | 1 |
| Claude · Sonnet medium | 70.2 | 4/11 | 75% | 3/4 | 1m37s | $0.25 | 97k | 11 | 0 |
| Claude · Haiku | 69.6 | 3/11 | 75% | 4/4 | 3m07s | $0.09 | 123k | 3 | 0 |

Without web research (`--no-web`, only OmaTrophy's own Steam guide fetch,
which found nothing usable for these items) every entry verified 0/11:
Sonnet 57.5, Qwen 55.0, Haiku 55.0, in 27 s, 1m49s and 47 s.

### Rise of the Tomb Raider (81 open)

| Entry | Score | Verified | Fields | Sections | Time | Cost | Tokens | DLC | Missable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude · Haiku | 94.1 | 79/81 | 75% | 4/4 | 9m57s | $0.14 | 282k | 59 | 16 |
| Claude · Sonnet medium | 81.7 | 57/81 | 73% | 3/4 | 3m48s | $0.69 | 141k | 67 | 0 |
| OpenCode · Qwen3.8 Flash Next Q2 | 77.8 | 43/81 | 71% | 4/4 | 23m59s | $0 | 2.5M | 67 | 0 |

## What the numbers don't show

- **Time is never filled.** No entry gave an item a time: the classify
  prompt leaves it out unless a source states one, and guide pages rarely
  do per achievement. That is why every "Fields" sits near 75%.
- **Verified means "on a page", not "useful".** Haiku's Tomb Raider quotes
  are often another site's wording of the description ("Survive for 5
  days"), which passes the check; the local model's Ground Zeroes quotes
  carried real detail (counts, conditions). Read a guide before trusting
  its score.
- **Missables.** Haiku's 16 Tomb Raider missables are Endurance challenge
  conditions from one Steam comment, not points of no return
  (unverified against the game).
- **DLC.** Sonnet and the local model tagged every RE7 DLC item; Haiku
  tagged 3 of 11. Every open RE7 item was DLC, so this run couldn't test
  whether DLC stays out of the main-story route step.
- **Sections.** Sonnet left one of the four sections empty in every game,
  which costs it 2.5 points each time.
- **Local speed** depends on the machine and on what else uses the GPU;
  no game was running here. The local model read up to 18x the tokens of
  a cloud one, mostly whole fetched pages.

## Takeaways

- Haiku is the cheap, steady default: best verified share, cents per game.
- Sonnet is the fastest and costs the most; it didn't write better
  checked guides here.
- A small local model can make a usable guide at no cost when it can
  fetch pages, but takes several times as long, and its quality depends
  on its web tools working. Without web research no entry could back its
  claims.
