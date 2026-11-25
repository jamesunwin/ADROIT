"""Build from fields as a form (the UI clarity plan §4, item 2): its rules, and the form on the page."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import yaml

pytest.importorskip("nicegui")

from nicegui import ui  # noqa: E402
from nicegui.testing import User  # noqa: E402

from adroit.core.model_spec import ModelSpec  # noqa: E402
from adroit.ui import field_form as ff  # noqa: E402
from tests.ui.test_model_library import capture  # noqa: E402

DOUBLET = """name: inert_doublet
fields:
- {name: H2, role: dark_matter, spin: 0, charges: {su2: 2, hypercharge: 0.5}, dark_parity: -1, mass_gev: 550}
- {name: psi, role: mediator, spin: 0.5, chirality: L, charges: {su3: 3bar, hypercharge: -0.6666666666666666, extra: {D: 1}}}
"""


def test_charges_are_typed_as_fractions():
    assert ff.number("1/6") == pytest.approx(1 / 6) and ff.number("−1/2") == -0.5 and ff.number(" 0.25 ") == 0.25
    assert ff.fraction_text(-2 / 3) == "-2/3" and ff.fraction_text(0.1234) == "0.1234"
    assert ff.extra_charges("D=1, BL=-1/3") == {"D": 1.0, "BL": pytest.approx(-1 / 3)}
    for bad in ("x", "1/0"):
        with pytest.raises(ValueError):
            ff.number(bad)
    with pytest.raises(ValueError, match="name=charge"):
        ff.extra_charges("D 1")


def test_the_form_and_its_yaml_are_the_same_model():
    """YAML → form → YAML keeps the model, and the YAML the form writes is what the command reads."""
    name, rows = ff.from_yaml(DOUBLET)
    assert name == "inert_doublet" and [r["name"] for r in rows] == ["H2", "psi"]
    assert rows[1]["hypercharge"] == "-2/3" and rows[1]["extra"] == "D=1" and rows[1]["su3"] == "3bar"
    again = yaml.safe_load(ff.to_yaml(name, rows))
    assert again == yaml.safe_load(DOUBLET)
    spec = ModelSpec.model_validate(again)
    assert spec.field("psi").charges.su3 == "3bar" and spec.field("H2").mass_gev == 550.0
    assert ff.problems(again) == []


def test_keys_the_form_does_not_show_are_kept():
    """Found writing the audit handover (2026-10-16): YAML → form → YAML had dropped a field's mass_justification and
    electric charge and the model's stability and assumptions."""
    text = """name: m
stability: Z2 with chi odd
assumptions: [a stated assumption]
fields:
- {name: chi, role: dark_matter, spin: 0.5, dark_parity: -1, mass_gev: 100, mass_justification: from the paper}
- {name: S, role: mediator, spin: 0, self_conjugate: true, charges: {electric_charge: 0}}
"""
    again = yaml.safe_load(ff.to_yaml(*ff.from_yaml(text), ff.extras(text)))
    assert again == yaml.safe_load(text) | {"fields": [
        {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0,
         "mass_justification": "from the paper"},
        {"name": "S", "role": "mediator", "spin": 0, "self_conjugate": True, "charges": {"electric_charge": 0}}]}
    assert list(again)[:3] == ["name", "stability", "assumptions"]
    assert ff.problems(again) == []


RICH = """name: rich
stability: Z2
fields:
- {name: chi, role: dark_matter, spin: 0.5, self_conjugate: "false", dark_parity: -1, mass_gev: 100, mass_justification: chosen}
- {name: psi, role: mediator, spin: 0.5, chirality: L, generations: 3, charges: {su3: 3bar, su2: 2, hypercharge: 0.16666666666666666, electric_charge: 0, extra: {D: -1}}}
- {name: S, role: mediator, spin: 0, self_conjugate: true, vev_gev: 3.5}
- {name: Zp, role: mediator, spin: 1, self_conjugate: true, mass_gev: 900}
"""


def _validated(text: str) -> ModelSpec:
    return ModelSpec.model_validate(yaml.safe_load(text))


def test_a_valid_model_survives_the_round_trip_unchanged():
    """The external audit's A04 (2026-10-16): the round trip is judged by the typed model, not the YAML's text. The
    quoted "false" (valid input, a Dirac field) had become self_conjugate: true."""
    back = ff.to_yaml(*ff.from_yaml(RICH), ff.extras(RICH))
    assert _validated(back) == _validated(RICH)
    assert _validated(back).field("chi").self_conjugate is False


@pytest.mark.parametrize("case,source,where", [
    ("fractional multiplet", "name: bad\nfields:\n- {name: X, role: dark_matter, spin: 0, dark_parity: -1, "
                             "charges: {su2: 2.9}}\n", "charges.su2"),
    ("non-mapping field", "name: bad\nfields:\n- {name: X, role: dark_matter, spin: 0, dark_parity: -1}\n- S\n",
     "field 2"),
    ("fractional generations", "name: bad\nfields:\n- {name: X, role: dark_matter, spin: 0, dark_parity: -1, "
                               "generations: 1.5}\n", "generations"),
])
def test_an_invalid_model_is_reported_not_rewritten(case, source, where):
    """The audit's controls: 2.9 had become 2, a non-mapping field had vanished, 1.5 generations had become 1, each
    with no problem reported. The form now refuses them, naming the field, and the YAML stays as written."""
    with pytest.raises(ValueError, match=where):
        ff.from_yaml(source)
    assert ff.problems(yaml.safe_load(source))


def test_a_value_the_form_cannot_show_stays_in_yaml():
    """A valid model with a spin-3/2 field or an SU(2) 9-plet is not squeezed into the form's menus."""
    for field in ("{name: X, role: dark_matter, spin: 1.5, dark_parity: -1}",
                  "{name: X, role: dark_matter, spin: 0, dark_parity: -1, charges: {su2: 9}}"):
        with pytest.raises(ValueError, match="edit it as YAML"):
            ff.from_yaml(f"name: m\nfields:\n- {field}\n")


def test_the_form_refuses_a_fractional_generation_count():
    with pytest.raises(ValueError, match="whole number"):
        ff.spec_data("m", [ff.blank_row() | {"name": "chi", "role": "dark_matter", "generations": 1.5}])


def test_mistakes_are_named_on_their_field_or_line():
    data = ff.spec_data("m", [ff.blank_row() | {"name": "S"}, ff.blank_row() | {"name": "S"}])
    found = ff.problems(data)
    assert "two fields are named S" in found and "one field must be the dark matter" in found
    bad = {"name": "m", "fields": [{"name": "chi", "role": "dark_matter", "spin": 0.5, "charges": {"su3": "6"}}]}
    assert any(p.startswith("field 1 (chi)") and "su3" in p for p in ff.problems(bad))
    with pytest.raises(ValueError, match="line 4: expected the node content"):     # the YAML's own line
        ff.from_yaml("name: m\nfields:\n- {name: chi, spin: [\n")
    with pytest.raises(ValueError, match=r"field 1 \(chi\).*not a number"):
        ff.spec_data("m", [ff.blank_row() | {"name": "chi", "hypercharge": "half"}])


def _names(user: User) -> list[str]:
    return [e.value for e in user.find(kind=ui.input).elements if e.props.get("label") == "name"]


async def _settled(user: User, count: int) -> list[str]:
    """The fields' names once the form has re-rendered (a refresh runs on the event loop)."""
    for _ in range(50):
        if len(_names(user)) == count:
            break
        await asyncio.sleep(0.02)
    return _names(user)


@pytest.fixture
def track1(user: User, tmp_path: Path) -> Path:
    from adroit.ui.app import build_pages
    return build_pages(tmp_path / "runs")


async def test_the_form_builds_the_model_the_command_reads(user: User, track1: Path, monkeypatch) -> None:
    calls = capture(monkeypatch)
    await user.open("/new/track1")
    await user.should_see("Add a field")
    await user.should_see("Edit as YAML")
    user.find("Add a field").click()
    assert sorted(await _settled(user, 3)) == ["", "S", "chi"]
    next(e for e in user.find(kind=ui.input).elements if e.props.get("label") == "name" and not e.value).value = "Zp"
    user.find("Build and audit").click()
    await user.should_see("Run:")
    command = calls[0]
    written = yaml.safe_load(Path(command[command.index("--fields") + 1]).read_text())
    assert [f["name"] for f in written["fields"]] == ["chi", "S", "Zp"]
    assert ModelSpec.model_validate(written).field("Zp").spin == 0


async def test_an_unready_model_is_not_built(user: User, track1: Path, monkeypatch) -> None:
    calls = capture(monkeypatch)
    await user.open("/new/track1")
    user.find("Add a field").click()                       # a third field with no name
    await _settled(user, 3)
    user.find("Build and audit").click()
    await user.should_see("field 3: give it a name")
    assert calls == []


async def test_the_yaml_switch_shows_the_same_model_and_reads_it_back(user: User, track1: Path) -> None:
    await user.open("/new/track1")
    switch = user.find(marker="yaml_switch").elements.pop()          # not the batch switch beside it
    switch.value = True
    area = next(e for e in user.find(kind=ui.textarea).elements if "fields:" in (e.value or ""))
    assert yaml.safe_load(area.value)["name"] == "singlet_fermion_with_scalar"
    area.value = DOUBLET
    switch.value = False
    for _ in range(50):
        if sorted(_names(user)) == ["H2", "psi"]:
            break
        await asyncio.sleep(0.02)
    assert sorted(_names(user)) == ["H2", "psi"]
    switch.value = True
    area.value = "name: m\nfields: [\n"
    switch.value = False
    await user.should_see("expected")
    assert switch.value is True and area.value == "name: m\nfields: [\n"          # the text is kept to be corrected
