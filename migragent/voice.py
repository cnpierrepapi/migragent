"""The house voice, for everything the agent writes itself.

WHERE IT APPLIES
----------------
Headlines, decks, the "why" under each group, the text of each claim and
condition, and the list of what a page does not say. Never to a quote: a quote
is the government's words, copied exactly, and changing a dash in it would
break the check that it is on the page.

WHERE THE RULES COME FROM
-------------------------
The owner's human-voice skill (~/.claude/skills/human-voice/SKILL.md): plain
words, short sentences, no em dashes, none of the vocabulary that marks text
as machine-written, no inflating a fact into significance, no selling. The
banned list below is the skill's list, plus the selling words a wire must not
use about a government page.

HOW IT IS ENFORCED
------------------
Asking is not enough, so `articles.py` does three things with this file. The
rules go into the prompt (`RULES`). Dashes are replaced in code (`tidy`). And
every written field is checked against the lists (`hits`): a headline or deck
that fails gets one rewrite, a "why" that fails is dropped because its quote
already says the same thing, and whatever still fails is named in the article's
report. Nothing that breaks the voice goes out without the report saying so.
"""
from __future__ import annotations

import re

RULES = """
Voice, for every field you write yourself (never for a "quote"):
- Plain words and short sentences, the way you would tell a friend what the page says.
  One idea per sentence. Say the thing directly, once.
- No em dashes or en dashes. Use a comma, a full stop, or "to" for a range.
- Never use these words: delve, tapestry, testament, landscape, interplay, intricate,
  meticulous, pivotal, crucial, vital, underscore, highlight, showcase, boasts, bolster,
  garner, vibrant, profound, renowned, groundbreaking, enduring, foster, cultivate,
  encompass, enhance, leverage, robust, seamless, elevate, empower, unlock, harness,
  navigate, realm, myriad, plethora, additionally, moreover, furthermore, notably,
  ultimately, comprehensive, streamline, landmark, significant, major, key, game-changing.
- No significance inflation: not "stands as", "serves as", "marks a", "represents a",
  "plays a role", "a testament to", "paves the way". Use "is", or state the fact.
- No "not just X but Y", no "it's not about X, it's about Y".
- No trailing clause that adds nothing (", ensuring ...", ", highlighting ...").
- Sentence case. Straight quotes.
"""

# The skill's list, as patterns. Word boundaries, so "keyboard" is not "key".
BANNED = [
    "delve", "delves", "delving", "tapestry", "testament", "landscape", "interplay", "intricate",
    "intricacies", "meticulous", "meticulously", "pivotal", "crucial", "vital", "underscore",
    "underscores", "highlight", "highlights", "highlighting", "showcase", "showcases", "boasts",
    "bolstered", "bolster", "garner", "vibrant", "profound", "renowned", "groundbreaking",
    "enduring", "diverse array", "valuable insights", "foster", "fosters", "cultivate", "encompass",
    "encompasses", "enhance", "enhances", "enhanced", "leverage", "leverages", "robust", "seamless",
    "seamlessly", "elevate", "empower", "empowers", "unlock", "unlocks", "harness", "navigate",
    "realm", "myriad", "plethora", "additionally", "moreover", "furthermore", "notably", "ultimately",
    "ever-evolving", "fast-paced",
    # selling words a wire does not use about a government page
    "comprehensive", "streamline", "streamlines", "streamlined", "landmark", "significant",
    "significantly", "major", "game-changing", "game changer",
]
INFLATION = [
    "stands as", "serves as", "marks a", "represents a", "functions as", "plays a crucial role",
    "plays a key role", "plays a role", "a testament to", "paves the way", "setting the stage",
    "key turning point", "indelible mark",
]
_WORDS = re.compile(r"\b(" + "|".join(re.escape(w) for w in BANNED) + r")\b", re.I)
_PHRASES = re.compile("|".join(re.escape(p) for p in INFLATION), re.I)
_NOT_JUST = re.compile(r"\bnot (just|only|merely)\b[^.]{0,80}\bbut\b", re.I)
_KEY_ADJ = re.compile(r"\bkey (change|changes|update|updates|requirement|requirements|details?)\b", re.I)


def tidy(text: str) -> str:
    """Dashes and curly quotes out, in code, so no prompt has to be obeyed for it."""
    if not text:
        return text
    t = re.sub(r"(\d)\s*[–—]\s*(\d)", r"\1 to \2", text)   # 2024–2026 -> 2024 to 2026
    t = re.sub(r"\s*[—–]\s*", ", ", t)                      # other dashes -> comma
    t = re.sub(r"\s+--\s+", ", ", t)
    t = (t.replace("“", '"').replace("”", '"')
          .replace("‘", "'").replace("’", "'"))
    t = re.sub(r",\s*,", ",", t)
    return re.sub(r"\s{2,}", " ", t).strip().rstrip(",")


def hits(text: str) -> list[str]:
    """Every rule the text breaks, as the words that broke it. Empty when it is clean."""
    if not text:
        return []
    found = [m.group(0).lower() for m in _WORDS.finditer(text)]
    found += [m.group(0).lower() for m in _PHRASES.finditer(text)]
    found += [m.group(0).lower() for m in _KEY_ADJ.finditer(text)]
    if _NOT_JUST.search(text):
        found.append("not just ... but")
    if re.search(r"[—–]", text):
        found.append("dash")
    return sorted(set(found))
