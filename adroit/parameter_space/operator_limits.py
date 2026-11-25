"""Direct detection of interactions that are neither spin-independent nor spin-dependent, through Path 1.

Some portals scatter on nuclei through nonrelativistic operators whose rates do not reduce
to σ_SI or σ_SD: a lepton partner's anapole (O₈ and O₉), for example. ADROIT's Path 1
(``orchestrator.exclusion``) computes any such interaction's signal in every experiment
module and sets each module's limit μ₉₀ on its overall strength. That takes minutes per
mass, so each *structure* (a fixed ratio of operator coefficients) is computed once on a
mass grid for a unit strength (``scripts/tabulate_operator_limits.py``) and stored in
``data/operator_limits/<name>.yaml``: μ₉₀(m) of the envelope over the modules validated at
each mass. A point whose interaction is ``scale`` × the unit one has

    r = (scale / μ₉₀(m))²

(the rate goes as the strength squared), native-90% exclusion at r > 1. The 95% verdict recomputes the module procedures with ``ratio95``.
"""

from __future__ import annotations

import math
from functools import lru_cache
from importlib import resources
from typing import Callable

import numpy as np
import yaml

from adroit.parameter_space import limit_tables

from adroit.core.dm_state import InteractionModel
from adroit.parameter_space.limits import StatisticalLimit


def anapole(m_chi: float) -> InteractionModel:
    """The anapole interaction of unit form factor F_A = 1 GeV⁻²: the library's card M_anapole (L = F_A χ̄γ^μγ⁵χ
    ∂^νF_μν, c₈ᵖ = 2eF_A, c₉ᴺ = 2e(Q_N + κ_N)F_A in ADROIT's operator conventions, checked against an explicit
    spinor reduction). Del Nobile's map (arXiv:1806.01291 eq. 2.42) has the same magnitudes and the opposite sign
    of c₉ relative to c₈, a convention of O₉ and q; the card's sign is the one ADROIT's rates use."""
    from adroit.core.dm_state import DarkMatterParticle
    from adroit.library.interactions import registry
    return registry.resolve("M_anapole", DarkMatterParticle(mass_gev=m_chi), {"anapole": 1.0})


STRUCTURES: dict[str, Callable[[float], InteractionModel]] = {"anapole": anapole}


@lru_cache(maxsize=8)
def table(name: str) -> dict | None:
    """The native-90% stored μ₉₀(m) of a structure, or None if it has not been computed."""
    path = resources.files("adroit.parameter_space").joinpath(f"data/operator_limits/{name}.yaml")
    if not path.is_file():
        return None
    return yaml.safe_load(path.read_text())


def mu_limit(name: str, mass: float) -> float | None:
    """μ₉₀ of the unit-strength structure at this mass (log–log interpolation); None outside the grid."""
    data = table(name)
    if data is None:
        return None
    masses, mus = np.array(data["masses_gev"]), np.array(data["mu_up"], dtype=float)
    good = np.isfinite(mus)
    masses, mus = masses[good], mus[good]
    if len(masses) < 2 or not masses[0] <= mass <= masses[-1]:
        return None
    return float(np.exp(np.interp(math.log(mass), np.log(masses), np.log(mus))))


def ratio(name: str, mass: float, scale: float) -> float | None:
    """r = (scale/μ₉₀)² of an interaction ``scale`` × the unit structure; None where it is not tabulated."""
    mu = mu_limit(name, mass)
    return None if mu is None else (scale / mu) ** 2


def _all_inputs(*_) -> tuple[str, ...]:
    """The input versions of every module (``limit_tables.inputs``): Path 1 takes the limit from those validated."""
    from adroit.experiments import registry
    return tuple(limit_tables.inputs(name) for name in registry.module_names())


@limit_tables.held(256, _all_inputs)                 # by every module's inputs (DY-01)
def limit95(name: str, mass: float) -> StatisticalLimit:
    """95% limit on the unit structure's strength at this mass: the smallest μ_up over the modules validated there,
    by Path 1's module procedures at CL = 0.95."""
    from adroit.orchestrator import exclusion
    from adroit.core.dm_state import CrossSectionKind
    from adroit.experiments import registry
    names = [n for n in registry.module_names() if any(exclusion._validated(n, k, mass) for k in CrossSectionKind)]
    if not names:
        return StatisticalLimit(value=None, confidence_level=.95, construction="no validated module at this mass")
    request = exclusion.ExclusionRequest(bespoke={repr(mass): STRUCTURES[name](mass)},
        masses_gev=[mass], modules=names, telescopes=False, confidence_level=0.95)
    result = exclusion.run(request)
    values = [(row.mu_up[0], row.experiment) for row in result.per_module if not row.omission_reason(0)]
    value, source = min(values) if values else (None, "")
    omitted = {row.experiment: row.omission_reason(0) or row.excludes_only      # D1: a fallback excludes only
               for row in result.per_module if row.omission_reason(0) or row.excludes_only}
    return StatisticalLimit(value=value, source=source, confidence_level=.95,
        construction=f"Path 1 module procedure at CL=.95; amplitude limit for unit {name}",
        omitted={**result.skipped, **omitted})


def ratio95(name: str, mass: float, scale: float) -> float | None:
    """Actual module limits at 95%; the bundled operator table is native 90%."""
    mu = limit95(name, mass).value
    return None if mu is None else (scale / mu) ** 2
