# Omarchy trophy family

TASK.md's pixel-blackletter direction replaces the parent brief's Taste
direction for this set. All deliverables are in this folder.

## Drawing

One shared trophy silhouette on a 4-unit grid: rectangular handle counters,
a stair-stepped bowl, a straight stem and a two-step foot. Every edge is
horizontal or vertical, including closing edges. There are no curves,
diagonals, gradients, glints or outlines baked into the metal.

Three flat material colours carry the upper-left lighting: a lit left
face, a shaded right face, and one highlight colour for the rim and foot.
The deliberately broad planes survive at 30 px. The broken rim inlay and
square plate bring in the Omarchy mark's interrupted-line language without
reproducing the mark itself.

| Tier | Lit | Shaded | Highlight |
| --- | --- | --- | --- |
| Bronze | `#c18b60` | `#805338` | `#e5b88b` |
| Silver | `#adb9c2` | `#647480` | `#d2dbe0` |
| Gold | `#e9bd55` | `#a5752d` | `#ffe297` |
| Platinum | `#d5e2f2` | `#828dbb` | `#ffffff` |

Platinum has a white rim with two extra internal steps, a pale blue-white
face and a blue-violet shadow. Its outline and size are identical to the
other tiers. Its first pale-face colour was darkened slightly after the
bright-background review, improving edge separation while preserving the
contrast with silver. Near-white highlights naturally have less contrast
against the light sheet background; the darker face carries the silhouette.

## Layers and placement

- `trophy-bronze.svg`, `trophy-silver.svg`, `trophy-gold.svg` and
  `trophy-platinum.svg` contain only the material body and plate recess.
- `trophy-accent.svg` contains the broken rim inlay and square plate border,
  in pure `#ffffff` with transparency. Tint this layer at runtime and place
  it over the tier at the same size and origin. No accent colour is baked
  into a tier file.
- The blank plate is at `(52, 40)` with size `24 × 24`; its open centre is
  `(56, 44)` with size `16 × 16`, centred at `(64, 52)`. Place the app's
  engraving inside that opening. No glyph is included.
- `trophy-frame.svg` is an original white square frame with an 8-unit rail,
  stepped terminals and two breaks, on the left and lower edges. Tint it
  independently and overlay at the same origin for framed platinum.

All six canvases are `128 × 128`, with viewBox `0 0 128 128`. Trophy bounds
are `(16, 20)` through `(112, 112)`. The shared inset leaves at least four
units of transparent clearance from the optional frame. Do not independently
trim or auto-fit the layers: their alignment depends on retaining the canvas.

## Rebuild and review

Run `python generate.py` from this folder, or pass its absolute path from
anywhere. It uses Python's standard library and `rsvg-convert` from librsvg.
Geometry, colours, layers and the contact sheet are defined in that one
script. It overwrites the six SVGs and `contact-sheet.png`.

The [contact sheet](contact-sheet.png) shows the four tiers plus framed
platinum, each at actual 256, 30 and 76 px, in all four combinations of
`#a7c080` / `#7fbbb3` accent and `#2d353b` / `#f2f0e9` background. View the
PNG at 100% to judge the small sizes.

The rendered sheet and a separate Qt render were visually inspected.
Validation confirmed only filled paths, grid-aligned orthogonal geometry,
and white-only overlay files. Qt 6.12's QSvgRenderer successfully rendered
all six files at 30, 76, 128 and 256 px; the four tiers' alpha masks matched
exactly at each size. At the native 128-unit size, the accent was entirely
inside the body and no frame pixel overlapped the trophy. SVG content uses
only basic paths and solid fills compatible with the requested SVG Tiny
subset. The live app integration was not changed or exercised.
