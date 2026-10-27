#!/usr/bin/env python3
"""Write assets/trophy-<tier>.svg: one cup drawing, four metals.

Run from the repo root after changing the shape or a palette:
  python3 tools/trophies.py
"""
import os

# Each metal: deep shadow, base, light, highlight, and the star's tone.
METALS = {
    'bronze':   ('#5a2c12', '#a85d2a', '#e39a5f', '#ffd2a6', '#7a3d18'),
    'silver':   ('#4d5661', '#9aa5b1', '#d9e0e7', '#ffffff', '#69737e'),
    'gold':     ('#6b4300', '#c9920f', '#f3cf4a', '#fff4bf', '#8f6100'),
    'platinum': ('#2c3858', '#9cb2de', '#e8efff', '#ffffff', '#6378a8'),
}

CUP = 'M30 20 H98 V36 C98 62 84 80 64 84 C44 80 30 62 30 36 Z'
RIM = 'M26 14 H102 a4 4 0 0 1 4 4 v2 a4 4 0 0 1 -4 4 H26 a4 4 0 0 1 -4 -4 v-2 a4 4 0 0 1 4 -4 Z'
HANDLE_L = 'M32 30 H20 C12 30 10 40 13 48 C17 58 27 64 38 66'
HANDLE_R = 'M96 30 H108 C116 30 118 40 115 48 C111 58 101 64 90 66'
STEM = 'M57 84 H71 L74 98 H54 Z'
KNOT = 'M50 96 H78 a3 3 0 0 1 3 3 v2 a3 3 0 0 1 -3 3 H50 a3 3 0 0 1 -3 -3 v-2 a3 3 0 0 1 3 -3 Z'
BASE = 'M42 104 H86 L90 114 H38 Z'
PLINTH = 'M32 114 H96 a3 3 0 0 1 3 3 v4 a3 3 0 0 1 -3 3 H32 a3 3 0 0 1 -3 -3 v-4 a3 3 0 0 1 3 -3 Z'
# Bowl reflection: a narrow sliver down the left of the cup.
GLARE = 'M40 24 H48 V40 C48 56 54 68 62 76 C50 72 40 58 40 40 Z'


def star(cx, cy, r):
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append(f'{cx + rr * math.cos(a):.2f},{cy + rr * math.sin(a):.2f}')
    return 'M' + ' L'.join(pts) + ' Z'


def svg(tier):
    deep, base, light, hi, engraved = METALS[tier]
    # Platinum shimmers: a cyan-to-violet wash over the whole cup.
    iris = (f'<g fill="url(#iris)"><path d="{CUP}"/><path d="{BASE}"/><path d="{PLINTH}"/><path d="{RIM}"/></g>'
            if tier == 'platinum' else '')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" width="128" height="128">
  <defs>
    <linearGradient id="metal" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{deep}"/>
      <stop offset="0.18" stop-color="{base}"/>
      <stop offset="0.36" stop-color="{hi}"/>
      <stop offset="0.52" stop-color="{light}"/>
      <stop offset="0.78" stop-color="{base}"/>
      <stop offset="1" stop-color="{deep}"/>
    </linearGradient>
    <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.25"/>
      <stop offset="0.5" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="1" stop-color="#000000" stop-opacity="0.25"/>
    </linearGradient>
    <linearGradient id="iris" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#7ff3ff" stop-opacity="0.35"/>
      <stop offset="0.5" stop-color="#ffffff" stop-opacity="0"/>
      <stop offset="1" stop-color="#c49bff" stop-opacity="0.4"/>
    </linearGradient>
    <linearGradient id="glare" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffffff" stop-opacity="0.85"/>
      <stop offset="1" stop-color="#ffffff" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <g fill="none" stroke="url(#metal)" stroke-width="7" stroke-linecap="round">
    <path d="{HANDLE_L}"/>
    <path d="{HANDLE_R}"/>
  </g>
  <g fill="url(#metal)">
    <path d="{STEM}"/>
    <path d="{BASE}"/>
    <path d="{CUP}"/>
    <path d="{KNOT}"/>
    <path d="{PLINTH}"/>
    <path d="{RIM}"/>
  </g>
  <g fill="url(#shade)">
    <path d="{CUP}"/>
    <path d="{BASE}"/>
  </g>
  {iris}
  <path d="{GLARE}" fill="url(#glare)"/>
  <path d="{star(64, 46, 13)}" fill="{engraved}" opacity="0.9"/>
  <path d="{star(64, 45, 11)}" fill="{hi}" opacity="0.55"/>
</svg>
'''


def main():
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'design', 'icons', 'first-draft')
    os.makedirs(out, exist_ok=True)
    for tier in METALS:
        with open(os.path.join(out, f'trophy-{tier}.svg'), 'w') as f:
            f.write(svg(tier))
        print(f'assets/trophy-{tier}.svg')


if __name__ == '__main__':
    main()
