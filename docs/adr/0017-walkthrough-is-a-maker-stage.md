# 17. The walkthrough is one more maker stage, checked like the rest

- Status: Accepted
- Date: 2026-11-06

## Context

A guide (ADR 14) says what each achievement takes and a route in prose,
but the owner asked for a walkthrough: the game's chapters or missions in
play order, with the achievements to get in each and a warning where a
missable one is lost, shown over the running game (ADR 16) so the player
can see where they are.

Walkthrough pages are long and per game; copying one would be a page
we'd have to keep, and an agent writing one freely invents missions.

## Decision

The maker gets a `walkthrough` stage after `route` (model, no tools),
with `prompts/guide/walkthrough.md`. It gets the classified achievements
in the route's order and the excerpts that best match them, then chunks
that read like a walkthrough (chapter, mission, act...), trusted sites
first, up to 16,000 characters. It answers
`<walkthrough>{"steps": [...]}</walkthrough>`: 5 to 30 steps (at most
40 kept), each a title, a few sentences, the achievements to get there,
which of them are missable there, and cites.

The same rules hold as for items: names the game doesn't have are
dropped and asked again, talk about the input is cut (as in route), and
each cite is checked against the page it names. A step with no verified
quote is marked unverified, not dropped: the order of a game's chapters
is worth showing even when no excerpt quotes it.

A failed walkthrough (no parse after the retry, or the agent erred) costs
only the walkthrough: the items and route are already made, and the
earlier walkthrough, if any, stays.

The plan holds the steps as `walkthrough`; `guide` gives them with
`api`s and `step`, the first step with an achievement left. The tracker
shows them under Up next with that step open.

## Consequences

- One more model call per guide (about one route's worth of tokens plus
  excerpts).
- Guides made before this have no walkthrough; `guides.MAKER` is 3, so
  the tracker says "older maker" and a re-make adds one.
- The step that is open follows the store's unlocks and hand ticks; the
  game's own progress (which mission the save is on) isn't read.
