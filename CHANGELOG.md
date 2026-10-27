# Changelog

## Unreleased

- First version: Steam achievement unlocks as toasts on the Overlay layer,
  over fullscreen games, with no API key and private profiles supported.
  Rarity picks the metal (bronze, silver, gold at 10% of players or fewer);
  100% of a game plays the platinum card over the game's hero art.
- Bar button with a style picker: three trophy art sets (Omarchy pixel grid
  with a theme-tinted inlay, faceted vector, painted), previews of every
  tier, position (top centre, left or right) and sound.
- A chime per tier, synthesised for OmaTrophy (`tools/sounds.py`, from
  the brief in `design/sounds/`), with the
  freedesktop sounds kept as the classic set.
- Stores are pluggable (`stores/`); Steam is the first.
- `omatrophy.py` CLI: `watch`, `test`, `status`, `set`.
