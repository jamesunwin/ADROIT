"""Fail-closed prerequisite certificates, with separately calibrated Born diagnostics."""

from __future__ import annotations
from functools import lru_cache
import math
import numpy as np
from adroit.core.evidence import content_hash
from adroit.core.chemical_equilibrium import ConversionInput, ChemicalEquilibriumCertificate
from adroit.theory.conversion_rates import rate_point
from adroit.constraints.kinetic_mixing import G_PRIME

# Chosen AFTER the nine development coupled-equation comparisons, BEFORE confirmation.
BORN_THRESHOLD = 100.0
PREREQUISITE_FLAG = (
    "effective coannihilation relic assumes chemical equilibrium; physical prerequisite pending"
)


def certify(inputs: ConversionInput) -> ChemicalEquilibriumCertificate:
    """Never turn a cut-dependent vacuum Born calculation into a complete thermal pass."""
    return _cached(inputs.model_dump_json()).model_copy(deep=True)


def _eligible(c: ChemicalEquilibriumCertificate) -> bool:
    inputs = c.inputs
    p = inputs.point
    r = inputs.request
    if (
        not all(math.isfinite(v) for v in (p.m_chi, p.m_med, p.g_chi))
        or p.m_chi <= 0
        or p.m_med <= p.m_chi
    ):
        c.status = "outside_domain"
        c.reasons = ["finite positive masses and heavier scalar partner required"]
        return False
    if not inputs.majorana or inputs.partner != "eR":
        c.status = "missing_rates"
        c.missing_channels = list(c.required_channels)
        c.reasons = ["conversion kernels are implemented only for the existing eR Majorana family"]
        return False
    if r is None:
        c.reasons = [
            "explicit freeze-out interval, rate uncertainty and approximation request required"
        ]
        return False
    if p.g_chi == 0:
        c.status = "failed"
        c.complete = True
        c.passed = False
        c.born_diagnostic_passed = False
        c.physical_prerequisite = "failed"
        c.minimum_relaxation_over_h = 0
        if r.source_born is not None:
            c.component_prerequisite = "unsupported"
        c.reasons = ["exact zero Yukawa decouples chi: all conversions vanish"]
        return False
    split = p.m_med / p.m_chi - 1
    if not (
        8000 <= p.m_chi <= 20000
        and 0.01 <= split <= 0.1
        and abs(p.g_chi) <= 1e-3
        and 10 <= r.x_low < r.x_high <= 50
        and p.m_chi / r.x_high >= 160
        and math.isclose(inputs.g_prime, G_PRIME, rel_tol=1e-12)
        and r.rate_relative_uncertainty >= 0.5
    ):
        c.status = "outside_domain"
        c.reasons = [
            "conditional calibration domain: m=8–20 TeV, splitting 1–10%, |y|<=1e-3, 10<=x_low<x_high<=50, T>=160 GeV; existing g_prime and >=50% declared rate uncertainty"
        ]
        return False
    return True


def _diagnostic(c: ChemicalEquilibriumCertificate) -> None:
    inputs = c.inputs
    r = inputs.request
    try:
        c.rates = [rate_point(inputs, float(x)) for x in np.linspace(r.x_low, r.x_high, r.samples)]
        c.minimum_relaxation_over_h = min(row.conservative_over_h for row in c.rates)
        c.calibrated_threshold = BORN_THRESHOLD
        if max(row.quadrature_relative_difference for row in c.rates) > 0.01:
            c.status = "unresolved"
            c.reasons = ["thermal Born quadrature differs by more than 1% under refinement"]
            return
        if abs(c.minimum_relaxation_over_h / BORN_THRESHOLD - 1) < 0.01:
            c.status = "unresolved"
            c.reasons = ["conditional equilibrium threshold is numerically marginal"]
            return
        c.born_diagnostic_passed = c.minimum_relaxation_over_h > BORN_THRESHOLD
        c.status = "missing_rates"
        c.missing_channels = [
            "inclusive soft/collinear scattering plus virtual/radiative decay cancellation",
            "finite-temperature plasma dispersion and statistical corrections",
            "higher-order y^4 odd-sector conversion (neglected in conditional small-y reference)",
        ]
        if r.include_odd_sector:
            c.missing_channels = c.missing_channels[:2]
        c.reasons = [
            (
                "conditional vacuum Born equilibrium diagnostic passes"
                if c.born_diagnostic_passed
                else "conditional vacuum Born rates do not establish equilibrium"
            ),
            "physical prerequisite remains pending: missing inclusive/thermal rates cannot be replaced by default rates",
            "threshold 100 selected after nine development reference errors; finite-case confirmation, not uniform accuracy",
        ]
    except (ArithmeticError, ValueError) as error:
        c.status = "unresolved"
        c.reasons = [f"conversion calculation unresolved: {error}"]


def _window(c: ChemicalEquilibriumCertificate) -> bool:
    """Tie the declared temperature window to the relic solver's freeze-out (audit M11): it must bracket x_f, and
    the rates are then sampled from x_f, where equilibrium must start to hold, to the declared x_high. A window
    that misses x_f is refused, so the pending item stays. Without x_f (an older input) the window is as declared."""
    r, x_f = c.inputs.request, c.inputs.freeze_out_x
    if x_f is None:
        return True
    if not r.x_low <= x_f < r.x_high:
        c.status = "unresolved"
        c.component_prerequisite = "unresolved" if r.source_born is not None else None
        c.reasons = [f"the declared window x = {r.x_low:g}–{r.x_high:g} does not bracket the relic solver's "
                     f"freeze-out x_f = {x_f:.3g}; equilibrium must hold from freeze-out on"]
        return False
    c.inputs = c.inputs.model_copy(update={"request": r.model_copy(update={"x_low": x_f})})
    return True


@lru_cache(maxsize=512)
def _cached(payload: str) -> ChemicalEquilibriumCertificate:
    inputs = ConversionInput.model_validate_json(payload)
    identity = inputs.model_dump(mode="json")
    if inputs.request is not None and inputs.request.source_born is None:
        identity["request"].pop("source_born", None)
    if inputs.request is not None and not inputs.request.include_odd_sector:
        identity["request"].pop("include_odd_sector", None)  # preserve v1 default-method identity
    c = ChemicalEquilibriumCertificate(inputs=inputs, parameter_sha256=content_hash(identity))
    if inputs.request is not None and (
        inputs.request.include_odd_sector or inputs.request.source_born is not None
    ):
        c.required_channels.append("chi chi<->phi phi_dagger")
    if inputs.request is not None and inputs.request.source_born is not None:
        from adroit.theory.component_equilibrium import prepare

        prepare(c)
    if _eligible(c) and _window(c):
        if c.inputs.request.source_born is not None:
            from adroit.theory.component_equilibrium import assess

            assess(c)
        else:
            _diagnostic(c)
        if c.inputs.request.plasma is not None:
            from adroit.theory import plasma_rates

            plasma_rates.assess(c)
    return c
