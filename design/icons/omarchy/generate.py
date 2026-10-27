#!/usr/bin/env python3
"""Generate the six path-only SVG assets and their raster review sheet.

Python standard library + rsvg-convert (librsvg) are the only dependencies.
Run from any directory: python /path/to/generate.py
"""

from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
NS = "http://www.w3.org/2000/svg"

# Every vertex is on the same 4-unit grid. Rectangular handle counters are
# negative space, not background-coloured paint.
LEFT_HANDLE = "M32 28H16V52H20V60H28V68H40V56H28V48H24V36H32Z"
RIGHT_HANDLE = "M96 28H112V52H108V60H100V68H88V56H100V48H104V36H96Z"
BOWL = "M32 20H96V60H88V72H80V80H72V84H56V80H48V72H40V60H32Z"
BOWL_SHADE = "M64 20H96V60H88V72H80V80H72V84H64Z"
STEM_BASE = "M56 76H72V100H84V104H92V112H36V104H44V100H56Z"
STEM_BASE_SHADE = "M64 76H72V100H84V104H92V112H64Z"
RIM_LIGHT = "M32 20H96V28H40V56H32Z"
# Platinum's extra steps are INSIDE the shared silhouette.
PLATINUM_RIM = "M32 20H96V28H88V32H80V28H48V32H40V56H32Z"
BASE_LIGHT = "M44 100H64V104H44Z"
PLATE_RECESS = "M52 40H76V64H52Z"

ACCENT = [
    "M40 28H64V32H40Z",
    "M72 28H88V36H84V32H72Z",
    # Empty 16 x 16 centre; no glyph is baked into the engraving plate.
    "M52 40H76V64H52Z M56 44V60H72V44Z",
]
# Two 8-unit breaks: left edge and lower edge. Each terminal drops from
# 8 units to 4 units. This is an original single-frame construction.
FRAME = [
    "M4 4H124V124H96V120H92V116H116V12H12V44H8V48H4Z",
    "M4 56H8V60H12V116H80V120H84V124H4Z",
]

PALETTES = {
    "bronze": ("#c18b60", "#805338", "#e5b88b"),
    "silver": ("#adb9c2", "#647480", "#d2dbe0"),
    "gold": ("#e9bd55", "#a5752d", "#ffe297"),
    "platinum": ("#d5e2f2", "#828dbb", "#ffffff"),
}


def path(d, fill):
    return f'<path fill="{fill}" fill-rule="evenodd" d="{d}"/>'


def body(tier):
    lit, shade, highlight = PALETTES[tier]
    return "\n".join([
        path(LEFT_HANDLE, lit), path(RIGHT_HANDLE, shade),
        path(STEM_BASE, lit), path(STEM_BASE_SHADE, shade),
        path(BASE_LIGHT, highlight), path(BOWL, lit),
        path(BOWL_SHADE, shade),
        path(PLATINUM_RIM if tier == "platinum" else RIM_LIGHT, highlight),
        path(PLATE_RECESS, shade),
    ])


def layer(geometry, fill):
    return "\n".join(path(d, fill) for d in geometry)


def svg(content):
    return (f'<svg xmlns="{NS}" width="128" height="128" '
            f'viewBox="0 0 128 128">\n{content}\n</svg>\n')


def validate(filename):
    """Check renderer constraints, orthogonal edges, and the shared grid."""
    root = ET.parse(filename).getroot()
    assert root.attrib["viewBox"] == "0 0 128 128"
    for child in root:
        assert child.tag == f"{{{NS}}}path"
        assert set(child.attrib) == {"fill", "fill-rule", "d"}
        d = child.attrib["d"]
        assert set(re.findall(r"[A-Za-z]", d)) <= set("MHVZ")
        assert all(int(n) % 4 == 0 for n in re.findall(r"\d+", d))
        if filename.stem in {"trophy-accent", "trophy-frame"}:
            assert child.attrib["fill"] == "#ffffff"
        # Check the implicit closing edge too; no diagonal may hide in Z.
        x = y = 0
        start = None
        tokens = re.findall(r"[MHVZ]|\d+", d)
        i = 0
        while i < len(tokens):
            command = tokens[i]
            i += 1
            if command == "M":
                x, y = map(int, tokens[i:i + 2])
                start = (x, y)
                i += 2
            elif command == "H":
                x = int(tokens[i])
                i += 1
            elif command == "V":
                y = int(tokens[i])
                i += 1
            else:
                assert x == start[0] or y == start[1]
                x, y = start
            assert 0 <= x <= 128 and 0 <= y <= 128


def contact_sheet():
    # Render the complete sheet in one pass. Every icon has an explicit
    # 30/76/256-pixel viewport; no enlarged raster is downsampled into place.
    width, height = 1536, 2040
    parts = [f'<svg xmlns="{NS}" width="{width}" height="{height}">',
             '<rect width="1536" height="2040" fill="#20272c"/>']

    def label(x, y, text, fill, size=14):
        parts.append(f'<text x="{x}" y="{y}" fill="{fill}" '
                     f'font-family="monospace" font-size="{size}">{text}</text>')

    label(28, 32, "OMATROPHY / OMARCHY GRID", "#e9ede7", 22)
    label(28, 55, "4-unit geometry / flat metal / shared tintable inlay / actual pixel sizes", "#aab5b4", 14)
    columns = ["bronze", "silver", "gold", "platinum", "platinum + frame"]
    panels = [("#2d353b", "#a7c080"), ("#2d353b", "#7fbbb3"),
              ("#f2f0e9", "#a7c080"), ("#f2f0e9", "#7fbbb3")]
    for p, (background, accent) in enumerate(panels):
        top = 72 + p * 492
        ink = "#cbd3cf" if p < 2 else "#374247"
        parts.append(f'<rect x="0" y="{top}" width="1536" height="492" fill="{background}"/>')
        label(28, top + 26, f"BACKGROUND {background}   /   ACCENT {accent}", ink)
        for j, name in enumerate(columns):
            cx = 220 + j * 284
            tier = "platinum" if j == 4 else name
            label(cx - 128, top + 55, name.upper(), ink)
            for size, y in [(256, top + 68), (30, top + 348), (76, top + 398)]:
                x = cx - size / 2
                parts.append(f'<svg x="{x}" y="{y}" width="{size}" height="{size}" viewBox="0 0 128 128">')
                if j == 4:
                    parts.append(layer(FRAME, accent))
                parts.extend([body(tier), layer(ACCENT, accent), '</svg>'])
        for text, y in [("256px", top + 194), ("30px", top + 368), ("76px", top + 442)]:
            label(16, y, text, ink, 12)
    parts.append('</svg>')
    with tempfile.TemporaryDirectory(prefix="omatrophy-") as tmp:
        source = Path(tmp) / "sheet.svg"
        source.write_text("\n".join(parts))
        subprocess.run(["rsvg-convert", str(source), "-o", str(ROOT / "contact-sheet.png")], check=True)


def main():
    for tier in PALETTES:
        (ROOT / f"trophy-{tier}.svg").write_text(svg(body(tier)))
    for name, geometry in [("accent", ACCENT), ("frame", FRAME)]:
        (ROOT / f"trophy-{name}.svg").write_text(svg(layer(geometry, "#ffffff")))
    for filename in sorted(ROOT.glob("trophy-*.svg")):
        validate(filename)
    contact_sheet()
    print("Generated and validated 6 SVGs; rendered contact-sheet.png")


if __name__ == "__main__":
    main()
