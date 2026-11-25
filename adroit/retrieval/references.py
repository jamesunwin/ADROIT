"""References: found in text, and confirmed to exist before any report carries them (DM9).

DarkAgents (arXiv:2606.11157) found language-model agents inventing references in
their final reports. In ADROIT an agent may cite a paper only by an identifier
that deterministic code has confirmed:

- an arXiv identifier is looked up in arXiv's API (title, authors, year);
- a DOI is looked up at Crossref;
- when the agent also gives a title, it must be the paper's title (``identify``): nothing it states may contradict
  the paper (a year, an identifier), and its words must be the title's. A description that only fits the paper (its
  experiment's name and words from the abstract) does not identify it, since it can fit another paper of the same
  experiment: the paper exists, but the citation is not confirmed (the external audit's A08, 2026-10-16).

Anything that cannot be confirmed (not found, the network unavailable, a title
that does not match) is removed from the text and listed as unverified. A
report never shows an unconfirmed reference as if it were one. Lookups are
cached under the data folder (git-ignored), so a reference is fetched once.
The network is touched only by ``arxiv_lookup`` and ``doi_lookup``; tests
inject a resolver.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

from pydantic import Field

from adroit.core.config import get_settings
from adroit.core.state import StrictModel

ARXIV_NEW = re.compile(r"(?<![\w./])(?:arXiv:\s*)?(\d{4}\.\d{4,5})(?:v\d+)?(?![0-9A-Za-z_])")
ARXIV_OLD = re.compile(r"(?<![\w./])(?:arXiv:\s*)?((?:hep-(?:ph|th|ex|lat)|astro-ph|nucl-(?:th|ex)|gr-qc)"
                       r"(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?")
# A DOI: its suffix may hold parentheses, kept whole where balanced (10.1016/S0370-2693(99)00001-2); a closing one
# alone ends it, as in "(see 10.1103/X)". A trailing full stop is the sentence's (``_key``).
DOI_BODY = r"10\.\d{4,9}/(?:[^\s\"<>,;()\[\]]|\([^\s\"<>()\[\]]*\))+"
DOI = re.compile(rf"(?<![\w/])({DOI_BODY})")
# An identifier written as a link (the auditor's LT16-01, 2026-11-16; AL5-04, its cycle 5, 2026-11-17). Every link is read
# for what it points to, its target decoded first (``_targets``): an arXiv identifier at arxiv.org, and a DOI anywhere
# in the link, at doi.org or inside a journal's own URL (journals.aps.org/.../10.1103/...). A link only recognised by
# its host, or read undecoded, had passed both the cleaner and the gate's measure (a journal's URL, 9999%2E99999,
# 10.1103%2F...), and a DOI with parentheses had been cut at the first.
URL = re.compile(r"<?https?://(?:[^\s<>\"'()\[\]]|\([^\s<>\"'()\[\]]*\))+>?", re.I)
LINK = re.compile(r"\[([^\]]*)\]\(\s*<?((?:[^()\s<>]|\([^()\s<>]*\))+)>?\s*\)")    # Markdown: [label](target)
ANCHOR = re.compile(r"<a\s[^>]*?href\s*=\s*[\"']([^\"']+)[\"'][^>]*>.*?</a\s*>", re.I | re.S)     # HTML: <a href>
ARXIV_AT = re.compile(r"arxiv\.org/(?:abs|pdf|html|format)/(\d{4}\.\d{4,5}|(?:hep-(?:ph|th|ex|lat)|astro-ph|"
                      r"nucl-(?:th|ex)|gr-qc)(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?", re.I)
DOI_AT = re.compile(DOI_BODY)
ATOM = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "adroit (research software; checks that cited references exist)"
REMOVED = "[unverified reference removed]"


class Reference(StrictModel):
    """A cited paper, and whether it was confirmed."""

    kind: str                                   # "arxiv" or "doi"
    id: str
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    abstract: str = ""                          # arXiv's, for ``names_paper``
    verified: bool = False
    checked_on: str = ""
    note: str = ""                              # why it is not verified


Resolver = Callable[[list["Reference"]], dict[str, "Reference"]]


def find(text: str) -> list[Reference]:
    """Every distinct arXiv identifier and DOI in ``text``, in order of appearance: those every link points to (its
    target decoded, ``_in_link``), then those written out."""
    found: dict[str, tuple[int, Reference]] = {}

    def add(kind: str, key: str, at: int) -> None:
        this, key = _identity(kind, _key(kind, key))
        found.setdefault(key, (at, Reference(kind=this, id=key)))
    for target, at in _targets(text):
        for kind, key in _in_link(target):
            add(kind, key, at)
    bare = URL.sub(lambda m: " " * len(m.group(0)), ANCHOR.sub(lambda m: " " * len(m.group(0)), text))
    for kind, pattern in PATTERNS:
        for match in pattern.finditer(bare):
            add(kind, match.group(1), match.start())
    return [ref for _, ref in sorted(found.values(), key=lambda x: x[0])]


PATTERNS = (("arxiv", ARXIV_NEW), ("arxiv", ARXIV_OLD), ("doi", DOI))


def _key(kind: str, key: str) -> str:
    """An identifier as written, without a sentence's full stop after a DOI."""
    return key.rstrip(".") if kind == "doi" else key


def _identity(kind: str, key: str) -> tuple[str, str]:
    """(kind, identifier) as ``find`` keys them: arXiv's own DOI (10.48550/arXiv.X) names the arXiv identifier X."""
    arxiv_doi = re.fullmatch(r"10\.48550/arxiv\.(.+)", key, flags=re.I)
    return ("arxiv", arxiv_doi.group(1)) if arxiv_doi else (kind, key)


def _decoded(target: str) -> str:
    """A link's target with its percent-encoding undone (twice-encoded too: %252E)."""
    for _ in range(3):
        plain = unquote(target)
        if plain == target:
            break
        target = plain
    return target


def _in_link(target: str) -> list[tuple[str, str]]:
    """The identifiers a link points to, read from its decoded target: an arXiv identifier at arxiv.org, and any DOI
    in it (doi.org's, or one inside a journal's URL)."""
    plain = _decoded(target)
    found = [("arxiv", m.group(1)) for m in ARXIV_AT.finditer(plain)]
    found += [("doi", m.group(0)) for m in DOI_AT.finditer(plain)]
    return [_identity(kind, _key(kind, key)) for kind, key in found]


def _targets(text: str) -> list[tuple[str, int]]:
    """Every link's target in ``text``, with where it is: an HTML anchor's, a Markdown link's, and each bare URL."""
    return ([(m.group(1), m.start()) for m in ANCHOR.finditer(text)] + [(m.group(2), m.start()) for m in LINK.finditer(text)]
            + [(m.group(0).strip("<>"), m.start()) for m in URL.finditer(text)])


def _links_removed(text: str, allowed: set[str]) -> str:
    """``text`` with each link to an identifier not in ``allowed`` replaced whole by REMOVED: an HTML anchor or a
    Markdown link (its label with it), then a bare URL, an angle autolink's brackets with it, its sentence's
    punctuation kept (LT16-01; AL5-04). A link to a confirmed paper is kept as it is."""
    def unconfirmed(target: str) -> bool:
        return any(key not in allowed for _, key in _in_link(target))

    def bare(m: re.Match) -> str:
        link = m.group(0)
        core = link if link.endswith(">") else link.rstrip(".,;:!?")
        return REMOVED + link[len(core):] if unconfirmed(core.strip("<>")) else link
    text = ANCHOR.sub(lambda m: REMOVED if unconfirmed(m.group(1)) else m.group(0), text)
    text = LINK.sub(lambda m: REMOVED if unconfirmed(m.group(2)) else m.group(0), text)
    return URL.sub(bare, text)


def _normal(title: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", title.lower()).split()


def same_title(claimed: str, actual: str) -> bool:
    """Whether a cited title is the paper's: 90% of their words shared (TeX, case, punctuation and plurals aside), or
    the citation is the title's leading half or more, of four words or more (a dropped subtitle). A fragment such as
    "Search Results" is not a title, and PICO-60's 2017 title (82% shared with the 2019 one) is not the 2019 paper's
    (the external audit's A08, 2026-10-16: "one contains the other" and 80% had accepted both)."""
    a, b = _words(claimed), _words(actual)
    if not a or not b:
        return False
    if len(set(a) & set(b)) / len(set(a) | set(b)) >= 0.9:
        return True
    return len(a) >= 4 and len(a) >= 0.5 * len(b) and b[:len(a)] == a


STOP = {"a", "an", "the", "of", "from", "for", "with", "and", "in", "on", "at", "to", "by", "as", "its", "their"}


GREEK = dict(zip("αβγδεηθκλμµνπρστφχψωΓΔΛΣΦΨΩ", "alpha beta gamma delta epsilon eta theta kappa lambda mu mu nu pi rho "
                                                 "sigma tau phi chi psi omega gamma delta lambda sigma phi psi omega"
                                                 .split()))


def _words(text: str) -> list[str]:
    """Lower-case words without TeX markup ($, _, braces) or plural s: "C$_3$F$_8$" is c3f8, "WIMPs" is wimp. TeX and
    Unicode spell the same title alike: "$\\sqrt{s}$" and "√s" are s, "$\\times$" and "×" are spaces, "$\\gamma$" and
    "γ" are gamma (arXiv titles use TeX, citations often Unicode)."""
    plain = re.sub(r"\\?sqrt|√|\\times|×", " ", text)
    plain = re.sub(r"[$_{}\\]", "", "".join(GREEK.get(c, c) for c in plain))
    return [w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w
            for w in re.sub(r"[^a-z0-9 ]", " ", plain.lower()).split()]


def _names(text: str) -> list[str]:
    """The name-like words of a description: two capitals or more (CDMS, WIMP, CDMSlite), or letters with digits
    (PICO-60, C3F8, CRESST-III's parts)."""
    tokens = re.findall(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*", re.sub(r"[$_{}\\]", "", text))
    named = [t for t in tokens if sum(c.isupper() for c in t) >= 2 or (re.search(r"\d", t) and re.search(r"[A-Za-z]", t))]
    return [w for t in named for w in _words(t)]


def contradiction(claimed: str, paper: Reference) -> str:
    """Why a citation cannot be this paper, whatever else it says: a year more than one from the paper's arXiv year,
    or another arXiv identifier; "" if nothing contradicts it. Checked before any match of words."""
    years = [int(y) for y in re.findall(r"\b((?:19|20)\d\d)\b", claimed)]
    if years and paper.year and all(abs(y - paper.year) > 1 for y in years):
        return f"it states {', '.join(map(str, years))}; the paper is from {paper.year}"
    ids = [m.group(1) for m in ARXIV_NEW.finditer(claimed)]
    if ids and paper.kind == "arxiv" and all(i != paper.id.split("v")[0] for i in ids):
        return f"it names arXiv:{ids[0]}"
    return ""


def identify(claimed: str, paper: Reference) -> tuple[str, str]:
    """How a cited title identifies this paper, and why: "contradicted" (``contradiction``), "title" (its own title,
    ``same_title``: the only identification), "description" (words that fit this paper, ``description_fits``, but
    could fit another of the same experiment: the paper exists, the citation is not confirmed) or "" (neither)."""
    reason = contradiction(claimed, paper)
    if reason:
        return "contradicted", f"the citation {claimed!r} contradicts this paper: {reason}"
    if same_title(claimed, paper.title):
        return "title", ""
    if description_fits(claimed, paper):
        return "description", (f"the citation {claimed!r} fits this paper but is not its title, and could fit "
                                "another of the same experiment")
    return "", f"the cited title {claimed!r} is not this paper's"


def description_fits(claimed: str, paper: Reference) -> bool:
    """Whether a description fits this paper (G12's live check L8a: "PICO-60 C3F8 2019 complete exposure"): it has a
    name-like word (an experiment, a material), every name-like word is in the paper's title or abstract, and so are
    80% of its other words, years and single characters aside. Fitting is not identifying (``identify``): PICO-60's
    2017 paper fits "PICO-60 C3F8 complete exposure" as its 2019 one does."""
    known = set(_words(f"{paper.title} {paper.abstract}"))
    words = [w for w in _words(claimed) if w not in STOP and len(w) > 1 and not re.fullmatch(r"(19|20)\d\d", w)]
    names = _names(claimed)
    if not names or not words or any(n not in known for n in names):
        return False
    return sum(w in known for w in words) >= 0.8 * len(words)


def arxiv_lookup(refs: list[Reference]) -> dict[str, Reference]:
    """arXiv's API for the arXiv identifiers among ``refs`` (network)."""
    import requests
    ids = [r.id for r in refs if r.kind == "arxiv"]
    if not ids:
        return {}
    response = requests.get("https://export.arxiv.org/api/query",
                            params={"id_list": ",".join(ids), "max_results": len(ids)},
                            headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    return parse_arxiv(response.text, ids)


def search_arxiv(query: str, max_results: int = 25) -> list[Reference]:
    """arXiv's newest papers for a free-text ``query`` (its API's ``all:`` search, newest submitted first; network):
    the record check's literature comparison (``orchestrator.record_check``)."""
    import requests
    words = " AND ".join(f"all:{w}" for w in re.findall(r"[\w+-]+", query)[:12])
    if not words:
        return []
    response = requests.get("https://export.arxiv.org/api/query",
                            params={"search_query": words, "sortBy": "submittedDate", "sortOrder": "descending",
                                    "max_results": max(1, min(int(max_results), 50))},
                            headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    return parse_search(response.text)


def parse_search(atom: str) -> list[Reference]:
    """Every entry of an arXiv API response, in its order, by its identifier (its version dropped)."""
    out = []
    for entry in ET.fromstring(atom).iter(f"{ATOM}entry"):
        url = (entry.findtext(f"{ATOM}id") or "").strip()
        title = " ".join((entry.findtext(f"{ATOM}title") or "").split())
        identifier = re.sub(r"v\d+$", "", url.rstrip("/").split("/abs/")[-1])
        if not identifier or not title or title.lower() == "error":
            continue
        published = entry.findtext(f"{ATOM}published") or ""
        out.append(Reference(kind="arxiv", id=identifier, title=title,
                             authors=[a.findtext(f"{ATOM}name") or "" for a in entry.iter(f"{ATOM}author")],
                             year=int(published[:4]) if published[:4].isdigit() else None,
                             abstract=" ".join((entry.findtext(f"{ATOM}summary") or "").split()),
                             verified=True, checked_on=date.today().isoformat(), note=f"submitted {published[:10]}"))
    return out


def parse_arxiv(atom: str, ids: list[str]) -> dict[str, Reference]:
    """Entries of an arXiv API response, keyed by the requested identifier."""
    out = {}
    today = date.today().isoformat()
    for entry in ET.fromstring(atom).iter(f"{ATOM}entry"):
        url = (entry.findtext(f"{ATOM}id") or "").strip()
        title = " ".join((entry.findtext(f"{ATOM}title") or "").split())
        key = next((i for i in ids if url.rstrip("/").split("/abs/")[-1].split("v")[0] == i.split("v")[0]
                    or url.endswith(i)), None)
        if key is None or not title or title.lower() == "error":
            continue
        published = entry.findtext(f"{ATOM}published") or ""
        authors = [a.findtext(f"{ATOM}name") or "" for a in entry.iter(f"{ATOM}author")]
        out[key] = Reference(kind="arxiv", id=key, title=title, authors=authors,
                             year=int(published[:4]) if published[:4].isdigit() else None,
                             abstract=" ".join((entry.findtext(f"{ATOM}summary") or "").split()),
                             verified=True, checked_on=today)
    return out


def doi_lookup(refs: list[Reference]) -> dict[str, Reference]:
    """Crossref for the DOIs among ``refs`` (network)."""
    import requests
    out = {}
    for ref in (r for r in refs if r.kind == "doi"):
        response = requests.get(f"https://api.crossref.org/works/{ref.id}",
                                headers={"User-Agent": USER_AGENT}, timeout=60)
        if response.status_code != 200:
            continue
        message = response.json().get("message", {})
        parts = (message.get("issued", {}).get("date-parts") or [[None]])[0]
        out[ref.id] = Reference(kind="doi", id=ref.id, title=" ".join(message.get("title") or []),
                                authors=[f"{a.get('given', '')} {a.get('family', '')}".strip()
                                         for a in message.get("author", [])],
                                year=parts[0], verified=True, checked_on=date.today().isoformat())
    return out


def network_resolver(refs: list[Reference]) -> dict[str, Reference]:
    """arXiv and Crossref together (network)."""
    return {**arxiv_lookup(refs), **doi_lookup(refs)}


class ReferenceCache:
    """Confirmed references on disk, so each is fetched once."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or get_settings().data_dir / "references.json"
        self.entries = {k: Reference.model_validate(v) for k, v in
                        (json.loads(self.path.read_text()) if self.path.exists() else {}).items()}

    def save(self) -> None:
        """Write the confirmed references to the cache file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({k: v.model_dump() for k, v in self.entries.items()}, indent=1))


def verify(refs: list[Reference], resolver: Resolver | None = None, cache: ReferenceCache | None = None,
           claimed_titles: dict[str, str] | None = None) -> list[Reference]:
    """Each reference, confirmed or not, with the paper's own title and authors where confirmed."""
    known = cache.entries if cache else {}
    missing = [r for r in refs if r.id not in known]
    found: dict[str, Reference] = {}
    note = "not found"
    if missing:
        try:
            found = (resolver or network_resolver)(missing)
        except Exception as exc:  # noqa: BLE001 - no confirmation without an answer
            note = f"not checked: {type(exc).__name__}"
    if cache is not None and found:
        cache.entries.update(found)
        cache.save()
    out = []
    for ref in refs:
        confirmed = known.get(ref.id) or found.get(ref.id)
        if confirmed is None:
            out.append(ref.model_copy(update={"verified": False, "note": note}))
            continue
        claimed = (claimed_titles or {}).get(ref.id)
        how, why = identify(claimed, confirmed) if claimed else ("title", "")
        if how != "title":
            out.append(confirmed.model_copy(update={"verified": False, "note": why}))
            continue
        out.append(confirmed)
    return out


def scrub(text: str, refs: list[Reference]) -> str:
    """The text with every unverified identifier replaced by REMOVED."""
    for ref in refs:
        if not ref.verified:
            text = re.sub(rf"(?:arXiv:\s*)?{re.escape(ref.id)}(?:v\d+)?", REMOVED, text)
    return text


AUTHOR_YEAR = re.compile(r"[A-Z][\w\-’']+(?: and [A-Z][\w\-’']+)? et al\.?(?:,?\s*\(?(?:19|20)\d{2}[a-z]?\)?)?")
UNCITED = "[citation without an identifier removed]"


def clean(text: str, confirmed: list[Reference]) -> str:
    """Agent text fit for a report: every identifier not confirmed in ``confirmed`` removed (a link to it whole, its
    label with it: LT16-01), and every author–year citation."""
    allowed = {r.id for r in confirmed if r.verified}
    text = _links_removed(text, allowed)
    stray = [r.model_copy(update={"verified": False}) for r in find(text) if r.id not in allowed]
    return AUTHOR_YEAR.sub(UNCITED, scrub(text, stray))


def unverified_in(text: str, cache: ReferenceCache | None = None, resolver: Resolver | None = None) -> list[str]:
    """The gate's measure: identifiers in a final report that are not confirmed (bare, or as an arXiv or DOI link:
    LT16-01), and author–year citations."""
    checked = verify(find(text), resolver, cache)
    return [r.id for r in checked if not r.verified] + AUTHOR_YEAR.findall(text)
