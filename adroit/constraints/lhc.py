"""LHC searches recast with SModelS: a model's spectrum, decays and cross-sections against the experiments' maps.

SModelS (arXiv:2306.17676; GPL-3) decomposes a spectrum into simplified-model topologies and
compares each topology's σ × BR with the ATLAS and CMS results in its database (3.2.1, CC BY 4.0:
131 analyses). It runs in its own environment in the tools folder, as a program
(``smodels_driver.py``, JSON in and out), never imported here.

What ADROIT gives it, for each point:
- **the spectrum** as an SLHA file: the dark-sector particles with their quantum numbers
  (QNUMBERS), masses and decays; widths below 10⁻¹¹ GeV make a particle long-lived, so
  disappearing tracks (a wino's or a higgsino's chargino) and displaced decays are covered;
- **cross-sections at 13 TeV** from the LHC SUSY Cross Section Working Group's tables
  (fetched into the tools folder): a coloured partner's pair production is a single
  colour-triplet scalar's (NNLO+NNLL, the stop table: QCD only; on a t-channel model χ exchange adds and its
  interference with QCD can subtract, so it is not a lower bound and decides nothing, decision D33,
  ``searches.QCD_ONLY``); a lepton partner's a right-handed slepton's
  (NLO+NLL); the wino's and higgsino's their electroweakinos' (aNNLO+NNLL).

The result is r = σ/σ₉₅ of the most sensitive analysis (excluded at r ≥ 1).
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

from adroit.core.config import child_environment
from adroit.core.config import get_settings

HBAR_C_GEV_M = 1.973269804e-16
G_F, F_PI, V_UD, M_PI, M_E = 1.1663788e-5, 0.1302, 0.97373, 0.13957, 0.000511
TABLES = {"coloured": "13TeV_stop_sbottom_pair_NNLOapprox+NNLL", "slepton": "13TeV_slepton_R_pair_NLO+NLL",
          "wino_c1c1": "13TeV_wino_C1C1_aNNLO+NNLL", "wino_c1p_n": "13TeV_wino_C1pN2_aNNLO+NNLL",
          "wino_c1m_n": "13TeV_wino_C1mN2_aNNLO+NNLL", "hino_c1c1": "13TeV_higgsino_C1C1_aNNLO+NNLL",
          "hino_n1c1p": "13TeV_higgsino_N1C1p_aNNLO+NNLL", "hino_n1c1m": "13TeV_higgsino_N1C1m_aNNLO+NNLL",
          "hino_n1n2": "13TeV_higgsino_N1N2_aNNLO+NNLL"}
_RESULTS: dict[str, dict] = {}


def _tools() -> Path:
    return get_settings().tools_dir


def available() -> bool:
    """Whether SModelS's environment and database and the SUSY cross-section tables are in the tools folder."""
    return ((_tools() / ".venv-smodels" / "bin" / "python").exists()
            and (_tools() / "smodels-db" / "official321.pcl").exists()
            and (_tools() / "susy-xsec" / "tables").is_dir())


def _table(name: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """The SUSY production table ``name`` as it is now, one reading: its masses and values are of the bytes of one
    version of the file (``file_reads``: device, inode, size, modification and change times), however the cache is
    evicted and refilled (the auditor's DX recheck, DY-02, 2026-11-13; before, BI-02 had keyed it by the file's stat but read
    it as it then was; before that, by its name)."""
    from adroit.core.file_reads import consistent
    path = str(_tools() / "susy-xsec" / "tables" / f"{name}.json")
    return consistent(path, lambda *version: _parsed(path, version))


@lru_cache(maxsize=16)
def _parsed(path: str, version: tuple[int, ...]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    from adroit.core.file_reads import read
    data = json.loads(read(path, version))
    rows = [r for r in data["data"] if r[1] > 0]
    return tuple(r[0] for r in rows), tuple(r[1] for r in rows)


def table_available(kind: str) -> bool:
    """Whether the production table of ``kind`` is in the tools folder."""
    return (_tools() / "susy-xsec" / "tables" / f"{TABLES[kind]}.json").is_file()


def table_range(kind: str) -> tuple[float, float] | None:
    """The masses (GeV) the production table of ``kind`` covers, or None without the table."""
    if not table_available(kind):
        return None
    masses = _table(TABLES[kind])[0]
    return masses[0], masses[-1]


def _listed(names: list[str]) -> str:
    return ", ".join(names) if len(names) <= 3 else f"{', '.join(names[:3])} and {len(names) - 3} more"


def unavailable(*kinds: str) -> str:
    """Why these production tables cannot be used ('' if each is in the tools folder)."""
    missing = [kind for kind in kinds if not table_available(kind)]
    return (f"the LHC SUSY Cross Section Working Group's table{'s' if len(missing) > 1 else ''} for "
            f"{_listed(missing)} not in the tools folder (adroit setup --fetch)") if missing else ""


def cross_section_pb(kind: str, mass: float) -> float | None:
    """σ (pb) inside the production table; None outside it, or without the table, never an invented zero."""
    if not table_available(kind):
        return None
    masses, sigmas = _table(TABLES[kind])
    if not masses[0] <= mass <= masses[-1]:
        return None
    if mass == masses[0]:
        return sigmas[0]
    i = next(k for k, m in enumerate(masses) if m >= mass)
    t = (math.log(mass) - math.log(masses[i - 1])) / (math.log(masses[i]) - math.log(masses[i - 1]))
    return math.exp(math.log(sigmas[i - 1]) + t * (math.log(sigmas[i]) - math.log(sigmas[i - 1])))


def chargino_width(delta: float, weight: float) -> float:
    """Γ(χ± → χ⁰ π±, e ν) of a mass splitting δ (GeV); ``weight`` 2 for a wino, 1 for a higgsino
    (Ibe, Matsumoto & Sato arXiv:1212.5989; Thomas & Wells hep-ph/9804359): cτ ≈ 6 cm for a 164 MeV wino."""
    pion = 0.0 if delta <= M_PI else (G_F ** 2 * F_PI ** 2 * V_UD ** 2 * delta ** 3 / math.pi
                                       * math.sqrt(1.0 - (M_PI / delta) ** 2))
    electron = G_F ** 2 * delta ** 5 / (15.0 * math.pi ** 3) if delta > M_E else 0.0
    return weight * (pion + electron)


def _qnumbers(pdg: int, label: str, charge3: int, spin_states: int, colour: int, distinct: bool) -> list[str]:
    """A QNUMBERS block; SModelS reads its entries only with their comments."""
    return [f"BLOCK QNUMBERS {pdg}  # {label}", f"     1  {charge3}   # 3 times electric charge",
            f"     2  {spin_states}   # number of spin states (2S+1)",
            f"     3  {colour}   # colour rep (1: singlet, 3: triplet, 8: octet)",
            f"     4  {1 if distinct else 0}   # particle/antiparticle distinction (0 = own anti)"]


def slha(particles: list[dict], decays: dict[int, tuple[float, list[tuple[float, list[int]]]]],
         xsections: list[tuple[tuple[int, int], float]], order: int = 3, label: str = "table") -> str:
    """An SLHA file: ``particles`` [{pdg, label, charge3, spin_states, colour, distinct, mass}], ``decays``
    {pdg: (width, [(BR, [daughters])])}, ``xsections`` [((pdg₁, pdg₂), σ in pb)] at 13 TeV ((pdg, 0) for
    single production), each with its QCD ``order`` and generator ``label`` (MadGraph's leading order: 0, "MG5LO")."""
    lines = []
    for x in particles:
        lines += _qnumbers(x["pdg"], x["label"], x["charge3"], x["spin_states"], x["colour"], x["distinct"])
    lines += ["BLOCK MASS"] + [f"   {x['pdg']:>8d}   {x['mass']:.6E}   # {x['label']}" for x in particles]
    for x in particles:
        width, channels = decays.get(x["pdg"], (0.0, []))
        lines.append(f"DECAY   {x['pdg']}   {width:.6E}")
        lines += [f"   {br:.6E}   {len(d)}   " + "   ".join(str(k) for k in d) for br, d in channels]
    for (a, b), sigma in xsections:
        if sigma > 0:
            final = f"1  {a}" if b == 0 else f"2  {a} {b}"            # single production: (pdg, 0)
            lines += [f"XSECTION  1.30E+04  2212 2212  {final}", f"  0  {order}  0  0  0  0  {sigma:.6E}  {label}"]
    return "\n".join(lines) + "\n"


def run(files: list[str], timeout_s: int = 3600) -> list[dict]:
    """SModelS on SLHA texts, in one batch (the database is loaded once); results cached by the text."""
    missing = [text for text in dict.fromkeys(files) if _key(text) not in _RESULTS]
    if missing:
        with tempfile.TemporaryDirectory() as folder:
            points = []
            for i, text in enumerate(missing):
                path = Path(folder) / f"p{i}.slha"
                path.write_text(text)
                points.append({"slha_path": str(path), "coverage": True, "sigmacut_fb": 0.0,
                               "compute_statistics": False})
            request = {"points": points, "database": str(_tools() / "smodels-db" / "official321.pcl")}
            done = subprocess.run(["nice", "-n", "10", str(_tools() / ".venv-smodels" / "bin" / "python"),
                                   str(Path(__file__).with_name("smodels_driver.py")), "-"],
                                  input=json.dumps(request), capture_output=True, text=True, timeout=timeout_s,
                                  env=child_environment())
            if done.returncode:
                raise RuntimeError(done.stderr[-2000:])
            rows = json.loads(done.stdout)["points"]
            if len(rows) != len(missing) or any(not isinstance(r, dict) for r in rows):
                raise RuntimeError("SModelS returned an incomplete/malformed batch")
            fresh = dict(zip(missing, rows, strict=True))
            for text, result in fresh.items():
                if result.get("status") != "error":
                    _RESULTS[_key(text)] = result
            return [fresh[text] if text in fresh else _RESULTS[_key(text)] for text in files]
    return [_RESULTS[_key(text)] for text in files]


def _key(text: str) -> str:
    driver = Path(__file__).with_name("smodels_driver.py").read_bytes()
    database = _tools() / "smodels-db" / "official321.pcl"
    version = (database.stat().st_mtime_ns, database.stat().st_size) if database.exists() else None
    return hashlib.sha256(text.encode() + driver + repr((version, "coverage=True,sigmacut=0")).encode()).hexdigest()
