"""Effective operators of the dark sector up to dimension 6, and their validity (DM12).

A dark field that is a Standard Model gauge singlet couples to the Standard
Model at dimension 5 and 6 through a **dark bilinear** times a **Standard Model
block** of the same Lorentz type, with coefficient c/Λ^{d−4}:

| dark field | bilinears (dimension) |
|---|---|
| Dirac fermion χ | χ̄χ, χ̄iγ⁵χ (3; S), χ̄γ^μχ, χ̄γ^μγ⁵χ (3; V), χ̄σ^{μν}χ, χ̄σ^{μν}iγ⁵χ (3; T) |
| Majorana fermion | χ̄χ, χ̄iγ⁵χ (S), χ̄γ^μγ⁵χ (V): its vector and tensor bilinears vanish |
| complex scalar φ | φ*φ (2; S), φ* i∂↔^μ φ (3; V) |
| real scalar S | S² (2; S) |
| neutral vector V | V_μV^μ (2; S) |

The Standard Model blocks: |H|² (2) and |H|⁴ (4) of type S; H† iD↔_μ H, the
currents f̄γ_μf of Q, uR, dR, L, eR (flavour matrices) and ∂^νB_μν (3) of type
V; B_μν and its dual (2) of type T. Their products of dimension 5 to the
chosen maximum are listed; those of dimension ≤ 4 are renormalizable and in
``lagrangian``. A dark field charged under the Standard Model is left to the
renormalizable generator.

**Validity of the EFT** (``eft_flags``): the operators describe a heavier
sector only at energies below Λ. Direct detection probes q ≲ 0.3 GeV;
freeze-out probes √s ≈ 2m_χ; the LHC probes √ŝ up to a few TeV. A
perturbative completion has its mediator at M ≲ 4πΛ (Λ = M/√(g₁g₂), g ≤ 4π).
"""

from __future__ import annotations

from adroit.core.model_spec import Charges, FieldRole, ModelField, ModelSpec
from adroit.model_building.lagrangian import Operator

Q_MAX_GEV = 0.3          # the largest momentum transfer of the searches (xenon at high recoil)
COLLIDER_GEV = 2000.0    # a typical partonic √ŝ reach at the LHC

SM_BLOCKS: list[tuple[str, str, int, list[str]]] = [        # (text, Lorentz type, dimension, fields)
    ("|H|²", "S", 2, ["H", "H"]), ("|H|⁴", "S", 4, ["H", "H", "H", "H"]),
    ("H† iD↔_μ H", "V", 3, ["H", "H"]),
    *[(f"{f}̄ γ_μ {f}", "V", 3, [f, f]) for f in ("Q", "uR", "dR", "L", "eR")],
    ("∂^ν B_μν", "V", 3, ["B"]), ("B_μν", "T", 2, ["B"]), ("B̃_μν", "T", 2, ["B"]),
]


def _singlet(c: Charges) -> bool:
    return c.su3 == "1" and c.su2 == 1 and c.hypercharge == 0


def bilinears(field: ModelField) -> list[tuple[str, str, int, str]]:
    """(text, Lorentz type, dimension, ModelSpec label) of a dark field's bilinears."""
    n = field.name
    if field.spin == 0.5:
        out = [(f"{n}̄{n}", "S", 3, "scalar"), (f"{n}̄iγ⁵{n}", "S", 3, "pseudoscalar"),
               (f"{n}̄γ^μγ⁵{n}", "V", 3, "axial")]
        if not field.self_conjugate:
            out += [(f"{n}̄γ^μ{n}", "V", 3, "vector"), (f"{n}̄σ^μν{n}", "T", 3, "dipole"),
                    (f"{n}̄σ^μν iγ⁵{n}", "T", 3, "dipole")]
        return out
    if field.spin == 0:
        if field.self_conjugate:
            return [(f"{n}²", "S", 2, "scalar")]
        return [(f"{n}*{n}", "S", 2, "scalar"), (f"{n}* i∂↔^μ {n}", "V", 3, "scalar_current")]
    if field.spin == 1:
        return [(f"{n}_μ{n}^μ", "S", 2, "scalar")]
    return []


def _label(dark_label: str, block: str) -> str:
    if "∂^ν B" in block:
        return "anapole" if dark_label == "axial" else "charge_radius"
    return dark_label


def operators(spec: ModelSpec, max_dimension: int = 6) -> list[Operator]:
    """The dark matter's effective operators with the Standard Model, of dimension 5 to ``max_dimension``."""
    out = []
    for field in spec.fields:
        if field.role is not FieldRole.dark_matter or not _singlet(field.charges):
            continue
        for text, kind, dim, label in bilinears(field):
            for block, block_kind, block_dim, sm_fields in SM_BLOCKS:
                d = dim + block_dim
                if kind != block_kind or not 5 <= d <= max_dimension:
                    continue
                out.append(Operator(blocks=[text, block], fields=[field.name, field.name, *sm_fields],
                                    structure="eft", lorentz=_label(label, block), dimension=float(d),
                                    count=9 if "γ_μ" in block and block[0] != "H" else 1, hermitian=True,
                                    text=f"({text})({block}) / Λ^{d - 4}"))
    return out


def eft_flags(dimension: float, cutoff_gev: float | None, dm_mass_gev: float | None) -> list[str]:
    """Where an operator of this dimension and cutoff Λ stops describing the physics."""
    if dimension <= 4:
        return []
    if cutoff_gev is None:
        return [f"a dimension-{dimension:g} operator needs its cutoff Λ (or a coupling of mass dimension "
                f"{4 - dimension:g}) to be checked"]
    out = []
    if cutoff_gev < Q_MAX_GEV:
        out.append(f"Λ = {cutoff_gev:.3g} GeV is below direct detection's momentum transfer (~{Q_MAX_GEV} GeV): "
                   "the contact description fails even there")
    if dm_mass_gev and cutoff_gev < 2 * dm_mass_gev:
        out.append(f"Λ = {cutoff_gev:.3g} GeV is below the freeze-out energy 2m_χ = {2 * dm_mass_gev:.3g} GeV: "
                   "a relic density computed in the EFT is not valid")
    if cutoff_gev < COLLIDER_GEV:
        out.append(f"Λ = {cutoff_gev:.3g} GeV is within the LHC's reach (√ŝ ~ {COLLIDER_GEV / 1000:g} TeV): "
                   "collider limits need the completion, not the EFT")
    if dm_mass_gev and 4 * 3.14159265 * cutoff_gev < 2 * dm_mass_gev:
        out.append("no perturbative completion (mediator M ≲ 4πΛ) is heavier than 2m_χ")
    return out
