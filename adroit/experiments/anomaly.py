"""Anomaly intake (DM14): a search with events, entered as a record that a person verifies.

Any direct-detection search that reports its events can be Track 2's input. It
is written as one YAML record in the schema of DM10's historical searches
(``AnomalyRecord``):
- the target, exposure and energy window;
- the event energies and the resolution;
- the expected background, with its uncertainty;
- the efficiency (points, a digitised figure, or a CSV from a digitiser);
- the halo the paper used;
- where each number comes from (``sources``), and who checked them
  (``verified_by``).

``check`` finds inconsistencies before any fit is made. A record with no
``verified_by`` is a draft: Path 2 refuses it unless asked to use unverified
records. ``RecordSearch`` turns a record into an experiment module, so a new
anomaly is a new file, not new code; Path 2 loads it by the name
``record:<path>``.

**A record's numbers are checked where they are calculated with** (``numerical_problems``): every number finite, the
window an interval, each event inside it, each source of the background's uncertainty non-negative, the background
bins and the efficiency curve valid. ``check`` reports them with its review notes (an unknown target, a resolution
wider than half the window, a halo outside its plausible range, no references, an efficiency not covering the window),
and ``RecordSearch``, which every calculation builds, refuses a record with any of them, from the curve it reads
itself. The auditor's input-boundary audit (IB-01, 2026-11-10) had found a negative uncertainty fitted as its absolute value
and an infinite one fitted and reported as "+inf%", while ``check`` passed the infinite one.

**A digitiser's CSV is read as written** (``read_curve``): a first line that is not two numbers is a header; every
later line must be two numbers, or it is named by its line; rows are put in order of energy, keeping the order of the
rows at one energy (a step); only a row repeating the one before it is dropped. The same audit (IB-02) had found a
step's left side dropped (``dict``), a ramp calculated instead (three times the events), and a malformed row skipped.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

import yaml
from pydantic import Field, ValidationError, model_validator

from adroit.core.state import StrictModel
from adroit.experiments.historical import HistoricalSearch

PREFIX = "record:"
HALO_RANGES = {"v0_km_s": (150.0, 300.0), "v_earth_km_s": (200.0, 280.0), "v_esc_km_s": (400.0, 700.0),
               "rho_gev_cm3": (0.2, 0.6)}


class Uncertainty(StrictModel):
    """The background count's uncertainty in events, by source; combined in quadrature."""

    plus: list[float]
    minus: list[float]


class Halo(StrictModel):
    """The halo the paper used: v₀, the detector's speed and v_esc (km/s), and the local density (GeV/cm³)."""
    v0_km_s: float = 220.0
    v_earth_km_s: float = 232.0
    v_esc_km_s: float = 544.0
    rho_gev_cm3: float = 0.3


class Curve(StrictModel):
    """An efficiency curve: ε at each recoil energy (keV)."""
    recoil_energy_kev: list[float]
    efficiency: list[float]


class Efficiency(StrictModel):
    """Exactly one of: points from the paper's text, a digitised figure in the package, or a digitiser's CSV."""

    points: Curve | None = None
    digitised: str = ""
    csv: str = ""                    # a two-column file (energy in keV, efficiency), beside the record
    note: str = ""

    @model_validator(mode="after")
    def _one(self) -> "Efficiency":
        if sum([self.points is not None, bool(self.digitised), bool(self.csv)]) != 1:
            raise ValueError("give the efficiency as exactly one of points, digitised or csv")
        return self


class AnomalyRecord(StrictModel):
    """One search with events (the schema of ``data/historical/*.yaml``)."""

    name: str
    target: str
    references: list[str] = Field(default_factory=list)
    exposure_kg_day: float = Field(gt=0)
    window_kev: tuple[float, float]
    events_kev: list[float]
    resolution_kev: float = Field(gt=0)
    resolution_note: str = ""
    background_events: float = Field(ge=0)
    background_note: str = ""
    background_uncertainty: Uncertainty | None = None
    background_shape: dict | None = None
    efficiency: Efficiency
    halo: Halo = Field(default_factory=Halo)
    halo_note: str = ""
    limit_method: str = ""
    quoted: list[dict] = Field(default_factory=list)
    collaboration_result: str = ""
    sources: dict[str, str] = Field(default_factory=dict)    # field → where in the paper it is given
    needs_person: list[str] = Field(default_factory=list)    # fields a draft could not fill from the text
    verified_by: str = ""                                    # who checked every number against the paper

    @model_validator(mode="after")
    def _background_bins(self) -> "AnomalyRecord":
        if self.background_shape is not None and "points" in self.background_shape:
            raw = self.background_shape["points"]
            check_background_bins(raw.get("edges_kev", []), raw.get("counts", []), self.window_kev)
        return self


def check_background_bins(edges: list[float], counts: list[float], window: tuple[float, float]) -> None:
    """Raise ValueError unless background bins increase, every count is positive and the bins cover the window
    (the intake's checks, now applied to every record; release audit minor: a ``record:`` file's bins were
    extended flat beyond their edges and zero counts allowed)."""
    if not all(_finite(x) for x in [*edges, *counts]):
        raise ValueError("background bins: every edge and count must be a finite number")
    if len(edges) != len(counts) + 1 or any(b <= a for a, b in zip(edges, edges[1:])) or any(n <= 0 for n in counts):
        raise ValueError("background bins must increase with positive counts")
    if not edges or edges[0] > window[0] or edges[-1] < window[1]:
        raise ValueError("background shape must cover the window")


def read_curve(path: Path) -> Curve:
    """A digitiser's two-column CSV (energy in keV, efficiency), read once (module docstring): a first line that is not
    two numbers is its header; any later line that is not is refused (ValueError) by its number; the rows in order of
    energy, those at one energy in the order written (a step); a row repeating the one before it dropped."""
    text = path.read_text()
    rows: list[tuple[float, float]] = []
    lines = [(n, line) for n, line in enumerate(text.splitlines(), 1) if line.strip()]
    for n, row in zip((n for n, _ in lines), csv.reader([line for _, line in lines],
                                                          delimiter="\t" if "\t" in text else ",")):
        try:
            if len(row) != 2:
                raise ValueError
            rows.append((float(row[0]), float(row[1])))
        except ValueError:
            if n == lines[0][0]:
                continue                                          # the header
            raise ValueError(f"{path.name}, line {n}: {','.join(row)!r} is not two numbers (energy in keV, "
                             "efficiency)") from None
    rows = sorted(rows, key=lambda r: r[0])                         # stable: a step keeps its order
    rows = [r for i, r in enumerate(rows) if i == 0 or r != rows[i - 1]]
    return Curve(recoil_energy_kev=[r[0] for r in rows], efficiency=[r[1] for r in rows])


FIELD_TEXT = {
    "name": "the search's name", "target": "the detector material as an element or compound (Xe, Ar, Ge, CaWO4)",
    "exposure_kg_day": "the exposure in kg·days", "window_kev": "the signal region's recoil-energy window [low, high] "
    "in keV", "events_kev": "the recoil energy of each candidate event, in keV",
    "resolution_kev": "the detector's energy resolution in keV (a positive number; the paper, or the detector's "
    "documentation, with a resolution_note saying where it comes from)",
    "background_events": "the expected background count in the signal region",
    "efficiency": "the efficiency, as exactly one of points, digitised or csv",
}


def _plain(error: dict, data: dict) -> str:
    """One validation error as a sentence a person can act on."""
    name = ".".join(str(x) for x in error["loc"]) or "record"
    field = str(error["loc"][0]) if error["loc"] else ""
    wanted = FIELD_TEXT.get(field, "")
    if error["type"] == "missing" or (field in data and data[field] in (None, "", [])):
        return f"{field or name}: not given yet; fill in {wanted or 'a value'}"
    if error["type"] in ("greater_than", "greater_than_equal"):
        bound = ">" if error["type"] == "greater_than" else "≥"
        limit = error["ctx"].get("gt", error["ctx"].get("ge"))
        return f"{name}: must be {bound} {limit:g}, but is {error['input']!r}" + (f" ({wanted})" if wanted else "")
    if error["type"] == "extra_forbidden":
        return f"{name}: not a field of an anomaly record (see adroit anomaly template)"
    return f"{name}: {error['msg'].removeprefix('Value error, ')}" + (f" ({wanted})" if wanted else "")


def read(path: Path) -> tuple[AnomalyRecord | None, list[str]]:
    """(the record, []) or (None, why it does not load yet, in plain language, one line per field)."""
    try:
        data = yaml.safe_load(Path(path).read_text())
    except yaml.YAMLError as error:
        return None, [f"the file is not readable YAML ({error})"]
    if not isinstance(data, dict):
        return None, ["the file is not a mapping of record fields (see adroit anomaly template)"]
    try:
        return AnomalyRecord.model_validate(data), []
    except ValidationError as error:
        return None, list(dict.fromkeys(_plain(e, data) for e in error.errors()))


def load(path: Path) -> AnomalyRecord:
    """A record from its YAML file."""
    return AnomalyRecord.model_validate(yaml.safe_load(Path(path).read_text()))


def _curve(record: AnomalyRecord, folder: Path | None) -> Curve | None:
    e = record.efficiency
    if e.points is not None:
        return e.points
    if e.csv:
        return read_curve((folder or Path.cwd()) / e.csv)
    from adroit.experiments import digitised
    table = digitised.load(e.digitised)
    return Curve(recoil_energy_kev=table["recoil_energy_kev"], efficiency=table["efficiency"])


def _efficiency_problems(curve: Curve, low: float, high: float, notes: bool = True) -> list[str]:
    """What makes an efficiency curve unusable; with ``notes``, also that it does not cover the whole window (zero is
    assumed outside it: a review note, not a refusal)."""
    e, eff = curve.recoil_energy_kev, curve.efficiency
    out = []
    if len(e) != len(eff) or len(e) < 2:
        return ["efficiency: needs at least two (energy, efficiency) points of equal number"]
    if not all(_finite(x) for x in [*e, *eff]):
        return ["efficiency: every energy and efficiency must be a finite number"]
    if any(b < a for a, b in zip(e, e[1:])):
        out.append("efficiency: the energies must not decrease (a repeated energy is a step)")
    if any(not 0.0 <= x <= 1.0 for x in eff):
        out.append("efficiency: values must lie in [0, 1]")
    if max(e) < low or min(e) > high:
        out.append("efficiency: the curve does not overlap the window")
    elif notes and (min(e) > low or max(e) < high):
        out.append("efficiency: the curve does not cover the whole window (zero is assumed outside it)")
    return out


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def numerical_problems(record: AnomalyRecord, curve: Curve | None) -> list[str]:
    """Why the record's numbers cannot be calculated with (module docstring), or []; ``curve``: its efficiency as the
    calculation reads it (None: not read). ``check`` reports them, and ``RecordSearch`` refuses them (IB-01)."""
    out = []
    numbers = {"exposure_kg_day": [record.exposure_kg_day], "window_kev": list(record.window_kev),
               "events_kev": record.events_kev, "resolution_kev": [record.resolution_kev],
               "background_events": [record.background_events],
               **{f"halo.{name}": [value] for name, value in record.halo.model_dump().items()}}
    u = record.background_uncertainty
    if u is not None:
        numbers.update({"background_uncertainty.plus": u.plus, "background_uncertainty.minus": u.minus})
    out += [f"{name}: every value must be a finite number" for name, values in numbers.items()
            if not all(_finite(x) for x in values)]
    low, high = record.window_kev
    if _finite(low) and _finite(high):
        if not 0 <= low < high:
            out.append(f"window: {record.window_kev} is not an interval of positive energies")
        outside = [e for e in record.events_kev if _finite(e) and not low <= e <= high]
        if outside:
            out.append(f"events: {outside} keV lie outside the window {low:g}-{high:g} keV")
    if u is not None and all(_finite(x) for x in u.plus + u.minus) and \
            (any(x < 0 for x in u.plus + u.minus) or math.sqrt(sum(x * x for x in u.minus)) > record.background_events):
        out.append("background uncertainty: negative, or a downward error larger than the background itself")
    if curve is not None and not out:
        out += _efficiency_problems(curve, low, high, notes=False)
    return out


def check(record: AnomalyRecord, folder: Path | None = None) -> list[str]:
    """Inconsistencies in a record, before any fit is made (an empty list: none found)."""
    from adroit.physics import targets
    out = numerical_problems(record, None)               # what a calculation refuses (IB-01), then the review notes
    low, high = record.window_kev
    try:
        targets.target(record.target)
    except (KeyError, ValueError):
        out.append(f"target: {record.target!r} is not an element or compound the system knows")
    if _finite(record.resolution_kev) and _finite(high - low) and record.resolution_kev > 0.5 * (high - low):
        out.append(f"resolution: {record.resolution_kev:g} keV is more than half the window")
    for name, (a, b) in HALO_RANGES.items():
        value = getattr(record.halo, name)
        if _finite(value) and not a <= value <= b:
            out.append(f"halo: {name} = {value:g} lies outside the plausible range {a:g}-{b:g}")
    if not record.references:
        out.append("references: none given")
    try:
        curve = _curve(record, folder)
    except (OSError, KeyError, ValueError) as error:
        return out + [f"efficiency: cannot be read ({error})"]
    return out + _efficiency_problems(curve, low, high)


def template() -> str:
    """A record to fill in, with every field explained."""
    return TEMPLATE


class RecordSearch(HistoricalSearch):
    """An experiment module made from a record (a file the user wrote, or a drafted and verified one)."""

    def __init__(self, record: AnomalyRecord, folder: Path | None = None, key: str = "record") -> None:
        data = record.model_dump(mode="json", exclude_none=True)
        curve = _curve(record, folder)
        if problems := numerical_problems(record, curve):     # what it calculates with, as it reads it (IB-01)
            raise ValueError(f"the anomaly record {record.name!r} cannot be calculated with: " + "; ".join(problems))
        data["efficiency"] = {"points": curve.model_dump()}
        super().__init__(key, data)
        self.anomaly = record

    @property
    def verified(self) -> bool:
        """Whether a person has checked the record (``verified_by`` is set)."""
        return bool(self.anomaly.verified_by.strip())

    def quoted_checks(self) -> list[dict]:
        """The paper's quoted numbers beside the module's values; none when the record quotes none."""
        return super().quoted_checks() if self.anomaly.quoted else []

    def background_on_grid(self):
        """Inline background bins, spread by the rule a digitised shape follows (``historical.shape_on_grid``: the
        shape restricted to the window, its exact integral there the record's count; BI-01)."""
        spec=self.anomaly.background_shape
        if spec is None or 'points' not in spec:
            return super().background_on_grid()
        from adroit.experiments.historical import shape_on_grid
        raw=spec['points']
        return shape_on_grid(raw['edges_kev'],raw['counts'],self.anomaly.background_events,self.anomaly.window_kev,
                             self.grid)

    @classmethod
    def from_name(cls, name: str) -> "RecordSearch":
        """``record:<path>`` → the module of the record in that file."""
        path = Path(name.removeprefix(PREFIX)).expanduser()
        return cls(load(path), path.parent, key=path.stem)


TEMPLATE = """\
# An anomaly record for ADROIT's Track 2 (DM14). Every number is the paper's; say where each comes from
# in `sources`, and mark anything you had to assume as "declared" in the notes. Check it with
#   adroit anomaly check THIS.yaml
# and set verified_by once a person has checked every number against the paper.
name: My search (2026)
target: Xe                       # an element or compound: Xe, Ar, Ge, Si, CaWO4, C3F8, ...
references: [arXiv:0000.00000]
exposure_kg_day: 1000.0          # before the selection; the efficiency carries the cuts
window_kev: [5.0, 50.0]          # nuclear-recoil energies
events_kev: [10.1, 22.4]         # each event's recoil energy, as listed
resolution_kev: 1.0              # a Gaussian width; if the paper gives none, declare one in resolution_note
resolution_note: ""
background_events: 0.5           # expected in the window
background_note: ""
background_uncertainty:          # optional; in events, by source (statistical, systematic, ...)
  plus: [0.2]
  minus: [0.1]
efficiency:                      # exactly one of the three forms
  points: {recoil_energy_kev: [5.0, 10.0, 50.0], efficiency: [0.2, 0.5, 0.5]}
  # csv: efficiency.csv          # a digitiser's two-column export, beside this file
halo: {v0_km_s: 220.0, v_earth_km_s: 232.0, v_esc_km_s: 544.0, rho_gev_cm3: 0.3}
sources:                         # field → where in the paper (section, table, figure)
  events_kev: ""
verified_by: ""                  # the person who checked every number against the paper
"""
