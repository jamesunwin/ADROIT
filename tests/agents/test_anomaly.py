"""DM14: the anomaly drafter — quotes checked against the text, and an unverified record for a person."""

import yaml

from adroit.agents.anomaly import AnomalyDraft, AnomalyDrafter, to_yaml, unquoted
from adroit.agents.llm import FakeLLMClient
from adroit.experiments import anomaly

TEXT = """We report 140.2 kg days of exposure.   Three WIMP-candidate events were observed,
at recoil energies of 8.2, 9.5 and 12.3 keV. The expected background is 0.41 events."""


def draft(**kw) -> AnomalyDraft:
    base = dict(name="CDMS II Si", target="Si", exposure_kg_day=140.2, window_kev=[7.0, 100.0],
                events_kev=[8.2, 9.5, 12.3], background_events=0.41, efficiency_figure="Fig. 1",
                sources={"exposure_kg_day": "140.2 kg days of exposure",
                         "events_kev": "at recoil energies of 8.2, 9.5 and 12.3 keV"},
                needs_person=["efficiency: digitise Fig. 1"])
    return AnomalyDraft(**{**base, **kw})


def test_quotes_must_appear_in_the_text_up_to_whitespace_and_case():
    assert unquoted(draft(), TEXT) == []
    bad = draft(sources={"background_events": "an expected background of 0.6 events"})
    assert unquoted(bad, TEXT) == ["background_events"]


def test_the_drafter_lists_unfound_quotes_for_a_person():
    fake = FakeLLMClient([draft(sources={"window_kev": "a window of 7-100 keV"})])
    out = AnomalyDrafter(fake, model="m").run(TEXT, "arXiv:1304.4279")
    assert any(item.startswith("window_kev") for item in out.needs_person)
    assert out.references == ["arXiv:1304.4279"]
    assert "Never compute, estimate or invent a number" in fake.calls[0]["system"]


def test_a_required_number_the_text_does_not_give_is_a_visible_placeholder(tmp_path):
    """Live check L5: the draft left resolution_kev out, and check printed a raw schema error. The draft now writes
    `resolution_kev: null`, and check names the field in plain language."""
    text = to_yaml(draft())
    assert "resolution_kev: not stated in the text" in text and "resolution_kev: null" in text.split("\nneeds_person:")[0]
    path = tmp_path / "draft.yaml"
    path.write_text(text)
    record, problems = anomaly.read(path)
    assert record is None and problems == ["resolution_kev: not given yet; fill in " + anomaly.FIELD_TEXT["resolution_kev"]]


def test_check_reads_bad_values_and_unknown_fields_in_plain_language(tmp_path):
    path = tmp_path / "draft.yaml"
    data = yaml.safe_load(to_yaml(draft(resolution_kev=0.5)))
    path.write_text(yaml.safe_dump({**data, "exposure_kg_day": -1, "window_kev": [], "colour": "blue"}))
    record, problems = anomaly.read(path)
    assert record is None
    assert any(p.startswith("exposure_kg_day: must be > 0, but is -1") for p in problems)
    assert any(p.startswith("window_kev: not given yet") for p in problems)
    assert "colour: not a field of an anomaly record (see adroit anomaly template)" in problems
    path.write_text("- just\n- a list\n")
    assert anomaly.read(path)[1] == ["the file is not a mapping of record fields (see adroit anomaly template)"]


def test_the_draft_is_an_unverified_record_waiting_for_its_efficiency(tmp_path):
    path = tmp_path / "draft.yaml"
    path.write_text(to_yaml(draft(resolution_kev=0.5)))
    data = yaml.safe_load(path.read_text())
    assert data["verified_by"] == "" and data["efficiency"] == {"csv": "efficiency.csv"}
    record = anomaly.load(path)
    assert any("efficiency: cannot be read" in p for p in anomaly.check(record, tmp_path))
    (tmp_path / "efficiency.csv").write_text("7,0.3\n100,0.3\n")
    record = record.model_copy(update={"references": ["arXiv:1304.4279"]})
    assert anomaly.check(record, tmp_path) == []


def test_a_to_do_the_drafter_already_wrote_is_not_repeated():
    """The R7 gate's L5 minor: the drafter's own resolution note and the code's generic one both appeared."""
    text = to_yaml(draft(needs_person=["resolution_kev: not stated; consult the detector papers"]))
    data = yaml.safe_load(text)
    assert [x for x in data["needs_person"] if x.startswith("resolution_kev")] == [
        "resolution_kev: not stated; consult the detector papers"]
