import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import difficulty


class SettingTest(unittest.TestCase):
    def check(self, cases):
        for desc, want in cases:
            with self.subTest(desc=desc):
                self.assertEqual(difficulty.setting('An achievement', desc), want)

    def test_names_the_setting_an_achievement_needs(self):
        self.check([
            ('Finish the game on Nightmare difficulty.', 'Nightmare'),
            ('Complete the game on Hard.', 'Hard'),
            ('Beat the game on Hard or higher', 'Hard'),
            ('Beat the game on Very Hard without dying', 'Very Hard'),
            ('Complete the game on Legendary', 'Legendary'),
            ('Complete the game in Hardcore mode', 'Hardcore'),
            ('On Death March difficulty, beat the game', 'Death March'),
            ('Clear every chapter with the difficulty set to Expert', 'Expert'),
            ('Clear every chapter at difficulty level Expert', 'Expert'),
            ('Finish on the highest difficulty', 'Highest'),
            ('Complete the campaign on all difficulties', 'Every'),
        ])

    def test_reads_the_name_too(self):
        self.assertEqual(difficulty.setting('Insane difficulty', 'Beat the final boss'), 'Insane')

    def test_leaves_text_that_only_sounds_hard(self):
        self.check([
            ('A hard-fought battle', None),
            ('Win in normal combat', None),
            ('Kill 10 enemies on Easy Street.', None),
            ('Win in Photo mode', None),
            ('Play in Story mode', None),
            ('Raise the difficulty', None),
            ('Beat the game on the same difficulty', None),
            ('Increase the Difficulty in Settings', None),
            ('', None),
        ])

    def test_any_difficulty_means_it_does_not_matter(self):
        self.check([
            ('Beat the game on any difficulty', None),
            ('Finish the story regardless of difficulty', None),
        ])

    def test_missing_text_is_no_setting(self):
        self.assertIsNone(difficulty.setting(None, None))


if __name__ == '__main__':
    unittest.main()
