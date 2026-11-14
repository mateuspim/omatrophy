"""Spot achievements that need a difficulty setting, from their own text.

The point is to know before the first launch: a "beat it on Nightmare"
achievement decides which setting a new save should start on. Stores
don't tag these, so this reads the name and description. It errs towards
missing one rather than flagging "a hard-fought battle": a wrong chip
costs trust, a missed one costs no more than today.
"""
import re

# Setting names games use. Words that are also common modes or places
# ("story", "survival", "classic", "hell") are left out: "in Story mode"
# is a fighting game's single player, not a difficulty.
SETTINGS = (r'very\s+hard|extra\s+hard|super\s+hard|easy|casual|normal|medium|standard|hard(?:er|est|ened)?'
            r'|extreme|expert|veteran|professional|insane|insanity|nightmare|legendary|heroic|brutal'
            r'|realistic|grounded|survivor|impossible|hardcore|ironman|permadeath|tactician|honou?r'
            r'|proud|critical|spartan|ranger|beginner|mastermind|iron')
# Of those, the ones that mean something else on their own ("using iron",
# "as the Ranger", "a steak on medium", "a match on Standard") only count
# next to "difficulty" or "mode", or in a list of settings ("on Standard or
# higher").
AMBIGUOUS = r'iron|ranger|spartan|standard|medium'
LEAD = r'\b(?i:on|in|at|using)\s+(?i:at\s+least\s+)?(?i:the\s+)?'
# A bare setting word only counts where the sentence ends or goes on about
# the run ("on Hard or higher", "on Hard without dying"), so "in normal
# combat" and "on hard ground" stay out. "in" doesn't lead one: "the
# Platinum rank in Standard" is a ranked format.
BARE_LEAD = r'\b(?:on|at)\s+(?:at\s+least\s+)?(?:the\s+)?'
ON_SETTING = re.compile(rf'{BARE_LEAD}(?!(?:{AMBIGUOUS})\b)({SETTINGS})'
                        r'(?=\s*(?:$|[.,;:!?()]|(?:or|and|without|with|in|on|while|before)\b))', re.I)
ON_AMBIGUOUS = re.compile(rf'{BARE_LEAD}({AMBIGUOUS})(?=\s*,?\s+(?:or|and)\b|\s*\([^)]*\)\s*difficulty)', re.I)
# "on Death March difficulty": any name, as the word "difficulty" says what
# it is; up to four capitalised words, so "on the same difficulty" doesn't
# name a setting called "same". Small words may join them ("Rite of
# Passage"), but not "on" or "in", which would read "Win on Offices on
# Hell on Earth" as a setting called "Offices on Hell on Earth": names
# with those are spelled out. "and" and "with" join only when no setting
# follows: "on Hard and Nightmare difficulty" names two.
WITH_SMALL_WORDS = r'Hell\s+on\s+Earth|Heaven\s+or\s+Hell|Hell\s+or\s+High\s+Water'
WORD = r"[A-Z∞][\w'+!:-]*"
JOIN = rf"(?:of|the|a|to|(?:and|with)(?!\s+(?i:{SETTINGS}|higher|harder|greater)\b))"
NAME = rf"{WITH_SMALL_WORDS}|{WORD}(?:\s+(?:{JOIN}\s+){{0,2}}{WORD}){{0,3}}"
NAMED_DIFFICULTY = re.compile(rf"(?:{LEAD}|\b(?:or|and)\s+)({NAME})\s+(?i:(?:or\s+(?:a\s+)?higher\s+)?difficult(?:y|ies))\b")
# After "on", a mode is the setting the run is played on ("on Dante Must
# Die mode", "on Professional mode"); "in Raid Mode" is what's played, so
# "in" only counts with a known setting word. Modes that are what's played
# whatever the lead ("on Horde Mode") are left out by name.
GAME_MODES = (r'horde|photo|challenge|arcade|versus|survival|story|ranked|campaign|practice|training|endless'
              r'|online|co-?op|casual')
ON_NAMED_MODE = re.compile(rf"\b(?i:on)\s+(?i:at\s+least\s+)?(?i:the\s+)?(?!(?i:{GAME_MODES})\s)({NAME})\s+(?i:mode)\b")
SETTING_DIFFICULTY = re.compile(rf'\b({SETTINGS})\s+(?:game\s+)?difficulty\b', re.I)
# "Casual mode" is often what's played (unranked), so it needs "difficulty".
SETTING_MODE = re.compile(rf'\b(?!(?:{GAME_MODES})\s)({SETTINGS})\s+(?:game\s+)?mode\b', re.I)
DIFFICULTY_SETTING = re.compile(rf'\bdifficulty\s+(?:level\s+|setting\s+|set\s+to\s+|of\s+)?({SETTINGS})\b', re.I)
# "Deliver 500 shapes in Classic - Insane": a mode, then its setting.
DASH_SETTING = re.compile(rf'\s[-–]\s+({SETTINGS})\s*[.!]?$', re.I)
TOP = re.compile(r'\b(?:the\s+)?(highest|hardest|maximum|max|top)\s+difficulty\b', re.I)
# "on all difficulties", but not "all difficulty challenges".
EVERY = re.compile(r'\b(?:all|every|each)\s+(?:the\s+)?difficult(?:y|ies)(?:\s+(?:levels?|settings?|modes?))?'
                   r'(?=\s*(?:$|[.,;:!?()]|(?:except|and|without|with|in|on)\b))', re.I)
# "on any difficulty" says the setting doesn't matter.
ANY = re.compile(r'\b(?:any|regardless\s+of(?:\s+the)?)\s+difficult', re.I)
# "on Normal or higher", "on at least Casual", "on Easy or Normal": a
# floor, which a harder run also meets, so it's marked "Normal+" and ranks
# after exact settings. Only the words around the setting count: "Kill at
# least 100 enemies on Hard" is Hard.
FLOOR_IN = re.compile(r'\bat\s+least\b|\bor\s+(?:a\s+)?higher\b', re.I)
FLOOR_AFTER = re.compile(rf'(?:\s+(?:game\s+)?(?:difficulty|mode))?(?:\s+(?:levels?|settings?|missions?))?\s*'
                         rf'(?:or\s+(?:a\s+)?(?:higher|harder|above|greater)|and\s+(?:up|above)'
                         rf'|,?\s*or\s+(?:{SETTINGS})\b|,\s*(?:{SETTINGS})\b)', re.I)
# Quotes around a name ("on "Hardcore" or higher") only get in the way.
QUOTES = re.compile(r'["“”‘’]|(?<!\w)\'|\'(?!\w)')

# Metro's Ranger settings name two things: "in Ranger Mode Hardcore",
# "in Ranger Hardcore mode". "Ranger" alone wouldn't tell them apart.
RANGER = re.compile(r'\b(ranger\s+(?:mode\s+)?(?:easy|normal|hardcore))\b', re.I)

STRONG = (RANGER, NAMED_DIFFICULTY, ON_NAMED_MODE, SETTING_DIFFICULTY, SETTING_MODE, DIFFICULTY_SETTING)
BARE = (ON_SETTING, ON_AMBIGUOUS, DASH_SETTING)
SMALL_WORDS = {'on', 'or', 'of', 'the', 'and', 'with', 'a', 'to'}


def setting(name, desc):
    """The difficulty setting an achievement needs ("Nightmare"; "Hardest"
    for the top one, "All" for every one; "Normal+" for "Normal or
    higher"), or None when its text names none. The description decides;
    the name only when there's no description, as a name is a title ("With
    Extreme Difficulty" for destroying tanks)."""
    desc = QUOTES.sub('', (desc or '').strip())
    return found_in(desc) if desc else found_in(QUOTES.sub('', (name or '').strip()))


def found_in(text):
    if ANY.search(text):
        return None
    if TOP.search(text):
        return 'Hardest'
    if EVERY.search(text):
        return 'All'
    for pattern in STRONG + BARE:
        found = pattern.search(text)
        if found:
            return tidy(found.group(1)) + ('+' if floor(text, found) else '')
    return None


def floor(text, found):
    """Whether the words around a found setting make it a floor."""
    return bool(FLOOR_IN.search(found.group(0)) or FLOOR_AFTER.match(text, found.end()))


def tidy(word):
    """"very  hard" -> "Very Hard"; "hell ON earth" -> "Hell on Earth";
    "Proud Mode" -> "Proud"; "Ranger Mode Easy" -> "Ranger Easy"."""
    words = re.sub(r'\s+mode\b', '', word.strip('!:'), flags=re.I).lower().split()
    return ' '.join(w if i and w in SMALL_WORDS else w[:1].upper() + w[1:] for i, w in enumerate(words))
