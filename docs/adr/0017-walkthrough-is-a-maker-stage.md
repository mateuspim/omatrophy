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

Added in 0.6.4, after the first bench that scored the walkthrough (MGS V
Ground Zeroes, 2026-11-10): an open achievement in no step is asked
again, since the walkthrough is for what is left; an achievement stays
in its first step only (sonnet had counted one open twice); a step's
missables take in the items classify marked missable; and a step's
quote must say more than the store's own text, as an item's must.

Added in 0.7.0, after the owner's RE5 guide (60/60 classified, 25 steps
all grounded, yet hard to follow): story steps were a sentence or two
with no place, and a cleanup step crammed eight achievements over four
chapters into one paragraph. A step now has one sentence of `text` and
ordered `actions` (`{where, what, achievement}`), checked like the rest;
more than 12 asks to split it by chapter or area. The tracker shows the
open step's actions as a checklist. A retry that comes back worse no
longer replaces the first answer, "act", "stage", "level" and "area"
need a number to mark an excerpt as a walkthrough, and a quote cut off
on a word like "the" no longer verifies.

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

## Note: markers and "I'm here" (0.7.0)

Guessing the step from unlocks went wrong on RE5: the flash-grenade
trophy, filed under 4-1, was got in 3-1, and the player showed at 4-1.
Placing the player after the last fully finished step (ca626b3) helped,
but a side trophy left open in a finished chapter still held them back.
Two fixes, as OmaTrophy still sees only achievements:

- The walkthrough stage names a `marker` per step (maker 5): the one
  achievement of the step that proves it finished, a chapter or mission
  clear, `""` when the game has none. The reader places the player after
  the last cleared marker and never past the next one not cleared;
  between them the finished-step rule still applies. Plans without
  markers read as before; `guides.MAKER` goes to 5, so they say "older
  maker".
- The player can say where they are: **I'm here** on a step (or
  `guide here`) pins it in the state folder, not in the guide, until
  they finish a step at or after it.
