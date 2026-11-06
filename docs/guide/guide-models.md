# Which model makes the best guide

Results of `omatrophy.py guide bench` on three Steam games, measured
2026-11-06 with the unreleased 100% guides build (after OmaTrophy 0.5.2).
How the score works: [docs/specs/guides.md](../specs/guides.md#benchmark).
Results vary per game, per run and, for a local model, per machine; treat
them as one sample, not a ranking to trust blindly. Run your own with your
games.

## Setup

- Entries: Claude Code with Opus 5.5 (`claude-opus-5-5`), Sonnet and
  Haiku; Codex with GPT-6.1 Terra, GPT-6.1 Sol and GPT-6 Luna; OpenCode
  with Qwen3.8 Flash Next at a 2-bit quant on a local server, its web
  search through a self-hosted SearXNG. Effort medium, except Haiku and
  Luna at their default.
- Web research on, outside ai-jail (ai-jail 3.1.0 refuses the way
  OmaTrophy starts agents; every agent's own lock check passed), nothing
  picked or kept. No game was running.
- Games, only their open achievements:
  - METAL GEAR SOLID V: GROUND ZEROES, 13 open (small)
  - Resident Evil 7 Biohazard, 11 open, all of them DLC (DLC test)
  - Rise of the Tomb Raider, 81 open, many in DLC or Endurance (big)
- A quote verifies only when it is on a page OmaTrophy holds and says more
  than the achievement's own name, description or DLC name.
- Cost is what the agent reports. Codex reports none (it bills a ChatGPT
  plan, not per call), so its cost is shown as "plan"; the local model
  costs only its electricity.

## Summary

| Agent · model | Where it runs | Score (MGS V GZ / RE7 / RotTR) | Average | Verified quotes | Time (3 games) | Cost (3 games) |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Code · Opus 5.5, medium | cloud | 95.0 / 88.6 / 88.6 | 90.7 | 94 of 105 (90%) | 14 min | $3.15 |
| Codex · GPT-6.1 Terra, medium | cloud | 88.8 / 91.4 / 85.0 | 88.4 | 81 of 105 (77%) | 6 min | plan |
| OpenCode · Qwen3.8 Flash Next, Q2 | local | 86.9 / 82.3 / 87.0 | 85.4 | 79 of 105 (75%) | 32 min | $0 |
| Claude Code · Sonnet, medium | cloud | 89.8 / 67.1 / 78.7 | 78.5 | 64 of 105 (61%) | 8 min | $1.27 |
| Claude Code · Haiku | cloud | 86.9 / 58.6 / 88.4 | 78.0 | 80 of 105 (76%) | 14 min | $0.28 |
| Codex · GPT-6 Luna | cloud | 89.6 / 60.0 / 76.1 | 75.2 | 48 of 105 (46%) | 8 min | plan |
| Codex · GPT-6.1 Sol, medium | cloud | 88.8 / 52.5 / 81.5 | 74.3 | 63 of 105 (60%) | 12 min | plan |

Every entry covered every open achievement.

## Per game

Score, verified items, filled fields (phase, difficulty, time, tip),
sections written, wall time, cost, tokens, items tagged with a DLC, items
marked missable.

### METAL GEAR SOLID V: GROUND ZEROES (13 open)

| Entry | Score | Verified | Fields | Sections | Time | Cost | Tokens | DLC | Missable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude · Opus 5.5 medium | 95.0 | 13/13 | 75% | 4/4 | 3m15s | $0.59 | 177k | 0 | 0 |
| Claude · Sonnet medium | 89.8 | 12/13 | 75% | 3/4 | 1m55s | $0.22 | 72k | 0 | 0 |
| Codex · GPT-6 Luna | 89.6 | 11/13 | 75% | 4/4 | 1m44s | plan | 159k | 2 | 1 |
| Codex · GPT-6.1 Terra medium | 88.8 | 11/13 | 71% | 4/4 | 1m23s | plan | 255k | 1 | 2 |
| Codex · GPT-6.1 Sol medium | 88.8 | 11/13 | 71% | 4/4 | 2m44s | plan | 324k | 0 | 2 |
| OpenCode · Qwen3.8 Flash Next Q2 | 86.9 | 10/13 | 75% | 4/4 | 5m17s | $0 | 576k | 0 | 0 |
| Claude · Haiku | 86.9 | 10/13 | 75% | 4/4 | 2m35s | $0.06 | 112k | 0 | 1 |

### Resident Evil 7 Biohazard (11 open, all DLC)

| Entry | Score | Verified | Fields | Sections | Time | Cost | Tokens | DLC | Missable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Codex · GPT-6.1 Terra medium | 91.4 | 10/11 | 72% | 4/4 | 1m32s | plan | 391k | 11 | 1 |
| Claude · Opus 5.5 medium | 88.6 | 9/11 | 75% | 4/4 | 4m04s | $0.84 | 314k | 11 | 0 |
| OpenCode · Qwen3.8 Flash Next Q2 | 82.3 | 7/11 | 75% | 4/4 | 5m47s | $0 | 1.05M | 11 | 1 |
| Claude · Sonnet medium | 67.1 | 3/11 | 75% | 3/4 | 2m05s | $0.28 | 118k | 11 | 0 |
| Codex · GPT-6 Luna | 60.0 | 0/11 | 75% | 4/4 | 1m38s | plan | 208k | 11 | 1 |
| Claude · Haiku | 58.6 | 1/11 | 52% | 4/4 | 1m58s | $0.08 | 97k | 11 | 0 |
| Codex · GPT-6.1 Sol medium | 52.5 | 0/11 | 50% | 3/4 | 2m15s | plan | 368k | 0 | 0 |

### Rise of the Tomb Raider (81 open)

| Entry | Score | Verified | Fields | Sections | Time | Cost | Tokens | DLC | Missable |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Claude · Opus 5.5 medium | 88.6 | 72/81 | 75% | 3/4 | 7m18s | $1.72 | 239k | 63 | 0 |
| Claude · Haiku | 88.4 | 69/81 | 67% | 4/4 | 9m48s | $0.14 | 278k | 57 | 15 |
| OpenCode · Qwen3.8 Flash Next Q2 | 87.0 | 62/81 | 75% | 4/4 | 21m05s | $0 | 909k | 67 | 0 |
| Codex · GPT-6.1 Terra medium | 85.0 | 60/81 | 70% | 4/4 | 3m18s | plan | 336k | 48 | 2 |
| Codex · GPT-6.1 Sol medium | 81.5 | 52/81 | 70% | 4/4 | 7m28s | plan | 612k | 50 | 0 |
| Claude · Sonnet medium | 78.7 | 49/81 | 75% | 3/4 | 4m30s | $0.77 | 156k | 67 | 0 |
| Codex · GPT-6 Luna | 76.1 | 37/81 | 76% | 4/4 | 5m28s | plan | 285k | 64 | 0 |

## What the numbers don't show

- **Time is never filled.** No entry gave an item a time: the classify
  prompt leaves it out unless a source states one, and guide pages rarely
  do per achievement. That is why "Fields" sits near 75%.
- **Verified means "on a page", not "useful".** A quote can be another
  site's wording of the description and still pass. Read a guide before
  trusting its score.
- **Codex's search runs on OpenAI's side**, so no page text comes back;
  only the pages it cites, fetched by OmaTrophy, can verify its quotes.
  On RE7, Sol and Luna cited no page OmaTrophy could fetch and verified
  nothing.
- **DLC.** Every RE7 open item is DLC: all entries but GPT-6.1 Sol tagged
  all 11 (Sol tagged none). That run couldn't test whether DLC stays out
  of the main-story route step.
- **Missables.** Haiku's 15 Tomb Raider missables are Endurance challenge
  conditions from a Steam comment, not points of no return (unverified
  against the game).
- **Sections.** Sonnet left one of the four sections empty in every game.
- **Runs differ.** The same Haiku and Sonnet entries a day earlier scored
  69.6 and 70.2 on RE7 (58.6 and 67.1 here), and Haiku 94.1 on Tomb
  Raider (88.4 here). Differences of a few points are noise.
- **Web search matters most for the local model.** With its search server
  down (2026-11-05) it verified 43 of 81 Tomb Raider items; with search
  working, 62.
- **Local speed** depends on the machine and on what else uses the GPU.
  The local model read 3-4x the tokens of a cloud one, mostly whole
  fetched pages.

## Takeaways

- Opus 5.5 had the highest average and the most verified quotes overall
  (best on two of three games), at about a dollar a game.
- GPT-6.1 Terra is close behind and the fastest; with a ChatGPT plan it
  costs nothing per guide.
- A small local model with working web search makes a usable guide for
  free, in 2-5x the time of a cloud model.
- Haiku is the cheap pay-per-use pick, but uneven: strong on the big game,
  weak on the DLC one.
