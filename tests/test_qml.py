"""Static checks on the views FreshObject builds from their text (ADR 10).
The live shell refuses a whole file for these, and nothing else in CI
compiles QML: on 2026-11-04 a bad edit doubled a block of TrackerView.qml
and the tracker stopped opening, while offscreen renders still drew it."""
import os, re, unittest

HERE = os.path.join(os.path.dirname(__file__), '..')
VIEWS = ('TrackerView.qml', 'StylePicker.qml', 'TrophyToast.qml', 'PlatinumCard.qml')


def text(name):
    with open(os.path.join(HERE, name), encoding='utf-8') as f:
        return f.read()


class Views(unittest.TestCase):
    def test_inline_component_names_are_unique(self):
        for name in VIEWS:
            found = re.findall(r'^\s*component (\w+)\s*:', text(name), re.M)
            dupes = sorted({c for c in found if found.count(c) > 1})
            self.assertEqual(dupes, [], f'{name}: inline components declared twice: {dupes}')

    def test_the_root_sets_each_handler_once(self):
        for name in VIEWS:
            # Two spaces in: a property or handler of the file's root object.
            found = re.findall(r'^  (Component\.onCompleted|on[A-Z]\w*)\s*:', text(name), re.M)
            dupes = sorted({h for h in found if found.count(h) > 1})
            self.assertEqual(dupes, [], f'{name}: the root sets these twice: {dupes}')


if __name__ == '__main__':
    unittest.main()
