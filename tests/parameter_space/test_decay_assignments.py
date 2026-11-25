"""Searches judged at extreme decay assignments (the owner's decision #7, 2026-10-20), after the auditor's RC20-04 (a native
exclusion at one assignment kept unqualified) and RC20-05 (a Majorana pair in the 4μ searches' vanilla denominator)."""
import math

import pytest

from adroit.parameter_space import library, searches
from adroit.parameter_space.portals.generic import GenericModel


def test_disagreeing_assignments_keep_no_native_exclusion_and_both_reasons():
    """The auditor's RC20-04: one assignment allowed (native too), the other pending at 95% with a native exclusion; the
    native decision is reconciled as the 95% one, and the pending assignment's reason is kept."""
    low = searches.Outcome(name="x", excluded=False, native_excluded=False, native_ratio=0.2757, ratio=0.2)
    high = searches.Outcome(name="x", excluded=None, native_excluded=True, native_ratio=2.4814,
                            why="native 90%; 95% comparison needs the source likelihood")
    both = searches._edges([low, high], "X decays unresolved")
    assert both.excluded is None and both.native_excluded is None and both.native_ratio is None
    assert both.why.startswith("X decays unresolved; native 90%")
    alike = searches._edges([high.model_copy(update={"native_ratio": 3.0}), high], "u")
    assert alike.native_excluded is True and alike.native_ratio == pytest.approx(2.4814)


def test_a_majorana_pair_is_not_in_the_four_muon_searches_vanilla_denominator():
    """The auditor's RC20-05: L_μ − L_τ with Majorana dark matter (axial coupling 0.1, g′ = 0.01, m_χ = 1 GeV, m_Z′ = 30 GeV):
    BR(μμ) among the Standard Model pairs alone is 1/3 (μμ, ττ and the two left-handed neutrinos at half), not the
    total's 0.005."""
    e = library.entry("lmu_minus_ltau")
    spec = e.spec()
    fields = [f.model_copy(update={"self_conjugate": True, "mass_gev": 1.0}) if f.name == "chi" else
              f.model_copy(update={"mass_gev": 30.0}) if f.name == "Zp" else f for f in spec.fields]
    terms = [t.model_copy(update={"lorentz": "axial"}) if [o.field for o in t.fields][:2] == ["chi", "chi"] else t
             for t in spec.terms]
    couplings = [c.model_copy(update={"value": {"g_chi": 0.1, "g_mt": 0.01}[c.name]}) for c in spec.couplings]
    engine = GenericModel.for_spec(spec.model_copy(update={"fields": fields, "terms": terms, "couplings": couplings}))
    ((g, m, width, muons, vanilla, _, _),) = searches._generic_lmu(engine, engine.point())
    assert muons < 0.01 and vanilla == pytest.approx(1 / 3, rel=1e-3) and g == pytest.approx(0.01)
    assert math.isfinite(width) and m == pytest.approx(30.0)
