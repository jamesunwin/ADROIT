"""Simplified models as typed models, and the ones that complete a library card (DM14).

A Track 2 candidate is a nucleon-level interaction (a library card). Promoting
it to a Track 1 study needs a full model that produces it at tree level: an
s-channel mediator between Dirac dark matter and the quarks. The computable
completions (DM13's classes) are:
- a vector mediator (χ̄γ^μχ q̄γ_μq): the spin-independent O1;
- an axial mediator (χ̄γ^μγ⁵χ q̄γ_μγ⁵q): the spin-dependent O4, or L15;
- a scalar mediator with Yukawa-like quark couplings, its dark matter and
  quark couplings each scalar or pseudoscalar: O1 (scalar–scalar), L1–L4,
  and the library's mediator cards.

These completions couple isoscalarly, so an isovector candidate has none
among them. Any other card is promoted only through the model builder's
proposals (an agent, opt-in).
"""

from __future__ import annotations

from adroit.core.model_spec import ModelSpec

KINDS = ("vector", "axial", "scalar", "scalar_pseudoscalar", "pseudoscalar_scalar", "pseudoscalar")
DEFAULT_COUPLINGS = {"vector": (1.0, 0.25), "axial": (1.0, 0.25)}     # (g_χ, g_q); the scalars: (1, 1)

COMPLETIONS = {
    "O1": ["vector", "scalar"], "O4": ["axial"],
    "L01": ["scalar"], "L02": ["scalar_pseudoscalar"], "L03": ["pseudoscalar_scalar"], "L04": ["pseudoscalar"],
    "L15": ["axial"],
    "M_vector": ["vector"], "M_axial": ["axial"], "M_scalar": ["scalar"], "M_pseudoscalar": ["pseudoscalar"],
    "M_scalar_pseudoscalar": ["scalar_pseudoscalar"], "M_pseudoscalar_scalar": ["pseudoscalar_scalar"],
}


def completions(card_id: str, isospin: str = "s") -> list[str]:
    """The computable simplified models that produce a card at tree level (none for an isovector one)."""
    if isospin == "v":
        return []
    return list(COMPLETIONS.get(card_id, []))


def model(kind: str, m_chi: float, m_med: float, g_chi: float | None = None, g_q: float | None = None,
          name: str = "") -> ModelSpec:
    """The typed model of a simplified model (``KINDS``) at a parameter point."""
    if kind not in KINDS:
        raise ValueError(f"unknown simplified model {kind!r}; one of {', '.join(KINDS)}")
    spin1 = kind in ("vector", "axial")
    g_chi0, g_q0 = DEFAULT_COUPLINGS.get(kind, (1.0, 1.0))
    dm_label, q_label = (kind, kind) if spin1 else (
        {"scalar": ("scalar", "scalar"), "pseudoscalar": ("pseudoscalar", "pseudoscalar"),
         "scalar_pseudoscalar": ("scalar", "pseudoscalar"),
         "pseudoscalar_scalar": ("pseudoscalar", "scalar")}[kind])
    mediator = "Zp" if spin1 else "S"
    raw = {
        "name": name or f"{kind}_mediator",
        "stability": "Z2: the dark matter is odd, every other field even",
        "fields": [
            {"name": "chi", "role": "dark_matter", "dark_parity": -1, "spin": 0.5, "mass_gev": m_chi},
            {"name": mediator, "role": "mediator", "dark_parity": 1, "spin": 1.0 if spin1 else 0.0,
             "self_conjugate": True, "mass_gev": m_med},
            {"name": "q", "role": "standard_model", "spin": 0.5},
        ],
        "couplings": [{"name": "g_chi", "value": g_chi0 if g_chi is None else g_chi},
                      {"name": "g_q", "value": g_q0 if g_q is None else g_q}],
        "terms": [
            {"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": mediator}],
             "lorentz": dm_label, "coupling": "g_chi"},
            {"fields": [{"field": "q", "conjugate": True}, {"field": "q"}, {"field": mediator}],
             "lorentz": q_label, "coupling": "g_q" if spin1 else "g_q*m_q/v"},
        ],
    }
    return ModelSpec.model_validate(raw)
