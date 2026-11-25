"""Broken-phase explicit vector currents with faithful flavour and NR matching."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from adroit.constraints import spin1
from adroit.core.model_contracts import VECTOR_FLAVOURS
from adroit.core.dm_state import InteractionModel
from adroit.parameter_space.classes import Point, Spin1Class
from adroit.parameter_space.limits import StatisticalLimit


class FlavourVectorClass(Spin1Class):
    """Named quark/lepton couplings fixed during mass/g_chi scans; no neutrino completion."""

    family: Literal["flavour_vector"] = "flavour_vector"
    kind: Literal[spin1.Spin1Kind.vector] = spin1.Spin1Kind.vector
    flavour_couplings: dict[str, float]
    fermion_masses_gev: dict[str, float] = Field(default_factory=dict)
    field_flavours: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _specified(self) -> FlavourVectorClass:
        if set(self.flavour_couplings) != set(VECTOR_FLAVOURS) or any(
            not math.isfinite(g) for g in self.flavour_couplings.values()
        ):
            raise ValueError(
                "declare all nine finite named flavour couplings, including explicit zeros"
            )
        if not set(self.fermion_masses_gev) <= set(VECTOR_FLAVOURS) or any(
            not math.isfinite(m) or m < 0 for m in self.fermion_masses_gev.values()
        ):
            raise ValueError("finite nonnegative named flavour masses required")
        return self

    def _check_point(self, p: Point) -> None:
        if p.g_q != 0 or p.g_l != 0:
            raise ValueError(
                "flavour contract fixes explicit currents; unused g_q/g_l slots must remain zero"
            )
        if (
            not all(math.isfinite(x) for x in (p.m_chi, p.m_med, p.g_chi))
            or min(p.m_chi, p.m_med) <= 0
        ):
            raise ValueError("positive finite masses and finite g_chi required")

    def universal_point(self, p: Point) -> Point | None:
        """Return the physically identical legacy neutrino-free universal-quark point."""
        self._check_point(p)
        q = [self.flavour_couplings[f] for f in VECTOR_FLAVOURS[:6]]
        if any(g != q[0] for g in q) or any(self.flavour_couplings[f] for f in VECTOR_FLAVOURS[6:]):
            return None
        if any(
            m != next(f.mass_gev for f in spin1.FERMIONS if f.name == name)
            for name, m in self.fermion_masses_gev.items()
        ):
            return None
        return p.model_copy(update={"g_q": q[0], "g_l": 0.0})

    def model(self, p: Point) -> spin1.Spin1Model:
        """The vector model with the named flavour currents, or the legacy universal-quark model where the point
        reduces to it (``universal_point``)."""
        self._check_point(p)
        universal = self.universal_point(p)
        if universal is not None:
            return Spin1Class(name=self.name).model(universal)
        return spin1.Spin1Model(
            kind=spin1.Spin1Kind.vector,
            m_med_gev=p.m_med,
            g_dm=p.g_chi,
            g_q=0,
            g_l=0,
            label=self.name,
            flavour_couplings=self.flavour_couplings,
            fermion_masses_gev=self.fermion_masses_gev,
        )

    def isoscalar(self) -> bool:
        """Whether tree-level proton and neutron vector charges are equal."""
        return self.flavour_couplings["u"] == self.flavour_couplings["d"]

    def dd(self, p: Point) -> tuple[str, float]:
        """(kind, σ in cm²): SI at a universal-quark point; otherwise the proton cross-section, a diagnostic of the
        flavour-vector NR current."""
        value = spin1.nucleon_cross_section_cm2(self.model(p), p.m_chi)
        return (
            "SI"
            if self.universal_point(p) is not None
            else "flavour-vector NR (sigma_p diagnostic)"
        ), value

    def dd_statistical_limit(self, p: Point) -> StatisticalLimit:
        """Exact module procedures for this isospin ratio, never a target-averaged SI rescaling."""
        from adroit.parameter_space.flavour_limits import limit95

        self._check_point(p)
        gu, gd = self.flavour_couplings["u"], self.flavour_couplings["d"]
        base = limit95(p.m_chi, p.m_med, 2 * gu + gd, gu + 2 * gd)
        scale = abs(p.g_chi)
        value = base.value / scale if base.value is not None and scale > 0 else None
        return base.model_copy(
            update={
                "value": value,
                "construction": "module procedure at CL=.95; amplitude limit on this exact physical NR current; sigma_p is diagnostic only"
                + ("; zero DM coupling gives zero tree recoil prediction" if scale == 0 else ""),
            }
        )

    def perturbative(self, p: Point) -> bool:
        """Whether g_χ and every flavour coupling are at most √(4π)."""
        self._check_point(p)
        return max(abs(p.g_chi), *(abs(g) for g in self.flavour_couplings.values())) <= math.sqrt(
            4 * math.pi
        )

    def spectrum_reference_reason(self, p: Point) -> str:
        """Identify when actual source spectra differ from fixed-SM templates."""
        return self.model(p).spectrum_reference_reason()

    def pending(self, p: Point) -> list[str]:
        """Constraints not computed here: collider recasts (and charged-lepton searches, with a lepton current) for a
        non-universal current, and nuclear scattering when the u and d couplings both vanish."""
        pending = []
        if self.universal_point(p) is None:
            pending.append(
                "colliders: flavour-resolved production/acceptance and recasts unavailable for this declared current"
            )
            if (
                self.flavour_couplings["e"]
                or self.flavour_couplings["mu"]
                or self.flavour_couplings["tau"]
            ):
                pending.append(
                    "charged-lepton current: low-energy/LEP/flavour-specific recasts not implemented for this general vector contract"
                )
        if not (self.flavour_couplings["u"] or self.flavour_couplings["d"]):
            pending.append(
                "radiatively induced nuclear scattering for a heavy-flavour/lepton-only vector current is not computed"
            )
        return pending

    def flags(self, p: Point) -> list[str]:
        """The class's standing caveats: no certified gauge completion of the broken-phase currents, and tree-level
        matching only."""
        return [
            "broken-phase simplified vector currents; no anomaly-free/electroweak gauge completion certified",
            "tree-level matching; radiative flavour-current mixing not included",
        ]

    def interaction(self, p: Point) -> InteractionModel:
        """The point's flavour-current model as an interaction for the rate code (``spin1.interaction``)."""
        return spin1.interaction(self.model(p), p.m_chi)
