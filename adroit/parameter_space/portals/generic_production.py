"""A generic model's mediator singly produced at the LHC (13 TeV), from its portrait (P2 of
``docs/generic_route_next.md``): the library's MadGraph tables (``constraints.production``), decomposed by flavour, so
that any pattern of couplings is covered, not only the library families'.

- **A vector** (q q̄ → X): the per-flavour tables at unit vector coupling to one quark, σ = Σ_q (g_V,q² + g_A,q²) σ_q
  over u, d, s, c and b (for massless quarks the axial coupling produces as the vector one; the top does not enter),
  at leading order, as the library's Z′ (its K ≈ 1.2–1.35 left out: conservative).
- **A scalar** (gg → X through the top and bottom loops): the tables at unit Yukawa-like coupling to the top, to the
  bottom and to both, for a scalar and for a pseudoscalar coupling, σ = κ_t² σ_t + κ_b² σ_b + κ_t κ_b (σ_tb − σ_t − σ_b)
  for each (they do not interfere in the rate), with κ_q = g_q v/m_q in the tables' own masses (MadGraph's Yukawa
  masses, ``TABLE_MASSES``), times the Higgs Cross Section Working Group's K-factor (as the library's). A scalar whose
  couplings to the six quarks are exactly the unmixed Standard Model h's times κ, with no pseudoscalar part
  (``heavy_higgs_kappa``), is a Standard-Model-like heavy Higgs in production: κ² times the Working Group's NNLO+NNLL
  σ (as the library's h₂). The quarks only, all six, an absent coupling as zero: they make it, its leptons do not
  (the tactical audit's T20-01: a muon-only scalar had been given the top loop's 53 pb); and the unmixed h, so that
  a mixed singlet's κ is sin θ (T20-02: the model's own h had given tan θ, 56% too much production at sin θ = 0.6).

In the narrow-width approximation the branching fractions are the portrait's own. Outside a table's masses, or
without it, nothing is returned and the reason is given.
"""
from __future__ import annotations

from adroit.core.state import StrictModel

QUARK_TABLES = {q: f"zprime_spin1_{q}_13TeV_LO" for q in ("u", "d", "s", "c", "b")}
GLUON_TABLES = {(cp, loop): f"ggS_spin0_{'S' if cp == 'even' else 'P'}_{loop}_13TeV_LO"
                for cp in ("even", "odd") for loop in ("t", "b", "tb")}
TABLE_MASSES = {"t": 172.5, "b": 4.7}     # MadGraph's Yukawa masses in the gluon-fusion tables (DMsimp_s_spin0)
V_GEV = 246.22
HIGGS_LIKE = 1e-6                         # the pattern residual below which a scalar is a heavy Higgs


class Production(StrictModel):
    """σ (pb) of the mediator's single production, how it was taken, or why not."""
    sigma_pb: float | None = None
    process: str = ""
    why: str = ""


def single(portrait) -> Production:
    """The portrait's mediator produced singly (module docstring)."""
    if portrait.spin == 1:
        return _drell_yan(portrait)
    return _gluon_fusion(portrait)


def _drell_yan(portrait) -> Production:
    from adroit.constraints import production
    missing = production.unavailable(*QUARK_TABLES.values())
    if missing:
        return Production(process="q q̄ → X", why=missing)
    total = 0.0
    for quark, table in QUARK_TABLES.items():
        c = portrait.coupling(quark)
        if c is None:
            continue
        sigma = production.sigma_pb(table, portrait.mass_gev)
        if sigma is None:
            return Production(process="q q̄ → X", why=f"{portrait.mass_gev:.4g} GeV is outside MadGraph's q q̄ → Z′ "
                                                         f"tables {production.mass_range(table)}")
        total += (c.even ** 2 + c.odd ** 2) * sigma
    return Production(sigma_pb=total, process="q q̄ → X at leading order, Σ_q (g_V² + g_A²) σ_q")


def heavy_higgs_kappa(portrait) -> float | None:
    """κ where the scalar's couplings to the six quarks are the unmixed Standard Model h's times κ, to ``HIGGS_LIKE``,
    with no pseudoscalar part; else None (module docstring)."""
    import numpy as np
    from adroit.parameter_space.portals.generic_portrait import TINY, _standard
    quarks = ("u", "d", "s", "c", "b", "t")
    found = [portrait.coupling(q) for q in quarks]
    if any(c is not None and abs(c.odd) > TINY for c in found):
        return None
    g = np.array([c.even if c is not None else 0.0 for c in found])
    h = np.array([_standard()["h"][q][0] for q in quarks])
    if not g.any():
        return None
    kappa = float(g @ h / (h @ h))
    return kappa if np.linalg.norm(g - kappa * h) <= HIGGS_LIKE * np.linalg.norm(g) else None


def _gluon_fusion(portrait) -> Production:
    from adroit.constraints import production
    m = portrait.mass_gev
    kappa = heavy_higgs_kappa(portrait)
    if kappa is not None:
        sigma = production.heavy_higgs_pb(m)
        if sigma is None:
            return Production(process="gg → X", why=f"{m:.4g} GeV is outside the Working Group's heavy-Higgs table")
        return Production(sigma_pb=kappa ** 2 * sigma,
                          process="gg → X as a Standard-Model-like heavy Higgs × κ² (NNLO+NNLL)")
    missing = production.unavailable(*GLUON_TABLES.values())
    if missing:
        return Production(process="gg → X", why=missing)
    k = production.gluon_fusion_k(m)
    total = 0.0
    for cp, part in (("even", "even"), ("odd", "odd")):
        kt, kb = (_kappa(portrait, q, part) for q in ("t", "b"))
        if not kt and not kb:
            continue
        s = {loop: production.sigma_pb(GLUON_TABLES[cp, loop], m) for loop in ("t", "b", "tb")}
        if any(v is None for v in s.values()):
            return Production(process="gg → X", why=f"{m:.4g} GeV is outside MadGraph's gg → S tables")
        total += kt ** 2 * s["t"] + kb ** 2 * s["b"] + kt * kb * (s["tb"] - s["t"] - s["b"])
    if k is None:
        return Production(process="gg → X", why=f"no gluon-fusion K-factor at {m:.4g} GeV")
    return Production(sigma_pb=total * k, process="gg → X through the t and b loops (LO tables × the Working Group's K)")


def _kappa(portrait, quark: str, part: str) -> float:
    """The quark's Yukawa-like coupling in the tables' units, g v/m (the tables' own m)."""
    c = portrait.coupling(quark)
    if c is None:
        return 0.0
    return (c.even if part == "even" else c.odd) * V_GEV / TABLE_MASSES[quark]
