# OmaTrophy trophy icons: brief

OmaTrophy shows Steam achievement unlocks as toasts on Omarchy, a Linux
desktop (Arch + Hyprland) with a calm, terminal-native look: flat themed
panels, monospace type, thin accent borders, no gloss on the UI itself. The
trophy is the one place allowed to feel precious, the way a PlayStation
trophy does, while still looking like it belongs on that desktop.

See `../ref/`: `current-trophies.png` is the placeholder set to beat;
`toast-ingame.png` and `platinum-card-ingame.png` show where they appear.

## Deliverables

Four trophies, one per tier, same silhouette, only the material changes:

| file stem | material | used for |
|---|---|---|
| `trophy-bronze` | warm bronze | common unlocks |
| `trophy-silver` | cool silver | uncommon (35% of players or fewer) |
| `trophy-gold` | rich gold | rare (10% or fewer) |
| `trophy-platinum` | platinum: bright cool white metal with a faint cyan-to-violet iridescence, clearly a step above silver | 100% of a game |

## Hard constraints

- Transparent background; nothing but the trophy (no plinth shadow, glow,
  sparkles, frame, or text). The app adds its own light, particles and
  shine, and masks the shine to the trophy's alpha, so the edge must be clean.
- Square canvas, trophy centered, about 8% padding.
- **Engraving plate:** on the cup's face, a smooth, slightly recessed blank
  area (shield, disc, or rounded plate) about 28% of the cup's width. Leave
  it empty: the app engraves a tier glyph there at runtime. Do not draw a
  star, letters or symbols on it.
- Reads at **30 px** (corner medal on a toast) and looks premium at
  **76–160 px** (platinum hero). Favor a bold, simple silhouette over fine
  detail; strong value contrast between lit and shaded metal.
- Light from the upper left, consistent across all four.
- No brand marks, no Steam/PlayStation/Xbox likeness.

## Taste

Distinctive rather than generic clip-art: consider a modern, slightly
geometric cup (faceted bowl, crisp handles, stepped base) that would sit well
next to monospace type. One silhouette for all tiers.

## Process

Render your results yourself and look at them before finishing (e.g.
`magick` for contact sheets at 30, 76 and 256 px over the dark background
`#2d353b` and over a bright one). Iterate until all four read clearly at
30 px and the platinum is unmistakably the top tier. Finish with a short
`NOTES.md`: what you made, the choices behind it, and the contact sheet path.
