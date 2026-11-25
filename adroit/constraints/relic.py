"""The thermal relic density of dark matter (DM7).

Standard freeze-out (Gondolo & Gelmini, Nucl. Phys. B360 (1991) 145):

    dY/dx = −√(π/45) M_Pl g*^{1/2}(T) m ⟨σv⟩_eff(x) (Y² − Y_eq²) / x² ,   x = m/T ,

with Y = n/s the dark matter number per entropy (χ and χ̄ together for
Dirac dark matter), Y_eq = 45 g x² K₂(x) / (4π⁴ h_eff), g = 4, and
⟨σv⟩_eff = ⟨σv⟩/2 (each χχ̄ annihilation removes two of the n particles,
at a rate ⟨σv⟩ n²/4). The thermal average is the exact relativistic one,

    ⟨σv⟩ = 8x/K₂(x)² ∫₀^∞ du σ(s) u(2 + u)(1 + u)² K₁(2x(1 + u)) ,   √s = 2m(1 + u) ,

which follows an s-channel resonance through its Breit–Wigner. Today,
Ωh² = m Y₀ s₀ / (ρ_c/h²), with s₀ = 2891.2 cm⁻³ and ρ_c/h² = 1.05375 × 10⁻⁵ GeV cm⁻³.

**Degrees of freedom.** g_eff(T) = g*ρ and h_eff(T) = g*s are Saikawa & Shirai's
Standard Model equation of state (arXiv:1803.01038, JCAP 05 (2018) 035), through
their fitting functions (their Appendix C, coefficients as printed): lattice QCD
across the crossover, the perturbative matching above it, and the hadron gas,
muons, electrons and the neutrinos' decoupling below. They replace the ideal gas
with a tanh step at 160 MeV (until 2026-10-19), which lay up to ~15% above the
lattice at T ≲ 0.5 GeV: Ωh² moves by up to ~5% above 10 GeV and more below
(``docs/relic_low_mass.md``). The table covers 1 MeV–10 TeV; below 1 MeV it is
held (A06: ``thermal_history_reason``).
"""

from __future__ import annotations

import contextvars
import hashlib
import io
import math
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Callable, NamedTuple

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.special import kve

from adroit.constraints import eos_reads
from adroit.external import fetch

M_PLANCK_GEV = 1.220890e19
S0_PER_CM3 = 2891.2
RHO_CRIT_H2_GEV_CM3 = 1.05375e-5
OMEGA_PER_MY = S0_PER_CM3 / RHO_CRIT_H2_GEV_CM3      # Ωh² = OMEGA_PER_MY × m Y₀
OBSERVED_OMEGA_H2 = 0.12
T_QCD_GEV, T_QCD_WIDTH_GEV = 0.160, 0.020

# (name, mass GeV, internal degrees of freedom, +1 fermion / −1 boson)
_ELECTROWEAK = [("photon", 0.0, 2, -1), ("neutrinos", 0.0, 6, 1), ("e", 0.000511, 4, 1),
                ("mu", 0.10566, 4, 1), ("tau", 1.77686, 4, 1), ("W", 80.37, 6, -1),
                ("Z", 91.1876, 3, -1), ("h", 125.25, 1, -1)]
_PARTONS = [("gluon", 0.0, 16, -1), ("u", 0.0022, 12, 1), ("d", 0.0047, 12, 1),
            ("s", 0.093, 12, 1), ("c", 1.27, 12, 1), ("b", 4.18, 12, 1), ("t", 172.5, 12, 1)]
_HADRONS = [("pi+-", 0.13957, 2, -1), ("pi0", 0.13498, 1, -1), ("K+-", 0.49368, 2, -1),
            ("K0", 0.49761, 2, -1), ("eta", 0.54786, 1, -1), ("rho", 0.77526, 9, -1),
            ("omega", 0.78266, 3, -1), ("K*", 0.8917, 12, -1), ("eta'", 0.95778, 1, -1),
            ("nucleons", 0.93892, 8, 1), ("phi", 1.01946, 3, -1)]


def _species(z: float, statistics: int) -> tuple[float, float]:
    """(ρ, P)/T⁴ per internal degree of freedom, for mass/temperature z."""
    def energy(y: float) -> float:
        e = math.hypot(y, z)
        return y * y * e / (math.exp(e) + statistics) if e < 700 else 0.0

    def pressure(y: float) -> float:
        e = math.hypot(y, z)
        return y ** 4 / e / (math.exp(e) + statistics) / 3.0 if e < 700 and e > 0 else 0.0
    upper = z + 60.0
    rho = quad(energy, 0.0, upper, limit=200)[0] / (2 * math.pi ** 2)
    p = quad(pressure, 0.0, upper, limit=200)[0] / (2 * math.pi ** 2)
    return rho, p


def _gas(temperature: float, particles: list) -> tuple[float, float]:
    """(g_eff, h_eff) of a list of particles at temperature T."""
    rho = p = 0.0
    for _, mass, dof, statistics in particles:
        r, q = _species(mass / temperature, statistics)
        rho, p = rho + dof * r, p + dof * q
    return rho * 30 / math.pi ** 2, (rho + p) * 45 / (2 * math.pi ** 2)


def ideal_gas(temperature: float) -> tuple[float, float]:
    """(g_eff, h_eff) of the Standard Model as an ideal gas with a tanh step from partons to hadrons at 160 MeV
    (width 20 MeV): the table until 2026-10-19, kept for comparison."""
    weight = 0.5 * (1.0 + math.tanh((temperature - T_QCD_GEV) / T_QCD_WIDTH_GEV))
    ew, quarks, hadrons = _gas(temperature, _ELECTROWEAK), _gas(temperature, _PARTONS), _gas(temperature, _HADRONS)
    return (ew[0] + weight * quarks[0] + (1 - weight) * hadrons[0], ew[1] + weight * quarks[1] + (1 - weight) * hadrons[1])


# Saikawa & Shirai, arXiv:1803.01038, Appendix C: fitting functions to their g*ρ(T), g*s(T). Coefficients as printed.
SS_A = (1.0, 1.11724, 3.12672e-1, -4.68049e-2, -2.65004e-2, -1.19760e-3, 1.82812e-4, 1.36436e-4, 8.55051e-5,
        1.22840e-5, 3.82259e-7, -6.87035e-9)
SS_B = (1.43382e-2, 1.37559e-2, 2.92108e-3, -5.38533e-4, -1.62496e-4, -2.87906e-5, -3.84278e-6, 2.78776e-6,
        7.40342e-7, 1.17210e-7, 3.72499e-9, -6.74107e-11)
SS_C = (1.0, 6.07869e-1, -1.54485e-1, -2.24034e-1, -2.82147e-2, 2.90620e-2, 6.86778e-3, -1.00005e-3, -1.69104e-4,
        1.06301e-5, 1.69528e-6, -9.33311e-8)
SS_D = (7.07388e1, 9.18011e1, 3.31892e1, -1.39779, -1.52558, -1.97857e-2, -1.60146e-1, 8.22615e-5, 2.02651e-2,
        -1.82134e-5, 7.83943e-5, 7.13518e-5)
SS_MATCH_GEV = 0.12               # the high-temperature fit's lower end (C.1, C.2); below it, C.3 and C.4
_M_E, _M_MU, _M_PI0, _M_PIC = 511e-6, 0.1056, 0.135, 0.140
_M_HADRON = (0.5, 0.77, 1.2, 2.0)
# the shapes of eqs. C.5–C.9: x ↦ exp(−a x)(1 + b x + c x² + d x³), (a, b, c, d)
_SHAPES = {"f_rho": (1.04855, 1.03757, 0.508630, 0.0893988), "b_rho": (1.03149, 1.03317, 0.398264, 0.0648056),
           "f_s": (1.04190, 1.03400, 0.456426, 0.0595248), "b_s": (1.03365, 1.03397, 0.342548, 0.0506182),
           "s_fit": (1.0419, 1.034, 0.456426, 0.0595249)}


def _poly(coefficients: tuple[float, ...], t: float) -> float:
    return sum(c * t ** i for i, c in enumerate(coefficients))


def _shape(name: str, x: float) -> float:
    a, b, c, d = _SHAPES[name]
    return math.exp(-a * x) * (1.0 + b * x + c * x * x + d * x ** 3)


def saikawa_shirai(temperature: float) -> tuple[float, float]:
    """(g_eff, h_eff) = (g*ρ, g*s) at T (GeV) from Saikawa & Shirai's fitting functions (arXiv:1803.01038, App. C:
    eqs. C.1–C.2 with Table 1 above 120 MeV, C.3–C.9 below)."""
    if temperature >= SS_MATCH_GEV:
        t = math.log(temperature)
        g = _poly(SS_A, t) / _poly(SS_B, t)
        return g, g / (1.0 + _poly(SS_C, t) / _poly(SS_D, t))
    x_e, x_mu, x_pi0, x_pic = (m / temperature for m in (_M_E, _M_MU, _M_PI0, _M_PIC))
    s_fit = 1.0 + 1.75 * _shape("s_fit", x_e)
    g = (2.030 + 1.353 * s_fit ** (4.0 / 3.0) + 3.495 * _shape("f_rho", x_e) + 3.446 * _shape("f_rho", x_mu)
         + 1.05 * _shape("b_rho", x_pi0) + 2.08 * _shape("b_rho", x_pic)
         + sum(w * _shape("b_rho", m / temperature) for w, m in zip((4.165, 30.55, 89.4, 8209.0), _M_HADRON)))
    h = (2.008 + 1.923 * s_fit + 3.442 * _shape("f_s", x_e) + 3.468 * _shape("f_s", x_mu)
         + 1.034 * _shape("b_s", x_pi0) + 2.068 * _shape("b_s", x_pic)
         + sum(w * _shape("b_s", m / temperature) for w, m in zip((4.16, 30.55, 90.0, 6209.0), _M_HADRON)))
    return g, h


@lru_cache(maxsize=1)
def dof_table() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(T in GeV, g_eff, h_eff) on a logarithmic grid from 1 MeV to 10 TeV (``saikawa_shirai``)."""
    temperatures = np.geomspace(1e-3, 1e4, 281)
    g, h = zip(*(saikawa_shirai(float(t)) for t in temperatures))
    return temperatures, np.array(g), np.array(h)


@lru_cache(maxsize=1)
def _log_tables() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    t, g, h = dof_table()
    log_t = np.log(t)
    return log_t, g, h, np.gradient(np.log(h), log_t)


def degrees_of_freedom(temperature: float) -> tuple[float, float, float]:
    """(g_eff, h_eff, g*^{1/2}) at T, with g*^{1/2} = h/√g (1 + d ln h / (3 d ln T))."""
    log_t, g, h, slope = _log_tables()
    lt = min(max(math.log(temperature), log_t[0]), log_t[-1])
    g_t = float(np.interp(lt, log_t, g))
    h_t = float(np.interp(lt, log_t, h))
    return g_t, h_t, h_t / math.sqrt(g_t) * (1.0 + float(np.interp(lt, log_t, slope)) / 3.0)


_DOF = contextvars.ContextVar("adroit_relic_dof", default=None)
_EOS_LABEL = contextvars.ContextVar("adroit_relic_eos", default="")
# Saikawa & Shirai's 2020 tables (arXiv:2005.03544; member.ipmu.jp/satoshi.shirai/DM2020/, eos2020.dat and its
# err1/err2), as published: T (GeV), g*s, g*ρ. The upper and lower edges of their band are the owner's declared
# equation-of-state variations (decision #3, 2026-10-20); ADROIT's nominal stays the 2018 fit (``degrees_of_freedom``,
# within −0.85% to +0.40% of the 2020 central table at the R3 crossings). Fetched by ``adroit setup --fetch`` (the
# manifest's ``EOS_ITEM``), not shipped: their page states no redistribution terms (the release audit's PR23-05, the
# owner's decision of 2026-10-23); each file is checked against its published sha256 when read.
EOS_ITEM = "Saikawa-Shirai relic cross sections (DM2020)"
EOS_TABLES = {
    "central": ("eos2020.dat", "c2a8429a75319d3fffce393560b14dfcac96ae6975b5c4913414bf114ff6a138"),
    "upper": ("eos2020_err1.dat", "9fc0c404be9512b2cfc4b6b8de898d73ab17837928cbdcb5936f9ca3cda9e121"),   # g* high
    "lower": ("eos2020_err2.dat", "14e83e7ba0c6ce00dd0502d6ee2f9a019cfb56e95b48a0efefb41b83070e7426"),   # g* low
}
LOW_T_SENSITIVITY = 0.05     # a relic density moved more than 5% by the thermal history below 1 MeV is pending
LOW_T_MASS_GEV = 10.0        # the Boltzmann solve reaches below 1 MeV only for m < 10 GeV (x ends at 10⁴)


def _dof(temperature: float) -> tuple[float, float, float]:
    """(g_eff, h_eff, g*^{1/2}) from the table in use: ``degrees_of_freedom``, or ``decoupled_neutrinos`` inside
    ``low_temperature_history``."""
    return (_DOF.get() or degrees_of_freedom)(temperature)


@lru_cache(maxsize=1)
def _decoupled_tables() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(ln T, g_eff, h_eff, d ln h/d ln T) from 1 keV to 1 MeV with the neutrinos decoupled at 1 MeV: photons and e±
    in equilibrium, and three neutrinos at T_ν, (T_ν/T)³ = h_γe(T)/(11/2) by the e± entropy given to the photons."""
    temperatures = np.geomspace(1e-6, 1e-3, 120)
    g, h = [], []
    for t in temperatures:
        rho, p = _species(0.000511 / t, 1)
        g_ge, h_ge = 2.0 + 4.0 * rho * 30.0 / math.pi ** 2, 2.0 + 4.0 * (rho + p) * 45.0 / (2.0 * math.pi ** 2)
        tnu3 = h_ge / 5.5
        g.append(g_ge + 5.25 * tnu3 ** (4.0 / 3.0))
        h.append(h_ge + 5.25 * tnu3)
    log_t, h_arr = np.log(temperatures), np.array(h)
    return log_t, np.array(g), h_arr, np.gradient(np.log(h_arr), log_t)


DECOUPLING_GEV = 1e-3       # the temperature below which ``decoupled_neutrinos`` replaces the table's hold


def decoupled_neutrinos(temperature: float, above: Callable[[float], tuple[float, float, float]] | None = None
                        ) -> tuple[float, float, float]:
    """``above`` (by default ``degrees_of_freedom``) above 1 MeV and, below, the history with the neutrinos decoupled
    (``_decoupled_tables``: g_eff → 3.363 and h_eff → 3.909 once the e± are gone). A sensitivity bracket for the
    table's hold at 1 MeV, not a sub-MeV cosmology (the external audit's A06, 2026-10-16)."""
    if temperature >= DECOUPLING_GEV:
        return (above or degrees_of_freedom)(temperature)
    log_t, g, h, slope = _decoupled_tables()
    lt = max(math.log(temperature), log_t[0])
    g_t, h_t = float(np.interp(lt, log_t, g)), float(np.interp(lt, log_t, h))
    return g_t, h_t, h_t / math.sqrt(g_t) * (1.0 + float(np.interp(lt, log_t, slope)) / 3.0)


def tabulated_dof(path: Path, text: str | None = None) -> Callable[[float], tuple[float, float, float]]:
    """(g_eff, h_eff, g*^{1/2}) at T from a table of T (GeV), h_eff and g_eff, micrOMEGAs' format (``Data/hgEff``), as
    ``degrees_of_freedom`` interpolates its own. Outside the table's temperatures the degrees of freedom are held at
    its end values, so d ln h/d ln T = 0 there; a T = 0 row (micrOMEGAs' tables end with one, stating that hold) is
    that continuation, not a point to take a logarithm of (the tactical audit's T20-10, 2026-10-20). ``text``: the
    file's contents as already read (``eos_table``), which are then parsed rather than the file read again."""
    rows = np.loadtxt(io.StringIO(text) if text is not None else path, comments="#")
    rows = rows[np.argsort(rows[:, 0])]
    rows = rows[rows[:, 0] > 0.0]
    if len(rows) < 2 or not np.all(np.isfinite(rows[:, :3])) or np.any(rows[:, 1:3] <= 0.0):
        raise ValueError(f"{path}: not a table of positive temperatures and degrees of freedom")
    log_t, h, g = np.log(rows[:, 0]), rows[:, 1], rows[:, 2]
    slope = np.gradient(np.log(h), log_t)

    def dof(temperature: float) -> tuple[float, float, float]:
        inside = temperature > 0.0 and log_t[0] <= math.log(temperature) <= log_t[-1]
        lt = math.log(temperature) if inside else log_t[0] if temperature <= 0.0 or math.log(temperature) < log_t[0] \
            else log_t[-1]
        g_t, h_t = float(np.interp(lt, log_t, g)), float(np.interp(lt, log_t, h))
        tilt = float(np.interp(lt, log_t, slope)) if inside else 0.0
        return g_t, h_t, h_t / math.sqrt(g_t) * (1.0 + tilt / 3.0)
    return dof


@contextmanager
def equation_of_state(dof: Callable[[float], tuple[float, float, float]], label: str = ""):
    """Solve with another table of the degrees of freedom inside the block (a cross-check on another code's), under
    ``label`` (``current_eos``; by default one of its own), which caches of anything the table moves key on."""
    tokens = _DOF.set(dof), _EOS_LABEL.set(label or f"table-{id(dof)}")
    try:
        yield
    finally:
        _EOS_LABEL.reset(tokens[1])
        _DOF.reset(tokens[0])


def current_eos() -> str:
    """The label of the degrees of freedom in use: "" for ADROIT's nominal (``degrees_of_freedom``)."""
    return _EOS_LABEL.get()


class EosUnavailable(fetch.MissingInput):
    """Saikawa & Shirai's tables are not installed (``eos_unavailable``)."""


def eos_folder() -> Path | None:
    """The folder of Saikawa & Shirai's fetched tables (``EOS_ITEM``), or None."""
    return fetch.locate(EOS_ITEM)


def eos_unavailable() -> str:
    """Why the equation of state's band cannot be computed, with what to do, or "": its tables not installed, or one
    of them unreadable or not as published (each file checked against its published sha256, as ``eos_table`` reads
    it). The consistency audit's CA-01 (2026-10-24): only the folder's presence was checked here, so a damaged table
    raised on one path and was never read on another, where the nominal decided. Each table's hash as read is noted
    for the calculation in force (``eos_reads``: the auditor's CT recheck, CU-02, 2026-10-28)."""
    folder = eos_folder()
    if folder is None:
        for name in EOS_TABLES:
            eos_reads.noted(name, "")
        return f"Saikawa & Shirai's equation-of-state tables are not installed: {fetch.how_to_get(EOS_ITEM)}"
    why = []
    for name, (file, sha256) in EOS_TABLES.items():
        path = folder / file
        try:
            found = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            eos_reads.noted(name, "")
            why.append(f"Saikawa & Shirai's {name} equation-of-state table cannot be read ({error.strerror or error}): "
                       f"delete {path} and {fetch.how_to_get(EOS_ITEM)}")
            continue
        eos_reads.noted(name, found)
        if found != sha256:
            why.append(f"Saikawa & Shirai's {name} equation-of-state table, {path}, is not the table as published (its "
                       f"sha256 differs): delete it and {fetch.how_to_get(EOS_ITEM)}")
    return why[0] if why else ""


EOS_BAND = ("upper", "lower")      # the band's edges, each a table of ``EOS_TABLES`` (the owner's decision #3)


def band_unavailable() -> str:
    """Why a decided thermal claim waits: "the equation of state's band is not computed: <``eos_unavailable``>", or
    "". The one reason every thermal producer gives (the plane's roots and band points, the single-idea study's
    thermal points, physical eligibility, the complementary relic comparison: the consistency audit's CA-02)."""
    why = eos_unavailable()
    return f"the equation of state's band is not computed: {why}" if why else ""


def band_values(compute: Callable[[], float | None]) -> dict[str, float | None]:
    """``compute()``, an Ωh², with each edge of the band in turn (``EOS_BAND``, ``eos_variant``): None where it fails
    or is not a finite, positive density. The tables must be present and as published (``band_unavailable``)."""
    out = {}
    for name in EOS_BAND:
        try:
            with eos_variant(name):
                value = compute()
        except (ValueError, RuntimeError, ArithmeticError):
            value = None
        out[name] = float(value) if value is not None and math.isfinite(value) and value > 0 else None
    return out


def eos_table(name: str) -> Callable[[float], tuple[float, float, float]]:
    """Saikawa & Shirai's 2020 table ``name`` (central, upper, lower; ``EOS_TABLES``), its file read once, checked
    against its published hash and parsed from the same bytes, and held for the process: the table used is always the
    one published, and it is noted so for the calculation in force (``eos_reads``: the auditor's CT recheck, CU-02,
    2026-10-28; the file had been read once to check and again to parse).

    Raises:
        EosUnavailable: if the tables have not been fetched.
    """
    table = _held(name)
    eos_reads.noted(name, EOS_TABLES[name][1], used=True)
    return table


@lru_cache(maxsize=3)
def _held(name: str) -> Callable[[float], tuple[float, float, float]]:
    file, sha256 = EOS_TABLES[name]
    folder = eos_folder()
    if folder is None:
        raise EosUnavailable(eos_unavailable())
    path = folder / file
    data = path.read_bytes()
    if (found := hashlib.sha256(data).hexdigest()) != sha256:
        eos_reads.noted(name, found)
        raise ValueError(f"{path}: not Saikawa & Shirai's {name} table as published (its sha256 differs)")
    return tabulated_dof(path, data.decode())


eos_table.cache_clear = _held.cache_clear


@contextmanager
def eos_variant(name: str):
    """Solve with Saikawa & Shirai's 2020 table ``name`` inside the block (``eos_table``; the owner's decision #3)."""
    with equation_of_state(eos_table(name), label=f"ss2020-{name}"):
        yield


@contextmanager
def low_temperature_history():
    """Solve with the neutrinos decoupled below 1 MeV (``decoupled_neutrinos``) in place of the table held there,
    inside the block, and with the equation of state in force when the block is entered above it: only the history
    below 1 MeV changes. The auditor's EOS review (2026-11-23): with another table in force (an upper or lower edge), the
    nominal degrees of freedom had replaced it above 1 MeV too, so the comparison moved Ωh² by the change of table
    and attributed it to the history below 1 MeV. Labelled "decoupled-neutrinos" on the nominal (as before) and
    "<the table's label>+decoupled-neutrinos" on another, so that caches keyed on the label keep them apart."""
    base, label = _DOF.get(), current_eos()
    above = base or degrees_of_freedom

    def dof(temperature: float) -> tuple[float, float, float]:
        return decoupled_neutrinos(temperature, above)
    with equation_of_state(dof, label=f"{label}+decoupled-neutrinos" if label else "decoupled-neutrinos"):
        yield


def thermal_history_reason(omega: Callable[[], float | None], m: float, computed: float | None = None) -> str:
    """Why a relic density cannot be decided, or "": ADROIT's degrees of freedom are those of an ideal gas held at
    their 1 MeV values below 1 MeV (no neutrino decoupling, no e± annihilation), so where the result moves by more
    than ``LOW_T_SENSITIVITY`` when the solve is repeated with ``decoupled_neutrinos``, it rests on a thermal history
    ADROIT does not model (the external audit's A06, 2026-10-16: a 200 keV scalar had Ωh² 0.128 against 0.207). A
    model whose solve only crosses 1 MeV after its annihilation has stopped is not affected. ``computed`` is
    ``omega()``'s value if already known."""
    if m >= LOW_T_MASS_GEV:
        return ""
    try:
        held = omega() if computed is None else computed
        with low_temperature_history():
            decoupled = omega()
    except RelicUnresolved as error:
        return f"with the neutrinos decoupled below 1 MeV, {error}"
    if not held or not decoupled or held <= 0 or decoupled <= 0:
        return ""
    change = decoupled / held - 1.0
    if abs(change) <= LOW_T_SENSITIVITY:
        return ""
    return (f"Ωh² depends on the thermal history below 1 MeV, which ADROIT does not model: {held:.3g} with its degrees "
            f"of freedom held at their 1 MeV values, {decoupled:.3g} with the neutrinos decoupled ({100 * change:+.0f}%)")


POLE_RATIO = (60.0 / 1e-3) ** (1.0 / 149)   # successive offsets of a pole's nodes from its centre
POLE_REACH = 0.1     # a pole's nodes reach a tenth of its distance from threshold (some 3.5 base cells), if beyond 60 w
# a pole's half-width w (in u) taken as at least this: float resolution about u ~ 1 only (AL3-21: at 10⁻⁹ the average
# was 1.03, 5.8 and 57 times its narrow-width limit at Γ = 10⁻¹⁰, 10⁻¹¹ and 10⁻¹² GeV for m = 45 GeV; now within 0.4%
# down to 10⁻¹³ GeV)
POLE_FLOOR = 1e-14
POLE_RESOLVED = 1e-16    # a pole with Γ/4m below this is not resolved by the grid: Ωh² is refused (``resolvable``)
# The grid's base nodes start at u = GRID_FIRST. A pole whose scale at the threshold (the larger of its half-width and
# its distance from the threshold, in u) is under a hundred of them also shapes the thermal weight below: there the
# grid runs a ladder of THRESHOLD_PER_DECADE nodes a decade from a hundredth of that scale (no lower than POLE_FLOOR) up
# to GRID_FIRST. The audit loop's AL5-01 (the auditor, 2026-11-17): a narrow pole 10⁻⁹ or less below the threshold, its
# own nodes all below it, had been integrated across the first cell, from 0.90 to 0.13 times its thermal average.
GRID_FIRST = 1e-9
THRESHOLD_PER_DECADE = 16


def resolvable(m: float, resonances) -> None:
    """``RelicUnresolved`` where a reachable s-channel pole is narrower than the grid resolves (Γ/4m below
    ``POLE_RESOLVED``; at 10⁻¹⁵ GeV and m = 45 GeV its average was 13 times its limit): the stated domain of the relic
    density (AL3-21). ``resonances`` holds (mass, width) pairs in GeV."""
    for mass, width in resonances or []:
        u_r = mass / (2.0 * m) - 1.0
        if 0.0 < width < 4.0 * m * POLE_RESOLVED and -30.0 * POLE_FLOOR < u_r < 80.0:
            raise RelicUnresolved(f"an s-channel resonance at {mass:.4g} GeV of width {width:.3g} GeV is narrower than "
                                  f"the relic integration resolves (Γ/4m below {POLE_RESOLVED:g})")


def energy_grid(m: float, resonance_gev: float | None = None, width_gev: float = 0.0) -> np.ndarray:
    """Nodes in u = √s/(2m) − 1 that resolve the thermal weight and any s-channel resonance.

    A resonance's nodes go out from its centre geometrically (offsets 10⁻³ to 60 half-widths w, then on at the same
    ratio) until they reach a tenth of its distance from threshold, where the base grid's own cells (2.8% of u) take
    over. Stopped at 60 w whatever the width, as before, the chord from the Breit–Wigner's tail to the next base node
    has an area that does not shrink with the width while the pole's does: a narrow pole's average was too large
    without bound (AL2-01: 1.23, 3.5 and 26 times at Γ = 10⁻⁴, 10⁻⁵, 10⁻⁶ GeV for M = 100, m = 45). A pole wide enough
    that 60 w already reaches that far keeps its nodes as they were. A pole near the threshold (its scale there under
    a hundred ``GRID_FIRST``) also gets a ladder up to the base nodes (AL5-01)."""
    u = np.geomspace(GRID_FIRST, 80.0, 900)
    if resonance_gev is not None and width_gev > 0.0:
        u_r = resonance_gev / (2.0 * m) - 1.0
        w = max(width_gev / (4.0 * m), POLE_FLOOR)
        if -30 * w < u_r < 80.0:
            below, above = -np.geomspace(60, 1e-3, 150), np.geomspace(1e-3, 60, 150)      # as before, to the bit
            if POLE_REACH * abs(u_r) > 60.0 * w:
                more = 60.0 * POLE_RATIO ** np.arange(1, math.ceil(math.log(POLE_REACH * abs(u_r) / (60.0 * w))
                                                                   / math.log(POLE_RATIO)) + 1)
                below, above = np.concatenate([-more[::-1], below]), np.concatenate([above, more])
            peak = u_r + w * np.concatenate([below, [0.0], above])
            u = np.union1d(u, peak[(peak > 0) & (peak < 80.0)])   # beyond u = 80 the thermal weight is nil
        low = max(1e-2 * max(width_gev / (4.0 * m), abs(u_r)), POLE_FLOOR)
        if low < GRID_FIRST:
            count = 1 + math.ceil(math.log10(GRID_FIRST / low) * THRESHOLD_PER_DECADE)
            u = np.union1d(u, np.geomspace(low, GRID_FIRST, count))
    return np.concatenate([[0.0], u])


def thermal_average(u: np.ndarray, sigma: np.ndarray, x: np.ndarray) -> np.ndarray:
    """⟨σv⟩(x) in the units of σ, by the Gondolo–Gelmini integral on the nodes u."""
    x = np.atleast_1d(np.asarray(x, dtype=float))[:, None]
    weight = u * (2 + u) * (1 + u) ** 2 * kve(1, 2 * x * (1 + u)) * np.exp(-2 * x * u)
    integral = np.trapezoid(sigma[None, :] * weight, u, axis=1)
    return 8.0 * x[:, 0] / kve(2, x[:, 0]) ** 2 * integral


def log_equilibrium_yield(x: float, m: float, internal_dof: float = 4.0) -> float:
    """ln Y_eq, with Y_eq = 45 g x² K₂(x) / (4π⁴ h_eff) (Maxwell–Boltzmann statistics)."""
    h = _dof(m / x)[1]
    return math.log(45.0 * internal_dof * x * x * kve(2, x) / (4.0 * math.pi ** 4 * h)) - x


def freeze_out(m: float, x_nodes: np.ndarray, sigma_v: np.ndarray, x_start: float = 3.0,
               x_end: float = 1e4, dirac: bool = True,
               log_yeq: Callable[[float], float] | None = None, settled: bool = True) -> float:
    """Y today: the Boltzmann equation from Y = Y_eq at ``x_start`` (⟨σv⟩ in GeV⁻² on ``x_nodes``).

    With ``log_yeq`` (ln Y_eq of all the species together, as a function of x) the rate is
    taken as given (⟨σ_eff v⟩ of ``coannihilation_average``, no factor ½). Without it the
    equilibrium yield counts g = 4 for a Dirac fermion (χ and χ̄) and g = 2 for a Majorana one.

    Raises RelicUnresolved where annihilation has not stopped by ``x_end`` (``_settled``); ``settled=False`` leaves
    that test out, for an estimate that is not Ωh² (``long_range_bracket``).
    """
    solution = _solved(m, x_nodes, sigma_v, x_start, x_end, dirac, log_yeq)
    y = math.exp(float(solution.y[0, -1]))
    if settled:
        _settled(m, x_nodes, sigma_v, y, x_end, dirac, log_yeq)
    return y


def _settled(m: float, x_nodes: np.ndarray, sigma_v: np.ndarray, y: float, x_end: float, dirac: bool,
             log_yeq: Callable[[float], float] | None) -> None:
    """Raise RelicUnresolved unless annihilation has stopped by ``x_end`` (the note above ``LATE_TOLERANCE``): the rate
    tabulated to twice it, the fall in that window within ``LATE_TOLERANCE``, and the fall to x → ∞ within
    ``REMAINDER_TOLERANCE`` (``remainder_change``: the rate as tabulated, to ``X_LAST`` on every route, then a tail
    bounded by its slope over the table's last decade)."""
    far = 2.0 * x_end
    if float(x_nodes[-1]) < far * (1.0 - 1e-12):
        raise RelicUnresolved(f"the rate is tabulated only to x = m/T = {float(x_nodes[-1]):g}, short of {far:g}: "
                              f"whether annihilation has stopped by x = {x_end:g} is not established")
    late = late_change(m, x_nodes, sigma_v, y, x_end, dirac, log_yeq)
    if late > LATE_TOLERANCE:
        raise RelicUnresolved(f"annihilation has not stopped by x = m/T = {x_end:g}: carried on to x = {far:g}, Ωh² "
                              f"would fall by a further {100 * late:.2g}% (more than {100 * LATE_TOLERANCE:g}%), as a "
                              "narrow resonance at the threshold keeps it going; ADROIT's solve, with the dark matter "
                              "in kinetic equilibrium, does not follow it further")
    rest, slope = remainder_change(m, x_nodes, sigma_v, y, x_end, dirac, log_yeq)
    if rest > REMAINDER_TOLERANCE:
        fall = "without bound" if rest >= 1.0 else f"by up to {100 * rest:.2g}%"
        trend = f"still rises as x^{slope:.2g}" if slope > 0 else f"goes as x^{slope:.2g}"
        raise RelicUnresolved(f"annihilation has not stopped by x = m/T = {x_end:g}: ⟨σv⟩ {trend} over its table's "
                              f"last decade (to x = {float(x_nodes[-1]):g}), and carried on Ωh² would fall {fall} (more "
                              f"than the relic density's {100 * REMAINDER_TOLERANCE:g}% theory uncertainty); ADROIT's "
                              "solve, with the dark matter in kinetic equilibrium, does not follow it further")


# The audit loop's AL6-01 (the auditor, 2026-11-17): the yield at x = 10⁴ was published as today's whatever was still
# annihilating then. A narrow pole at the threshold keeps ⟨σv⟩ rising as T falls: the 2HDM+a's thermal root at
# g_q = 0.001 (Ωh² 0.1200) fell by a further 23% to x = 2 × 10⁴. A constant ⟨σv⟩ falls by 0.04% there; the library's
# Sommerfeld-enhanced multiplets, with their bound states, by 1.0% (the wino) to 1.7% (the quintuplet). The tolerance is
# half the relic density's theory uncertainty (``likelihood.LikelihoodSettings.relic_theory``, 10%): within it the
# remaining fall moves χ²_Ω by at most about 0.25 at the band's centre.
LATE_TOLERANCE = 0.05
# The audit loop's AL7-02 (the auditor's cycle 7): the window's fall is a screen, not a bound on the remainder. A rate rising
# as x^0.8 to x = 10⁸ fell by 2.4% in the window and by a further 13.6% to 10⁸; a rate tabulated short of the window
# had passed with no change at all. So a rate is tabulated to twice the endpoint at least, and the fall to x → ∞ is
# within the relic density's theory uncertainty: 1/Y grows by ∫λ dx, the rate as every route tabulates it to X_LAST
# (10⁶), then a tail bounded by its slope over the last decade (no bound where it rises as x or faster). With the rate
# so tabulated, the library's default points are bounded at 1.2% (B − L) or less, but for the Sommerfeld-enhanced
# multiplets: 2.0% (the wino), 3.3% (the Dirac quintuplet), 4.7% (the quintuplet); dark QED's bound states, 4.2%.
REMAINDER_TOLERANCE = 0.10
# The rate's nodes on every route: to twice the endpoint for the solve, as before, then on to X_LAST, read only for the
# remainder's bound (no node below 2 × 10⁴ moves, and the solve interpolates linearly, so Ωh² is unchanged to the bit).
X_NODES = np.geomspace(1.0, 2e4, 140)
X_LAST = 1e6
X_BEYOND = np.geomspace(2e4, X_LAST, 21)[1:]


def rate_nodes() -> np.ndarray:
    """The x nodes every route tabulates ⟨σv⟩ on (``X_NODES``, then ``X_BEYOND``)."""
    return np.concatenate([X_NODES, X_BEYOND])


def remainder_change(m: float, x_nodes: np.ndarray, sigma_v: np.ndarray, y_end: float, x_end: float, dirac: bool,
                     log_yeq: Callable[[float], float] | None) -> tuple[float, float]:
    """(1 − Y(∞)/Y(x_end), bounded; the rate's log-slope n over the table's last decade): 1/Y grows by ∫λ dx, the rate
    as tabulated from ``x_end`` to the last node, and beyond it a tail bounded by that slope (λ ∝ x^(n−2), g*^½ held at
    the last node, which it does not exceed later); 1 (no bound) where n ≥ 1."""
    last = float(x_nodes[-1])
    log_x, log_sv = np.log(x_nodes), np.log(np.maximum(sigma_v, 1e-300))

    def rate(x):
        return np.exp(np.interp(np.log(x), log_x, log_sv))
    effective = 1.0 if log_yeq is not None else 0.5 if dirac else 1.0
    base = math.sqrt(math.pi / 45.0) * M_PLANCK_GEV * m * effective

    def lam(x):
        return base * np.array([_dof(m / v)[2] for v in np.atleast_1d(x)]) * rate(x) / np.atleast_1d(x) ** 2
    xs = np.geomspace(x_end, last, 400)
    grown = y_end * float(np.trapezoid(lam(xs), xs))
    first = max(last / 10.0, x_end)
    slope = float(np.log(rate(last) / rate(first)) / math.log(last / first))
    if slope >= 1.0:
        return 1.0, slope
    grown += y_end * float(lam(last)[0]) * last / (1.0 - slope)
    return grown / (1.0 + grown), slope


def late_change(m: float, x_nodes: np.ndarray, sigma_v: np.ndarray, y_end: float, x_end: float, dirac: bool,
                log_yeq: Callable[[float], float] | None) -> float:
    """1 − Y(x_far)/Y(x_end): how much further the yield falls from ``x_end`` to x_far, twice it or the rate's last
    node if that comes first. Long after freeze-out (Y ≫ Y_eq) dY/dx = −λ(x) Y², so 1/Y grows by ∫λ dx; λ is the rate
    ``_boltzmann`` integrates, read from the same nodes (no extrapolation)."""
    far = min(2.0 * x_end, float(x_nodes[-1]))
    if far <= x_end:
        return 0.0
    effective = 1.0 if log_yeq is not None else 0.5 if dirac else 1.0
    xs = np.geomspace(x_end, far, 65)
    sv = np.exp(np.interp(np.log(xs), np.log(x_nodes), np.log(np.maximum(sigma_v, 1e-300))))
    g_star_half = np.array([_dof(m / x)[2] for x in xs])
    lam = math.sqrt(math.pi / 45.0) * M_PLANCK_GEV * g_star_half * m * effective * sv / xs ** 2
    grown = y_end * float(np.trapezoid(lam, xs))
    return grown / (1.0 + grown)


class RelicUnresolved(ArithmeticError):
    """The Boltzmann equation could not be integrated to the end: Ωh² is not computed (never the yield where the
    integrator stopped)."""


EQUILIBRIUM_HOLDS = 1e3          # Γ/H above which the yield is its equilibrium value, so a later start loses nothing
LATER_STARTS = (5.0, 8.0, 12.0, 18.0)


def _solved(m: float, x_nodes: np.ndarray, sigma_v: np.ndarray, x_start: float, x_end: float, dirac: bool,
            log_yeq: Callable[[float], float] | None):
    """The Boltzmann solution, integrated to ``x_end`` or not at all. BDF first, as always; where it stops short (an
    enormous rate near a resonance makes the equation so stiff that BDF's step can underflow: the vector Higgs portal
    at λ = 10 just below m_h/2 did, and its yield at x ≈ 4, still at equilibrium, had been read as the relic, Ωh² ≈
    10⁷; found by the physics-extensions verdict study), Radau; then later starts, from Y = Y_eq wherever the rate
    still holds the yield at equilibrium (Γ/H > ``EQUILIBRIUM_HOLDS``). Raises RelicUnresolved if none reaches the
    end. A solution that reaches the end at the first try is unchanged."""
    solution = _boltzmann(m, x_nodes, sigma_v, x_start, x_end, dirac, log_yeq)
    if solution.success:
        return solution
    tried = [f"BDF from x = {x_start:g}: {solution.message}"]
    solution = _boltzmann(m, x_nodes, sigma_v, x_start, x_end, dirac, log_yeq, method="Radau")
    if solution.success:
        return solution
    tried.append(f"Radau: {solution.message}")
    for later in (x for x in LATER_STARTS if x > x_start):
        if _equilibrium_rate(m, x_nodes, sigma_v, later, dirac, log_yeq) < EQUILIBRIUM_HOLDS:
            break
        solution = _boltzmann(m, x_nodes, sigma_v, later, x_end, dirac, log_yeq)
        if solution.success:
            return solution
        tried.append(f"BDF from x = {later:g}: {solution.message}")
    raise RelicUnresolved(f"the Boltzmann equation could not be integrated (m = {m:.6g} GeV): " + "; ".join(tried))


def _equilibrium_rate(m: float, x_nodes: np.ndarray, sigma_v: np.ndarray, x: float, dirac: bool,
                      log_yeq: Callable[[float], float] | None) -> float:
    """Γ/H at x for the yield at equilibrium: λ(x) Y_eq(x) x, the rate _boltzmann integrates."""
    effective = 1.0 if log_yeq is not None else 0.5 if dirac else 1.0
    equilibrium = log_yeq or (lambda z: log_equilibrium_yield(z, m, 4.0 if dirac else 2.0))
    sv = math.exp(float(np.interp(math.log(x), np.log(x_nodes), np.log(np.maximum(sigma_v, 1e-300)))))
    rate = math.sqrt(math.pi / 45.0) * M_PLANCK_GEV * _dof(m / x)[2] * m * effective * sv / x ** 2
    return rate * math.exp(equilibrium(x)) * x


def freeze_out_x(m: float, x_nodes: np.ndarray, sigma_v: np.ndarray, dirac: bool = True,
                 log_yeq: Callable[[float], float] | None = None, departure: float = 1.0) -> float | None:
    """x_f = m/T_f: where the yield first leaves equilibrium, Y = (1 + departure) Y_eq (Y = 2 Y_eq by default),
    from the same Boltzmann equation as ``freeze_out``; None if it never does before x = 10⁴."""
    equilibrium = log_yeq or (lambda x: log_equilibrium_yield(x, m, 4.0 if dirac else 2.0))
    def departed(x: float, y: np.ndarray) -> float:
        return float(y[0]) - equilibrium(x) - math.log1p(departure)
    departed.terminal, departed.direction = True, 1.0
    solution = _boltzmann(m, x_nodes, sigma_v, 3.0, 1e4, dirac, log_yeq, events=departed)
    found = solution.t_events[0]
    return float(found[0]) if len(found) else None


def _boltzmann(m: float, x_nodes: np.ndarray, sigma_v: np.ndarray, x_start: float, x_end: float, dirac: bool,
               log_yeq: Callable[[float], float] | None, events=None, method: str = "BDF"):
    """The solution y = ln Y(x) of dY/dx = −λ(x) (Y² − Y_eq²) from Y = Y_eq at ``x_start``.

    Raises:
        ValueError: if ⟨σv⟩ is not finite at some node (an engine's fault, named here rather than inside the
            integrator's Jacobian).
    """
    bad = ~np.isfinite(np.asarray(sigma_v, dtype=float))
    if bad.any():
        raise ValueError(f"⟨σv⟩ is not finite at x = {np.asarray(x_nodes)[bad][:3].tolist()} (m = {m:g} GeV)")
    log_x, log_sv = np.log(x_nodes), np.log(np.maximum(sigma_v, 1e-300))
    effective = 1.0 if log_yeq is not None else 0.5 if dirac else 1.0
    equilibrium = log_yeq or (lambda x: log_equilibrium_yield(x, m, 4.0 if dirac else 2.0))

    def rate(x: float) -> float:
        sv = math.exp(float(np.interp(math.log(x), log_x, log_sv)))
        g_star_half = _dof(m / x)[2]
        return math.sqrt(math.pi / 45.0) * M_PLANCK_GEV * g_star_half * m * effective * sv / x ** 2

    def terms(x: float, y: float) -> tuple[float, float]:
        # dy/dx = −r eʸ (1 − e^{−2d}), d = y − y_eq; d is clipped so that trial steps far from
        # the solution cannot overflow (the solution itself has |d| ≪ 1 while r is large).
        d = min(max(y - equilibrium(x), -30.0), 30.0)
        r = rate(x) * math.exp(min(y, 0.0))
        return r, math.exp(-2.0 * d)

    def rhs(x: float, y: np.ndarray) -> np.ndarray:
        r, back = terms(x, float(y[0]))
        return np.array([-r * (1.0 - back)])

    def jac(x: float, y: np.ndarray) -> np.ndarray:
        r, back = terms(x, float(y[0]))
        return np.array([[-r * (1.0 + back)]])
    y0 = [equilibrium(x_start)]
    return solve_ivp(rhs, (x_start, x_end), y0, method=method, jac=jac, rtol=1e-7, atol=1e-9, events=events)


def omega_h2(sigma_of_s: Callable[[np.ndarray], np.ndarray], m: float,
             resonance_gev: float | None = None, width_gev: float = 0.0,
             dirac: bool = True) -> float:
    """Ωh² of dark matter of mass m with the total annihilation cross-section σ(s) in GeV⁻²."""
    resolvable(m, [(resonance_gev, width_gev)] if resonance_gev is not None else [])
    u = energy_grid(m, resonance_gev, width_gev)
    sigma = sigma_of_s((2.0 * m * (1.0 + u)) ** 2)
    x_nodes = rate_nodes()
    sigma_v = thermal_average(u, sigma, x_nodes)
    return OMEGA_PER_MY * m * freeze_out(m, x_nodes, sigma_v, dirac=dirac)


class Species(NamedTuple):
    """One particle in the thermal bath of the dark sector: its mass (GeV) and internal degrees of freedom.

    A particle and its antiparticle are two species (a Dirac fermion: two of 2 each); a
    self-conjugate particle is one (a Majorana fermion: 2; a real scalar: 1; a real vector: 3).
    """

    mass: float
    dof: float


def coannihilation_average(species: list[Species], pairs: dict[tuple[int, int], Callable[[np.ndarray], np.ndarray]],
                           x_nodes: np.ndarray,
                           resonances: list[tuple[float, float]] | None = None) -> np.ndarray:
    """⟨σ_eff v⟩(x) in GeV⁻², x = m₁/T, for a set of species that annihilate among themselves.

    The relativistic generalisation of Gondolo & Gelmini with coannihilations (Edsjö &
    Gondolo, hep-ph/9704361):

        ⟨σ_eff v⟩ = Σ_ij g_i g_j ∫ ds σ_ij(s) λ(s, m_i², m_j²)/√s K₁(√s/T)
                    / [8T (Σ_k g_k m_k² K₂(m_k/T))²] ,

    the sum over ordered pairs. ``pairs`` maps each unordered pair (i, j), i ≤ j, to
    σ(i j → anything)(s) in GeV⁻². With one Dirac species (χ and χ̄) it is ⟨σv⟩/2, and
    with one Majorana species ⟨σv⟩, as the single-species code above.
    """
    m1 = min(sp.mass for sp in species)
    x = np.asarray(x_nodes, dtype=float)
    temperature = m1 / x
    numerator = np.zeros_like(x)
    for (i, j), sigma_of_s in pairs.items():
        mi, mj = species[i].mass, species[j].mass
        threshold = mi + mj
        resolvable(threshold / 2.0, resonances)
        u = energy_grid(threshold / 2.0, *(resonances[0] if resonances else (None, 0.0)))
        for r in (resonances or [])[1:]:
            u = np.union1d(u, energy_grid(threshold / 2.0, *r))
        root_s = threshold * (1.0 + u)
        s = root_s ** 2
        lam = np.clip((s - mi * mi - mj * mj) ** 2 - 4.0 * mi * mi * mj * mj, 0.0, None)
        sigma = np.asarray(sigma_of_s(s), dtype=float)
        ds_du = 2.0 * threshold ** 2 * (1.0 + u)
        z = root_s[None, :] / temperature[:, None]
        with np.errstate(invalid="ignore", over="ignore"):
            weight = kve(1, z) * np.exp(-(root_s[None, :] - 2.0 * m1) / temperature[:, None])
        weight = np.nan_to_num(weight, nan=0.0, posinf=0.0)
        integral = np.trapezoid((sigma * lam / root_s * ds_du)[None, :] * weight, u, axis=1)
        numerator += (1.0 if i == j else 2.0) * species[i].dof * species[j].dof * integral
    bath = sum(sp.dof * sp.mass ** 2 * kve(2, sp.mass / temperature) * np.exp(-(sp.mass - m1) / temperature)
               for sp in species)
    return numerator / (8.0 * temperature * bath ** 2)


def log_equilibrium_yield_species(x: float, species: list[Species]) -> float:
    """ln Y_eq of all the species together, x = m₁/T (Maxwell–Boltzmann statistics)."""
    m1 = min(sp.mass for sp in species)
    h = _dof(m1 / x)[1]
    total = sum(sp.dof * (sp.mass / m1) ** 2 * kve(2, x * sp.mass / m1) * math.exp(-x * (sp.mass / m1 - 1.0))
                for sp in species)
    return math.log(45.0 * x * x * total / (4.0 * math.pi ** 4 * h)) - x


def pair_weight(species: list[Species], i: int, j: int, x_nodes: np.ndarray) -> np.ndarray:
    """n_i n_j / n² in equilibrium (twice that for i ≠ j, the two orderings), x = m₁/T."""
    m1 = min(sp.mass for sp in species)
    temperature = m1 / np.asarray(x_nodes, dtype=float)

    def density(sp: Species) -> np.ndarray:
        return sp.dof * sp.mass ** 2 * kve(2, sp.mass / temperature) * np.exp(-(sp.mass - m1) / temperature)
    total = sum(density(sp) for sp in species)
    return (1.0 if i == j else 2.0) * density(species[i]) * density(species[j]) / total ** 2


def omega_h2_species(species: list[Species], pairs: dict[tuple[int, int], Callable[[np.ndarray], np.ndarray]],
                     resonances: list[tuple[float, float]] | None = None,
                     thermal: dict[tuple[int, int], Callable[[np.ndarray], np.ndarray]] | None = None) -> float:
    """Ωh² of the lightest species, the heavier ones having decayed into it after freeze-out.

    ``thermal`` adds rates that are not a cross-section of s alone: ⟨σv⟩(T) in GeV⁻² of a pair
    (i, j), averaged over the pair's internal states, e.g. bound-state formation in
    ionisation equilibrium (``sommerfeld.bound_state_rate``); each enters ⟨σ_eff v⟩ with its
    pair's weight n_i n_j / n².
    """
    m1, x_nodes, sigma_v = _effective_rate(species, pairs, resonances, thermal)
    y0 = freeze_out(m1, x_nodes, sigma_v, log_yeq=lambda x: log_equilibrium_yield_species(x, species))
    return OMEGA_PER_MY * m1 * y0


def freeze_out_x_species(species: list[Species], pairs: dict[tuple[int, int], Callable[[np.ndarray], np.ndarray]],
                         resonances: list[tuple[float, float]] | None = None,
                         thermal: dict[tuple[int, int], Callable[[np.ndarray], np.ndarray]] | None = None
                         ) -> float | None:
    """x_f = m₁/T_f of the bath that ``omega_h2_species`` solves (``freeze_out_x``)."""
    m1, x_nodes, sigma_v = _effective_rate(species, pairs, resonances, thermal)
    return freeze_out_x(m1, x_nodes, sigma_v, log_yeq=lambda x: log_equilibrium_yield_species(x, species))


def _effective_rate(species, pairs, resonances, thermal) -> tuple[float, np.ndarray, np.ndarray]:
    """(m₁, x nodes, ⟨σ_eff v⟩ on them) of a bath, its thermal rates included."""
    m1 = min(sp.mass for sp in species)
    x_nodes = rate_nodes()
    sigma_v = coannihilation_average(species, pairs, x_nodes, resonances)
    for (i, j), rate in (thermal or {}).items():
        sigma_v = sigma_v + pair_weight(species, i, j, x_nodes) * np.asarray(rate(m1 / x_nodes), dtype=float)
    return m1, x_nodes, sigma_v


def omega_h2_rate(species: list[Species], rate: Callable[[np.ndarray], np.ndarray]) -> float:
    """Ωh² from ⟨σ_eff v⟩(T) given directly (GeV⁻²), for a bath whose rate is computed as a whole
    (the electroweak multiplets' Sommerfeld-enhanced annihilation, ``portals.multiplet``)."""
    m1 = min(sp.mass for sp in species)
    x_nodes = rate_nodes()
    sigma_v = np.asarray(rate(m1 / x_nodes), dtype=float)
    return OMEGA_PER_MY * m1 * freeze_out(m1, x_nodes, sigma_v,
                                          log_yeq=lambda x: log_equilibrium_yield_species(x, species))


def dark_matter(m: float, spin: float, self_conjugate: bool) -> list[Species]:
    """The species of one dark matter particle: a Dirac fermion or complex field is two."""
    dof = {0.0: 1.0, 0.5: 2.0, 1.0: 3.0}[spin]
    return [Species(m, dof)] if self_conjugate else [Species(m, dof), Species(m, dof)]


def omega_h2_single(sigma_of_s: Callable[[np.ndarray], np.ndarray], m: float, spin: float,
                    self_conjugate: bool, resonances: list[tuple[float, float]] | None = None) -> float:
    """Ωh² of one dark matter particle of any spin with σ(DM DM̄ → anything)(s) in GeV⁻²."""
    sp = dark_matter(m, spin, self_conjugate)
    pairs = {(0, 0): sigma_of_s} if self_conjugate else {(0, 1): sigma_of_s}
    return omega_h2_species(sp, pairs, resonances)
