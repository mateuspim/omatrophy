# OmaTrophy brand assets

The mark is a pixel trophy cup on a dark tile, drawn on the same stepped
grid as the Omarchy trophy set ([`icon.svg`](../icon.svg)): every edge is
horizontal or vertical, so it stays crisp at 32 px. The wordmark sets "Oma"
in light grey and "Trophy" in trophy gold, like the other Oma plugins.

## Colours

| Role | Colour |
| --- | --- |
| Accent: "Trophy", chip bullets, `$` | `#e9bd55` |
| Mark shading (deep, light, highlight) | `#a5752d`, `#ffe297`, `#fff4bf` |
| Mark tile, feature chips | `#101b22` |
| Wordmark "Oma", tagline | `#eff4f7` (`#101b22` in `logo-light.svg`) |
| Subline | `#9ca9b4` |
| Background | `#0b1015` → `#0a111b` → `#102236`, gold glow `#a5752d` bottom-left, blue glow `#1d3a5c` top-right, 56 px dot grid `#7a8f9d` |
| Chip and install-box stroke | `#35454d` |

Type is JetBrains Mono (JetBrainsMono Nerd Font), the same face the
captures use. The logos keep live text, so render them where it is
installed.

## Assets

| Asset | Use |
| --- | --- |
| [`icon.svg`](../icon.svg) | the mark: README title, marketplace |
| [`brand/logo.svg`](brand/logo.svg) | mark + wordmark on dark surfaces |
| [`brand/logo-light.svg`](brand/logo-light.svg) | mark + wordmark on light surfaces |
| [`brand/preview.svg`](brand/preview.svg) | README hero source, renders [`preview.png`](../preview.png) |
| `brand/captures/*.png` | 2× offscreen renders from `dev/samples/` |

## Rules

- UI pixels in the hero come only from `dev/render.sh` captures of the
  fake sample games: no desktop screenshots, no real game titles or
  account data, no generated pictures of the UI.
- The hero follows the house layout shared with OmaDroid and OmaReach:
  left column at x = 208 (mark, wordmark, tagline, subline, chips, install
  box), tilted UI cards on the right. Layout coordinates are in
  `design/hero/NOTES.md`.
- Refresh it with the steps in the
  [development runbook](runbooks/development.md#refresh-the-preview).
