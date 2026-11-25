"""The Yukawa inputs of a model's stated Yukawa-like couplings (the owner's decision #2, 2026-10-20).

A model declares one convention (``ModelSpec.yukawa``) for the masses its stated couplings mean by m_q, m_l and m_f
(a coupling written g m_q/v): the interaction basis's inputs, before any mixing. They are separate from the kinematic
masses (``kinematics.KINEMATIC_MASSES``: thresholds, phase space and propagators, b the DMsimp card's 4.7 GeV in both
routes, whatever the convention) and from explicitly supplied numbers, and they never change the Standard Model Higgs
boson's own Yukawas, which keep the "sm" convention.

- **"sm"** (the default for a model that declares none): b and c MS-bar (one loop, from m̄_b(m̄_b) = 4.18 and
  m̄_c(m̄_c) = 1.27 GeV) at m_h, as the library's Higgs widths take them; t and the leptons at their pole masses, u, d,
  s at the PDG MS-bar masses at 2 GeV (``feynman.yukawa_mass``). So a 2HDM's stated m_q/v · tan β is tan β times h's
  Yukawa (the audit's G1-12).
- **"DMsimp_s_spin0_MD"**: the LHC Dark Matter Forum's spin-0 simplified model with massive b and c, its UFO's YUKAWA
  block (ymup, ymdo, yms, ymc, ymb, ymt, yme, ymm, ymtau), declared by the library's Yukawa-like scalar and
  pseudoscalar mediators.

Two models with the same declared convention agree across ADROIT's routes; two with different Yukawa inputs need not.
"""
from __future__ import annotations

from adroit.core.model_spec import YUKAWA_CONVENTIONS

SM = "sm"
CARDS = {
    "DMsimp_s_spin0_MD": {"u": 0.00255, "d": 0.00504, "s": 0.101, "c": 1.27, "b": 4.7, "t": 172.0,
                          "e": 0.000511, "mu": 0.10566, "tau": 1.777},
}
SOURCES = {
    "DMsimp_s_spin0_MD": "the LHC DM Forum's spin-0 simplified model with massive b and c (the UFO directory "
                         "DMsimp_s_spin0_MD in the tools folder, version 1.1 of 2016.06.02: its parameters.py "
                         "defaults, YUKAWA block, no restriction card)",
}
assert set(YUKAWA_CONVENTIONS) == {SM, *CARDS}


def mass(convention: str, name: str) -> float:
    """The mass a stated coupling's m_f means for the fermion ``name`` under ``convention`` (GeV); 0 for a neutrino."""
    if name.startswith("nu"):
        return 0.0
    if convention == SM:
        from adroit.model_building.feynman import yukawa_mass
        return yukawa_mass(name)
    return CARDS[convention][name]


QUARKS = ("u", "d", "s", "c", "b", "t")


def carried_masses(mb, state: str) -> dict[str, float] | None:
    """The masses a scalar state's quark couplings carry (y = m/v): the Higgs boson's ("sm") for the Higgs doublet's
    own state, the model's declared convention for a state with no doublet component, None for one that mixes the
    two under a convention other than "sm" (its couplings then carry both, and neither is silently taken)."""
    convention = mb.gauge.spec.yukawa
    if convention == SM:
        return {q: mass(SM, q) for q in QUARKS}
    found = next((s for s in mb.spectrum.states if s.name == state), None)
    weights = found.composition if found is not None else {}
    doublet = sum(abs(w) for k, w in weights.items() if k.split("[")[0].split(".")[0] in ("H", "h"))
    other = sum(abs(w) for w in weights.values()) - doublet
    if other <= 1e-12:
        return {q: mass(SM, q) for q in QUARKS}
    if doublet <= 1e-12:
        return {q: mass(convention, q) for q in QUARKS}
    return None


def describe(convention: str) -> str:
    """The convention resolved, for reports: its name, what it means and its numbers."""
    names = ("u", "d", "s", "c", "b", "t", "e", "mu", "tau")
    numbers = ", ".join(f"{n} {mass(convention, n):.4g}" for n in names)
    if convention == SM:
        return (f'"sm": b and c MS-bar (one loop) at m_h, t and the leptons at their pole masses, u, d, s MS-bar at '
                f"2 GeV; the masses in the stated Yukawa-like couplings (GeV): {numbers}")
    return f'"{convention}": {SOURCES[convention]}; the masses in the stated Yukawa-like couplings (GeV): {numbers}'
