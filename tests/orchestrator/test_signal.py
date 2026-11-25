"""Path 2 (DM6) on a small candidate set: the pipeline end to end."""

from __future__ import annotations

import numpy as np
import pytest

from adroit.core.dm_state import (ExperimentInfo, ExpectedSignal, Fidelity, HaloModel, NuclearModel,
                                  PublishedConventions)
from adroit.experiments import registry
from adroit.experiments.base import ExperimentModule, element_rates
from adroit.inference import dm_tournament
from adroit.orchestrator import signal
from adroit.physics import targets

LZ = "LZ extended window (2026)"     # the example search with an event; nothing in Path 2 is specific to it


@pytest.mark.needs("solar_model")
def test_path_two_on_three_candidates() -> None:
    candidates = [signal.Candidate(label="L10s@1000", card_id="L10", isospin="s", mass_gev=1000.0),
                  signal.Candidate(label="L01s@30", card_id="L01", isospin="s", mass_gev=30.0),
                  signal.Candidate(label="O01s@1000,d=300", card_id="O1", isospin="s",
                                   mass_gev=1000.0, splitting_kev=300.0)]
    result = signal.run(signal.SignalRequest(experiment=LZ, candidates=candidates, null_modules=[], toys=2000,
                                             leaders=3))
    labels = [e.label for e in result.tournament.ranking]
    assert dm_tournament.NULL in labels and len(labels) <= 4
    # the event of interest at 248 keV: L10 at 1 TeV explains it, a light WIMP cannot
    by_label = {f.label: f for f in result.fits}
    assert by_label["L10s@1000"].z_local > 3.0 and by_label["L01s@30"].z_local == 0.0
    assert 0.0 < result.global_p_closed_form < 1.0 and result.n_classes >= 2
    assert "What would separate the leaders" in signal.report(result)


@pytest.mark.usefixtures("resigned")
@pytest.mark.needs("solar_model")
def test_path_two_judges_its_leaders_against_complementary_constraints() -> None:
    """Every verified record judges each leader; a bare operator needs a completion for tier 3."""
    from adroit.constraints import database
    candidates = [signal.Candidate(label="O01s@1000,d=300", card_id="O1", isospin="s",
                                   mass_gev=1000.0, splitting_kev=300.0)]
    request = dict(experiment=LZ, candidates=candidates, null_modules=[], toys=200, leaders=1)
    off = signal.run(signal.SignalRequest(**request, complementary=False))
    assert off.verdicts == {} and off.tournament.ranking[0].complementary in ("not applied", "—")
    judged = signal.run(signal.SignalRequest(**request))
    verdicts = judged.verdicts["O01s@1000,d=300"]
    by_class = {v.constraint_id.split("-")[0]: v for v in verdicts}
    assert {v.constraint_id for v in verdicts} == {r.id for r in database.usable()}
    assert ('planck-2018-omega' in {v.constraint_id for v in verdicts}) == database.record('planck-2018-omega').usable
    assert by_class["fermi"].needed_calculation
    assert by_class["icecube"].applicability.value == "needs_calculation"
    exploratory = signal.run(signal.SignalRequest(**request,unverified_records=True))
    by_id = {v.constraint_id:v for v in exploratory.verdicts['O01s@1000,d=300']}
    assert by_id['planck-2018-omega'].needed_calculation
    assert by_id['planck-2018-omega'].applicability.value == 'needs_calculation'
    assert "Complementary constraints" in signal.report(judged)


class ToyGermanium(ExperimentModule):
    """A synthetic search, unlike LZ in every respect: germanium, three events at a few keV, and a
    background that expects several events. Path 2 must take everything it needs from the module."""

    GRID = np.linspace(1.0, 50.0, 197)

    @property
    def info(self) -> ExperimentInfo:
        return ExperimentInfo(name="toy germanium", target="Ge", exposure_kg_day=100.0,
                              energy_window_kev=(1.0, 50.0), fidelity=Fidelity.C)

    def target(self):
        return targets.target("Ge")

    def conventions(self) -> PublishedConventions:
        return PublishedConventions(halo=HaloModel(), nuclear_model=NuclearModel.shell_model)

    def published_limits(self) -> list:
        return []

    def expected_signal(self, particle, interaction, halo, model, target=None) -> ExpectedSignal:
        rate = sum(element_rates(self.GRID, particle, interaction, target or self.target(),
                                 halo, model).values())
        density = 100.0 * rate
        return ExpectedSignal(experiment="toy germanium", particle=particle,
                              total_events=float(np.trapezoid(density, self.GRID)),
                              observable=self.GRID.tolist(), density=density.tolist())

    def upper_limit(self, signal, cl: float = 0.9) -> float:
        return 2.303 / signal.total_events if signal.total_events > 0 else float("inf")

    def observations(self) -> tuple[np.ndarray, np.ndarray]:
        return np.array([5.0, 7.0, 12.0]), np.full(3, 0.5)      # one width (R17-3: σ(E) is refused)

    def signal_grid_kev(self) -> np.ndarray:
        return self.GRID

    def background_on_grid(self) -> np.ndarray:
        return np.full(self.GRID.size, 0.08)            # about 4 expected events


def test_path_two_on_a_search_unlike_lz(monkeypatch) -> None:
    """Germanium, low-energy events and a real background: toys, not the one-event form."""
    monkeypatch.setitem(registry.SIGNAL_SEARCHES, "toy germanium", ToyGermanium)
    candidates = [signal.Candidate(label=f"O1s@{m}", card_id="O1", isospin="s", mass_gev=m)
                  for m in (5.0, 10.0, 30.0)]
    result = signal.run(signal.SignalRequest(experiment="toy germanium", candidates=candidates,
                                             null_modules=[], toys=300, leaders=2, complementary=False))
    assert result.global_p_closed_form is None and "toys" in result.global_method
    assert {f.label for f in result.fits} == {c.label for c in candidates}
    assert all(s.best_target for s in result.separations)
    assert "toy germanium" in signal.report(result)


class ZeroAtAnEvent(ToyGermanium):
    """The toy search with its background density zero at the 5 keV event (the RZ23 re-audit's control)."""

    def background_on_grid(self) -> np.ndarray:
        out = super().background_on_grid()
        out[np.isclose(self.GRID, 5.0)] = 0.0
        return out


def test_a_background_zero_at_an_observed_event_is_refused(monkeypatch) -> None:
    """The RZ23 re-audit's RF23-03 (2026-10-23): with the background zero at an observed event the background-only
    likelihood vanishes, every Z and AIC against it is infinite, and the tournament ordered the candidates by label
    (A before Z, though Z's likelihood is the larger by ΔAIC = 13) and exported NaN ΔAIC. Path 2 refuses the search,
    naming the event, before any fit; the background is not floored."""
    monkeypatch.setitem(registry.SIGNAL_SEARCHES, "zero at an event", ZeroAtAnEvent)
    candidates = [signal.Candidate(label=label, card_id="O1", isospin="s", mass_gev=m)
                  for label, m in (("A_5", 5.0), ("Z_30", 30.0))]
    with pytest.raises(ValueError, match="not a positive number at the observed event at 5 keV"):
        signal.run(signal.SignalRequest(experiment="zero at an event", candidates=candidates, null_modules=[],
                                        toys=10, leaders=2, complementary=False))
    assert signal._background_reason(ToyGermanium()) == ""


def test_the_library_space_is_general() -> None:
    """Every operator and Lagrangian card, both isospins, any masses; no experiment's own space."""
    space = signal.library_model_space(masses=[10.0, 100.0], splittings_kev=[0.0, 50.0])
    cards = {c.card_id for c in space}
    assert {"O1", "O4", "O15", "L01", "L20"} <= cards and not any(c.endswith("_LZ") for c in cards)
    assert len(space) == len(cards) * 2 * 2 * 2
    assert "O1s@10,d=50" in {c.label for c in space}


@pytest.mark.slow
def test_every_class_member_is_combined_and_the_joint_criterion_ranks_them() -> None:
    """Release audit M6: O1v leads its class by the signal fit (ΔZ ≈ 0.01) but has Z_J = 0; O1s, which used to be
    skipped, has Z_J ≈ 1.3 and ranks second, behind the background alone."""
    from adroit.orchestrator import signal
    cands = [signal.Candidate(label=f"O1{i}@{m}", card_id="O1", isospin=i, mass_gev=float(m))
             for i in "sv" for m in (10, 12)]
    r = signal.run(signal.SignalRequest(experiment="CDMS II Si (2013)", candidates=cands, toys=200,
                                        complementary=False))
    order = [e.label for e in r.tournament.ranking]
    assert {c.label for c in r.combinations} == {c.label for c in cands}
    assert order[:2] == ["background only", "O1s@12"]
    assert r.tournament.indistinguishable == ["background only"]          # no vacuous ΔAIC set
    assert "no indistinguishable candidate set is formed" in signal.report(r)
    # a null that cannot constrain the candidate is not a coverage gap; one that could, unvalidated, is
    o1s = next(c for c in r.combinations if c.label == "O1s@10")
    assert "DEAP-3600 (2019)" in o1s.insensitive_nulls and "PICO-60 C3F8 (2019)" in o1s.omitted_nulls


@pytest.mark.needs("diamx", "cresst")
def test_a_halo_mismatch_between_signal_and_null_is_flagged() -> None:
    from adroit.orchestrator import signal
    cdms = registry.load_module("CDMS II Si (2013)")
    assert signal._halo_note(cdms, {"CRESST-III 2019": 0.01}) == ""
    note = signal._halo_note(cdms, {"CRESST-III 2019": 0.01, "XENONnT SR0+SR1": 0.02})
    assert note.startswith("; halo mismatch") and "XENONnT SR0+SR1" in note and "CRESST" not in note.split("while")[1]


def test_a_candidate_with_no_fitted_signal_counts_no_null_as_insensitive() -> None:
    """Mini audit: with μ̂ = 0 every finite omitted null read as "cannot constrain", and coverage as complete."""
    from adroit.orchestrator import signal
    request = signal.SignalRequest(experiment="CDMS II Si (2013)", toys=10, complementary=False)
    combo = signal.combine(request, signal.Candidate(label="O1s@3", card_id="O1", isospin="s", mass_gev=3.0))
    assert combo.mu_hat_signal == 0.0
    assert all("= ∞" in why for why in combo.insensitive_nulls.values())
    assert combo.null_coverage != "complete" or not combo.omitted_nulls


def test_a_capped_class_keeps_every_interaction_and_isospin_before_more_masses() -> None:
    """Minor (after R6): the cap kept members by signal fit alone, so a family the null experiments could tell
    apart was dropped for more masses of one family."""
    from types import SimpleNamespace as NS
    fits = [NS(label=f"L10s@{m}", z_local=5.0 - m / 1e4) for m in range(100, 100 + 40)]
    fits += [NS(label="L10v@500", z_local=1.0), NS(label="O01s@500", z_local=0.5)]
    classes = {f.label: 0 for f in fits}
    kept = {f.label for f in signal._leaders(fits, classes, 1)}
    assert len(kept) == signal.CLASS_MEMBERS == 32
    assert {"L10v@500", "O01s@500"} <= kept and signal._uncombined(fits, classes, 1) == len(fits) - 32


def test_the_toys_interval_is_a_structured_field() -> None:
    low, high = signal.toy_interval(0.00258, 100_000)
    assert low < 0.00258 < high and (round(low, 5), round(high, 5)) == (0.00228, 0.00291)
    assert signal.toy_interval(0.0, 1000)[0] == 0.0
    assert {"global_toys", "global_p_interval"} <= set(signal.SignalResult.model_fields)
