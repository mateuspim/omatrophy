"""On a light theme the metal colours turn to darker inks in the panel
and the tracker: pale silver and platinum text, bars and rails vanished
on flexoki-light and white. Reads the two views' palettes from their text;
no Qt needed."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CREAM = (0xff, 0xfc, 0xf0)  # flexoki-light's background


def luminance(rgb):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def palettes(name):
    text = (ROOT / name).read_text()
    found = re.search(r'metalColors: lightTheme \? \(\{(.*?)\}\)\s*: \(\{(.*?)\}\)', text, re.S)
    assert found, f'{name}: metalColors is not chosen by lightTheme'
    def parse(body):
        return {k: tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
                for k, v in re.findall(r'(\w+): "#([0-9a-f]{6})"', body)}
    return parse(found[1]), parse(found[2])


class LightMetals(unittest.TestCase):
    def test_both_views_share_the_same_inks(self):
        self.assertEqual(palettes('StylePicker.qml'), palettes('TrackerView.qml'))

    def test_every_ink_reads_on_a_light_card(self):
        light, dark = palettes('TrackerView.qml')
        self.assertEqual(set(light), {'bronze', 'silver', 'gold', 'platinum'})
        self.assertEqual(set(light), set(dark))
        for metal, ink in light.items():
            # WCAG's 4.5:1 for small text, which the share of players is.
            self.assertGreaterEqual(contrast(ink, CREAM), 4.5, metal)
            # The pale metals are what failed: they stay under 1.5:1.
        self.assertLess(contrast(dark['silver'], CREAM), 1.5)


if __name__ == '__main__':
    unittest.main()
