"""Existing tree-level Higgs portal with the complete potential retained at every point."""

from __future__ import annotations

import math
from typing import Literal
import numpy as np
from pydantic import model_validator

from adroit.core.model_contracts import ResolvedScalarPotential
from adroit.core.theory import ScalarVacuumCertificate,ScalarUnitarityCertificate
from adroit.core.model_spec import ModelSpec
from adroit.core.running import RGRequest, ScalarRGCertificate
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.higgs import HiggsPortalScalar, V, M_H
from adroit.parameter_space.portals.base import Nucleon


class CompleteScalarPortal(HiggsPortalScalar):
    """Independent scan coordinates m_S/lambda_HS with fixed lambda_S, v, Higgs mass/scale."""

    family: Literal["complete_scalar_singlet"] = "complete_scalar_singlet"
    potential: ResolvedScalarPotential
    running: RGRequest | None = None

    @model_validator(mode="after")
    def _backend_map(self) -> CompleteScalarPortal:
        if not math.isclose(self.potential.v_gev, V, rel_tol=1e-10) or not math.isclose(
            self.potential.higgs_mass_gev, M_H, rel_tol=1e-10
        ):
            raise ValueError(
                "complete scalar numerical class requires the Higgs component's fixed SM inputs"
            )
        if self.running is not None and self.running.scalar_matching != "tree_level_identification":
            raise ValueError("tree-level Higgs component requires explicitly labelled tree_level_identification for running; use standalone coefficient RG inputs for declared MSbar parameters")
        return self

    def point_potential(self, p: Point) -> ResolvedScalarPotential:
        """Preserve the full family: mu_S^2=m_S^2-lambda_HS v^2/2 at each scan/fit point."""
        if (
            not all(math.isfinite(x) for x in (p.m_chi, p.m_med, p.g_chi, p.g_q, p.g_l))
            or p.m_chi <= 0
        ):
            raise ValueError("positive scalar mass and finite physical parameters required")
        if (
            not math.isclose(p.m_med, self.potential.higgs_mass_gev, rel_tol=1e-10)
            or p.g_q
            or p.g_l
        ):
            raise ValueError(
                "complete scalar contract fixes the Higgs mediator and has no g_q/g_l slots"
            )
        quadratic = p.m_chi * p.m_chi - p.g_chi * self.potential.v_gev**2 / 2
        if not math.isfinite(quadratic):
            raise ValueError("derived singlet quadratic coefficient overflows")
        return self.potential.model_copy(
            update={"singlet_mass_gev": p.m_chi, "lambda_hs": p.g_chi, "mu_s2_gev2": quadratic}
        )

    def channels(self, s: np.ndarray, p: Point) -> dict[str, np.ndarray]:
        """The Higgs-portal scalar's channels, after checking the point against the full potential
        (``point_potential``)."""
        self.point_potential(p)
        return super().channels(s, p)

    def nucleon(self, p: Point) -> Nucleon:
        """The Higgs-portal scalar's scattering, after checking the point (``point_potential``)."""
        self.point_potential(p)
        return super().nucleon(p)

    def invisible(self, p: Point) -> dict[str, float]:
        """Use the potential-derived hSS vertex and validate the physical point."""
        self.point_potential(p)
        return super().invisible(p)

    def perturbative(self, p: Point) -> bool:
        """The Higgs-portal bound |λ_hs| ≤ 4π and also |λ_S| ≤ 4π."""
        potential = self.point_potential(p)
        return super().perturbative(p) and abs(potential.lambda_s) <= 4 * math.pi

    def vacuum_certificate(self, p: Point) -> ScalarVacuumCertificate:
        """Certify this point's full scalar potential at its declared scale."""
        from adroit.theory.scalar_vacuum import for_potential
        return for_potential(self.point_potential(p))

    def unitarity_certificate(self,p: Point) -> ScalarUnitarityCertificate:
        """Check every scalar-pair channel in the declared high-energy potential limit."""
        from adroit.theory.scalar_unitarity import for_potential
        return for_potential(self.point_potential(p))

    def running_certificate(self, p: Point) -> ScalarRGCertificate:
        """Run only with an explicit upper scale and matching contract."""
        from adroit.theory.scalar_running import for_potential
        return for_potential(self.point_potential(p), self.running)

    def flags(self, p: Point) -> list[str]:
        """The Higgs-portal flags plus the scalar potential's: its RG status, and the tree-level vacuum and unitarity
        certificates."""
        self.point_potential(p)
        return [
            *super().flags(p),
            ("complete scalar potential retained; RG certificate remains pending" if self.running is None
             else f"declared-scale scalar RG: {self.running_certificate(p).status}; no quantum-vacuum certificate"),
            f"tree-level scalar vacuum: {self.vacuum_certificate(p).vacuum}; a metastable vacuum's zero-temperature "
            "lifetime is computed, its thermal history is not",
            f"tree-level scalar unitarity: {self.unitarity_certificate(p).status}",
        ]


def match(spec: ModelSpec) -> tuple[CompleteScalarPortal, Point, list[str]]:
    """Map the complete declared potential to the unchanged SM Higgs-portal engine."""
    from adroit.model_building.scalar_contract import resolved_spec
    from adroit.parameter_space.classify import Unsupported

    resolved = resolved_spec(spec)
    potential = spec.scalar_potential.resolve()
    if not math.isclose(potential.v_gev, V, rel_tol=1e-10) or not math.isclose(
        potential.higgs_mass_gev, M_H, rel_tol=1e-10
    ):
        raise Unsupported(
            f"current Higgs component fixes v={V:g} GeV and m_h={M_H:g} GeV; alternate SM inputs require a separate validated backend map"
        )
    if spec.scalar_running and spec.scalar_running.scalar_matching != "tree_level_identification":
        raise Unsupported("the tree-level Higgs component does not perform MSbar matching; label tree_level_identification or use standalone coefficient running inputs")
    cls = CompleteScalarPortal(name=spec.name, potential=potential, running=spec.scalar_running)
    point = Point(
        m_chi=potential.singlet_mass_gev,
        m_med=potential.higgs_mass_gev,
        g_chi=potential.lambda_hs,
        g_q=0,
        g_l=0,
    )
    notes = [
        f"complete Z2 scalar potential in {spec.scalar_potential.basis} coordinates; L=-V",
        f"lambda_S={potential.lambda_s:.17g} retained at scale {potential.scale_gev:g} GeV; no self-coupling default",
        "scan/fit m_S and lambda_HS with mu_S^2 derived at each point; Higgs inputs and lambda_S fixed",
        f"{len(resolved.terms)} complete scalar terms checked/expanded; no global-vacuum or UV certificate claimed",
    ]
    return cls, point, notes
