"""Static checks on the views FreshObject builds from their text (ADR 10).
The live shell refuses a whole file for these, and nothing else in CI
compiles QML: on 2026-11-04 a bad edit doubled a block of TrackerView.qml
and the tracker stopped opening, while offscreen renders still drew it."""
import os, re, unittest

HERE = os.path.join(os.path.dirname(__file__), '..')
VIEWS = ('TrackerView.qml', 'StylePicker.qml', 'TrophyToast.qml', 'PlatinumCard.qml', 'DifficultyCard.qml',
         'MissableCard.qml', 'RecapCard.qml',
         'MilestoneCard.qml', 'PlatinumShare.qml')


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

    def test_no_property_set_twice_in_a_row(self):
        # The live shell refuses the whole file for a property assigned
        # twice in one object; an edit on 2026-11-06 left two `visible:`.
        for name in VIEWS:
            lines = text(name).split('\n')
            for i in range(len(lines) - 1):
                a = re.match(r'^(\s+)([a-z]\w*):\s', lines[i])
                b = re.match(r'^(\s+)([a-z]\w*):\s', lines[i + 1])
                self.assertFalse(a and b and a.groups() == b.groups(),
                                 f'{name}:{i + 2}: {a.group(2) if a else ""} set twice')


def own_blocks(source, opener):
    """(line, own text) of every block opened by the regex `opener` (ending
    in `{`): the text at the block's own depth, without nested objects, so
    a child's property never counts for its parent."""
    for m in re.finditer(opener, source, re.M):
        depth, i, own = 1, m.end(), []
        while depth and i < len(source):
            ch = source[i]
            depth += (ch == '{') - (ch == '}')
            if depth == 1 and ch != '}':
                own.append(ch)
            i += 1
        yield source.count('\n', 0, m.start()) + 1, ''.join(own)


class TextFormats(unittest.TestCase):
    """Game names, achievement text, guide tips and agent prose come from
    stores, web pages and the user's agent. A Text left on AutoText renders
    a string that looks like HTML, and `<img src="http://...">` in it is
    fetched as the view shows: a beacon, or a fake line in the panel."""

    def qml_files(self):
        return sorted(n for n in os.listdir(HERE) if n.endswith('.qml'))

    def test_every_text_sets_its_format(self):
        for name in self.qml_files():
            for line, own in own_blocks(text(name), r'^\s*(?:component\s+\w+\s*:\s*)?Text\s*\{'):
                self.assertIn('textFormat:', own, f'{name}:{line}: a Text without textFormat renders HTML')

    def test_only_prose_is_markdown_and_it_goes_through_safe_markdown(self):
        for name in self.qml_files():
            source = text(name)
            for m in re.finditer(r'textFormat:\s*\w+\.(\w+)', source):
                if m.group(1) in ('PlainText',):
                    continue
                self.assertEqual((name, m.group(1)), ('TrackerView.qml', 'MarkdownText'),
                                 f'{name}: {m.group(1)} outside the guide prose')
        source = text('TrackerView.qml')
        for line, own in own_blocks(source, r'^\s*Prose\s*\{'):
            self.assertRegex(own, r'text:\s*.*root\.safeMarkdown\(', f'TrackerView.qml:{line}: prose not made safe')
        safe = re.search(r'function safeMarkdown\(text\) \{(.*?)\n  \}', source, re.S).group(1)
        self.assertIn('/!+(?=\\[)/g', safe, 'safeMarkdown must drop every ! before a [ (images)')
        self.assertIn('<img', safe)


if __name__ == '__main__':
    unittest.main()
