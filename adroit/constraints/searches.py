"""Searches for the portals' mediators and partners, and the CMB, as curated records (the portal library's part 2).

Each evaluator looks at one model at one point and returns an ``Outcome`` (excluded, allowed,
or undecided with the reason, which makes the point pending), or None where the search does
not apply. A record no person has verified gives an undecided outcome unless the caller asks
for unverified records, as everywhere else in ADROIT.

- **CMB** (Planck 2018, arXiv:1807.06209 eq. (89c)): p_ann = Σ_c f_eff,c(m) ⟨σv⟩_c / m below
  3.2 × 10⁻²⁸ cm³ s⁻¹ GeV⁻¹ (half the rate for a particle–antiparticle pair), with Slatyer's
  f_eff (arXiv:1506.03811) and the s-wave part of ⟨σv⟩ (from two speeds, ``s_wave``). A cascade
  channel without a tabulated f_eff is bounded by 0 ≤ f_eff ≤ 1; only a known-channel
  lower bound can exclude, and the bound is not a spectral likelihood.
- **Dark photons** (DarkCast's compilation of published limits on ε): visible searches on
  ε √BR(visible) (prompt searches always; displaced and beam-dump searches only when A′ → χχ̄ is
  closed, as they assume the visible lifetime), invisible searches on ε √BR(χχ̄).
- **Flavour**: B⁺ → K⁺ a for a pseudoscalar with Yukawa-like couplings (Dolan et al.
  arXiv:1412.5174 eqs. (2.11), (A.3)–(A.4)), against BaBar's B⁺ → K⁺νν̄ < 3.7 × 10⁻⁵ (arXiv:1303.7465)
  for a → χχ̄; visible a decays are undecided (lifetime-dependent searches, not yet records).
- **LHC dilepton resonances** (ATLAS, arXiv:1903.06248, 139 fb⁻¹): σ_fid B(Z′ → ℓℓ) of a B − L Z′
  against the limit at its relative width, with σ from our leading-order table normalised to
  ATLAS's Z′_SSM (``scripts/derive_records.py``).
- **LEP-II** contact interactions for B − L: M_Z′/g > 6.9 TeV (Heeck, arXiv:1408.6845 eq. (16)).
- **A coloured partner** (ATLAS, arXiv:2010.14293): the one-flavour squark exclusion in (m_φ, m_χ),
  for partners of u_R or d_R (φ → qχ always), with QCD production taken as a lower bound: χ exchange (∝ y⁴) and
  its interference with QCD are not computed (docs/benchmark_limits.md, "Known limitation").
- **The muon's g − 2** (2025 world average against the Standard Model, arXiv:2506.03069 and
  2505.21476): Δa_μ = 38(63) × 10⁻¹¹; a new contribution outside its 95% interval is excluded.
- **L_μ − L_τ**: BaBar's e⁺e⁻ → μ⁺μ⁻Z′(→ μ⁺μ⁻) (arXiv:1606.03501, via DarkCast) on g′ √(BR_μμ/BR_μμ
  without dark matter), and Belle II's invisible Z′ (arXiv:2212.03066) on g′ √BR(invisible).
- **The inert doublet at LEP** (Lundström et al. arXiv:0810.3924; the Z and W widths): excluded
  if m_H₀ < 80, m_A₀ < 100 and m_A₀ − m_H₀ > 8 GeV, if m_H± < 70 GeV, or if the Z or W can decay
  into the inert scalars.
- **The 2HDM+a at the LHC** (ATLAS, arXiv:2306.00641 Fig. 4a): the (m_a, m_A) exclusion of its
  full scenario 1a benchmark, including m_χ = 10 GeV, with a → χχ̄ open.
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from contextvars import ContextVar
from functools import lru_cache
from pathlib import Path

import numpy as np
import yaml
from scipy.integrate import quad

from adroit.core.state import StrictModel
from pydantic import Field

M_MU = 0.1056584
M_B, M_K, TAU_B_GEV = 5.27934, 0.493677, 6.582119e-25 / 1.638e-12
CMB_SPEEDS = (1e-2, 5e-3)


class Outcome(StrictModel):
    """One search at one point: excluded (True), allowed (False) or undecided (None, with the reason)."""

    name: str
    excluded: bool | None
    why: str = ""
    value: float | None = None          # what was compared with the limit (a ratio, or the coupling)
    ratio: float | None = None          # prediction / 95% limit, scaling as the signal (for the combined likelihood)
    delta_chi2: float | None = None     # χ²(point) − χ²(Standard Model), for a measurement (g − 2)
    confidence_level: float | None = 0.95
    source: str = ""
    statistical_construction: str = "published limit or contour; see source"
    native_excluded: bool | None = None
    native_ratio: float | None = None
    width_ratio: float | None = None
    reference_width_ratio: float | None = None
    coverage: dict = Field(default_factory=dict)
    highest_confidence_level: float | None = None   # mixed sources (``confidence_level`` None): the highest CL
    flags: list[str] = Field(default_factory=list)  # noted on the point without deciding it (e.g. a stronger model)

    def at95(self) -> Outcome:
        """The outcome at 95% CL, from a native one at another CL.

        An upper limit rises with the confidence level, so a prediction below a native limit at CL ≤ 95% is below
        the 95% limit too: "allowed" carries over. A native exclusion at CL ≥ 95% (BBN at 95.4%) carries over too.
        Anything else needs the source likelihood and is undecided. The native result is kept beside it, and the
        native ratio never enters the 95% combination.
        """
        if self.confidence_level == 0.95 or self.native_excluded is not None:   # at 95%, or converted already
            return self
        if self.excluded is None and (self.ratio is None or "95% comparison needs" in self.why):
            return self.model_copy(update={"ratio": None, "delta_chi2": None}) if self.ratio is not None else self
        cl = self.confidence_level if self.confidence_level is not None else self.highest_confidence_level
        level = f"{100 * self.confidence_level:g}%" if self.confidence_level else "mixed/unspecified CL"
        native = {"native_excluded": self.excluded, "native_ratio": self.ratio, "ratio": None, "delta_chi2": None}
        if self.excluded is False and cl is not None and cl <= 0.95:
            return self.model_copy(update={**native, "excluded": False, "why": "; ".join(filter(None, [
                self.why, f"allowed at its native {level}, hence at 95% (upper limits rise with CL)"]))})
        if self.excluded is True and self.confidence_level is not None and self.confidence_level >= 0.95:
            return self.model_copy(update={**native, "excluded": True, "why": "; ".join(filter(None, [
                self.why, f"excluded at its native {level}, hence at 95%"]))})
        return self.model_copy(update={**native, "excluded": None,
            "why": "; ".join(filter(None, [self.why, f"native {level}; 95% comparison needs the source likelihood"]))})


# --- records and data ------------------------------------------------------------------------------------

def _record(record_id: str):
    from adroit.constraints import database
    return database.record(record_id)


def exists(record_id: str) -> bool:
    """Whether the constraint database has a record with this id."""
    from adroit.constraints import database
    return any(r.id == record_id for r in database.records())


_UNVERIFIED_USED: ContextVar[set | None] = ContextVar("adroit_unverified_used", default=None)
# (the versions used, the objects admitted, the objects looked up, every version read): ``records_used``
_RECORDS_USED: ContextVar[tuple[dict, dict, dict, dict] | None] = ContextVar("adroit_records_used", default=None)


def admits(record, unverified: bool) -> bool:
    """Whether a constraint may use ``record``: a person verified it as it is, or the run enables unverified records,
    in which case the use is noted (``unverified_used``), so that a conclusion can say it depends on an unverified
    record, apart from the run's setting (the owner's direction D-4, 2026-10-25). Every record admitted, verified or
    not, is noted too, with the version the search holds (``records_used``): a claim is bound to the records that
    decided it (the auditor's CR recheck, CS-02, 2026-10-27), as they were used, not as they read when it is certified
    (the auditor's CS recheck, CT-01, 2026-10-28). Every search's record gate."""
    if not record.usable and not unverified:
        return False
    if (noted := _RECORDS_USED.get()) is not None:
        _note(*noted, record)
    if not record.usable and (used := _UNVERIFIED_USED.get()) is not None:
        used.add(record.id)
    return True


def _note(versions: dict, admitted: dict, looked: dict, reads: dict, record) -> None:
    """``record`` admitted: its version as admitted among those read (``_held``, once per object admitted), and among
    ``versions`` the one version read, or "" where there were two."""
    _held(admitted, reads, record)
    versions[record.id] = _one(reads[record.id])


def _held(objects: dict, reads: dict, record) -> None:
    """``record``'s version among those read (``reads``), taken once per record object (``objects`` keeps the object
    last seen: an object's own content does not change, and the data file it names is noted as it is read, ``_seen``).
    An admission and a look-up each keep their own (``records_used``), so a record looked up before its data file
    changes is still read again when it is admitted. Every version of a record admitted or read within one evaluation
    is kept: a second leaves it with none known (""), for good, even where the file returns to its first content
    (the auditor's CT recheck, CU-04, 2026-10-28)."""
    if objects.get(record.id) is record:
        return
    from adroit.constraints.review_identity import version
    objects[record.id] = record
    reads.setdefault(record.id, set()).add(version(record))


def consulted(record) -> None:
    """A record object looked up by its id (``database.record``), noted in the evaluation in force as ``_seen`` notes a
    data read: a search that admits a record and then reads its values may be given another version of it, from a
    records file changed meanwhile, and the claim is bound to the versions it read (the auditor's CU recheck, CV-02,
    2026-10-28: LEP's bounds were read as B after their admission as A, and the claim bound A)."""
    if (noted := _RECORDS_USED.get()) is None:
        return
    versions, _, looked, reads = noted
    _held(looked, reads, record)
    if record.id in versions:
        versions[record.id] = _one(reads[record.id])


def _seen(record_id: str, held: str) -> None:
    """A read of ``record_id``'s data in the version ``held`` (``_bundled``), noted in the evaluation in force (CU-04):
    beside the record's other versions, and among the versions used once the record is admitted (``_note``)."""
    if (noted := _RECORDS_USED.get()) is None:
        return
    versions, _, _, reads = noted
    reads.setdefault(record_id, set()).add(held)
    if record_id in versions:
        versions[record_id] = _one(reads[record_id])


def _one(seen: set[str]) -> str:
    """The one version seen, or "" where there were two (or it could not be taken)."""
    return next(iter(seen)) if len(seen) == 1 else ""


@contextmanager
def unverified_used():
    """The ids of the unverified records the searches use inside the block (``admits``)."""
    found: set[str] = set()
    token = _UNVERIFIED_USED.set(found)
    try:
        yield found
    finally:
        _UNVERIFIED_USED.reset(token)


@contextmanager
def records_used():
    """Every record the searches use inside the block, verified or not (``admits``): its id and the version they held
    (``review_identity.version``, and that of each data file as read, ``_bundled``; "" where it could not be taken, or
    where two versions were used)."""
    found: dict[str, str] = {}
    token = _RECORDS_USED.set((found, {}, {}, {}))
    try:
        yield found
    finally:
        _RECORDS_USED.reset(token)


@contextmanager
def records_read():
    """Every record read inside the block, by any reader (admitted, ``admits``; looked up by id, ``database.record``;
    its data file read, ``_bundled``), with the one version read: "" where two were, or where the record differs from
    it when the block ends (``confirmed``). The dict is filled when the block ends. For a producer outside the scan,
    whose numbers rest on every record it read, and which keeps these versions with them (the auditor's CV recheck, CW-02,
    2026-10-30: the exclusion's telescope limits, computed from a curve read as B between A at both ends, were saved
    and exported as A's)."""
    found: dict[str, str] = {}
    noted: tuple[dict, dict, dict, dict] = ({}, {}, {}, {})
    token = _RECORDS_USED.set(noted)
    try:
        yield found
    finally:
        _RECORDS_USED.reset(token)
        found.update(confirmed({rid: _one(seen) for rid, seen in noted[3].items()}))


def confirmed(versions: dict[str, str]) -> dict[str, str]:
    """``versions`` (``records_used``) after an evaluation, sorted, with "" for each record whose version now differs
    from the one admitted: its data file may have changed between its admission and its read, so which version the
    evaluation read is not known (CT-01). Each read notes the version it read (``_bundled``); this check is the
    bracket's other end, for a change that lasts."""
    from adroit.constraints import database
    from adroit.constraints.review_identity import version
    try:
        now = {r.id: r for r in database.records()}
    except (OSError, ValueError, TypeError, AttributeError, yaml.YAMLError):
        now = {}
    return {rid: v if v and rid in now and version(now[rid]) == v else "" for rid, v in sorted(versions.items())}


def _blocked(name: str, record_id: str, unverified: bool) -> Outcome | None:
    """An undecided outcome if the record may not be used, its record's id as its source, so that the evidence names
    the record a person must verify (the batch audit's B20-11: it was in the prose only)."""
    record = _record(record_id)
    if admits(record, unverified):
        return None
    return Outcome(name=name, excluded=None, why=f"its record ({record.id}) awaits a person's verification",
                   source=record.id)


def _bundled(record_id: str) -> dict:
    """A record's data file as one read (``review_identity.snapshot``: read again whenever the file changes), the
    version of exactly what was read noted in the evaluation in force (``_seen``). The values a search uses and the
    version its claim is bound to come from the same read: a cache kept by the record's id alone had gone on giving a
    changed file's old contents (CT-01), and a fingerprint taken apart from the read can name a version the search
    never read (the auditor's CT recheck, CU-01 and CU-04, 2026-10-28)."""
    from adroit.constraints import database
    from adroit.constraints.review_identity import snapshot
    data, held = snapshot(database.record(record_id))
    _seen(record_id, held)
    return data


def _forget() -> None:
    """Every data file read again (tests change them)."""
    from adroit.constraints import review_identity
    review_identity._data.cache_clear()
    review_identity._fingerprint.cache_clear()


_bundled.cache_clear = _forget


def _tool(name: str) -> Path | None:
    from adroit.external import fetch
    try:
        return fetch.locate(name)
    except KeyError:
        return None


class DarkCastLimit(StrictModel):
    """One DarkCast limit, in the format DarkCast itself reads it with (``darkcast.Limit``; the owner's record review,
    2026-10-13: ADROIT's reader had taken every file as coupling boundaries): either boundaries in the coupling, a
    lower one and, for a beam dump's closed region, an upper one (``bands``), or a map of r = the observed limit on the
    yield over the predicted yield on an (m, ε) grid, excluded where r < 1 (``grid``, ``rvalues``; LHCb's displaced
    search). 1e5 marks no limit at a mass."""

    model_config = {"arbitrary_types_allowed": True}
    masses: list[float]
    bands: list[tuple[list[float], list[float] | None]] = Field(default_factory=list)
    grid: list[float] = Field(default_factory=list)
    rvalues: list[list[float]] = Field(default_factory=list)

    @property
    def is_map(self) -> bool:
        """Whether this limit is an r-value map rather than coupling boundaries."""
        return bool(self.grid)


def _darkcast_module():
    import sys
    import warnings
    folder = _tool("DarkCast")
    if folder is None:
        raise FileNotFoundError("DarkCast is not in the tools folder (adroit setup --fetch)")
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)     # its bibtex strings carry LaTeX backslashes
        import darkcast
    return darkcast


@lru_cache(maxsize=64)
def darkcast(stem: str) -> DarkCastLimit:
    """A DarkCast limit, read by DarkCast's own ``Limit`` (which tells boundaries from r-value maps); a format it does
    not define is refused rather than guessed."""
    import warnings
    module = _darkcast_module()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        bounds = module.Limit(stem).bounds
    if set(bounds) == {"rvals"}:
        r = bounds["rvals"]
        masses, grid = [float(x) for x in r.axes[0]], [float(x) for x in r.axes[1]]
        values = np.asarray(r.vals, dtype=float)
        if values.size != len(masses) * len(grid):
            raise ValueError(f"DarkCast's {stem}: an r-value map that is not a full (m, ε) grid")
        return DarkCastLimit(masses=masses, grid=grid, rvalues=values.reshape(len(masses), len(grid)).tolist())
    if set(bounds) not in ({"lower"}, {"lower", "upper"}):
        raise ValueError(f"DarkCast's {stem}: bounds {sorted(bounds)} are neither boundaries nor an r-value map")
    lower = bounds["lower"]
    masses, low = [float(x) for x in lower.axes[0]], [float(x) for x in lower.vals]
    high = None
    if "upper" in bounds:
        upper = bounds["upper"]
        high = [float(x) for x in np.exp(np.interp(np.log(masses), np.log(np.asarray(upper.axes[0], dtype=float)),
                                                   np.log(np.asarray(upper.vals, dtype=float))))]
    return DarkCastLimit(masses=masses, bands=[(low, high)])


DARKCAST_RECORD = "darkcast-dark-photon"


def darkcast_info(stem: str) -> dict:
    """What a DarkCast search's own paper states (the data file of the record ``DARKCAST_RECORD``,
    data/darkcast_searches.yaml, with quotes and pages): its name, reference, kind of signal, confidence level (None if
    unstated) and mass resolution. Read as the record's data (``_bundled``), so a search applies the confidence level
    and resolution of the version its claim is bound to (the auditor's CU recheck, CV-01, 2026-10-28: kept for the process,
    a changed resolution went on admitting an exclusion that a fresh process leaves pending, while the claim bound the
    changed file)."""
    return _bundled(DARKCAST_RECORD)["searches"][stem]


def _map_value(limit: DarkCastLimit, m: float, coupling: float) -> float | None:
    """r at (m, ε), interpolated bilinearly in (log m, log ε) of log r; None outside the map's grid."""
    from scipy.interpolate import RegularGridInterpolator
    masses, grid = np.asarray(limit.masses), np.asarray(limit.grid)
    if not (masses[0] <= m <= masses[-1] and grid[0] <= coupling <= grid[-1]):
        return None
    table = np.log(np.maximum(np.asarray(limit.rvalues), 1e-300))
    value = RegularGridInterpolator((np.log(masses), np.log(grid)), table)([[math.log(m), math.log(coupling)]])[0]
    return float(math.exp(value))


def f_eff_table():
    """Slatyer's f_eff(m) (feff_PPPC_3keV.dat): masses, and a column per channel (header split on runs of spaces)."""
    import re

    import numpy as np
    folder = _tool("Slatyer f_eff")
    if folder is None:
        return None
    lines = (folder / "feff_PPPC_3keV.dat").read_text().splitlines()
    names = [x.replace(" ", "") for x in re.split(r"\s{2,}", lines[0].strip())][1:]
    rows = np.array([[float(x) for x in line.split()] for line in lines[1:] if line.strip()])
    if rows.shape[1] != len(names) + 1:
        raise ValueError("the f_eff file's header does not match its columns")
    return rows[:, 0], names, rows[:, 1:]


def _injection_table():
    """Slatyer's f_eff of e± and of photons injected at energy E (feff_3keV.dat): log₁₀(E/eV), f_e, f_γ; the file as it
    is now (``file_reads.stamp``: a replaced table is read again, BI-02)."""
    from adroit.core.file_reads import stamp
    folder = _tool("Slatyer f_eff")
    if folder is None:
        return None
    return _injection_rows(*stamp(folder / "feff_3keV.dat"))


@lru_cache(maxsize=4)
def _injection_rows(path: str, size: int, mtime: int, ctime: int):
    rows = np.loadtxt(path, comments="#", skiprows=1)
    return rows[:, 0], rows[:, 1], rows[:, 2]


def injection_f(kind: str, energy_gev) -> np.ndarray:
    """f_eff of an e⁺e⁻ pair ("e") or of photons ("gamma") injected at ``energy_gev`` each."""
    log_e, f_e, f_g = _injection_table()
    values = f_e if kind == "e" else f_g
    return np.interp(np.log10(np.maximum(np.asarray(energy_gev, dtype=float), 1e-9) * 1e9), log_e, values)


def muon_f_eff(m: float) -> float:
    """f_eff of χχ → μ⁺μ⁻ at mass m: each muon (energy m) decays to an electron with the Michel spectrum
    2x²(3 − 2x), x = 2E*/m_μ, isotropic, boosted to the lab; the electron's energy is deposited with f_e(E)
    and the neutrinos' is lost. Reproduces Slatyer's μ⁺μ⁻ value at 5 GeV to 2% (0.182 against 0.185)."""
    gamma = m / M_MU
    beta = math.sqrt(max(1.0 - 1.0 / gamma ** 2, 0.0))
    xs = np.linspace(1e-4, 1.0, 300)
    total = 0.0
    for x in xs:
        rest = x * M_MU / 2.0
        energies = np.linspace(gamma * rest * (1.0 - beta), gamma * rest * (1.0 + beta), 40)
        span = energies[-1] - energies[0]
        mean = np.trapezoid(injection_f("e", energies) * energies, energies) / span if span > 0 else 0.0
        total += 2.0 * x * x * (3.0 - 2.0 * x) * mean
    return total * (xs[1] - xs[0]) / m


def f_eff_low_mass(m: float) -> dict[str, float] | None:
    """f_eff below Slatyer's 5 GeV table: e⁺e⁻ and γγ exactly, μ⁺μ⁻ from the Michel spectrum."""
    if _injection_table() is None or m < M_MU:
        return None
    out = {"e+e-": float(injection_f("e", m)), "gammagamma": float(injection_f("gamma", m))}
    out["mu+mu-"] = float(muon_f_eff(m))
    return out


def _band_value(masses: np.ndarray, values: np.ndarray, m: float) -> float | None:
    """A band edge at m, interpolated in log–log between neighbours that both hold a limit."""
    i = int(np.searchsorted(masses, m))
    if i == 0 or i >= len(masses):
        return None
    a, b = values[i - 1], values[i]
    if not (0 < a < 1e4 and 0 < b < 1e4):
        return None
    t = (math.log(m) - math.log(masses[i - 1])) / (math.log(masses[i]) - math.log(masses[i - 1]))
    return math.exp(math.log(a) + t * (math.log(b) - math.log(a)))


def darkcast_excludes(stem: str, m: float, coupling: float) -> bool | None:
    """Whether a DarkCast limit excludes the coupling at mass m; None outside its masses (or its map's ε grid)."""
    limit = darkcast(stem)
    if limit.is_map:
        r = _map_value(limit, m, coupling)
        return None if r is None else r < 1.0
    masses = np.asarray(limit.masses)
    if not masses[0] <= m <= masses[-1]:
        return None
    for lower, upper in limit.bands:
        lower, upper = np.asarray(lower), None if upper is None else np.asarray(upper)
        low = _band_value(masses, lower, m)
        if low is None:
            continue
        high = math.inf if upper is None else _band_value(masses, upper, m)
        if high is not None and low < coupling < high:
            return True
    return False


def darkcast_ratio(stem: str, m: float, coupling: float) -> float | None:
    """(coupling / limit)² of a one-sided DarkCast limit at m (the signal scales as the coupling squared), or 1/r of
    an r-value map (predicted over the limit); None for a two-sided (beam-dump) band, which enters the combination as
    a cut."""
    limit = darkcast(stem)
    if limit.is_map:
        r = _map_value(limit, m, coupling)
        return None if r is None else 1.0 / r
    masses, bands = np.asarray(limit.masses), limit.bands
    if len(bands) != 1 or bands[0][1] is not None or not masses[0] <= m <= masses[-1]:
        return None
    low = _band_value(masses, np.asarray(bands[0][0]), m)
    return None if low is None else (coupling / low) ** 2


def interpolate(points: list[list[float]], x: float) -> float | None:
    """y(x) of a curve, linear in log–log; None outside it."""
    xs, ys = np.array([p[0] for p in points]), np.array([p[1] for p in points])
    if not xs[0] <= x <= xs[-1]:
        return None
    return float(np.exp(np.interp(math.log(x), np.log(xs), np.log(ys))))


# --- formulas ------------------------------------------------------------------------------------------------

def muon_g2_vector(g: float, m_zp: float) -> float:
    """Δa_μ from a neutral vector with vector coupling g to the muon:
    (g²/4π²) ∫₀¹ x²(1 − x)/[x² + (1 − x) m_Z′²/m_μ²] dx (→ g²/8π² for a light Z′)."""
    r = (m_zp / M_MU) ** 2
    integral = quad(lambda x: x * x * (1.0 - x) / (x * x + (1.0 - x) * r), 0.0, 1.0, limit=200)[0]
    return g * g / (4.0 * math.pi ** 2) * integral


def muon_g2_axial(g_a: float, m_v: float) -> float:
    """Δa_μ from a neutral vector with axial coupling g_A to the muon, L ⊃ g_A V_μ μ̄γ^μγ⁵μ (Jegerlehner & Nyffeler,
    Phys. Rept. 477 (2009) 1, eq. (263)): (g_A²/4π²) λ² ½∫₀¹ [2x(1 − x)(x − 4) − 4λ²x³]/[(1 − x)(1 − λ²x) + λ²x] dx,
    λ = m_μ/m_V; negative, → −5g_A²m_μ²/(12π²m_V²) for a heavy vector, and growing as 1/m_V² for a light one (its
    longitudinal mode). The vector part is ``muon_g2_vector``; for real couplings the two add."""
    lam2 = (M_MU / m_v) ** 2
    integral = quad(lambda x: (2.0 * x * (1.0 - x) * (x - 4.0) - 4.0 * lam2 * x ** 3)
                    / ((1.0 - x) * (1.0 - lam2 * x) + lam2 * x), 0.0, 1.0, limit=200)[0]
    return g_a * g_a / (4.0 * math.pi ** 2) * lam2 * 0.5 * integral


def muon_g2_scalar_partner(y: float, m_phi: float, m_chi: float) -> float:
    """Δa_μ from a neutral fermion χ and a charged scalar φ with the chiral coupling y φ* χ̄ P_R μ:
    −(y² m_μ²/16π²) ∫₀¹ x²(1 − x)/[x m_φ² + (1 − x) m_χ² − x(1 − x) m_μ²] dx (negative; no chirality flip)."""
    integral = quad(lambda x: x * x * (1.0 - x) / (x * m_phi ** 2 + (1.0 - x) * m_chi ** 2 - x * (1.0 - x) * M_MU ** 2),
                    0.0, 1.0, limit=200)[0]
    return -y * y * M_MU ** 2 / (16.0 * math.pi ** 2) * integral


def b_to_k_pseudoscalar(m_a: float, g_y: float, h_per_gy: float, f0: float, pole_gev2: float,
                        mb_minus_ms: float) -> float:
    """BR(B⁺ → K⁺ a) for Yukawa-like couplings g_Y (Dolan et al. eqs. (A.3)–(A.4), |h^S_sb| = h g_Y)."""
    if m_a >= M_B - M_K:
        return 0.0
    lam = (M_B ** 2 - M_K ** 2 - m_a ** 2) ** 2 - 4.0 * M_K ** 2 * m_a ** 2
    form = f0 / (1.0 - m_a ** 2 / pole_gev2)
    width = math.sqrt(lam) * form ** 2 * ((M_B ** 2 - M_K ** 2) / mb_minus_ms) ** 2 * (h_per_gy * g_y) ** 2 \
        / (16.0 * math.pi * M_B ** 3)
    return width / TAU_B_GEV


ALPHA_0 = 1.0 / 137.035999          # α at q² = 0: the two photons are on shell
LOOP_MESONS = {"u": 0.13957, "d": 0.13957, "s": 0.493677}  # Dolan et al.'s τ_u = τ_d = m_a²/4m_π², τ_s = m_a²/4m_K²


def pseudoscalar_loop(tau: complex | float) -> complex:
    """F_A(τ) of Dolan et al. (arXiv:1412.5174) eq. (B.3), τ = m_a²/4m_f²: 2 arcsin²(√τ)/τ for τ ≤ 1, and
    −(1/2τ)[log((1 + √(1 − 1/τ))/(1 − √(1 − 1/τ))) − iπ]² above; 2 for a heavy fermion (τ → 0)."""
    if tau <= 0:
        return complex(2.0)
    if tau <= 1.0:
        return complex(2.0 * math.asin(math.sqrt(tau)) ** 2 / tau)
    root = math.sqrt(1.0 - 1.0 / tau)
    return -0.5 / tau * (math.log((1.0 + root) / (1.0 - root)) - 1j * math.pi) ** 2


def pseudoscalar_photon_width(m_a: float, couplings: dict[str, float]) -> float:
    """Γ(a → γγ) in GeV at one loop, Dolan et al. eq. (B.2): α² m_a³/(256π³) |Σ_f N_c Q_f² (g_f/m_f) F_A(τ_f)|², for
    a pseudoscalar with L ⊃ −i g_f a f̄γ⁵f (``couplings``: g_f by fermion name, as ``spin1.FERMIONS`` names them).
    m_f is each fermion's kinematic mass (``feynman.SM_FERMIONS``), as in its loop, except that u, d and s take
    the π's and K's masses in τ (Dolan et al.'s Appendix B: with the current masses their loops would be wrong;
    their g_f/m_f stays the coupling over the fermion's own mass)."""
    from adroit.model_building.feynman import SM_FERMIONS
    total = 0j
    for f in SM_FERMIONS:
        g = couplings.get(f.name, 0.0)
        if g == 0.0 or f.mass <= 0:
            continue
        loop = LOOP_MESONS.get(f.name, f.mass)
        colours = 3 if f.colour == "3" else 1
        total += colours * f.charge ** 2 * g / f.mass * pseudoscalar_loop(m_a ** 2 / (4.0 * loop ** 2))
    return ALPHA_0 ** 2 * m_a ** 3 / (256.0 * math.pi ** 3) * abs(total) ** 2


def s_wave(cls, p) -> dict[str, float]:
    """⟨σv⟩ at v → 0 by channel (cm³/s): a class's own rate during recombination where it gives one (a Sommerfeld-
    enhanced rate, which σv = a + b v² does not describe), else σv = a + b v² from two small speeds (p-wave channels
    drop out), where no annihilation pole's velocity scale lies below them (``velocity_scales``) and it holds at
    ``CMB_CHECK`` too. Otherwise the rate where σv = a + b v² holds again far below (``_low_speed``). Raises
    CMBUnresolved where it does not."""
    own = cls.cmb_sigma_v(p) if hasattr(cls, "cmb_sigma_v") else None
    if own is not None:
        return own
    scales = velocity_scales(cls, p)
    fast, slow = (cls.sigma_v_today(p, v) for v in CMB_SPEEDS)
    out = {}
    for name in fast:
        a = (4.0 * slow.get(name, 0.0) - fast[name]) / 3.0
        if a > 1e-3 * max(fast[name], 1e-300):
            out[name] = a
    if not scales or scales[0] >= CMB_STRUCTURE:
        fast_total, slow_total = sum(fast.values()), sum(slow.values())
        b = (fast_total - slow_total) / (CMB_SPEEDS[0] ** 2 - CMB_SPEEDS[1] ** 2)
        expected = (4.0 * slow_total - fast_total) / 3.0 + b * CMB_CHECK ** 2      # every channel's a, and b v²
        if _flat(sum(cls.sigma_v_today(p, CMB_CHECK).values()), expected):
            return out
    return _low_speed(cls, p, scales)


# The audit loop's AL6-02 (the auditor, 2026-11-17): σv = a + b v² from v = 0.01 and 0.005 had been taken as the rate during
# recombination whatever σv did below them; near a narrow pole at the threshold it rises (an ALP portal at m_a = 2m_χ:
# 4.8 × 10⁻²⁶ cm³/s, allowed, where σv flattens out at 6.0 × 10⁻²⁰, excluded). Its repair checked the reduction at
# CMB_CHECK and followed the descent to the first two speeds that agreed. AL7-01 (the auditor's cycle 7): agreement at one
# speed, or a locally flat pair, does not certify the limit. A second, narrower pole (b at 200 GeV beside a at 300 GeV)
# left σv = a + b v² holding at 10⁻³ and rose 170-fold below 10⁻⁵, the CMB allowing where it excludes; and a v⁴ term
# with a rise below took an early flat pair. Each annihilation pole now sets a velocity scale: the two speeds' reduction
# stands only where every scale lies above the probes, and otherwise the rate is σv = a + b v² where that holds again on
# three successive speeds at least CMB_BELOW times below every scale, agreeing with the lowest speed that has a rate
# (which covers a plateau and a p-wave rate falling to zero alike). AL7-05: zero at two successive speeds the amplitudes
# resolve (at or above CMB_RESOLVED) is a closed final state, whose rate is zero. A tree route reads zero below its
# amplitudes' floor (u = v²/8 ≤ 10⁻¹², v ≲ 2.8 × 10⁻⁶), and such a zero is never taken as a rate.
CMB_CHECK = 1e-3
CMB_DESCENT = (1e-3, 3e-4, 1e-4, 3e-5, 1e-5, 3e-6, 1e-6, 3e-7, 1e-7)
CMB_FLAT = 1e-2
CMB_STRUCTURE = 0.03          # a pole whose velocity scale is below this changes σv below the two probes
CMB_BELOW = 3.0               # the speeds the rate is read at lie this far below every pole's velocity scale
CMB_RESOLVED = 3e-6           # the lowest speed of the descent every route's amplitudes resolve (u = v²/8 > 10⁻¹²)


class CMBUnresolved(ArithmeticError):
    """σv near v = 0 is not resolved by the lowest speed searched: the rate during recombination is not computed."""


def _flat(a: float, b: float) -> bool:
    """Two rates the same within ``CMB_FLAT`` (both zero included)."""
    return abs(a - b) <= CMB_FLAT * max(abs(a), abs(b))


def velocity_scales(cls, p) -> list[float]:
    """Each annihilation pole's velocity scale, smallest first: the relative speed at which s − M² changes by the pole's
    distance from the threshold or its width (s ≈ 4m² + m²v²), √max(|4m² − M²|, MΓ)/m. The poles are the class's
    ``annihilation_poles`` (the dark matter pair's own s-channel), else its ``resonances``."""
    poles = (cls.annihilation_poles(p) if hasattr(cls, "annihilation_poles") else
             cls.resonances(p) if hasattr(cls, "resonances") else [])
    m = getattr(p, "m_chi", None)
    if not poles or not m:
        return []
    return sorted(math.sqrt(max(abs(4.0 * m * m - mass * mass), mass * width)) / m for mass, width in poles
                  if mass > 0)


def _low_speed(cls, p, scales: list[float]) -> dict[str, float]:
    """The rates by channel at v → 0 from the descent (the note above ``CMB_CHECK``)."""
    rates = [cls.sigma_v_today(p, v) for v in CMB_DESCENT]
    totals = [sum(r.values()) for r in rates]
    for i in range(len(CMB_DESCENT) - 1):              # closed below a speed the amplitudes resolve (AL7-05)
        if CMB_DESCENT[i + 1] >= CMB_RESOLVED and not any(totals[i:]):
            return {}
    lowest = max((i for i, t in enumerate(totals) if t > 0.0), default=None)
    reach = scales[0] / CMB_BELOW if scales else math.inf
    for i in range(len(CMB_DESCENT) - 2):
        (u, v, w), (t0, t1, t2) = CMB_DESCENT[i:i + 3], totals[i:i + 3]
        if u > reach or min(t0, t1, t2) <= 0.0:
            continue
        b = (t1 - t2) / (v * v - w * w)                 # σv = a + b v² from the two lower speeds
        a = t2 - b * w * w
        if not _flat(t0, a + b * u * u):
            continue
        if lowest > i + 2 and not _flat(totals[lowest], a + b * CMB_DESCENT[lowest] ** 2):
            continue
        out = {}
        for name, low in rates[i + 2].items():
            mid = rates[i + 1].get(name, 0.0)
            share = (v * v * low - w * w * mid) / (v * v - w * w)
            if share > 1e-3 * max(mid, 1e-300):
                out[name] = share
        return out
    below = (f"; a resonance's velocity scale ({scales[0]:.2g}) lies within reach of the lowest speed with a rate "
             f"({CMB_DESCENT[lowest]:g})" if scales and lowest is not None and reach < CMB_DESCENT[lowest] else "")
    found = (f"σv has not flattened out by v = {CMB_DESCENT[lowest]:g}, the lowest speed with a rate (σv = a + b v² "
             f"does not hold within {100 * CMB_FLAT:g}% on three successive speeds below every pole's velocity scale)"
             if lowest is not None else "σv is zero at every speed searched, below the amplitudes' resolution")
    raise CMBUnresolved(f"σv near v = 0 is not resolved: σv = a + b v² from v = {CMB_SPEEDS[0]:g} and "
                        f"{CMB_SPEEDS[1]:g} does not describe it below them (as near a narrow resonance at the "
                        f"threshold), and {found}{below}")
