# 23. Draw the platinum image in a throwaway offscreen Quickshell

- Status: Accepted
- Date: 2026-11-14

## Context

The owner wanted a finished game's platinum saved as an image to share,
from the tracker and the platinum shelf, uploading nothing. The image
should be the platinum card the owner already saw, not a second design
that drifts from it.

Quickshell's `grabToImage` renders an item to a PNG, but only an item in
a window that is drawing. In the live shell that means a visible card:
the toast window is a click-through layer over the game, and the panel
and tracker would have to host a hidden card and keep it rendering.

`dev/render.sh` already drew every card offscreen in a throwaway
Quickshell instance, but on the offscreen platform Qt picks its software
renderer, which drops every `MultiEffect`: the card's stepped mask (and
with it the hero art), its shadow, the trophy frame and the omarchy set's
inlay. Forcing the RHI backend to OpenGL there (`QT_QUICK_BACKEND=rhi`,
`QSG_RHI_BACKEND=opengl`) gets the GPU and every effect; Vulkan fails on
that platform.

## Decision

- `omatrophy.py share <store> <game>` builds the platinum event (the one
  the toast gets, plus the platinum date, the store's name and the
  `icons` setting) and hands it to `share.py`.
- `share.py` writes a temporary Quickshell config (`shell.qml`, the event
  as a JSON file, links to Omarchy's `Commons` and `Ui`), runs
  `quickshell -p` on it offscreen on OpenGL, and the scene grabs
  `PlatinumShare.qml` at 2400 x 1260 and quits. The PNG moves to
  `<XDG_PICTURES_DIR>/omatrophy/<game>-platinum.png`.
- `PlatinumShare.qml` loads `PlatinumCard.qml` with `still: true`, which
  jumps to the end of the card's timeline (open, written, counted, lit),
  over the game's art blurred into the theme, with a footer.
- Art goes in only as local files: `omatrophy.py` first fetches store
  art missing from the cache, once, as the platinum toast does (owner's
  call, 2026-11-14), and a URL still left is dropped, so the throwaway
  shell never fetches and nothing is uploaded.
- The panel and tracker run the command (`--notify`) and show a tick or
  the error; they draw nothing themselves.

## Consequences

- The live shell is untouched: no restart, no hidden window, and a save
  can't upset a running game (ADR 8).
- The image and the toast share one card, so a card change shows in both.
- A save starts a second Quickshell for about a second and needs a GPU
  OpenGL context; without one Qt falls back to software and the image
  loses its art and masks (unverified on machines other than the owner's).
- The event goes into the scene 300 ms after it starts: the card's border
  is a `Shape`, which kept the colour it was first drawn in until its path
  changed, so a card built before the theme loaded kept the default grey.
- The image follows the current theme (Commons.Color reads it from
  `$HOME`); `dev/render.sh --theme` gives the throwaway shell a home of its
  own to draw under another.
