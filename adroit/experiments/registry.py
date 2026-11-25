"""The experiment modules the system knows, by name.

A module is loaded only when asked for, since each reads data that must
first be fetched (``adroit.external.fetch``).
"""

from __future__ import annotations

from collections.abc import Callable

from adroit.experiments.base import ExperimentModule


def _cresst() -> ExperimentModule:
    from adroit.experiments.cresst_iii import CresstIII2019
    return CresstIII2019()


def _cdmslite() -> ExperimentModule:
    from adroit.experiments.cdmslite import CdmsliteRun2
    return CdmsliteRun2()


def _pico() -> ExperimentModule:
    from adroit.experiments.pico60 import Pico60
    return Pico60()


def _deap() -> ExperimentModule:
    from adroit.experiments.deap3600 import Deap3600
    return Deap3600()


def _xenon(search: str) -> Callable[[], ExperimentModule]:
    def load() -> ExperimentModule:
        from adroit.experiments.xenon import DiamxXenon
        return DiamxXenon(search)
    return load


MODULES: dict[str, Callable[[], ExperimentModule]] = {
    "CRESST-III 2019": _cresst,
    "CDMSlite Run 2": _cdmslite,
    "PICO-60 C3F8 (2019)": _pico,
    "DEAP-3600 (2019)": _deap,
    "LZ WS2022+WS2024": _xenon("LZ WS2022+WS2024"),
    "XENONnT SR0+SR1": _xenon("XENONnT SR0+SR1"),
    "PandaX-4T Run0+Run1": _xenon("PandaX-4T Run0+Run1"),
}


def _lz_extended() -> ExperimentModule:
    from adroit.experiments.lz_extended_window import LzExtendedWindow
    return LzExtendedWindow()


def _historical(key: str) -> Callable[[], ExperimentModule]:
    def load() -> ExperimentModule:
        from adroit.experiments.historical import HistoricalSearch
        return HistoricalSearch(key)
    return load


def _historical_searches() -> dict[str, Callable[[], ExperimentModule]]:
    from adroit.experiments import historical
    return {historical.record(key)["name"]: _historical(key) for key in historical.records()}


# Searches whose events Path 2 explains. They are loaded by name like any module, but are not
# among the default modules of an exclusion (MODULES): a search with a signal is not a null result.
# The historical searches (DM10) are records in data/historical/.
SIGNAL_SEARCHES: dict[str, Callable[[], ExperimentModule]] = {
    "LZ extended window (2026)": _lz_extended,
    **_historical_searches(),
}


def module_names() -> list[str]:
    """Every known module that sets limits by default (the searches with signals are separate)."""
    return list(MODULES)


def signal_search_names() -> list[str]:
    """The searches with events that Path 2 can explain."""
    return list(SIGNAL_SEARCHES)


def load_module(name: str) -> ExperimentModule:
    """The module called ``name``.

    Raises:
        KeyError: if there is none. ``record:<path>`` loads an anomaly record from a file.
        DataUnavailable: if its data have not been fetched.
    """
    if name.startswith("record:"):                 # an anomaly record in a file (DM14)
        from adroit.experiments.anomaly import RecordSearch
        return RecordSearch.from_name(name)
    if name.startswith('anomaly:'):
        from adroit.experiments.confirmed_anomaly import ConfirmedAnomalySearch
        return ConfirmedAnomalySearch(name)
    if name.startswith('private-search:'):
        from adroit.experiments.private_search import PrivateEventSearch
        return PrivateEventSearch.from_name(name)
    known = {**MODULES, **SIGNAL_SEARCHES}
    if name not in known:
        raise KeyError(f"no module {name!r}; known: {', '.join(known)}")
    from adroit.experiments import response_cache
    response_cache.heal_now()                  # a cut-short nuclear-response file set aside, once (AL2-16)
    return known[name]()
