#!/usr/bin/env python3
"""Draw made-up store art for the fake games in dev/samples/ and point the
samples at it, so dev/render.sh shows the panel the way it looks with real
art. Every picture is generated here (no game's real art may ship in the
repo); rerunning gives the same files.

    python3 dev/sample-art.py
"""
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES = os.path.join(HERE, 'samples')
ART = os.path.join(SAMPLES, 'art')
# Image sources in the samples resolve against the QML files at the repo root.
PREFIX = 'dev/samples/art/'

# Sky top, sky bottom, far land, near land, sun: one mood per game.
PALETTES = [
    ('#0b1026', '#3b2a6b', '#2a1f4f', '#120c26', '#ffb36b'),
    ('#1a0f0a', '#a8461f', '#5c2412', '#24100a', '#ffd38a'),
    ('#06222b', '#1f7a7a', '#0f4a50', '#062429', '#c8fff4'),
    ('#f3e6c8', '#d9b98a', '#a8825a', '#6b4e33', '#fff6e0'),
    ('#140a1f', '#7a1f3d', '#4a1230', '#1c0814', '#ff6b6b'),
    ('#0a0f1a', '#2b4a7a', '#1a2e4f', '#0a1222', '#9fd0ff'),
    ('#0d1a10', '#3f6b3a', '#244a24', '#0e1f0e', '#e8ffb0'),
    ('#1e1a2e', '#8a7ab8', '#4d4470', '#221d33', '#ffffff'),
]
GLYPHS = ['star', 'diamond', 'ring', 'bolt', 'chevron', 'drop']


def seed(text):
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


def slug(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def ridge(width, height, base, rough, n, s):
    """A closed polygon of hills along the bottom of the picture."""
    pts = []
    for i in range(n + 1):
        x = width * i / n
        y = base - rough * (((s >> (i * 3)) & 7) / 7)
        pts.append(f'{x:.0f},{y:.0f}')
    return f'0,{height} ' + ' '.join(pts) + f' {width},{height}'


def scene(name, width, height, title):
    s = seed(name)
    top, bottom, far, near, sun = PALETTES[s % len(PALETTES)]
    sx = width * (0.25 + 0.5 * ((s >> 8) % 100) / 100)
    sr = height * 0.22
    words = ''
    if title:
        size = min(34, int(width * 1.5 / max(len(name), 8)))
        words = (f'<text x="22" y="{height - 26}" font-family="sans-serif" font-weight="800" '
                 f'font-size="{size}" letter-spacing="1" fill="#ffffff" fill-opacity="0.94">'
                 f'{name.upper().replace("&", "&amp;")}</text>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>
    </linearGradient>
    <radialGradient id="glow" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="{sun}" stop-opacity="0.55"/><stop offset="1" stop-color="{sun}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="shade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0.55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity="0.55"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#sky)"/>
  <circle cx="{sx:.0f}" cy="{height * 0.45:.0f}" r="{sr * 3:.0f}" fill="url(#glow)"/>
  <circle cx="{sx:.0f}" cy="{height * 0.45:.0f}" r="{sr:.0f}" fill="{sun}"/>
  <polygon points="{ridge(width, height, height * 0.72, height * 0.3, 9, s)}" fill="{far}"/>
  <polygon points="{ridge(width, height, height * 0.9, height * 0.22, 6, s >> 40)}" fill="{near}"/>
  <rect width="{width}" height="{height}" fill="url(#shade)"/>
  {words}
</svg>
'''


def glyph(kind):
    return {
        'star': '<polygon points="32,12 37,26 52,26 40,35 44,50 32,41 20,50 24,35 12,26 27,26"/>',
        'diamond': '<polygon points="32,10 52,32 32,54 12,32"/>',
        'ring': '<circle cx="32" cy="32" r="16" fill="none" stroke-width="7"/>',
        'bolt': '<polygon points="36,8 16,36 30,36 26,56 48,26 34,26"/>',
        'chevron': '<polygon points="12,22 32,38 52,22 52,34 32,50 12,34"/>',
        'drop': '<path d="M32 10 C44 28 48 34 48 40 A16 16 0 0 1 16 40 C16 34 20 28 32 10 Z"/>',
    }[kind]


def icon(name, locked):
    s = seed(name)
    _, light, mid, dark, sun = PALETTES[s % len(PALETTES)]
    if locked:
        light, dark, sun = '#5a5f6b', '#2a2d34', '#9aa0aa'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{light}"/><stop offset="1" stop-color="{dark}"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" fill="url(#g)"/>
  <g fill="{sun}" stroke="{sun}">{glyph(GLYPHS[(s >> 4) % len(GLYPHS)])}</g>
</svg>
'''


def write(name, text):
    with open(os.path.join(ART, name), 'w') as f:
        f.write(text)
    return PREFIX + name


def header(game):
    return write(f'{slug(game)}-header.svg', scene(game, 460, 215, True))


def hero(game):
    return write(f'{slug(game)}-hero.svg', scene(game, 1920, 620, False))


def ach_icon(name, locked=False):
    return write(f'icon-{slug(name)}{"-locked" if locked else ""}.svg', icon(name, locked))


def fill_game(row):
    """Point one game row (and its achievements) at generated art."""
    if 'game' in row and 'header' in row:
        row['header'] = header(row['game'])
    if 'hero' in row:
        row['hero'] = hero(row['game'])
    for key in ('latest', 'session', 'next'):
        for a in row.get(key) or []:
            a['icon'] = ach_icon(a['name'])
    for a in row.get('achievements') or []:
        a['icon'] = ach_icon(a['name'])
        a['icon_locked'] = ach_icon(a['name'], locked=True)


def fill(sample):
    if isinstance(sample, list):
        for row in sample:
            fill_game(row)
        return
    if 'achievements' in sample:
        fill_game(sample)
        return
    for key in ('playing',):
        if sample.get(key):
            fill_game(sample[key])
    for key in ('recent', 'shelf'):
        for row in sample.get(key) or []:
            fill_game(row)
    for event in sample.values():
        if isinstance(event, dict) and 'type' in event:
            if 'icon' in event:
                event['icon'] = ach_icon(event['name'])
            fill_game(event)


def main():
    os.makedirs(ART, exist_ok=True)
    for name in sorted(os.listdir(SAMPLES)):
        if not name.endswith('.json'):
            continue
        path = os.path.join(SAMPLES, name)
        with open(path) as f:
            sample = json.load(f)
        fill(sample)
        with open(path, 'w') as f:
            json.dump(sample, f, indent=1)
            f.write('\n')


if __name__ == '__main__':
    main()
