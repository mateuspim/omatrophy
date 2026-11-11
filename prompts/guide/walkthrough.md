You are writing the walkthrough part of a 100% achievement guide for
**{{game}}**. The player has {{progress}}. Using the excerpts given and the
achievements below (in the route's order), write a step-by-step path
through the game: its chapters, missions or areas in the order the player
meets them, with the achievements to get at each step and a warning at the
step where a missable one is lost. You have no tools and need none.

Excerpts (chunk id, then source URL, then text):

{{excerpts}}

Achievements, in the route's order (name, phase, notes, then the store's
description; `[unlocked]` ones are done):

{{table}}

Steps:

- One step per chapter, mission, area or block of the game, in play
  order; 5 to 30 steps. Post-game, DLC and online come last, one step
  each. A step can hold no achievement when the story passes through it.
- `title`: the chapter, mission or area as the game names it, when an
  excerpt names it; else a short plain name ("After the credits").
- `text`: one sentence: what this step is for ("Finish the chapter and
  pick up the two kill achievements on the way"). Spoiler-light for
  hidden achievements.
- `actions`: what to do there, in the order the player meets it: each
  `{"where": "...", "what": "...", "achievement": "..."}`. `where` is the
  place as the game names it (a room, an area, a boss arena, a menu);
  `what` one short instruction; `achievement` the name it earns, or ""
  when the action only gets the player on. A story step says where to go
  and what to do there too, not only "play through the chapter". Leave
  out an action that only says to play or finish the chapter for its
  "Completed ..." achievement: the step already lists it, and the
  tracker showed it twice. A step with nothing else to do has no
  actions. A
  cleanup pass (chapter select, free roam) gets one action per place, in
  the order to replay them, each with its chapter or area in `where`;
  more than about 8 actions, split the step by chapter or area. At most
  12 actions a step.
- `achievements`: names exactly as listed, the ones got in this step,
  `[unlocked]` ones included: they show the player where they are. Every
  achievement in exactly one step: the step where it unlocks. One that
  builds up over many steps (collect them all, every mission, every rank)
  goes where it finishes, often a late step of its own, not the first
  step that starts it.
- `missables`: names from `achievements` that are lost if the player
  moves on without them.
- `cites`: quotes backing the step, as below.

{{rules}}

<walkthrough>
{"steps": [{"title": "...", "text": "...", "achievements": ["..."], "missables": [],
            "actions": [{"where": "...", "what": "...", "achievement": "..."}],
            "cites": [{"source": "S1.2", "quote": "..."}]}]}
</walkthrough>
