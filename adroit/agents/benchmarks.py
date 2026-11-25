"""G11's literature-benchmark agent: a model's published benchmarks, extracted from the paper with their quotes and
checked deterministically (paid; opt-in).

The agent reads the paper (its text, page by page) and returns every number the authors computed for the model
that ADROIT can compare: Ωh² at a stated parameter point, a thermal mass, a thermal splitting, σ_SI at a stated
point. Each target carries its parameter point, its 1-based page, its location and a verbatim quote, as the zoo's
survey wrote them by hand.

**The check** (``quote_check``), as the zoo's quotes were checked on 2026-10-13: every number in the quote must
appear on the stated page, and the target's value must be one of the quote's numbers (in the paper's unit). A
target that fails is dropped, with the reason; ADROIT compares only what passes.
"""

from __future__ import annotations

import re
import unicodedata

from pydantic import Field

from adroit.agents.llm import StructuredLLM
from adroit.core.state import StrictModel

DEFAULT_MODEL = "claude-opus-5-5"
UNITS = {"cm2": 1.0, "cm^2": 1.0, "pb": 1e-36, "fb": 1e-39, "zb": 1e-45, "gev": 1.0, "tev": 1e3, "mev": 1e-3,
         "kev": 1e-6, "": 1.0, "%": 0.01, "percent": 0.01}
PERCENT = ("%", "percent")
QUANTITIES = ("omega_h2", "thermal_mass_gev", "thermal_splitting", "sigma_si_cm2")

SYSTEM = """You read a dark matter paper and extract the benchmark numbers its authors computed for one model, so
that another code can be compared with them. Return JSON for the Benchmarks schema: a list "targets", each with
- quantity: "omega_h2" (the relic density at a parameter point), "thermal_mass_gev" (the dark matter mass at which
  the relic density is the observed value), "thermal_splitting" (the relative mass splitting at which it is), or
  "sigma_si_cm2" (the spin-independent cross-section on a nucleon at a parameter point);
- value: the number exactly as printed; unit: as printed ("" for Ωh², "GeV" or "TeV" for a mass, "pb", "cm2",
  "zb" for a cross-section);
- at: the parameter point, the paper's own inputs with their values (empty for a stated thermal mass);
- page: the 1-based page of the PDF it is printed on (the text marks pages as "=== page N ===");
- location: table, figure or equation and row or column; quote: an excerpt that prints the value (it must contain
  the value and should contain the parameter values), copied character for character from the page text given
  below, as the text extraction prints it: never re-typeset it (no formula, fraction, power or symbol rewritten in
  your own notation; a display formula the extraction splits across lines is quoted as split, or the quote is the
  words and numbers around it).
Only numbers the authors printed for this model. Not a curve read by eye; not a number from another paper; not
an experimental limit. Return only the JSON object."""


class BenchmarkTarget(StrictModel):
    """One extracted target (module docstring)."""
    quantity: str
    value: float
    unit: str = ""
    at: dict[str, float | str] = Field(default_factory=dict)
    page: int
    location: str = ""
    quote: str


class Benchmarks(StrictModel):
    targets: list[BenchmarkTarget] = Field(default_factory=list)


def paged_text(pages: list[str]) -> str:
    """The paper's text with page markers (``pages`` in order, 1-based)."""
    return "\n".join(f"=== page {k} ===\n{text}" for k, text in enumerate(pages, start=1))


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    for a, b in (("−", "-"), ("–", "-"), ("×", "x"), (" ", " "), ("ﬁ", "fi"), ("ﬂ", "fl")):
        text = text.replace(a, b)
    return text


NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
SCIENTIFIC = re.compile(r"(\d+(?:\.\d+)?)\s*(?:(?:x|·|\*)\s*10\s*\^?\s*\{?\s*(-?)\s*(\d+)\s*\}?|\s10\s*\^?\s*\{?\s*(-)\s*(\d+)\s*\}?)")


def numbers(text: str) -> list[float]:
    """The numbers in a text, a × 10^b (in any of its printed forms) read as one number."""
    text = SCIENTIFIC.sub(lambda m: f" {m.group(1)}e{m.group(2) or m.group(4) or ''}{m.group(3) or m.group(5)} ",
                          _normalise(text))
    return [float(x) for x in NUMBER.findall(text)]


def _percentages(text: str) -> list[float]:
    """The numbers printed as percentages, as fractions."""
    return [float(x) / 100.0 for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", _normalise(text))]


def _same(x: float, y: float) -> bool:
    """Two printed numbers are the same number (relative tolerance; zero is only zero)."""
    return x == y if x == 0.0 or y == 0.0 else abs(x - y) <= 1e-9 * max(abs(x), abs(y))


def _unit(target: BenchmarkTarget) -> str:
    return target.unit.strip().lower().replace(" ", "")


ROW_SPAN = 600                  # characters: a table row's numbers, printed in their order within this span


def _in_order(quoted: list[float], window: str) -> bool:
    """The quote's numbers (two or more) printed in the window in the quote's order, within ``ROW_SPAN``
    characters: a table row whose cells the text extraction keeps in order but not verbatim."""
    found = [(m.start(), abs(float(m.group()))) for m in NUMBER.finditer(_normalise(window))]
    if len(quoted) < 2:
        return False
    for k, (start, value) in enumerate(found):
        if not _same(quoted[0], value):
            continue
        position, j = start, k
        for x in quoted[1:]:
            j = next((i for i in range(j + 1, len(found)) if _same(x, found[i][1])), None)
            if j is None or found[j][0] - start > ROW_SPAN:
                break
            position = found[j][0]
        else:
            return position - start <= ROW_SPAN
    return False


def quote_check(target: BenchmarkTarget, pages: list[str]) -> str:
    """Why the target fails the check, or "" (module docstring): the quote is on the stated page (or a neighbour),
    verbatim up to typesetting or as a table row (its numbers there in its order, ``_in_order``); every number of
    it is printed there; the value is one of the quote's numbers in its stated unit; every number of the parameter
    point is printed in the paper; and the unit is understood. The audit's AG-2 (G12): an absolute tolerance let a
    printed "0" match any tiny number, and a quote was never itself looked for."""
    from adroit.core import quotes
    if not 1 <= target.page <= len(pages):
        return f"page {target.page} is not in the paper"
    if _unit(target) not in UNITS:
        return f"the unit {target.unit!r} is not understood"
    # the stated page, or its neighbour: a table can straddle the break in the text extraction
    window = " ".join(pages[max(0, target.page - 2):target.page + 1])
    raw_signed = [abs(float(x)) for x in NUMBER.findall(_normalise(target.quote))]
    if not quotes.contains(window, target.quote) and not _in_order(raw_signed, window):
        return f"the quote is not on page {target.page}"
    on_page = [abs(float(y)) for y in NUMBER.findall(_normalise(window))]
    raw = [abs(float(x)) for x in NUMBER.findall(_normalise(target.quote))]       # the printed digits, unjoined
    quoted = numbers(target.quote)
    if not quoted:
        return "the quote holds no number"
    missing = [x for x in raw if not any(_same(x, y) for y in on_page)]
    if missing:
        return f"the quote's numbers {missing[:3]} are not on page {target.page}"
    # the value as printed: one of the quote's numbers (a percentage as a fraction where the unit is not a
    # percentage), or a mantissa times 10 to an exponent printed next to each other ("3 × 10 −26" broken apart)
    signed = [float(x) for x in NUMBER.findall(_normalise(target.quote))]
    joined = [a * 10.0 ** b for a, ten, b in zip(signed, signed[1:], signed[2:]) if ten == 10 and b == int(b)
              and abs(b) < 60] + [10.0 ** b for ten, b in zip(signed, signed[1:]) if ten == 10 and b == int(b)
                                  and abs(b) < 60]
    fractions = [] if _unit(target) in PERCENT else _percentages(target.quote)
    candidates = quoted + fractions + joined
    if not any(abs(target.value - c) <= 1e-6 * max(abs(target.value), 1e-300) for c in candidates):
        return f"the value {target.value:g} is not among the quote's numbers"
    paper = " ".join(pages)
    in_paper = [abs(float(y)) for y in NUMBER.findall(_normalise(paper))] + [abs(y) for y in numbers(paper)]
    for name, value in target.at.items():
        if isinstance(value, (int, float)) and not any(_same(abs(float(value)), y) for y in in_paper):
            return f"the parameter point's {name} = {value:g} is not printed in the paper"
    return ""


def in_adroit_units(target: BenchmarkTarget) -> float:
    """The value in the zoo's units: GeV, cm², dimensionless. A unit outside ``UNITS`` is refused (``quote_check``
    drops such a target first)."""
    unit = _unit(target)
    if unit not in UNITS:
        raise ValueError(f"the unit {target.unit!r} is not understood")
    return target.value * UNITS[unit]


class BenchmarkAgent:
    """A paper and a model → its checked benchmarks (module docstring)."""

    def __init__(self, llm: StructuredLLM, model: str = DEFAULT_MODEL) -> None:
        self.llm, self.model = llm, model

    def run(self, model_description: str, pages: list[str], run_id: str | None = None) -> tuple[list, list]:
        """(the targets that pass the check, [(target, why)] that fail)."""
        message = [{"role": "user", "content": f"The model:\n{model_description}\n\nThe paper:\n{paged_text(pages)}"}]
        found = self.llm.complete_structured(SYSTEM, message, Benchmarks, model=self.model, run_id=run_id,
                                             actor="benchmark_agent")
        kept, dropped = [], []
        for t in found.targets:
            why = quote_check(t, pages) if t.quantity in QUANTITIES else f"{t.quantity} is not compared"
            (dropped.append((t, why)) if why else kept.append(t))
        return kept, dropped
