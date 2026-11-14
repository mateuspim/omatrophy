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
LEAD = r'\b(?i:on|in|at|using)\s+(?i:at\s+least\s+)?(?i:the\s+)?'
# A bare setting word only counts where the sentence ends or goes on about
# the run ("on Hard or higher", "on Hard without dying"), so "in normal
# combat" and "on hard ground" stay out. "in" doesn't lead one: "the
# Platinum rank in Standard" is a ranked format.
ON_SETTING = re.compile(rf'\b(?:on|at|using)\s+(?:at\s+least\s+)?(?:the\s+)?({SETTINGS})'
                        r'(?=\s*(?:$|[.,;:!?()]|(?:or|and|without|with|in|on|while|before)\b))', re.I)
# "on Death March difficulty": any name, as the word "difficulty" says what
# it is; up to four capitalised words, so "on the same difficulty" doesn't
# name a setting called "same". Small words may join them ("Rite of
# Passage"), but not "on" or "in", which would read "Win on Offices on
# Hell on Earth" as a setting called "Offices on Hell on Earth": names
# with those are spelled out.
WITH_SMALL_WORDS = r'Hell\s+on\s+Earth|Heaven\s+or\s+Hell|Hell\s+or\s+High\s+Water'
WORD = r"[A-Z∞][\w'+!:-]*"
NAME = rf"{WITH_SMALL_WORDS}|{WORD}(?:\s+(?:(?:of|the|and|with|a|to)\s+){{0,2}}{WORD}){{0,3}}"
NAMED_DIFFICULTY = re.compile(rf"(?:{LEAD}|\b(?:or|and)\s+)({NAME})\s+(?i:(?:or\s+(?:a\s+)?higher\s+)?difficult(?:y|ies))\b")
# After "on", a mode is the setting the run is played on ("on Dante Must
# Die mode", "on Professional mode"); "in Raid Mode" is what's played, so
# "in" only counts with a known setting word.
ON_NAMED_MODE = re.compile(rf"\b(?i:on)\s+(?i:at\s+least\s+)?(?i:the\s+)?({NAME})\s+(?i:mode)\b")
SETTING_DIFFICULTY = re.compile(rf'\b({SETTINGS})\s+(?:game\s+)?(?:difficulty|mode)\b', re.I)
DIFFICULTY_SETTING = re.compile(rf'\bdifficulty\s+(?:level\s+|setting\s+|set\s+to\s+|of\s+)?({SETTINGS})\b', re.I)
# "Deliver 500 shapes in Classic - Insane": a mode, then its setting.
DASH_SETTING = re.compile(rf'\s[-–]\s+({SETTINGS})\s*[.!]?$', re.I)
TOP = re.compile(r'\b(?:the\s+)?(highest|hardest|maximum|max|top)\s+difficulty\b', re.I)
EVERY = re.compile(r'\b(?:all|every|each)\s+(?:the\s+)?difficult(?:y|ies)(?:\s+(?:levels?|settings?))?\b', re.I)
# "on any difficulty" says the setting doesn't matter.
ANY = re.compile(r'\b(?:any|regardless\s+of(?:\s+the)?)\s+difficult', re.I)
# "on Normal or higher", "on at least Casual": a floor, which a harder run
# also meets, so it's marked "Normal+" and ranks after exact settings.
FLOOR = re.compile(r'\b(?:or\s+(?:a\s+)?(?:higher|harder|above|greater)|at\s+least|and\s+(?:up|above))\b', re.I)
# Quotes around a name ("on "Hardcore" or higher") only get in the way.
QUOTES = re.compile(r'["“”‘’]|(?<!\w)\'|\'(?!\w)')

SMALL_WORDS = {'on', 'or', 'of', 'the', 'and', 'with', 'a', 'to'}


def setting(name, desc):
    """The difficulty setting an achievement needs ("Nightmare", "Highest",
    "Every"; "Normal+" for "Normal or higher"), or None when its text names
    none."""
    found = named(name, desc)
    if found and found not in ('Highest', 'Every') and FLOOR.search(f'{name or ""}. {desc or ""}'):
        return found + '+'
    return found


def named(name, desc):
    """The setting's name alone, as `setting` finds it."""
    text = QUOTES.sub('', f'{name or ""}. {(desc or "").strip()}')
    if ANY.search(text):
        return None
    if TOP.search(text):
        return 'Highest'
    if EVERY.search(text):
        return 'Every'
    for pattern in (NAMED_DIFFICULTY, ON_NAMED_MODE, SETTING_DIFFICULTY, DIFFICULTY_SETTING):
        found = pattern.search(text)
        if found:
            return tidy(found.group(1))
    # A bare word is weaker evidence, so only the description counts: a
    # name like "The Devil in Iron" is a title, not a rule.
    desc = QUOTES.sub('', (desc or '').strip())
    for pattern in (ON_SETTING, DASH_SETTING):
        found = pattern.search(desc)
        if found:
            return tidy(found.group(1))
    return None


def tidy(word):
    """"very  hard" -> "Very Hard"; "hell ON earth" -> "Hell on Earth";
    "Proud Mode" -> "Proud"."""
    words = re.sub(r'\s+mode$', '', word.strip('!:'), flags=re.I).lower().split()
    return ' '.join(w if i and w in SMALL_WORDS else w[:1].upper() + w[1:] for i, w in enumerate(words))
