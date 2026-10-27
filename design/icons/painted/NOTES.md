# Painted trophy set

Created four original faceted metal cups with angular open handles, a stepped base, upper-left lighting, and a small blank recessed shield for runtime engraving. Broad bright and dark metal planes preserve the cup shape at small sizes.

- `trophy-bronze.png`: warm copper-brown bronze.
- `trophy-silver.png`: restrained cool neutral silver.
- `trophy-gold.png`: rich yellow gold with amber shadows.
- `trophy-platinum.png`: bright white platinum with cyan and violet reflections.

All four are 1024×1024, 8-bit RGBA PNGs. The trophy occupies x=82–941 and y=107–915: 8% horizontal padding and slightly more vertical padding to preserve proportions. The shield remains empty; no glyph, text, glow, particles, cast shadow, or backdrop is baked in.

Platinum was generated and refined first; each other tier was generated as a material edit of that master using the built-in image generation tool. ImageMagick removed edge specks, smoothed the alpha, aligned the canvases, and applied one shared platinum alpha mask to all tiers. A small color bleed under the variant masks prevents dark edge contamination. No CLI/API fallback was used. Exact prompts: [PROMPTS.md](PROMPTS.md).

Visually inspected [contact-sheet.png](contact-sheet.png): 256, 76, and 30 px on dark `#2d353b` and bright `#f4f1e9`. Also inspected the 30 px renders enlarged with nearest-neighbor scaling. Handles remain open, the stepped base remains legible, and no background fringe is visible at 30 px. Platinum retains cool colored reflections while silver stays neutral; the engraving plate detail naturally simplifies at 30 px.

Validation: all four alpha channels match byte-for-byte, have fully transparent exterior and handle openings, and an opaque trophy interior with antialiased boundaries. Shared alpha SHA-256: `59b6be77756b46966c4fbcf91286265681a5f73e2bb80cd8a7c528e4feba85de`.

