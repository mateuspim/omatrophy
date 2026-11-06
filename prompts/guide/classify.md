You are writing part of a 100% achievement guide for **{{game}}**. Classify
each achievement below using only the excerpts given. You have no tools and
need none.

Excerpts (chunk id, then source URL, then text):

{{excerpts}}

Achievements to classify (name, then the store's description; `hidden`
marks a secret one, `unlocked` ones are listed only so you can name them as
combo partners):

{{achievements}}

Every achievement in the game, for `combine_with`:

{{all_names}}

For each achievement to classify, give:

- `name`: exactly as listed.
- `phase`: one of {{phases}}. `missable` for anything that can be locked
  out (a point of no return, a choice, a timed event); `story` for
  progression; `quick` for things under 15 minutes; `challenge` for skill or
  difficulty runs; `grind` for long counters; `collect` for collectibles;
  `online` for multiplayer.
- `difficulty`: 1 (trivial) to 5 (very hard).
- `time`: short text such as "~10-30 min", and `minutes`: `[low, high]`
  as whole numbers. When no source gives a time, estimate one from what
  the achievement asks and the game's length, and set
  `"time_estimate": true`; the guide shows it as unverified.
- `missable`: true or false; `missable_note`: where the point of no return
  is, or "" when unknown.
- `counter`: `{"target": 50, "label": "kills"}` for a count of 2 or more,
  else null.
- `combine_with`: names of achievements best done in the same run.
- `tips`: one or two plain sentences.
- `dlc`: the DLC or separate mode the achievement belongs to, or "" for
  the base game. The store's description often names it: "Feed Jack every
  type of food in Jack's 55th Birthday" belongs to `Jack's 55th Birthday`,
  not to the main story. Use the name as the description or a source
  writes it.
- `cites`: `[{"source": "<chunk id or URL>", "quote": "<verbatim>"}]`.
- `unverified`: the fields above that no quote backs.

{{rules}}

<items>
[{"name": "...", "phase": "quick", "difficulty": 1, "time": "~5 min", "minutes": [5, 5],
  "missable": false, "missable_note": "", "counter": null, "combine_with": [],
  "tips": "...", "dlc": "", "cites": [{"source": "S1.2", "quote": "..."}], "unverified": []}]
</items>
