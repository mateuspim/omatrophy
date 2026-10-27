# OmaTrophy vector trophies

Four original, hand-authored SVG trophies share one geometric cup: open
chamfered handles, a broad faceted bowl, a short flared stem, and a stepped
base. The angular outline complements the app's thin borders and monospace
type. Upper-left highlights and deeper right facets give the metal volume
without adding effects outside the silhouette.

- **Bronze:** warm copper-brown with restrained peach highlights.
- **Silver:** cool blue-gray metal, deliberately darker than platinum.
- **Gold:** rich yellow-gold with ochre shadows and pale polished highlights.
- **Platinum:** a broad cool-white face, pale cyan reflections, and faint
  lavender shaded facets. Its higher brightness separates it from silver.

The blank recessed shield is 19 units wide, about 29% of the 66-unit bowl.
Its center is approximately `(64, 49)` in the 128-unit viewBox; a runtime
glyph can fit inside `x=58..70, y=43..55`. There are no drawn symbols.

Every SVG has a transparent background and `viewBox="0 0 128 128"`.
The painted bounds are 10–118 in both axes, giving 7.8% padding per side.
The files contain only paths, linear gradients, and their definitions;
there are no fonts, strokes, masks, filters, embedded images, or external
references. The font used to label the contact sheet is not in the SVGs.

## Generation and review

`generate.py` holds the single shared path definition and four material
palettes. Run `python generate.py` here to regenerate all four SVGs and
[contact-sheet.png](contact-sheet.png). It requires Python 3, `rsvg-convert`,
ImageMagick (`magick`), and Fontconfig (`fc-match`). Temporary renders stay
inside this folder and are removed automatically.

The contact sheet shows all tiers at actual 256, 76, and 30 px canvas sizes,
on dark `#2d353b` and light `#f2f0ea` backgrounds. It was rendered and visually
inspected: the handles remain open at 30 px, the materials remain distinct,
and the shield reads as an empty inset at larger sizes. At 30 px the shield
is intentionally only a small tonal detail.

Validation confirmed identical path attributes across all tiers, an allowed
SVG element set, identical rendered alpha channels, and the expected padding.
Rendering was checked with librsvg; direct Qt SVG rendering was not tested.
The SVG feature set is intentionally limited for Qt SVG Tiny 1.2 support.
