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
SETTINGS = (r'very\s+hard|extra\s+hard|super\s+hard|easy|casual|normal|medium|hard(?:er|est)?|extreme|expert'
            r'|veteran|insane|nightmare|legendary|heroic|brutal|realistic|grounded|survivor|impossible'
            r'|hardcore|ironman|permadeath')
# A bare setting word only counts where the sentence ends or goes on about
# the run ("on Hard or higher", "on Hard without dying"), so "in normal
# combat" and "on hard ground" stay out.
ON_SETTING = re.compile(rf'\b(?:on|in|at|using)\s+(?:the\s+)?({SETTINGS})'
                        r'(?=\s*(?:$|[.,;:!)]|(?:or|and|without|with|in|on|while|before)\b))', re.I)
# "on Death March difficulty": any name, as the word "difficulty" says what
# it is; up to three words, each capitalised so "on the same difficulty"
# doesn't name a setting called "same".
# Names with a small word in them are spelled out: allowing "on" inside a
# name would read "Win on Offices on Hell on Earth" as a setting called
# "Offices on Hell on Earth".
WITH_SMALL_WORDS = r'Hell\s+on\s+Earth|Heaven\s+or\s+Hell|Hell\s+or\s+High\s+Water'
NAMED_DIFFICULTY = re.compile(r"\b(?i:on|in|at|using)\s+(?i:the\s+)?"
                              rf"({WITH_SMALL_WORDS}|(?:[A-Z][\w'+-]*\s+){{0,2}}[A-Z][\w'+-]*)"
                              r'\s+(?i:difficult(?:y|ies))\b')
SETTING_DIFFICULTY = re.compile(rf'\b({SETTINGS})\s+(?:difficulty|mode)\b', re.I)
DIFFICULTY_SETTING = re.compile(rf'\bdifficulty\s+(?:level\s+|setting\s+|set\s+to\s+|of\s+)?({SETTINGS})\b', re.I)
TOP = re.compile(r'\b(?:the\s+)?(highest|hardest|maximum|max|top)\s+difficulty\b', re.I)
EVERY = re.compile(r'\b(?:all|every|each)\s+(?:the\s+)?difficult(?:y|ies)(?:\s+(?:levels?|settings?))?\b', re.I)
# "on any difficulty" says the setting doesn't matter.
ANY = re.compile(r'\b(?:any|regardless\s+of(?:\s+the)?)\s+difficult', re.I)

SMALL_WORDS = {'on', 'or', 'of', 'the', 'and'}


def setting(name, desc):
    """The difficulty setting an achievement needs ("Nightmare", "Highest",
    "Every"), or None when its text names none."""
    text = f'{name or ""}. {desc or ""}'
    if ANY.search(text):
        return None
    if TOP.search(text):
        return 'Highest'
    if EVERY.search(text):
        return 'Every'
    for pattern in (NAMED_DIFFICULTY, SETTING_DIFFICULTY, DIFFICULTY_SETTING, ON_SETTING):
        found = pattern.search(text)
        if found:
            return tidy(found.group(1))
    return None


def tidy(word):
    """"very  hard" -> "Very Hard"; "hell ON earth" -> "Hell on Earth"."""
    words = word.lower().split()
    return ' '.join(w if i and w in SMALL_WORDS else w[:1].upper() + w[1:] for i, w in enumerate(words))
