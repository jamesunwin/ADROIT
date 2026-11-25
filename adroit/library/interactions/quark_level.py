"""Quark- and gluon-level effective operators → nonrelativistic coefficients, through DirectDM (DM8).

A bespoke model reaches the rate code through the quark-level operator basis
of DirectDM (Bishara, Brod, Grinstein, Zupan, arXiv:1708.02678): its Wilson
coefficients, at the scale of a given flavour theory, are run and matched by
DirectDM onto the nucleon-level operators O_i of Anand et al., with its own
nucleon inputs. DirectDM runs in its own environment (``directdm_driver``).

**Exact in q.** DirectDM composes each coefficient from a constant and
terms in q², 1/q² (photon exchange), 1/(m_π² + q²) and q²/(m_π² + q²), and the
same for the η. Each is a term of ``OperatorCoefficient``:
- q^{±2} is ``q_power`` = ±2;
- 1/(m² + q²) is (1/m²) × the propagator m²/(m² + q²);
- q²/(m² + q²) = 1 − m²/(m² + q²).

So nothing is fitted or approximated in the conversion.

**The operator mass.** DirectDM writes q/m_N with m_N the mean nucleon mass.
Here the operators carry q over the atomic mass unit
(``conventions.OPERATOR_MASS_GEV``), so a coefficient whose operator carries
(q/m_N)^k is multiplied by (m_u/m_N)^k.
"""

from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from enum import Enum
from pathlib import Path

from pydantic import Field

from adroit.core.config import child_environment
from adroit.core.config import get_settings
from adroit.core.dm_state import DarkMatterParticle, InteractionModel, ModelLayer, OperatorCoefficient
from adroit.core.state import StrictModel
from adroit.external import fetch
from adroit.physics.conventions import OPERATOR_MASS_GEV

DIRECTDM = "DirectDM"
DRIVER = Path(__file__).with_name("directdm_driver.py")
VENV = ".venv-directdm"
# Powers of q/m_N in O_1 … O_15 (arXiv:1308.6288, Eq. 7).
Q_OVER_M_POWER = {1: 0, 2: 0, 3: 1, 4: 0, 5: 1, 6: 2, 7: 0, 8: 0, 9: 1, 10: 1, 11: 1, 12: 0,
                  13: 1, 14: 1, 15: 2}
NO_RESPONSE = {2}       # O_2 has no leading-order nuclear response (rates.OPERATORS)


class DMType(str, Enum):
    """DirectDM's dark matter types."""

    dirac = "D"
    majorana = "M"
    complex_scalar = "C"
    real_scalar = "R"


class QuarkLevelModel(StrictModel):
    """Wilson coefficients of DirectDM's operator basis, at the scale of a flavour theory.

    ``flavours`` 5 means μ = m_Z, 4 means μ = m_b(m_b), 3 means μ = 2 GeV. Coefficient
    names are DirectDM's (``C61u`` = (χ̄γ^μχ)(ūγ_μu) of dimension six, ...), values in
    GeV^{4-d} for an operator of dimension d.
    """

    name: str
    dm_type: DMType = DMType.dirac
    flavours: int = Field(default=5, ge=3, le=5)
    coefficients: dict[str, float]
    rge: bool = True
    dropped: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


def _python() -> Path:
    return get_settings().tools_dir / VENV / "bin" / "python"


def available() -> bool:
    """Whether DirectDM and its environment are in place."""
    return _python().is_file() and fetch.locate(DIRECTDM) is not None


def components(model: QuarkLevelModel, mass_gev: float, q_gev: list[float] | None = None) -> dict:
    """DirectDM's decomposition of the nonrelativistic coefficients (``directdm_driver``);
    with ``q_gev``, also its assembled coefficients there (for checks)."""
    folder = fetch.locate(DIRECTDM)
    if folder is None or not _python().is_file():
        raise fetch.MissingInput(f"DirectDM is not set up (the tool and its environment {VENV} in the tools folder; "
                                 f"docs/dm8_lagrangians.md): {fetch.how_to_get(DIRECTDM)}")
    request = {"directdm": str(folder), "flavours": model.flavours, "dm_type": model.dm_type.value,
               "coefficients": model.coefficients, "mass_gev": mass_gev, "rge": model.rge,
               "q_gev": list(q_gev or [])}
    done = subprocess.run([str(_python()), str(DRIVER)], input=json.dumps(request), text=True,
                          capture_output=True, timeout=300, env=child_environment())
    if done.returncode != 0:
        lines = (done.stderr or done.stdout).strip().splitlines()
        message = lines[-1] if lines else f"exit status {done.returncode}"
        try:
            message = json.loads(message)["error"]
        except (ValueError, KeyError, TypeError):
            pass
        raise ValueError(f"DirectDM: {message}")
    return json.loads(done.stdout.strip().splitlines()[-1])


def _terms(parts: dict, operator: int, nucleon: str, m_pi: float, m_eta: float) -> dict:
    """{(q_power, propagator mass): value} for one operator and nucleon, from DirectDM's parts."""
    get = lambda key: parts.get(key, 0.0)            # noqa: E731
    out: dict[tuple[int, float | None], float] = defaultdict(float)
    out[(0, None)] += get(f"cNR{operator}{nucleon}")
    out[(2, None)] += get(f"cNR{operator}q2{nucleon}")
    out[(-2, None)] += get(f"cNR{operator}bq2{nucleon}")
    for meson, mass in (("pi", m_pi), ("eta", m_eta)):
        pole, q2_pole = get(f"cNR{operator}{meson}{nucleon}"), get(f"cNR{operator}q2{meson}{nucleon}")
        out[(0, mass)] += pole / mass ** 2 - q2_pole        # 1/(m²+q²) and q²/(m²+q²) = 1 − m²/(m²+q²)
        out[(0, None)] += q2_pole
    return out


def to_interaction(model: QuarkLevelModel, mass_gev: float) -> tuple[DarkMatterParticle, InteractionModel]:
    """The particle and its nonrelativistic interaction, for the rate code."""
    result = components(model, mass_gev)
    parts, m_pi, m_eta, m_n = result["components"], result["mpi"], result["meta"], result["mN"]
    grouped: dict[tuple[int, int, float | None], list[float]] = defaultdict(lambda: [0.0, 0.0])
    dropped = list(model.dropped)
    for operator in range(1, 15):
        scale = (OPERATOR_MASS_GEV / m_n) ** Q_OVER_M_POWER[operator]
        for index, nucleon in enumerate("pn"):
            for (q_power, mass), value in _terms(parts, operator, nucleon, m_pi, m_eta).items():
                if value != 0.0:
                    grouped[(operator, q_power, mass)][index] += value * scale
    coefficients = []
    for (operator, q_power, mass), (p, n) in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        if p == 0.0 and n == 0.0:
            continue
        if operator in NO_RESPONSE:
            dropped.append(f"O{operator} (no leading-order nuclear response): c^p = {p:.3g}, c^n = {n:.3g}")
            continue
        coefficients.append(OperatorCoefficient(operator=operator, proton=p, neutron=n, q_power=q_power,
                                                mediator_mass_gev=mass))
    spin = 0.0 if model.dm_type in (DMType.complex_scalar, DMType.real_scalar) else 0.5
    particle = DarkMatterParticle(mass_gev=mass_gev, spin=spin,
                                  self_conjugate=model.dm_type in (DMType.majorana, DMType.real_scalar))
    interaction = InteractionModel(name=model.name, layer=ModelLayer.quark, coefficients=coefficients,
                                   parameters=dict(model.coefficients), dropped=dropped,
                                   references=["arXiv:1708.02678 (DirectDM)", *model.references])
    return particle, interaction
