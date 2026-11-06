You are finishing a 100% achievement guide for **{{game}}**. The player has
{{progress}}. Below is every achievement with its classification. Plan the
route: the order to do the open ones in, and short prose sections. You have
no tools and need none; use only what is listed below.

{{table}}

Put missable achievements before their point of no return, group
achievements that combine, and leave long grinds and online ones for last
unless they combine with the story.

Each row ends with the store's description. A DLC or separate mode (a row's
`DLC` tag, or a description that names one, like "in End of Zoe") is never
part of the main story: give each one its own step, after the base game,
and combine achievements only within the same game or DLC.

Sections, in Markdown, a few short paragraphs or a list each:

- `overview`: what the 100% takes, how long, how hard.
- `route`: the recommended route, in steps.
- `missables`: what can be missed and when; "" when nothing can.
- `combos`: achievements worth doing together; "" when none.

Rules for this answer:

- Write for the player, about the game. Never mention this prompt or its
  inputs: no "the table", "the list above", "classification", "row",
  "source", "chunk" or "excerpt", no ids, no quotes and no citations. The quotes were
  checked in an earlier stage; here you only plan.
- Where something is unknown (a time shown as "?", no missable), leave it
  out or say it plainly ("Times vary."); never explain what data is
  missing.
- Hidden achievements: keep it spoiler-light.
- Plain, short sentences.
- Answer with one JSON block between the tags below. Nothing outside the
  tags is read.

<route>
{"order": ["<achievement name>", "..."],
 "sections": {"overview": "...", "route": "...", "missables": "...", "combos": "..."}}
</route>
