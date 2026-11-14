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
            ('Beat the game on Hard or higher', 'Hard+'),
            ('Beat the game on Very Hard without dying', 'Very Hard'),
            ('Complete the game on Legendary', 'Legendary'),
            ('Complete the game in Hardcore mode', 'Hardcore'),
            ('On Death March difficulty, beat the game', 'Death March'),
            ('Complete the entire game on Duelist Difficulty preset.', 'Duelist'),
            ('Win a Long Game on Offices on Hell on Earth Difficulty.', 'Hell on Earth'),
            ('Clear every chapter with the difficulty set to Expert', 'Expert'),
            ('Clear every chapter at difficulty level Expert', 'Expert'),
            ('Complete the game on "Nightmare" or higher.', 'Nightmare+'),
            ("Reach milestone 5 in 'Challenge' difficulty.", 'Challenge'),
            ('Finish the story on at least Standard (Classic) difficulty.', 'Standard+'),
            ('Complete Shadow of the Tomb Raider on One with the Jungle difficulty', 'One with the Jungle'),
            ('Finish the game on the "Death March!" difficulty level.', 'Death March'),
            ('Complete the game on Dante Must Die mode.', 'Dante Must Die'),
            ("Clear Riku's story on Proud Mode or a higher difficulty level.", 'Proud+'),
            ('Clear game on Final Mix or a higher difficulty level.', 'Final Mix+'),
            ('Complete the game in Tactician mode.', 'Tactician'),
            ('Feel like taking the plunge into Survival Mode on extreme? Come back alive', 'Extreme'),
            ('Deliver 2,000 Alien shapes in Classic - Insane', 'Insane'),
            ('Finish on the highest difficulty', 'Hardest'),
            ('Complete the campaign on all difficulties', 'All'),
        ])

    def test_a_floor_is_marked_with_a_plus(self):
        self.check([
            ('Finish the game on Normal difficulty or higher.', 'Normal+'),
            ('Finish the story on at least Casual difficulty.', 'Casual+'),
            ('Complete Rock The Cradle on Very Hard or above.', 'Very Hard+'),
            ('Finish on the highest difficulty or higher', 'Hardest'),
        ])

    def test_a_floor_is_read_next_to_the_setting_only(self):
        self.check([
            ('Kill at least 100 enemies on Hard', 'Hard'),
            ('Beat it at least 3 times on Normal.', 'Normal'),
            ('Win with at least 50 percent HQ integrity on General difficulty', 'General'),
            ('Complete Lotus Towers on Hardened, Veteran, or Realistic.', 'Hardened+'),
            ('Beat the game on Easy or Normal.', 'Easy+'),
            ('Complete an Extreme difficulty mission or higher without anyone dying.', 'Extreme+'),
            ('Finish the story on Medium difficulty level or higher', 'Medium+'),
        ])

    def test_words_that_mean_something_else_alone_need_more(self):
        self.check([
            ('Craft a sword using iron and wood', None),
            ('Complete the game using the Ranger', None),
            ('Win a match on Standard.', None),
            ('Cook a steak on medium.', None),
            ('Complete the game on Standard or higher.', 'Standard+'),
            ('Complete the game in Iron Mode.', 'Iron'),
            ('Complete the game in Ranger Mode Easy.', 'Ranger Easy'),
            ('Complete the game in Ranger Hardcore mode.', 'Ranger Hardcore'),
        ])

    def test_modes_that_are_what_is_played_are_not_settings(self):
        self.check([
            ('Reach wave 50 on Horde Mode', None),
            ('Take a photo on Photo Mode', None),
            ('Win a match in Casual mode', None),
            ('Finish the story on at least Casual difficulty.', 'Casual+'),
        ])

    def test_two_settings_are_not_one_name(self):
        self.assertEqual(difficulty.setting('X', 'Win on Hard and Nightmare difficulty'), 'Nightmare')
        self.assertIsNone(difficulty.setting('X', 'Beat it in New Game+ with Higher Difficulty'))
        self.assertEqual(difficulty.setting('X', 'Complete the game on Hell and Hell mode.'), 'Hell and Hell')

    def test_all_needs_to_be_about_the_settings(self):
        self.assertIsNone(difficulty.setting('X', 'Complete all difficulty challenges'))

    def test_the_description_decides_over_a_joke_name(self):
        self.assertIsNone(difficulty.setting('With Extreme Difficulty', 'Destroy 50 tanks'))
        self.assertIsNone(difficulty.setting('Nightmare Mode', 'Head into Undermountain with a plethora of bosses!'))

    def test_reads_the_name_when_there_is_no_description(self):
        self.assertEqual(difficulty.setting('Insane difficulty', ''), 'Insane')

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
