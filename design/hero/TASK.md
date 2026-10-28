# OmaTrophy README hero and wordmark: brief

OmaTrophy is an Omarchy shell plugin: Steam achievement unlocks as themed
trophy toasts over fullscreen games (bronze, silver, gold by rarity), a
platinum card when a game reaches 100%, a trophy cabinet in the bar and an
achievement tracker overlay. It is about to go public on GitHub. Make its
README hero and its wordmark logos, as siblings of OmaDroid and OmaReach.

Work only in this folder. Everything you need is in `ref/`.

## Deliverables (all in this folder)

1. `preview.svg`: the hero, a 3840×2160 SVG. Reference the UI captures by
   the relative path `captures/<name>.png` (they will live in
   `docs/brand/captures/` next to the final `docs/brand/preview.svg`; copy
   `ref/{now,tracker,gold,platinum,games}.png` into `./captures/` so your
   renders resolve the same way). Inline the mark from `ref/icon.svg`
   so the SVG renders standalone.
2. `preview.png`: `rsvg-convert -o preview.png preview.svg`, 3840×2160.
3. `logo.svg` (for dark backgrounds) and `logo-light.svg` (for light):
   icon + wordmark, same structure as `ref/sibling-omadroid-logo*.svg`.
4. `NOTES.md`: colours, fonts, layout coordinates, and what you chose and why.

## Composition (house standard, match the siblings)

Look at `ref/sibling-omadroid.png`, `ref/sibling-omareach.png` and the
source `ref/sibling-omadroid.svg`, and reuse its structure.

- Background: dark navy diagonal gradient `#0b1015 → #0a111b → #102236`, dot
  grid (56 px, `#7a8f9d`, opacity about .11–.16), an accent radial glow
  bottom-left, a blue radial glow top-right.
- Accent: trophy gold `#e9bd55` (from the icon; deeper `#a5752d`, light
  `#ffe297`). Wordmark "Oma" in `#eff4f7`, "Trophy" in the accent.
- Left column at x≈208: the pixel trophy mark (~232 px), the wordmark, a
  mono bold tagline (~88 px), e.g. "Trophies over your games.", a two-line
  grey subline (`#9ca9b4`, ~48 px), e.g. "Steam unlocks as toasts over
  fullscreen games. / Bronze to platinum, no API key.", then 2–3 rows of
  feature chips (`#101b22` fill, `#35454d` stroke, gold bullet or a
  JetBrainsMono Nerd Font glyph): Overlay toasts · Rarity tiers ·
  Platinum card · Trophy cabinet · Tracker · Theme colours · No API key.
  Then the install box:
  `$ omarchy plugin add github.com/mateuspim/omatrophy`.
- Right half: the real UI, slightly rotated or in light perspective, with a
  soft shadow. Use the tracker (`tracker.png`) as the large back card and
  the gold toast (`gold.png`) and/or platinum card (`platinum.png`) layered
  in front, so a viewer sees "a trophy toast pops over the list". Crop the
  captures' empty margins with nested `<svg>` viewBoxes or clipPaths; the
  tracker capture has empty space above its title (art placeholder) and the
  toasts sit on a plain background: crop to the card frames. The captures
  are 2× renders: gold.png 2000×520, platinum.png 2000×800,
  tracker.png 2000×1800, now.png 920×1800.
- Font: JetBrainsMono Nerd Font (installed; the captures use the same).
- Don't invent UI: no fake screenshots, no generated pictures of the
  plugin. The only UI pixels are the captures. Decoration (glows, rays,
  pixel sparkles built on the trophy's own grid) is fine.
- No home paths, real names, account ids or real game titles anywhere.

## Check before you finish

Render with `rsvg-convert` and look at the PNG. Text must not collide with
the UI cards; chips must fit; nothing clipped at the canvas edges; the
toast must read at README width (~900 px wide). Iterate until it looks as
finished as the siblings.
