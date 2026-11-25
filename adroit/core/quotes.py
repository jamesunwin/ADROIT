"""Matching a quoted passage against a document's extracted text, up to typesetting.

Text extracted from a PDF differs from what a reader sees on the page in a few mechanical ways: a word broken at a
line end keeps its hyphen (``exper-`` then ``iment`` on the next line, or ``exper- iment`` once the lines are joined),
soft hyphens and zero-width characters appear, ligatures come out as single characters (ﬁ, ﬂ), and minus signs and
dashes are any of several Unicode characters (−, –, —, ‐). Both the quote and the text are brought to one form
before the comparison, and nothing else is changed: a different number, word or superscript stays different.

A hyphen followed by white space is ambiguous (a broken word, ``exper- iment``, or a hyphenated word broken at its
hyphen, ``dark-`` / ``matter``), so both readings are tried, each applied alike to the quote and the text.
"""

from __future__ import annotations

import re
from functools import lru_cache

INVISIBLE = dict.fromkeys(map(ord, "­​‌‍⁠﻿"))       # soft hyphen, zero widths
LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st",
             "ﬆ": "st"}
DASHES = "‐‑‒–—―−﹘﹣－"            # hyphens, dashes, minus signs
_TABLE = str.maketrans({**INVISIBLE, **{ord(k): v for k, v in LIGATURES.items()}, **dict.fromkeys(map(ord, DASHES), "-")})
_BROKEN = re.compile(r"(?<=\w)-\s+(?=\w)")


def normalise(text: str, join_broken_words: bool = True, case_sensitive: bool = False) -> str:
    """The text with invisible characters removed, ligatures spelt out, every dash and minus as ``-``, a hyphen
    before white space joined (``exper- iment`` → ``experiment``) or kept (``dark- matter`` → ``dark-matter``),
    white space collapsed, and (unless ``case_sensitive``) case folded."""
    text = _BROKEN.sub("" if join_broken_words else "-", text.translate(_TABLE))
    text = re.sub(r"\s+", " ", text).strip()
    return text if case_sensitive else text.casefold()


@lru_cache(maxsize=32)
def _forms(body: str, case_sensitive: bool) -> tuple[str, str]:
    return normalise(body, True, case_sensitive), normalise(body, False, case_sensitive)


def contains(body: str, quote: str, case_sensitive: bool = False) -> bool:
    """Whether the quote appears in the text up to typesetting (``normalise``); an empty quote never does."""
    forms = _forms(body, case_sensitive)
    for join, form in zip((True, False), forms):
        q = normalise(quote, join, case_sensitive)
        if q and q in form:
            return True
    return False
