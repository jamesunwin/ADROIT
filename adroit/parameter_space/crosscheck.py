"""ADROIT's relic density beside micrOMEGAs's, for the portals micrOMEGAs ships (an optional cross-check).

micrOMEGAs (``constraints.micromegas``) has its own models of the inert doublet (with W W* and
Z Z* final states), the real scalar singlet and a Z′ coupling to 3(B − L). For a library entry
and a point, ``crosscheck`` maps the slots onto micrOMEGAs's parameters, with the same
electroweak inputs and Higgs width where the model allows, and returns both Ωh².
"""

from __future__ import annotations

import math

from adroit.core.state import StrictModel
from adroit.parameter_space.classes import Point

# The inert-doublet UFO's electroweak inputs (α = 1/128.9, M_W = 79.947, M_Z = 91.1876), passed to micrOMEGAs.
IDM_EW = {"EE": math.sqrt(4.0 * math.pi / 128.9), "SW": math.sqrt(1.0 - (79.947 / 91.1876) ** 2), "MW": 79.947}


def _idm(p: Point) -> dict[str, float]:
    return {"M_H0": p.m_chi, "M_A0": p.m_chi + p.g_q, "M_Hpm": p.m_med, "lambda_345": p.g_chi, "lambda_2": 0.5,
            "m_h": 125.09, **IDM_EW}


MAPPINGS = {
    "inert_doublet": ("IDM", _idm),
    "higgs_portal_scalar": ("SingletDM", lambda p: {"M_S": p.m_chi, "lambda_hs": p.g_chi, "m_h": 125.09}),
    "b_minus_l": ("ZpPortal", lambda p: {"M_DM": p.m_chi, "M_Zp": p.m_med, "g_SM": p.g_q / 3.0, "g_DM": p.g_chi}),
}


class CrossCheck(StrictModel):
    """Ωh² of one point from ADROIT and from micrOMEGAs."""

    entry: str
    point: Point
    adroit: float | None
    micromegas: float | None = None
    model: str = ""
    version: str = ""
    error: str = ""

    @property
    def ratio(self) -> float | None:
        """ADROIT's Ωh² over micrOMEGAs's, or None unless both are available and non-zero."""
        return self.adroit / self.micromegas if self.adroit and self.micromegas else None


def crosscheck(entry_id: str, point: Point, its_equation_of_state: bool = False) -> CrossCheck:
    """Both Ωh² at the point (micrOMEGAs with W W*, Z Z* final states and its own widths, so the Higgs's
    decays into dark matter are in both). ``its_equation_of_state``: ADROIT's side solved with micrOMEGAs' own degrees
    of freedom (Drees, Hajkarim & Schmitz, its ``Data/hgEff/DHS.thg``), so that the two codes are compared like with
    like; with ADROIT's (Saikawa & Shirai) its Ωh² is 3.7% higher at the cross-check's points
    (``docs/relic_low_mass.md``)."""
    from adroit.constraints import micromegas as mo
    from adroit.parameter_space import library
    if entry_id not in MAPPINGS:
        raise KeyError(f"micrOMEGAs has no model for {entry_id!r}; it has {', '.join(MAPPINGS)}")
    model, mapping = MAPPINGS[entry_id]
    from adroit.constraints import relic
    engine = library.entry(entry_id).model_class
    if its_equation_of_state:
        with relic.equation_of_state(relic.tabulated_dof(mo.resolve_install(None) / "Data" / "hgEff" / "DHS.thg")):
            ours = engine.omega_h2(point)
    else:
        ours = engine.omega_h2(point)
    request = mo.OmegaRequest(model=model, params=mapping(point), settings={"vv_modes": ["1:1"]})
    result = mo.run_micromegas(request)
    return CrossCheck(entry=entry_id, point=point, adroit=ours, micromegas=result.omega_h2, model=model,
                      version=result.version, error=result.error or "")
