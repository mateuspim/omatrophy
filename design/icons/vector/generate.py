#!/usr/bin/env python3
"""Hand-authored trophy geometry; material palettes are the only tier variation.

Run `python generate.py` to write the SVGs and the review contact sheet.
Rendering requires rsvg-convert and ImageMagick. No Python packages required.
"""

from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent

# Deep edge, shade, midtone, light, polished highlight, reflected light.
MATERIALS = {
    "bronze": ("#492a1c", "#79452b", "#b67448", "#e6ac77", "#ffe0af", "#cb8e63"),
    "silver": ("#303e4b", "#586977", "#8e9fab", "#c3d0d7", "#edf5f7", "#a8bac7"),
    "gold": ("#53400d", "#8b6517", "#c79727", "#f0cc62", "#fff0b1", "#ddb94c"),
    "platinum": ("#464d72", "#7d87ac", "#c2cce4", "#ecf9ff", "#ffffff", "#c3f2ef"),
}

# All contours are shared. Each exported file is self-contained, with no <use>,
# clipping, strokes, filters, masks, raster data, text, or external dependencies.
GEOMETRY = '''
  <!-- Open angular handles, behind the bowl. -->
  <path fill="url(#handles)" fill-rule="evenodd" d="M33 25H20L10 35V49L20 64L42 72L44 63L27 56L19 45V38L23 34H34Z M95 25H108L118 35V49L108 64L86 72L84 63L101 56L109 45V38L105 34H94Z"/>
  <path fill="url(#edge)" d="M20 25H33V27H21L12 36V48L22 62L40 69L42 72L20 64L10 49V35Z M95 25H108L118 35L115 35L107 28H95Z"/>
  <path fill="url(#shadow)" d="M94 34H105L109 38V45L101 56L86 62L87 65L103 58L112 46V37L106 31H95Z"/>
  <!-- Short flared stem and two solid, chamfered base steps. -->
  <path fill="url(#metal)" d="M58 76H70L72 90L79 99H49L56 90Z"/>
  <path fill="url(#edge)" d="M58 78H62L61 90L56 96H51L56 90Z"/>
  <path fill="url(#bevel)" d="M46 98H82L88 107H40Z"/>
  <path fill="url(#metal)" d="M40 107H88V111H40Z"/>
  <path fill="url(#bevel)" d="M35 108H93L100 114H28Z"/>
  <path fill="url(#metal)" d="M28 114H100V116L98 118H30L28 116Z"/>
  <path fill="url(#edge)" d="M35 108H93L95 110H33Z M29 114H99V115H29Z"/>
  <!-- Broad face with two restrained side facets. -->
  <path fill="url(#metal)" d="M31 21H97L93 53Q92 63 83 70L71 79Q64 84 57 79L45 70Q36 63 35 53Z"/>
  <path fill="url(#leftFacet)" d="M31 21H41L44 51Q45 62 51 69L60 81L57 79L45 70Q36 63 35 53Z"/>
  <path fill="url(#rightFacet)" d="M87 21H97L93 53Q92 63 83 70L71 79L68 81L77 69Q83 62 84 51Z"/>
  <path fill="url(#edge)" d="M32 23H34L38 53Q39 62 47 69L57 77L45 70Q36 63 35 53Z"/>
  <!-- Recessed blank shield: 19 / 66 = 29% of the bowl width.
       Safe runtime engraving area: x=58..70, y=43..55. -->
  <path fill="url(#recessRim)" d="M54.5 40Q64 38 73.5 40V50.5Q73.5 57 64 61Q54.5 57 54.5 50.5Z"/>
  <path fill="url(#plate)" d="M55.5 41Q64 39.3 72.5 41V50.5Q72.5 56.3 64 59.8Q55.5 56.3 55.5 50.5Z"/>
  <!-- Low, crisp lip and a narrow underside give the cup real thickness. -->
  <path fill="url(#shadow)" d="M31 21H97L96.5 25H31.5Z"/>
  <path fill="url(#metal)" d="M28 10H100L103 13V20L100 23H28L25 20V13Z"/>
  <path fill="url(#bevel)" d="M28 10H100L103 13H25Z"/>
  <path fill="url(#edge)" d="M28 10H100L101 11H27Z"/>
  <path fill="url(#shadow)" d="M25 20H103L100 23H28Z"/>
'''


def gradient(name, coords, stops):
    content = "".join(f'<stop offset="{offset}" stop-color="{color}"/>' for offset, color in stops)
    return f'    <linearGradient id="{name}" gradientUnits="userSpaceOnUse" {coords}>{content}</linearGradient>'


def svg(tier, palette):
    deep, shade, mid, light, white, reflection = palette
    # Platinum's broad white face and lavender edge are deliberate; silver
    # retains a lower-value blue-gray face. Both use identical contours/stops.
    gradients = [
        gradient("metal", 'x1="28" y1="28" x2="100" y2="45"', [(0, shade), (.17, light), (.29, white), (.43, light), (.70, mid), (.91, shade), (1, deep)]),
        gradient("handles", 'x1="10" y1="26" x2="118" y2="62"', [(0, shade), (.10, light), (.22, mid), (.45, deep), (.68, shade), (.89, reflection), (1, deep)]),
        gradient("edge", 'x1="20" y1="10" x2="105" y2="110"', [(0, white), (.40, light), (1, mid)]),
        gradient("shadow", 'x1="30" y1="20" x2="98" y2="30"', [(0, mid), (.48, shade), (1, deep)]),
        gradient("leftFacet", 'x1="33" y1="28" x2="59" y2="77"', [(0, white), (.38, light), (1, mid)]),
        gradient("rightFacet", 'x1="84" y1="24" x2="91" y2="74"', [(0, mid), (.45, shade), (1, deep)]),
        gradient("bevel", 'x1="32" y1="0" x2="97" y2="13"', [(0, light), (.27, white), (.60, reflection), (1, shade)]),
        gradient("recessRim", 'x1="58" y1="40" x2="69" y2="61"', [(0, shade), (.45, mid), (.75, light), (1, white)]),
        gradient("plate", 'x1="55" y1="40" x2="73" y2="60"', [(0, mid), (.47, light), (1, reflection)]),
    ]
    return '\n'.join(['<?xml version="1.0" encoding="UTF-8"?>',
                      '<svg xmlns="http://www.w3.org/2000/svg" version="1.2" baseProfile="tiny" width="128" height="128" viewBox="0 0 128 128">',
                      f'  <!-- OmaTrophy / {tier}. Generated from shared hand-authored paths. -->',
                      '  <defs>', *gradients, '  </defs>', GEOMETRY, '</svg>', ''])


def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)


def contact_sheet():
    font = subprocess.check_output(["fc-match", "-f", "%{file}", "monospace"], text=True)
    # Intermediate files stay inside this folder and are removed after use.
    with tempfile.TemporaryDirectory(prefix=".render-", dir=ROOT) as temp:
        temp = Path(temp)
        sections = []
        for theme, bg, fg in [("DARK", "#2d353b", "#e1e6e8"), ("LIGHT", "#f2f0ea", "#303d46")]:
            cells = []
            for tier in MATERIALS:
                parts = []
                for size, height in [(256, 276), (76, 108), (30, 64)]:
                    icon = temp / f"{tier}-{size}.png"
                    run("rsvg-convert", "-w", size, "-h", size, "-o", icon, ROOT / f"trophy-{tier}.svg")
                    part = temp / f"{theme}-{tier}-{size}.png"
                    run("magick", icon, "-background", bg, "-alpha", "remove", "-gravity", "center", "-extent", f"290x{height}", part)
                    parts.append(part)
                label = temp / f"{theme}-{tier}-label.png"
                run("magick", "-size", "290x42", f"xc:{bg}", "-fill", fg, "-font", font, "-pointsize", "17", "-gravity", "center", "-annotate", "+0+0", tier.upper(), label)
                cell = temp / f"{theme}-{tier}.png"
                run("magick", label, *parts, "-append", cell)
                cells.append(cell)
            row = temp / f"{theme}-row.png"
            run("magick", *cells, "+append", row)
            heading = temp / f"{theme}-heading.png"
            run("magick", "-size", "1160x52", f"xc:{bg}", "-fill", fg, "-font", font, "-pointsize", "16", "-gravity", "west", "-annotate", "+22+0", f"OMATROPHY  /  {theme}     |     256 px  /  76 px  /  30 px (top to bottom)", heading)
            sections.extend([heading, row])
        run("magick", *sections, "-append", ROOT / "contact-sheet.png")


def validate():
    ns = "{http://www.w3.org/2000/svg}"
    contours = []
    allowed = {"svg", "defs", "linearGradient", "stop", "path"}
    for tier in MATERIALS:
        root = ET.parse(ROOT / f"trophy-{tier}.svg").getroot()
        assert root.attrib["viewBox"] == "0 0 128 128"
        assert all(el.tag.removeprefix(ns) in allowed for el in root.iter())
        contours.append([el.attrib for el in root.findall(ns + "path")])
    assert all(paths == contours[0] for paths in contours)
    print(f"Validated {len(MATERIALS)} SVGs: identical {len(contours[0])}-path geometry; only basic SVG elements.")


if __name__ == "__main__":
    for tier, palette in MATERIALS.items():
        (ROOT / f"trophy-{tier}.svg").write_text(svg(tier, palette))
    validate()
    contact_sheet()
    print(ROOT / "contact-sheet.png")
