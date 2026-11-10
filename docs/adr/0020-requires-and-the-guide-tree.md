# 20. Hard prerequisites (`requires`) and the guide as a tree

- Status: Accepted
- Date: 2026-11-10
- Builds on [ADR 14](0014-generate-guides-through-the-users-agent.md) and
  [ADR 17](0017-walkthrough-is-a-maker-stage.md)

## Context

The owner's Resident Evil 5 guide (Opus, 60 of 60 classified, 51
verified) read badly as a plan of play. `combine_with` ("best done in
the same run") was the only link between achievements, and the model
used it loosely: every "Completed Chapter X" combined with Recruit and
Soldier. Nothing said that War Hero (Professional) can't be had before
Veteran is beaten, so Up next could offer it, and sixteen story
achievements took as much room as the hard ones.

## Decision

- Classify asks for `requires`: the achievements that must be unlocked
  first because the game locks this one until then. Only when an
  excerpt says so; it is a claim like the others (in `CLAIMS`), listed
  as unverified when no quote of the item verifies. It is not
  `combine_with`, which stays the soft "same run".
- The maker checks it as it checks the rest: names the game doesn't
  have are errors that ask again, an item never requires itself, and an
  edge that would close a cycle (with the batch, earlier batches or the
  unlocked items of the earlier guide) is dropped where it closes, with
  an error that asks again. What still closes one after the retry is
  dropped for good.
- `guide` gives each item's `requires` as `api`s and a `tree`: `story`
  (story items in play order), `chains` (each item that needs others,
  its prerequisites indented under it) and `alone` (the rest).
- Up next skips an item whose `requires` aren't all done: the game
  won't give it yet.
- The tracker's Guide view gets a Tree toggle that shows the tree as an
  indented outline, not a drawn graph (the owner's choice: it reads in
  the narrow guide column, over a game, at any font size). Story folds
  to one "n / m" line. A locked item is dimmed and says "needs X".
- `guides.MAKER` goes to 4, so guides made before say "older maker".

## Consequences

- Older guides have no `requires`: their tree is the story line and
  everything else on its own, and Up next is as before.
- A prerequisite no excerpt states is left out, so the tree can be
  thinner than the game's real one; that is the price of not guessing.
- An imported guide may hold a cycle; the tree walks each chain once
  and stops at the closing edge, and items with no root stay "on their
  own".
