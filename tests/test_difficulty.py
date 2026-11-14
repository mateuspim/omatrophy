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
            ('Complete the entire game on Duelist Difficulty preset.', 'Duelist'),
            ('Win a Long Game on Offices on Hell on Earth Difficulty.', 'Hell on Earth'),
            ('Clear every chapter with the difficulty set to Expert', 'Expert'),
            ('Clear every chapter at difficulty level Expert', 'Expert'),
            ('Complete the game on "Nightmare" or higher.', 'Nightmare'),
            ("Reach milestone 5 in 'Challenge' difficulty.", 'Challenge'),
            ('Finish the story on at least Standard (Classic) difficulty.', 'Standard'),
            ('Complete Shadow of the Tomb Raider on One with the Jungle difficulty', 'One with the Jungle'),
            ('Finish the game on the "Death March!" difficulty level.', 'Death March'),
            ('Complete the game on Dante Must Die mode.', 'Dante Must Die'),
            ("Clear Riku's story on Proud Mode or a higher difficulty level.", 'Proud'),
            ('Clear game on Final Mix or a higher difficulty level.', 'Final Mix'),
            ('Complete the game in Tactician mode.', 'Tactician'),
            ('Feel like taking the plunge into Survival Mode on extreme? Come back alive', 'Extreme'),
            ('Deliver 2,000 Alien shapes in Classic - Insane', 'Insane'),
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
            ('Clear Episode One in Invisible Mode.', None),
            ('Clear one Gauntlet in Raid Mode.', None),
            ('Reach the Platinum rank or higher in Standard', None),
            ('Finish the game in Invisible Enemy mode.', None),
            ('', None),
        ])

    def test_a_bare_setting_word_in_the_name_is_a_title(self):
        self.assertIsNone(difficulty.setting('The Devil in Iron', 'Defeat the Kinscourge'))

    def test_any_difficulty_means_it_does_not_matter(self):
        self.check([
            ('Beat the game on any difficulty', None),
            ('Finish the story regardless of difficulty', None),
        ])

    def test_missing_text_is_no_setting(self):
        self.assertIsNone(difficulty.setting(None, None))


if __name__ == '__main__':
    unittest.main()
