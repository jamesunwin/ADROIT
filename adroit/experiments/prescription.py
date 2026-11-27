"""A requested nuclear prescription is the one computed, or the calculation is refused (1.0.1, the independent audits'
V1-01 and F1-01, 2026-11-25).

``physics.nuclear.responses`` gives an isotope without a revised density matrix the shell model's responses under
``haxton_2022``. That is intended where the Elastic release publishes none for the isotope (¹²⁴Xe and ¹²⁶Xe, for
example) and ``nuclear.describe`` records it. But it took the same branch when the runtime was missing (V1-01), and
when one published matrix was missing or unreadable (F1-01: ¹²⁹Xe's file renamed moved the axial example's best fit
from g_χ = 0.561 to 0.710 with no warning). ``require`` refuses both, naming what is missing: the Elastic folder, the
Mu2e script, its environment's interpreter, and every matrix the release publishes for the target's isotopes
(``PUBLISHED``), each present, non-empty and readable as text. A warm response cache is not evidence that the inputs
were checked: the check runs whether or not responses are cached.

Where it is called: every workflow that can compute ``haxton_2022`` responses, before any calculation: the request
checks of Signal best fits and Explain a signal (their signal and null searches), Path 1 exclusion when a prescription
is requested by name, the LZ extended window's spectrum, and the forecasts. ``tests/experiments/test_haxton_required.py``
pins every call site of the rate functions outside ``physics`` (file, enclosing function, callee, count; aliases
included) and fails on a new one, each listed with why no workflow reaches it unguarded (the repairs audit's RA-07).
The guarantee is for these workflows: a direct call of ``nuclear.responses`` or ``element_rates`` from elsewhere is not
guarded until the refusal moves into ``physics`` (1.0.2).

Kept here, outside the code the limit tables are fingerprinted by (``limit_tables._digest``: ``physics/``,
``experiments/base.py`` and each tabulated module's class file): moving the refusal into ``nuclear.responses`` itself
would invalidate every stored table and validation record, which the owner re-signs. That is scheduled for 1.0.2 with
the tables' next recomputation (the deferred list, F1-01 residual); until then a direct library call of
``nuclear.responses`` or ``element_rates`` with ``haxton_2022`` must call ``require`` first, as every workflow does."""

from __future__ import annotations

import os

from adroit.core.dm_state import NuclearModel

# The density matrices the Elastic release (Haxton & McElvain, github.com/Berkeley-Electroweak-Physics/Elastic)
# publishes for the interaction ADROIT reads for each element (``haxton.INTERACTIONS``), by mass number. An isotope
# listed here must have its matrix installed; one not listed (¹²⁴Xe, ¹²⁶Xe, ³⁶Ar, ...) takes the shell model by design.
PUBLISHED: dict[str, tuple[int, ...]] = {
    "Xe": (128, 129, 130, 131, 132, 134, 136), "I": (127,), "Cs": (133,), "Ge": (70, 72, 73, 74, 76),
    "F": (19,), "Na": (23,), "Al": (27,), "Si": (28, 29, 30), "C": (12, 13), "Ar": (40,)}


def _readable(path) -> str | None:
    """Why ``path`` cannot serve as a density matrix, or None."""
    if path is None:
        return "missing"
    if not os.access(path, os.R_OK):
        return "unreadable"
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError) as error:
        return f"unreadable ({type(error).__name__})"
    return None if text.strip() else "empty"


def require(model: NuclearModel, target=None) -> None:
    """Raise ``physics.haxton.ResponsesUnavailable`` (a RuntimeError), naming what is missing, if ``model`` needs inputs
    that are not installed. The revised responses are the only such prescription: their runtime, and, for ``target``
    (a ``Target``; by default xenon), every matrix the release publishes for its isotopes."""
    if model is not NuclearModel.haxton_2022:
        return
    from adroit.physics import haxton, targets
    _, script, _ = haxton._paths()      # raises with "fetch … first" or "build the Mu2e environment at …"
    if not script.is_file() or not os.access(script, os.R_OK):
        raise haxton.ResponsesUnavailable(f"the Mu2e script {script} is missing: fetch {haxton.MU2E!r} again")
    target = target if target is not None else targets.target("Xe")
    problems = []
    for isotope in target.isotopes:
        if isotope.mass_number not in PUBLISHED.get(isotope.element, ()):
            continue                    # no revised matrix published: the shell model, by design and recorded
        why = _readable(haxton.density_matrix_file(isotope))
        if why is not None:
            problems.append(f"{isotope.name} ({why})")
    if problems:
        raise haxton.ResponsesUnavailable(
            f"the revised nuclear responses (haxton_2022) need Haxton & McElvain's density matrices for "
            f"{', '.join(problems)}: fetch {haxton.ELASTIC!r} again; nothing was computed with another prescription")


def require_module(module, model: NuclearModel | None = None) -> None:
    """``require`` for a search: ``model`` where one is asked for by name, else every prescription its conventions
    declare (SI and SD), on its own target. A request is refused when it is checked, before any calculation."""
    conventions = module.conventions()
    target = module.target()
    for each in ({model} if model is not None else {conventions.nuclear_model, conventions.spin_dependent_model}):
        require(each, target)
