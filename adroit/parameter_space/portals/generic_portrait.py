"""The mediator's portrait (P1 of ``docs/generic_route_next.md``): what the library's searches read from a mediator,
taken from a generic model's own Feynman rules at a point.

For every new Z₂-even neutral, colourless boson (spin 0 or 1) of the model: its mass and total width; its partial
widths into each final pair (Standard Model fermions by name, the dark matter, other new states), the invisible part
(pairs of dark matter and neutrinos only) and the unresolved part (any pair with another new state: whether it is seen
depends on its decays, which the portrait does not follow; the tactical audit's T20-03, 2026-10-20: a Z₂-odd charged
pair had been called invisible); the bounds those decays leave on BR(invisible) (below); its coupling to each Standard Model fermion and to the dark matter as the Lagrangian
writes it; its CP character; and how far its couplings are the photon's, the Z's or the Higgs's.

**Couplings, as the Lagrangian writes them.** For a vector X, L ⊃ X_μ f̄ γ^μ (g_V + g_A γ⁵) f; for a scalar,
L ⊃ X f̄ (g_S + i g_P γ⁵) f. G2's FFV vertex is γ(c + c₂γ⁵) with the antiparticle in its first slot, the opposite order
flipping c (``dd_matching``'s conventions), so (g_V, g_A) = (c, c₂) or (−c, c₂); its FFS vertex is c + ic₂γ⁵ in either
order, (g_S, g_P) = (c, c₂). A Majorana or real field's vertex is twice its Lagrangian coefficient, halved here. A
coupling is reported where |g| > 10⁻¹⁴ of the largest.

**CP.** A scalar is "even" (scalar couplings only), "odd" (pseudoscalar only) or "mixed"; a vector "vector",
"axial" or "mixed" — from its couplings to the Standard Model's fermions, or, for a state with none (a singlet that
does not mix, as the 2HDM+a's a at θ = 0), from its coupling to the dark matter (the batch audit's B20-10).

**Photon-, Z- and Higgs-like.** A vector's couplings to the Standard Model fermions, (g_V, g_A) for each, are
decomposed by least squares onto the Standard Model's own photon and Z couplings (``_standard``: the same generator
and inputs, nothing mixed): g ≈ ε_A g^A + ε_Z g^Z, and a scalar's (g_S, g_P) onto the Standard Model's h's, placed as a
scalar and as a pseudoscalar coupling: g_S ≈ κ g_S^h,
g_P ≈ κ₅ g_S^h (κ = −1 for g_S = +m_f/v: G2's h couples as −m_f/v; an ALP with Yukawa-like couplings has κ₅). ε_A is a dark photon's kinetic mixing ε (a
kinetically mixed vector's couplings appear in its vertices, not in G1's composition, which keeps its state pure), κ a
singlet's mixing angle sin θ; ``pattern_residual`` is the part of the couplings neither explains, |g − fit|/|g| (0 for
a pure dark photon or a pure Higgs-mixed scalar, near 1 for a B − L or a quark-only mediator). The fit runs over every
Standard Model fermion, a coupling the model lacks entering as zero, so a mediator coupled to the muon alone is
neither photon- nor Higgs-like (the tactical audit's T20-01); and the references are the unmixed Standard Model's, so
κ is sin θ, the factor on the Standard Model's heavy-Higgs production, not the ratio to the model's own h, tan θ
(T20-02).

**Unresolved decays (the owner's decision #7, 2026-10-20).** The share of Standard Model pairs seen as such,
``visible_share``, is exact: it is the width into Standard Model pairs other than neutrinos. BR(invisible) has two
extreme assignments, ``invisible_bounds``: the lower counts every unresolved pair as seen, the upper counts as unseen
every unresolved pair whose states are all neutral and colourless (``Channel.may_hide``). A pair with a charged or
coloured state is never invisible, whatever its share. A search is decided only where both assignments give the same
decision (``searches._edges``); there is no tolerated share below which unresolved width is ignored (the 1% of
T20-03 is withdrawn).

**The hadronic window (the owner's decision, 2026-10-20; ``generic_hadronic``).** Below the hadronic opening (2m_π;
3m_π for a CP-odd scalar) a quark or gluon pair is closed. In the window (to 2 GeV for a pure vector current, to 3 GeV
inclusive for any other) the quark and gluon pairs are not computed: they are left out of ``channels`` and the width,
and the portrait carries their reason and bound, 0 ≤ Γ_had ≤ m (``hadronic_reason``, ``hadronic_bound_gev``). Its
width and branching fractions are then bounds: ``assignments`` gives each extreme (the hadronic width at 0 or at its
bound, the unresolved pairs seen or not), ``invisible_bounds`` their range, and ``visible_share``, a single number,
is refused.

The widths are G2's tree-level two-body widths (``feynman.two_body_width``, the rules' own); a channel below threshold
is absent. No QCD correction is applied to a quark channel (the library's s-channel widths are also tree level).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field

from adroit.core.state import StrictModel

STANDARD = ("A", "Z", "W", "g", "h")
TINY = 1e-14



class Channel(StrictModel):
    """One two-body decay: its final pair, its width (GeV), whether nothing visible comes out (dark matter and
    neutrinos only), whether that is unknown (a new state other than the dark matter), and, if it is, whether the pair
    could be unseen (every state neutral and colourless: module docstring)."""
    final: tuple[str, str]
    width_gev: float
    invisible: bool = False
    unresolved: bool = False
    may_hide: bool = False


class FermionCoupling(StrictModel):
    """A fermion's coupling to the mediator as the Lagrangian writes it (module docstring): (g_V, g_A) for a vector,
    (g_S, g_P) for a scalar."""
    fermion: str
    even: float                    # g_V or g_S
    odd: float                     # g_A or g_P


class MediatorPortrait(StrictModel):
    """One new neutral boson at a point (module docstring)."""
    name: str
    spin: float
    mass_gev: float
    width_gev: float
    channels: list[Channel] = Field(default_factory=list)
    invisible_width_gev: float = 0.0
    unresolved_width_gev: float = 0.0
    standard_model: list[FermionCoupling] = Field(default_factory=list)
    dark_matter: FermionCoupling | None = None
    cp: str = ""
    photon_like: float = 0.0       # ε_A: the vector's couplings as a multiple of the photon's
    z_like: float = 0.0            # ε_Z: … of the Z's
    higgs_like: float = 0.0        # κ: the scalar's couplings as a multiple of the SM-like h's
    pseudo_higgs_like: float = 0.0 # κ₅: its pseudoscalar couplings as a multiple of the h's (scalar) ones
    pattern_residual: float = 1.0  # the part of the couplings these do not explain
    hadronic_reason: str = ""      # why the quark and gluon pairs are not computed (the hadronic window), or ""
    hadronic_bound_gev: float = 0.0  # their width's upper bound there (m), 0 elsewhere

    def partial(self, a: str, b: str) -> float:
        """The width into the pair (a, b), either order (an antiparticle named with ~)."""
        pair = sorted((a, b))
        return sum(c.width_gev for c in self.channels if sorted(c.final) == pair)

    def coupling(self, fermion: str) -> FermionCoupling | None:
        return next((c for c in self.standard_model if c.fermion == fermion), None)

    def visible_share(self) -> float:
        """The share of the width into Standard Model pairs other than neutrinos: exact, whatever the unresolved
        pairs do (module docstring). 1 exactly for a mediator that decays to nothing else. Raises
        ``hadronic_window.HadronicUnknown`` in the hadronic window, where it is a range (``assignments``)."""
        from adroit.constraints import hadronic_window as hw
        if self.hadronic_reason:
            raise hw.HadronicUnknown(self.hadronic_reason)
        if self.width_gev <= 0:
            return 0.0
        if self.invisible_width_gev == 0.0 and self.unresolved_width_gev == 0.0:
            return 1.0
        return sum(c.width_gev for c in self.channels if not (c.invisible or c.unresolved)) / self.width_gev

    def assignments(self) -> list[tuple[float, float, float]]:
        """(Γ, BR(invisible), the share of Standard Model pairs other than neutrinos) at each extreme assignment
        (module docstring): the hadronic width at 0 and at its bound, each unresolved pair that could be unseen
        counted as seen and as unseen. One assignment where neither is unknown."""
        hidden = sum(c.width_gev for c in self.channels if c.unresolved and c.may_hide)
        visible = sum(c.width_gev for c in self.channels if not (c.invisible or c.unresolved))
        out = []
        for extra in sorted({0.0, self.hadronic_bound_gev}):
            width = self.width_gev + extra
            for unseen in sorted({0.0, hidden}):
                out.append((width, (self.invisible_width_gev + unseen) / width if width > 0 else 0.0,
                            (visible + extra) / width if width > 0 else 0.0))
        return list(dict.fromkeys(out))

    def invisible_bounds(self) -> tuple[float, float]:
        """BR(invisible)'s two extreme assignments (module docstring): the dark matter's and neutrinos' pairs alone,
        at the hadronic width's bound, and those with every unresolved pair that could be unseen, at no hadronic
        width. Equal where nothing is unresolved or unknown, or where every unresolved pair holds a charged or
        coloured state."""
        found = [a[1] for a in self.assignments()]
        return min(found), max(found)

    def unresolved_reason(self) -> str:
        """What the unresolved pairs and the hadronic window leave unknown (``invisible_bounds``), or "" if
        nothing."""
        parts = []
        low, high = self.invisible_bounds()
        if self.unresolved_width_gev > 0 and self.width_gev > 0:
            pairs = sorted({" ".join(c.final) for c in self.channels if c.unresolved})
            parts.append(f"{self.name} decays {self.unresolved_width_gev / self.width_gev:.3g} of the time to new "
                         f"states ({'; '.join(pairs)}) whose decays decide whether they are seen, which ADROIT does "
                         "not follow")
        if self.hadronic_reason:
            parts.append(f"{self.hadronic_reason}: Γ between {self.width_gev:.3g} and "
                         f"{self.width_gev + self.hadronic_bound_gev:.3g} GeV")
        return "; ".join(parts) + (f": BR(invisible) is between {low:.3g} and {high:.3g}" if parts else "")


def portraits(engine, p) -> list[MediatorPortrait]:
    """Every new neutral, colourless Z₂-even boson of the generic model at the point, heaviest last; none where a
    coupling is below the generic route's resolution (``generic._feeble``: a partly dropped coupling pattern would be
    misread, e.g. a feeble B − L vector whose quark couplings vanish as a dark photon)."""
    from adroit.parameter_space.portals.generic import _feeble
    if _feeble(engine.spec_json, engine.scan, engine.tied, p.m_chi, p.m_med):
        return []
    mb, rules, _ = engine.at(p)
    dm = mb.spectrum.dark_matter().name
    found = [x for x in rules.particles if x.parity == 1 and x.name not in STANDARD and x.spin in (0, 1)
             and x.colour == "1" and abs(x.charge) < 1e-9 and x.mass > 0]
    return sorted((_portrait(mb, rules, x, dm) for x in found), key=lambda m: m.mass_gev)


def _portrait(mb, rules, x, dm: str) -> MediatorPortrait:
    from adroit.model_building.feynman import SM_FERMIONS
    sm = {f.name for f in SM_FERMIONS}
    neutrinos = {f.name for f in SM_FERMIONS if f.name.startswith("nu")}
    by = {r.name: r for r in rules.particles} | {r.anti: r for r in rules.particles if r.anti}
    couplings, dark = {}, None
    for v in rules.vertices:
        if v.kind not in ("FFV", "FFS") or v.legs[2] != x.name:
            continue
        a, b = v.legs[0], v.legs[1]
        base = a.rstrip("~")
        if b.rstrip("~") != base:
            continue                                # an off-diagonal vertex (two different fermions): not a coupling
        flipped = v.kind == "FFV" and not a.endswith("~") and b.endswith("~")
        c, c2 = complex(v.c), complex(v.c2)
        even = (-c if flipped else c).real
        odd_part = c2.real
        if not by[base].anti or by[base].anti == base:       # Majorana: the vertex is twice the coefficient
            even, odd_part = even / 2, odd_part / 2
        entry = FermionCoupling(fermion=base, even=even, odd=odd_part)
        if base in sm:
            couplings[base] = entry
        elif base == dm:
            dark = entry
    largest = max([abs(c.even) + abs(c.odd) for c in couplings.values()] + [0.0])
    kept = [c for c in couplings.values() if abs(c.even) + abs(c.odd) > TINY * max(largest, 1.0)]
    channels, hadronic = _hadronic(rules, x, _channels(rules, x, by))
    dark_names = {dm, f"{dm}~"}
    invisible = dark_names | neutrinos | {f"{n}~" for n in neutrinos}
    known = dark_names | sm | {f"{f}~" for f in sm} | set(STANDARD) | {"W~"}
    channels = [c.model_copy(update={"invisible": all(f in invisible for f in c.final),
                                     "unresolved": any(f not in known for f in c.final),
                                     "may_hide": all(_neutral(by[f]) for f in c.final)}) for c in channels]
    return MediatorPortrait(name=x.name, spin=x.spin, mass_gev=x.mass, width_gev=sum(c.width_gev for c in channels),
                            channels=channels, invisible_width_gev=sum(c.width_gev for c in channels if c.invisible),
                            unresolved_width_gev=sum(c.width_gev for c in channels if c.unresolved),
                            standard_model=kept, dark_matter=dark, cp=_cp(x.spin, kept or ([dark] if dark else [])),
                            hadronic_reason=hadronic, hadronic_bound_gev=x.mass if hadronic else 0.0,
                            **_pattern(x, couplings))


def _hadronic(rules, x, channels: list[Channel]) -> tuple[list[Channel], str]:
    """(the channels computed, why the quark and gluon pairs are not, or ""): below x's hadronic opening and in its
    window those pairs are left out, with the window's reason where they would be open (module docstring)."""
    from adroit.constraints import hadronic_window as hw
    from adroit.parameter_space.portals import generic_hadronic as gh
    if gh.state(rules, x.name) == hw.PARTONIC:
        return channels, ""
    kept = [c for c in channels if not any(f in gh.PARTON_NAMES for f in c.final)]
    return kept, gh.windowed(rules).get(x.name, "")


def _neutral(particle) -> bool:
    """Whether a state is neutral and colourless (a charged or coloured one is always seen: module docstring)."""
    return abs(particle.charge) < 1e-9 and particle.colour == "1"


def _channels(rules, x, by) -> list[Channel]:
    """Every open two-body decay of x from the rules' vertices (``pair_production.decay_table``'s sum, by name)."""
    from adroit.model_building.feynman import _colour_factor, two_body_width
    out: dict[tuple[str, str], float] = {}
    for v in rules.vertices:
        if v.legs.count(x.name) != 1 or len(v.legs) != 3:
            continue
        others = [o for o in v.legs if o != x.name]
        if sum(by[o].mass for o in others) >= x.mass:
            continue
        colour = _colour_factor(x.colour, [by[o].colour for o in others]) or 1.0
        width = two_body_width(v, v.legs.index(x.name), [by[o].mass for o in v.legs], colour)
        width *= 0.5 if others[0] == others[1] else 1.0
        if width > 0:
            key = tuple(sorted(others))
            out[key] = out.get(key, 0.0) + float(width)
    return [Channel(final=k, width_gev=w) for k, w in sorted(out.items())]


def _cp(spin: float, couplings: list[FermionCoupling]) -> str:
    even = any(abs(c.even) > TINY for c in couplings)
    odd = any(abs(c.odd) > TINY for c in couplings)
    names = ("even", "odd") if spin == 0 else ("vector", "axial")
    return "mixed" if even and odd else names[0] if even else names[1] if odd else ""


def _sm_couplings(rules, boson: str, sm: set[str]) -> dict[str, tuple[float, float]]:
    """A Standard Model boson's (even, odd) couplings to each SM fermion, in the portrait's convention."""
    out = {}
    for v in rules.vertices:
        if v.kind not in ("FFV", "FFS") or v.legs[2] != boson or v.legs[0].rstrip("~") != v.legs[1].rstrip("~"):
            continue
        base = v.legs[0].rstrip("~")
        if base in sm:
            flipped = v.kind == "FFV" and not v.legs[0].endswith("~") and v.legs[1].endswith("~")
            c, c2 = complex(v.c), complex(v.c2)
            out[base] = ((-c if flipped else c).real, c2.real)
    return out


def _pattern(x, couplings: dict) -> dict[str, float]:
    """ε_A, ε_Z (a vector) or κ (a scalar) and the residual (module docstring): over every Standard Model fermion,
    against the unmixed Standard Model's photon, Z and h."""
    import numpy as np
    from adroit.model_building.feynman import SM_FERMIONS
    if not couplings:
        return {}
    fermions = [f.name for f in SM_FERMIONS]
    absent = FermionCoupling(fermion="", even=0.0, odd=0.0)
    g = np.array([v for f in fermions for v in (couplings.get(f, absent).even, couplings.get(f, absent).odd)])
    references = ["A", "Z"] if x.spin == 1 else ["h", "h5"]
    basis = []
    for boson in references:
        known = _standard()[boson[:1]]
        pattern = [known.get(f, (0.0, 0.0)) for f in fermions]
        basis.append([v for even, _ in pattern for v in ((0.0, even) if boson == "h5" else (even, 0.0))]
                     if boson[0] == "h" else [v for pair in pattern for v in pair])
    basis = np.array(basis, dtype=float).T
    usable = np.abs(basis).sum(0) > 0
    coefficients = np.zeros(len(references))
    if usable.any():
        coefficients[usable] = np.linalg.lstsq(basis[:, usable], g, rcond=None)[0]
    residual = float(np.linalg.norm(g - basis @ coefficients) / max(np.linalg.norm(g), 1e-300))
    if x.spin == 1:
        return {"photon_like": float(coefficients[0]), "z_like": float(coefficients[1]), "pattern_residual": residual}
    return {"higgs_like": float(coefficients[0]), "pseudo_higgs_like": float(coefficients[1]),
            "pattern_residual": residual}


@lru_cache(maxsize=1)
def _standard() -> dict[str, dict[str, tuple[float, float]]]:
    """The Standard Model's photon, Z and h couplings to its fermions, through G1 and G2 (a singlet dark scalar
    beside it, as ``generic._measured_over_tree``)."""
    from adroit.core.model_spec import ModelSpec
    from adroit.model_building import feynman, spectrum
    from adroit.model_building.feynman import SM_FERMIONS
    model = ModelSpec.model_validate({"name": "sm", "phase": "unbroken", "fields": [
        {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1, "mass_gev": 1e3},
        {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}}]})
    rules = feynman.feynman_rules(spectrum.compute(model))
    sm = {f.name for f in SM_FERMIONS}
    return {boson: _sm_couplings(rules, boson, sm) for boson in ("A", "Z", "h")}
