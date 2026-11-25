"""Where the generic route disagrees with the literature by O(1) (D35; the external audit of 2026-10-16, item 17).

G12's held-out half found three disagreements without a localised cause (the G12 closure record), recorded by the
owner as an O(1) disagreement between ADROIT and the paper, by factors of 1.25 to 2.5. A trigger here recognises
each regime from the generic route's own quantities at a point, so that a point in it is known without its paper:

- **forbidden channels at a large splitting** (D'Agnolo et al., arXiv:1505.07107): final states heavier than the
  dark matter pair carry at least ``MATERIAL`` of its ⟨σv⟩ at freeze-out, and their splitting
  Δ = (m_c + m_d)/(2 m_χ) − 1 exceeds ``FORBIDDEN_AGREED``, the largest at which the route agreed with the paper
  (Δ = 0.101 and 0.309 within 2%; 0.651 missed by 2.5× in the splitting);
- **an unbroken dark U(1)** (von Harling & Petraki, arXiv:1407.7874): where it binds the dark matter, its
  Sommerfeld effect and bound states together lower Ωh² by at least ``MATERIAL`` (ADROIT's ⟨σ_eff v⟩ about 25%
  weaker than the paper's; which of the two is not localised, so both count);
- **Majorana dark matter near a vector pole** (Okada et al., arXiv:1601.07526, whose cause is not localised): 2 m_χ
  within ``POLE_WINDOW`` of an s-channel vector's mass (its benchmarks sit about 5% below the Z′ pole; ADROIT's
  annihilation 1.8× and 2.5× the paper's).

Inside a regime, Ωh² and the thermal contour are exploratory and carry ``QUALIFICATION``, and a decisive verdict
stands only if the evaluated grid supports it at every relic target in the interval ``TARGET_SCALES`` (the band of
grid points between them, every root at its ends; the re-audit's R17-2, 2026-10-17); otherwise it is pending
(``parameter_space.verdict._across``, ``orchestrator.single_idea._band_across``). A regime is looked for at the
nominal thermal points and at every evaluated point a shifted target in the interval reaches, on the grid and at its
resolution (``verdict._reaching``, ``single_idea._reaching``; the re-audit's R18-4, 2026-10-18). The triggers were derived from the
held-out results and are not tuned against them again; they make results pending or qualified and widen no
acceptance. The owner kept the thresholds (2026-10-17), recorded with their caveats in ``docs/freeze_out_build.md``
§9: the held-out half no longer tests these regimes blind, and a disagreement in a regime nobody has compared would
not be flagged.
"""

from __future__ import annotations

import numpy as np

from adroit.constraints import relic

MATERIAL = 0.05                  # a share of the rate at freeze-out, or of Ωh², that counts (as A06's 5%)
FORBIDDEN_AGREED = 0.309         # the largest forbidden splitting at which the route agreed with D'Agnolo et al.
POLE_WINDOW = 0.10               # |2 m_χ / m_V − 1| for Okada et al.'s regime
TARGET_SCALES = (1 / 2.5, 2.5)   # the relic target's range across the disagreement
QUALIFICATION = "O(1) disagreement with the literature in this regime: ×1.25–2.5"


def regimes(model, p) -> list[str]:
    """The regimes (module docstring) a generic model's point is in, each with its quantities; [] outside them, or
    where Ωh² is not computed."""
    from adroit.parameter_space.portals import generic as g
    if model.domain(p):
        return []
    x_f = g._freeze_out(model.spec_json, model.scan, model.tied, p.m_chi, p.m_med)
    if x_f is None:
        return []
    found = [majorana_pole(model, p), forbidden(model, p, x_f), bound_states(model, p)]
    return [f for f in found if f]


def forbidden(model, p, x_f: float) -> str:
    """The forbidden regime's description at the point, or "": the share of the dark matter pair's ⟨σv⟩ at x_f from
    final states whose splitting exceeds ``FORBIDDEN_AGREED``. Only those channels are tabulated, and only where the
    pair has one (most models stop at the first check)."""
    from adroit.parameter_space.portals import generic as g
    mb, rules, tree_model = model.at(p)
    dm = mb.spectrum.dark_matter()
    m = dm.mass_gev
    anti = dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~"
    bath, _, pairs, finals = g._bath(model.spec_json, model.scan, model.tied, p.m_chi, p.m_med)
    names = [b[0] for b in bath]
    key = tuple(sorted((names.index(dm.name), names.index(anti))))
    masses = {n: x.mass for n, x in tree_model.particles.items()}
    far = {(c, d): (masses.get(c, 0.0) + masses.get(d, 0.0)) / (2.0 * m) - 1.0 for c, d in finals.get(key, [])}
    far = {f: delta for f, delta in far.items() if delta > FORBIDDEN_AGREED}
    if not far or key not in pairs:
        return ""
    poles = g._s_channel(tree_model, dm.name, anti, rules)
    u = relic.energy_grid(m)
    for mass, width in poles:
        u = np.union1d(u, relic.energy_grid(m, mass, width))
    s = (2.0 * m * (1.0 + u)) ** 2

    def average(sigma) -> float:
        return float(relic.thermal_average(u, np.asarray(sigma, float), np.array([x_f]))[0])

    total = average(pairs[key](s))
    part = sum(average(g._tabulate(tree_model, dm.name, anti, f, poles)(s)) for f in far)
    share = part / total if total > 0 else 0.0
    if share < MATERIAL:
        return ""
    return (f"forbidden channels ({', '.join(' '.join(f) for f in sorted(far))}) at a splitting "
            f"Δ = {min(far.values()):.3g} > {FORBIDDEN_AGREED} carry {share:.0%} of the pair's ⟨σv⟩ at freeze-out "
            "(D'Agnolo et al.'s regime)")


def bound_states(model, p) -> str:
    """The dark-U(1) regime's description at the point, or "": where an unbroken dark U(1) binds the dark matter
    (G7 forms its hydrogen-like bound states), the share by which its long-range effects, the Sommerfeld effect and
    the bound states together, lower Ωh² below the perturbative value. Both act mostly after freeze-out, so the
    share is read from Ωh², not from the rate at x_f; it is computed only for such a model."""
    if not (model.sommerfeld and model.bound_states):
        return ""
    if not any(grp.bound == "dark_u1" for grp in model.long_range_effects(p).groups):
        return ""
    full = model.omega_h2(p)
    perturbative = model.model_copy(update={"sommerfeld": False}).omega_h2(p)
    share = 1.0 - full / perturbative if full and perturbative else 0.0
    if share < MATERIAL:
        return ""
    return (f"a dark U(1)'s Sommerfeld effect and bound states lower Ωh² by {share:.0%} (von Harling & Petraki's "
            "regime)")


def majorana_pole(model, p) -> str:
    """Okada et al.'s regime at the point, or "": Majorana dark matter with 2 m_χ within ``POLE_WINDOW`` of a
    Z₂-even vector's mass."""
    mb, rules, _ = model.at(p)
    dm = mb.spectrum.dark_matter()
    if dm.kind != "majorana":
        return ""
    near = [x for x in rules.particles if x.parity == 1 and x.spin == 1 and x.mass > 0
            and abs(2.0 * dm.mass_gev / x.mass - 1.0) <= POLE_WINDOW]
    if not near:
        return ""
    v = min(near, key=lambda x: abs(2.0 * dm.mass_gev / x.mass - 1.0))
    return (f"Majorana dark matter at 2 m_χ = {2 * dm.mass_gev:.4g} GeV, {2 * dm.mass_gev / v.mass - 1:+.1%} from the "
            f"{v.name} pole at {v.mass:.4g} GeV (Okada et al.'s regime)")
