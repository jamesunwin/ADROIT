"""Exact input-bound NR detector limits for independent proton/neutron currents."""

from __future__ import annotations

import math

from adroit.core.dm_state import DarkMatterParticle, CrossSectionKind
from adroit.parameter_space import limit_tables
from adroit.parameter_space.limits import StatisticalLimit
from adroit.parameter_space.operator_limits import _all_inputs


@limit_tables.held(256, _all_inputs)                 # by every module's inputs (DY-01)
def limit95(
    mass: float, mediator_mass: float, proton_charge: float, neutron_charge: float
) -> StatisticalLimit:
    """Evaluate the full vector NR reduction/propagator at unit g_chi and declared isospin."""
    from adroit.orchestrator import exclusion
    from adroit.experiments.registry import module_names

    if (
        not all(math.isfinite(x) for x in (mass, mediator_mass, proton_charge, neutron_charge))
        or min(mass, mediator_mass) <= 0
    ):
        raise ValueError("finite charges and positive mass required")
    names = [
        n for n in module_names() if any(exclusion._validated(n, k, mass) for k in CrossSectionKind)
    ]
    if not names or not (proton_charge or neutron_charge):
        return StatisticalLimit(
            value=None,
            confidence_level=0.95,
            construction="no eligible sensitive module/NR current",
        )
    from adroit.library.interactions import registry

    interaction = registry.resolve(
        "M_vector",
        DarkMatterParticle(mass_gev=mass),
        {"g_chi": 1.0, "m_med": mediator_mass, "gV_p": proton_charge, "gV_n": neutron_charge},
        name="declared flavour-vector unit current",
    )
    result = exclusion.run(
        exclusion.ExclusionRequest(
            bespoke={repr(mass): interaction},
            masses_gev=[mass],
            modules=names,
            telescopes=False,
            confidence_level=0.95,
            workers=1,
        )
    )
    values = [
        (row.mu_up[0], row.experiment) for row in result.per_module if not row.omission_reason(0)
    ]
    value, source = min(values) if values else (None, "")
    omitted = {
        row.experiment: row.omission_reason(0) or row.excludes_only   # D1: a fallback excludes, never allows
        for row in result.per_module
        if row.omission_reason(0) or row.excludes_only
    }
    return StatisticalLimit(
        value=value,
        source=source,
        confidence_level=0.95,
        construction="Path 1 full vector NR response/propagator at CL=.95; unit-g_chi amplitude limit",
        omitted={**result.skipped, **omitted},
    )
