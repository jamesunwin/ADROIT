"""Which comparisons each experimental record decides (1.0.1, the repairs audit's RA-01, 2026-11-25).

A point's certificate knows the records its calculation read and the version of each (``Bound.records``); its
comparisons are named by constraint (``PointResult.excluded``). This table joins them, so that a record whose version
is unknown qualifies the comparisons that read it, and no other: an exclusion stands only where at least one deciding
comparison's records are all established (``assessment.from_crossing``). A record not in the table qualifies every
comparison (``qualified``), never none. ``tests/parameter_space/test_point_assessment.py`` requires every record in
``data/records.yaml`` to be listed, every name to be a constraint a scan reports (``checklist.ITEM_OF``), and every
edge the code declares (each ``_blocked(name, record)`` gate and ``searches.outcomes``' record map) to be here (the
recheck's RB-01: a theory input shared by two comparisons had been tied to one).
"""
from __future__ import annotations

EVERY = None        # an unplaced record: every comparison is qualified

# record id -> the constraint names (``PointResult.excluded`` keys) whose comparison reads it
COMPARISONS: dict[str, tuple[str, ...]] = {
    "fermi-1503.02641-dsph": ("gamma rays (Fermi-LAT dwarfs)",),
    "fermi-2311.04982-spectral": ("gamma rays (Fermi-LAT dwarfs)",),
    "fermi-lat-1506.00013-lines": ("γ-ray lines (Fermi-LAT, H.E.S.S.)",),
    "hess-1805.05741-lines": ("γ-ray lines (Fermi-LAT, H.E.S.S.)",),
    "hess-2608.07234-lines": ("γ-ray lines (Fermi-LAT, H.E.S.S.)",),
    "dampe-2112.08860-lines": ("γ-ray lines (Fermi-LAT, H.E.S.S.)",),
    "calore-2202.03076-pbar": ("antiprotons (AMS-02)",),
    "icecube-1612.05949-sd": ("capture in the Sun (IceCube)",),
    "icecube-1612.05949-si": ("capture in the Sun (IceCube)",),
    "planck-2018-pann": ("CMB (Planck)",),
    "cms-2405.13778-V1": ("colliders (CMS)",),
    "cms-2405.13778-A1": ("colliders (CMS)",),
    "cms-2405.13778-V2": ("colliders (CMS)",),
    "cms-2405.13778-A2": ("colliders (CMS)",),
    "smodels-3.2.1": ("LHC searches (SModelS)",),
    "cms-1806.00843-dijet": ("LHC dijet resonances (CMS, ATLAS)",),
    "atlas-1910.08447-dijet-gaussian": ("LHC dijet resonances (CMS, ATLAS)",),
    "cms-1908.01115-ttbar": ("LHC tt̄ resonances (CMS)",),
    "cms-2107.13021-monojet-spin0": ("LHC monojet, spin-0 mediator (CMS)",),
    "atlas-1903.06248-dilepton": ("LHC dilepton resonances (ATLAS)",),
    "atlas-2010.14293-squark": ("LHC squark search (ATLAS)",),
    "atlas-2306.00641-2hdma": ("LHC 2HDM+a searches (ATLAS)",),
    "atlas-2108.13391-monoh": ("2HDM+a mono-Higgs (ATLAS)",),
    "atlas-2111.08372-monoz": ("2HDM+a mono-Z (ATLAS)",),
    "atlas-2009.14791-zz": ("heavy scalar → ZZ, WW (ATLAS)",),
    "atlas-2004.14636-ww": ("heavy scalar → ZZ, WW (ATLAS)",),
    "lep-inert-doublet": ("LEP (inert doublet)",),
    "lep-charginos": ("LEP (charged partners)",),
    "opal-hep-ex-0309014-sleptons": ("LEP (charged partners)",),
    "cms-1808.03684-4mu": ("L_μ − L_τ (Z → 4μ)",),
    "atlas-2301.09342-4mu": ("L_μ − L_τ (Z → 4μ)",),
    "lmu-ltau-babar-belle2": ("L_μ − L_τ (BaBar/Belle II)",),
    "ccfr-1406.2332-trident": ("L_μ − L_τ (CCFR)",),
    "atlas-2301.10731-hinv": ("invisible Higgs width (ATLAS)",),
    "lep-hep-ex-0509008-zinv": ("invisible Z width (LEP)",),
    "atlas-2207.00092-higgs-mu": ("Higgs signal strength (ATLAS)",),
    "muon-g2-2025": ("muon g−2",),
    "lep-contact-bl": ("LEP-II contact interactions",),
    "pdg-2024-electroweak-st": ("electroweak precision (S, T)",),
    "darkcast-dark-photon": ("dark-photon searches",),
    # the invisible decay's record also gives LHCb's B → K a (a → μμ) comparison its form factors (searches._lhcb_mumu)
    "flavour-b-to-k-invisible": ("flavour (B → K a)", "flavour (B → K a, a → μμ)"),
    "lhcb-1612.07818-b-to-k-mumu": ("flavour (B → K a, a → μμ)",),
    "li-2412.04572-bsgamma": ("B → X_s γ (charged Higgs)",),
    "dmwg-1810.09420-bsmumu": ("B_s → μμ (2HDM)",),
    # the N_eff records: either name, conservatively both
    "sabti-1910.01649-bbn": ("BBN and N_eff", "N_eff (Planck 2018)"),
    "ibe-1912.12152-dark-photon-neff": ("BBN and N_eff", "N_eff (Planck 2018)"),
    "escudero-1901.02010-neff": ("BBN and N_eff", "N_eff (Planck 2018)"),
}
# records no comparison of a point's exclusion reads (the relic target: the thermal claim's own checks cover it)
NOT_A_COMPARISON = ("planck-2018-omega",)


def qualified(record_ids) -> set[str] | None:
    """The constraint names whose comparisons the records ``record_ids`` qualify; None (every comparison) if any record
    is not in the table."""
    names: set[str] = set()
    for rid in record_ids:
        if rid in NOT_A_COMPARISON:
            continue
        found = COMPARISONS.get(rid, EVERY)
        if found is EVERY:
            return None
        names.update(found)
    return names
