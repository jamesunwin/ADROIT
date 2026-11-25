"""Chemical-equilibrium certificate at explicitly requested regulated-Born component accuracy."""

from __future__ import annotations
import numpy as np
from adroit.core.chemical_equilibrium import ChemicalEquilibriumCertificate
from adroit.theory.source_born import rate_point

# Selected after twelve source-prescription coupled development cases, before confirmation.
THRESHOLD = 100.0
BOUNDARY_TOLERANCE = 0.01


def assess(c: ChemicalEquilibriumCertificate) -> None:
    """Require every retained rate; resolve the criterion over the declared finite regulator bank."""
    r = c.inputs.request
    if not r.include_odd_sector:
        c.status = "missing_rates"
        c.missing_channels = ["chi chi<->phi phi_dagger: explicit odd-sector request required"]
        c.reasons = [
            "all retained Born conversions are required before a component-accuracy certificate"
        ]
        return
    try:
        c.rates = [
            rate_point(c.inputs, float(x)) for x in np.linspace(r.x_low, r.x_high, r.samples)
        ]
        c.minimum_relaxation_over_h = min(v.conservative_over_h for v in c.rates)
        upper = min(v.upper_envelope_over_h for v in c.rates)
        c.calibrated_threshold = THRESHOLD
        if any(v.odd_sector_sigma_v_gev2 is None for v in c.rates):
            raise ValueError("missing odd-sector rate")
        if max(v.quadrature_relative_difference for v in c.rates) > 0.01:
            raise ValueError("rate refinement differs by more than 1%")
        _resolve(c, upper)
    except (ArithmeticError, ValueError) as error:
        c.status = "unresolved"
        c.component_prerequisite = "unresolved"
        c.passed = None
        c.complete = False
        c.reasons = [f"source component calculation unresolved: {error}"]


def prepare(c: ChemicalEquilibriumCertificate) -> None:
    """Declare the requested component accuracy before any applicability decision."""
    c.algorithm_version = 4                         # 3: the thermal-mass regulator variant and the x_f window (M11);
                                                    # 4: its decays at the thermal mass too (2026-10-12)
    c.scope = (
        "chemical equilibrium at declared retained-Abelian regulated vacuum-Born/MB component accuracy; "
        "source energy cuts, a thermal-mass collinear regulator variant and full finite-mass angular range; "
        "no inclusive/plasma, kinetic or initial-thermalization certificate"
    )
    c.approximation = (
        "source-regulated vacuum Born/MB, retained Abelian channels including y^4 odd conversion"
    )
    c.uncomputed_corrections = [
        "inclusive virtual/radiative/soft matching",
        "plasma dispersions and quantum statistical factors",
        "full broken-electroweak/Higgs conversion channels outside retained component",
    ]
    c.references = ["https://arxiv.org/abs/1705.09292", "https://doi.org/10.1007/JHEP07(2019)136"]


def _resolve(c: ChemicalEquilibriumCertificate, upper: float) -> None:
    low = c.minimum_relaxation_over_h
    if low > THRESHOLD * (1 + BOUNDARY_TOLERANCE):
        c.status = "passed"
        c.passed = True
        c.complete = True
        c.component_prerequisite = "supported"
        c.born_diagnostic_passed = True
        c.reasons = [
            "declared component criterion passes every sampled temperature and regulator/uncertainty envelope"
        ]
    elif upper < THRESHOLD * (1 - BOUNDARY_TOLERANCE):
        c.status = "failed"
        c.passed = False
        c.complete = True
        c.component_prerequisite = "unsupported"
        c.born_diagnostic_passed = False
        c.reasons = [
            "even the upper declared envelope fails the component criterion at a sampled temperature; effective coannihilation unsupported at this accuracy"
        ]
    else:
        c.status = "unresolved"
        c.component_prerequisite = "unresolved"
        c.reasons = [
            "criterion boundary or regulator/uncertainty envelopes do not resolve a stable decision"
        ]
    c.reasons += [
        "threshold calibrated on source-prescription development cases; finite-case validation, not uniform relic coverage",
        "physical_prerequisite remains pending for higher-accuracy inclusive/plasma claims; scope is explicitly component accuracy",
    ]
