# OmaTrophy hero and wordmark

The composition follows the sibling hero's dark dotted field, left-aligned message, outlined chips, command box and overlapping tilted captures. The gold toast is enlarged over the tracker to make the unlock immediately recognizable at README width. Both captures use the supplied fictional sample; no UI was fabricated.

## Palette and type

- Background diagonal: `#0b1015` → `#0a111b` → `#102236`; a bottom-left `#a5752d` glow and top-right `#1d3a5c` glow add depth. The 56 px grid uses `#7a8f9d` at 0.13 opacity.
- Trophy accent: `#e9bd55`, with `#a5752d`, `#ffe297` and `#fff4bf` in the supplied mark. The dark icon tile is `#101b22`.
- Main text: `#eff4f7`; secondary text: `#9ca9b4`. Chips use `#101b22` and `#35454d`; the command box uses `#0e151b` and `#35454d`.
- JetBrains Mono / JetBrainsMono Nerd Font, with DejaVu Sans Mono and monospace fallbacks. The lockups retain live text like the sibling logos, so installed fonts affect their rendering. The light logo changes “Oma” to `#101b22` while retaining the gold trophy and wordmark accent.

## Layout (3840 × 2160)

- Left column starts at x=208. The 232 px mark starts at (208, 408); the 205 px wordmark starts at x=495, baseline y=602. The bold 82 px tagline has baseline y=805; the 48 px subline has baselines y=943 and 1021.
- Three rows of 100 px-high chips start at y=1112, 1234 and 1356. The install box is (208, 1534), 1660 × 148 px.
- The tracker starts at (2110, 355), rotated 2 degrees. Its source viewBox is `240 240 1520 1480`, removing the empty art placeholder above the title; the thin framing and shadow separate it from the background.
- The gold toast starts at (2040, 1170), rotated −2 degrees, and is enlarged to 1520 × 415 px. Its source viewBox is `520 80 960 262`, cropping the plain outer margin to the toast frame. Shadows are decorative; all UI pixels are from the captures.
- Logos use a 1500 × 256 viewBox, with the supplied 128 px icon scaled to 232 px and a 205 px wordmark. Their transparent backgrounds suit placement on either surface.

Render from this folder with `rsvg-convert -o preview.png preview.svg`. Capture references are relative to `captures/`, so the same structure works when moved together to `docs/brand/`. Checked the 3840 × 2160 render and a 900 px-wide render for spacing, canvas edges and toast readability.
