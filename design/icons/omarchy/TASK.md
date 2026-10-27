# Omarchy trophies: brief

Read `../BRIEF.md` for what the trophies are for and where they appear, then
replace its "Taste" section with this direction. Previous rounds (`../vector`,
`../painted`) were glossy trophy clip-art; the owner wants something more
modern and sleek, in the visual language of the Omarchy logo.

## The Omarchy language (see `../../ref/`)

- `omarchy-logo.svg` / `.png`: a pixel blackletter built on a strict
  **15-unit grid**. Every edge is horizontal or vertical; corners are cut in
  15-unit steps (stair-stepped chamfers), never rounded or curved. Counters
  are crisp rectangles. Solid, flat, single colour.
- `omarchy-mark-and-font.png`, top-left glyph: the Omarchy mark, a square
  frame drawn as a thick outline that is **broken** in two places (left
  middle, bottom right), with stepped inner ends.
- In the desktop, these always render in **one theme colour** (for example
  sage green `#a7c080` on dark `#2d353b`).

## What to make

A trophy cup drawn in that language: built on a pixel grid (use a 4- or
8-unit module inside the 128 viewBox so it scales cleanly), stepped corners,
straight edges only, a bold readable silhouette (bowl, two handles, stem,
base), modern and minimal: closer to a logo mark than to an illustration.

Shading is **flat planes**: a lit face and a shaded face (and at most one
highlight plane), no smooth gradients, no gloss. The tiers are materials
expressed as flat tones:

| tier | lit / shaded / highlight |
|---|---|
| bronze | warm copper tones |
| silver | cool neutral greys |
| gold | warm yellows |
| platinum | near-white with a cool blue-violet shade; must read as the top tier, e.g. through an extra stepped crown/rim detail or a brighter highlight plane, never by being bigger |

**Accent layer.** Each trophy also gets a thin accent detail in the Omarchy
spirit: for example an inlay line along the rim, or a broken stepped line
like the mark's outline, plus a small square **engraving plate** on the bowl
(leave the plate empty: the app engraves a glyph there). Draw the accent
detail as a **separate SVG file** in pure white (`#ffffff`) on transparent,
on exactly the same canvas, so the app can tint it with the user's theme
accent at runtime: `trophy-accent.svg` (shared by all tiers, since the
silhouette is shared). Don't include the accent in the tier files; leave the
spot it sits on as part of the body.

Also make `trophy-frame.svg`: the platinum trophy's frame, a square outline
in the style of the Omarchy mark (thick stroke, stepped ends, two breaks),
white on transparent, sized so the trophy sits inside it with room to
breathe. Original drawing, not a copy of the mark.

## Files

`trophy-bronze.svg`, `trophy-silver.svg`, `trophy-gold.svg`,
`trophy-platinum.svg`, `trophy-accent.svg`, `trophy-frame.svg`; viewBox
`0 0 128 128`; plain filled paths only (no strokes, gradients, filters,
masks, text or images: Qt's SVG Tiny renderer). One generator script for the
shared geometry. `contact-sheet.png` showing each tier with the accent tinted
`#a7c080` and again `#7fbbb3`, at 30, 76 and 256 px, on `#2d353b` and on a
bright background; plus the framed platinum. `NOTES.md` with the choices.

Render and look at your results, and iterate until it reads as one family
with the Omarchy logo and still reads as a trophy at 30 px.
Work only inside this folder.
