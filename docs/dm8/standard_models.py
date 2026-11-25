"""Standard quark-level models through DirectDM, compared with every library card (section 2).

Five models, each at m_χ = 100 GeV, coefficient 10⁻⁶ GeV⁻² (dimension 6) or
10⁻⁷ GeV⁻³ (dimension 7, whose operators carry m_q):
- universal vector (DMWG V1): C61q for q = u, d, s, c, b;
- universal axial (DMWG A1): C64q;
- isovector axial: C64u = −C64d, in the three-flavour theory;
- scalar with Yukawa-like couplings: C75q;
- pseudoscalar with Yukawa-like couplings: C78q.

For each, the best five cards and the named cards' fits, with the residual
(relative, in matching's rate-weighted measure) and the operators that carry it,
with DirectDM's running from m_Z to 2 GeV and without it. For the vector
model, also the vector card at its physical couplings, g_V = 3g_q and
g_T = 3(κ_p + κ_n)g_q, rather than fitted ones.

Run from the repository root (seconds; needs DirectDM's environment):

    uv run python docs/dm8/standard_models.py

Writes docs/dm8/standard_models.txt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.library.interactions import matching  # noqa: E402
from adroit.library.interactions import quark_level as ql  # noqa: E402
from adroit.library.interactions import registry  # noqa: E402

MASS_GEV = 100.0
KAPPA_P, KAPPA_N = 1.7928, -1.9130
ALL = "udscb"
MODELS = {
    "universal vector (V1)": (5, {f"C61{q}": 1e-6 for q in ALL}, ["M_vector", "O1"]),
    "universal axial (A1)": (5, {f"C64{q}": 1e-6 for q in ALL}, ["M_axial", "O4", "L15"]),
    "isovector axial": (3, {"C64u": 1e-6, "C64d": -1e-6}, ["M_axial", "O4"]),
    "scalar, Yukawa-like": (5, {f"C75{q}": 1e-7 for q in ALL}, ["M_scalar", "O1", "L01"]),
    "pseudoscalar, Yukawa-like": (5, {f"C78{q}": 1e-7 for q in ALL}, ["M_pseudoscalar", "O6"]),
}


def line(fit: matching.CardMatch) -> str:
    """One card's fit in a line."""
    remainder = ", ".join(f"O{i}: {share:.2f}" for i, share in fit.remainder.items()) or "—"
    return f"    {fit.card_id:24s} {fit.verdict:9s} residual {fit.residual:.2g}   remainder {remainder}"


def physical_vector(rge: bool) -> str:
    """The vector card at the couplings a universal quark vector current gives, against DirectDM."""
    flavours, coefficients, _ = MODELS["universal vector (V1)"]
    model = ql.QuarkLevelModel(name="V1", flavours=flavours, coefficients=coefficients, rge=rge)
    particle, interaction = ql.to_interaction(model, MASS_GEV)
    m_med = matching.CONTACT_MASS_GEV
    g_q = -coefficients["C61u"] * m_med ** 2          # C61q = −g_χ g_q / M², g_χ = 1
    g_t = 3 * (KAPPA_P + KAPPA_N) * g_q
    card = registry.resolve("M_vector", particle, {"g_chi": 1.0, "m_med": m_med, "gV_p": 3 * g_q,
                                                   "gV_n": 3 * g_q, "gT_p": g_t, "gT_n": g_t})
    target = matching.vector(interaction)
    difference = np.linalg.norm(matching.vector(card) - target) / np.linalg.norm(target)
    fitted = matching.fit_card("M_vector", particle, interaction).values
    return (f"    running {rge!s:5s}: physical couplings differ by {difference:.2g}; "
            f"the free fit has g_T/g_V = {fitted['gT_p'] / fitted['gV_p']:.3f} (physical {g_t / (3 * g_q):.3f})")


def main() -> None:
    """Every model, its best cards and the named ones."""
    out = [f"DirectDM → library cards, m_χ = {MASS_GEV:g} GeV", ""]
    for name, (flavours, coefficients, named) in MODELS.items():
        fits = {}
        for rge in (True, False):
            model = ql.QuarkLevelModel(name=name, flavours=flavours, coefficients=coefficients, rge=rge)
            fits[rge] = matching.match(*ql.to_interaction(model, MASS_GEV))
        out += [f"{name} ({flavours} flavours): best five, with running", *map(line, fits[True][:5])]
        for rge in (True, False):
            by_id = {f.card_id: f for f in fits[rge]}
            out += [f"  named, {'with' if rge else 'without'} running",
                    *(line(by_id[c]) for c in named if c in by_id)]
        out.append("")
    out += ["the vector card at physical couplings, against DirectDM",
            physical_vector(True), physical_vector(False), ""]
    text = "\n".join(out)
    Path(__file__).with_suffix(".txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
