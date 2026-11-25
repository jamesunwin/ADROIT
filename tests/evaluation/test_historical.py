from types import SimpleNamespace

from adroit.evaluation import historical
from adroit.evaluation.core import Half


def _case(key: str):
    return next(c for c in historical.cases() if c.id == key)


def test_every_verdict_names_its_search_and_source() -> None:
    cases = historical.cases()
    assert {c.id for c in cases} == {"cdms_ii_si_2013", "cdms_ii_ge_2009"}
    for c in cases:
        assert c.inputs["search"] and "arXiv:" in c.inputs["significance"]["source"]
    assert {c.half for c in cases} == {Half.development, Half.held_out}


def test_the_system_agrees_only_when_each_item_agrees() -> None:
    si = _case("cdms_ii_si_2013")
    assert historical.judge(si, SimpleNamespace(global_z=1.5), 1e-4) == {"significance": True, "standard": True}
    assert historical.judge(si, SimpleNamespace(global_z=3.2), 1e-4)["significance"] is False
    assert historical.judge(si, SimpleNamespace(global_z=1.5), 0.2)["standard"] is False
    assert historical.judge(si, SimpleNamespace(global_z=1.5), None)["standard"] is False
    ge = _case("cdms_ii_ge_2009")
    assert historical.judge(ge, SimpleNamespace(global_z=0.4), None) == {"significance": True}


def test_the_request_uses_the_library_space_and_todays_null_searches() -> None:
    req = historical.request(_case("cdms_ii_si_2013"))
    assert req.experiment == "CDMS II Si (2013)" and not req.candidates
    assert "LZ WS2022+WS2024" in req.null_modules and not req.complementary
    assert historical.request(_case("cdms_ii_si_2013"), nulls=[]).null_modules == []


def test_the_summary_counts_agreement() -> None:
    from adroit.evaluation.core import CaseResult
    results = [CaseResult(case_id="a", passed=True, note="significance: agrees"),
               CaseResult(case_id="b", passed=False, note="standard: DISAGREES")]
    out = historical.summarise(results, [])
    assert out["cases agreeing with the literature"] == "1/2" and out["b"] == "standard: DISAGREES"
