"""Out-of-table production and uncovered topologies are not evidence of allowance."""
import json
from types import SimpleNamespace

import pytest

from adroit.constraints import lhc
from adroit.parameter_space import searches
from adroit.parameter_space.classes import Point
from adroit.parameter_space.portals.tchannel import TChannel
from adroit.parameter_space.portals.multiplet import ElectroweakMultiplet

pytestmark = pytest.mark.skipif(lhc.unavailable(*lhc.TABLES) != "", reason="the SUSY Working Group's production "
                                "tables are not in the tools folder")


@pytest.mark.parametrize("kind", ["coloured", "slepton", "wino_c1c1"])
def test_production_boundaries_are_explicit(kind):
    masses, cross = lhc._table(lhc.TABLES[kind])
    assert lhc.cross_section_pb(kind, masses[-1]) == pytest.approx(cross[-1])
    assert lhc.cross_section_pb(kind, masses[-1]+1) is None
    assert lhc.cross_section_pb(kind, masses[0]-1) is None


@pytest.mark.parametrize("cls,point", [
    (TChannel(partner="uR"), Point(m_chi=100, m_med=3001)),
    (TChannel(partner="muR"), Point(m_chi=100, m_med=1001)),
    (ElectroweakMultiplet(multiplet="wino"), Point(m_chi=2001, m_med=1, g_q=0))])
def test_audit_out_of_table_point_is_pending(cls, point):
    result = searches.lhc_search(cls, point, True)
    assert result.excluded is None and result.ratio is None and "tabulated" in result.why


@pytest.mark.parametrize("r,missing,expected", [(0.6, 1., None), (1.2, 1., True), (0.6, 0., False)])
def test_coverage_does_not_erase_a_valid_exclusion(monkeypatch, r, missing, expected):
    monkeypatch.setattr(searches, "lhc_spectrum", lambda *args: ("spectrum", 0.1))
    result = searches.lhc_search(None, Point(m_chi=10, m_med=20), True,
        {"status": "ok", "r_max": r, "analysis": "ATLAS-test", "coverage_sigmacut_fb": 0.,
         "coverage": {"missing prompt": {"total_xsec_fb": missing, "top": [{"sms":"x", "xsec_fb":missing}]}}})
    assert result.excluded is expected
    assert result.coverage["missing prompt"]["top"][0]["sms"] == "x"
    if expected is None:
        assert result.ratio is None and result.value == r


def test_driver_request_enables_complete_coverage(monkeypatch):
    requests = []
    def run(*args, **kw):
        request = json.loads(kw["input"])
        requests.extend(request["points"])
        return SimpleNamespace(returncode=0, stdout=json.dumps({"points":[
            {"status":"ok", "r_max":0.5, "coverage":{}, "coverage_sigmacut_fb":0}]}), stderr="")
    monkeypatch.setattr(lhc.subprocess, "run", run)
    lhc._RESULTS.clear()
    assert lhc.run(["test coverage"])[0]["r_max"] == 0.5
    assert requests[0]["coverage"] is True and requests[0]["sigmacut_fb"] == 0
    lhc._RESULTS.clear()


@pytest.mark.parametrize("r", [0.6, 1.2, 5.0])
def test_a_coloured_partner_is_pending_at_any_r_with_qcd_production_alone(monkeypatch, r):
    """Decision D33 (the external audit's R20, 2026-10-16): QCD-only production is not established as a lower bound,
    since the t-channel interference's sign is not established, so SModelS's r ≥ 1 no longer excludes a coloured
    t-channel partner; r is kept as the value."""
    monkeypatch.setattr(searches, "lhc_spectrum", lambda *args: ("spectrum", 0.1))
    result = searches.lhc_search(TChannel(partner="uR"), Point(m_chi=100, m_med=900, g_chi=1.0), True,
        {"status": "ok", "r_max": r, "analysis": "CMS-test", "coverage_sigmacut_fb": 0., "coverage": {}})
    assert result.excluded is None and result.ratio is None and result.value == r
    assert "QCD pair production alone" in result.why and "not a lower bound" in result.why
