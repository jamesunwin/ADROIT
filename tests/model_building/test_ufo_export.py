"""The UFO export of a typed model's Feynman rules (G2/G4): MadDM's cross-check of the generic route."""

from pathlib import Path

import pytest

from adroit.constraints import maddm
from adroit.core.model_spec import ModelSpec
from adroit.model_building import feynman as fy
from adroit.model_building import spectrum as sp
from adroit.model_building import ufo_export as ux

WINO = {"name": "wino", "phase": "unbroken", "fields": [
    {"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1, "mass_gev": 1000.0,
     "charges": {"su2": 3}}]}


def _rules():
    return fy.feynman_rules(sp.compute(ModelSpec.model_validate(WINO)))


def _fake_sm(tmp_path: Path) -> Path:
    sm = tmp_path / "sm"
    sm.mkdir()
    for name in ux.COPIED:
        (sm / name).write_text("gauge = [0, 1]\n" if name == "__init__.py" else "# sm\n")
    return sm


def test_new_particles_avoid_madgraphs_ghost_codes():
    """MadDM skips 9000001–9000004 (FeynRules' ghosts) when it assigns Z₂ parities; a coannihilator there would be
    dropped without notice (it was: MadDM's wino Ωh² read 0.0326, χ⁰χ⁰ alone)."""
    table = ux.names(_rules())
    new = [code for name, (_, _, code) in table.items() if name not in ux.SM_NAMES]
    assert new and min(new) >= ux.PDG_START > 9000004
    assert table["A"][2] == 22 and table["W"][:2] == ("W+", "W-")


def test_new_names_are_lower_case_and_distinct():
    """MadGraph lower-cases names on import; a capital would make the dark matter unknown to MadDM."""
    from adroit.model_building.feynman import ParticleRecord, Rules
    rules = Rules([ParticleRecord("N0", 0.5, 300.0, "N0~", "1", 0.0, -1), ParticleRecord("n0", 0.5, 310.0, "n0~", "1", 0.0, -1),
                   ParticleRecord("H'", 0, 400.0, "", "1", 0.0, 1)], [], 1.2)
    table = ux.names(rules)
    new = [table[n][0] for n in ("N0", "n0", "H'")]
    assert all(x == x.lower() for x in new) and len(set(new)) == 3 and "h" not in new


def test_the_files_are_written_in_unitary_gauge_with_a_massless_photon(tmp_path: Path):
    out = ux.write(_rules(), tmp_path / "out", "wino_point", sm_dir=_fake_sm(tmp_path))
    assert "gauge = [0]" in (out / "__init__.py").read_text()
    particles = (out / "particles.py").read_text()
    photon = particles[particles.index("name = 'a'"):]
    assert "mass = Param.ZERO" in photon[:photon.index(")")]
    assert "Vertex(" in (out / "vertices.py").read_text()


def test_external_couplings_leave_the_process_files_alike_across_points(tmp_path: Path):
    """F1: with the couplings external parameters, every file MadGraph's process depends on (all but parameters.py)
    is the same at two masses whose couplings differ (g_s and the mixing move with m_χ); the point's numbers are the
    parameters' defaults and ``coupling_settings``, which equal the couplings written as numbers."""
    import re
    from adroit.constraints import pair_production as pp
    sm = _fake_sm(tmp_path)
    folders, values = [], []
    for mass in (1000.0, 1300.0):
        spec = {**WINO, "fields": [{**WINO["fields"][0], "mass_gev": mass}]}
        rules = fy.feynman_rules(sp.compute(ModelSpec.model_validate(spec)), g_s=1.2 if mass == 1000.0 else 1.1)
        folders.append(ux.write(rules, tmp_path / f"ext{mass:.0f}", "point", sm_dir=sm, external_couplings=True))
        numbers = ux.write(rules, tmp_path / f"num{mass:.0f}", "point", sm_dir=sm).joinpath("couplings.py").read_text()
        written = [complex(float(a), float(b)) for a, b in re.findall(r"complex\(([-0-9.e+]+),([-0-9.e+]+)\)", numbers)]
        settings = ux.coupling_settings(rules)
        parts = {line.split()[1] + line.split()[2]: float(line.split()[3]) for line in settings}
        values.append(written)
        assert written == [complex(parts[f"ADROITGCR{n}"], parts[f"ADROITGCI{n}"]) for n in range(1, len(written) + 1)]
    assert values[0] != values[1]
    assert pp._key(folders[0], {}, structure=True) == pp._key(folders[1], {}, structure=True)
    assert pp._key(folders[0], {}) != pp._key(folders[1], {})


@pytest.mark.slow
@pytest.mark.skipif(not maddm.available(), reason="MadGraph and MadDM are not installed")
def test_maddm_reproduces_the_generic_wino(tmp_path: Path):
    """MadDM on the exported wino at 1 TeV, with χ± as coannihilators: within G4's 10% of the generic route."""
    from adroit.parameter_space.portals.generic import GenericModel
    model = ux.write(_rules(), tmp_path, "wino_point")
    result = maddm.run(model, "chi0", {}, "wino_relic", tmp_path / "work", relic=True, direct=False,
                       coannihilators=["chip", "chip~"])
    engine = GenericModel.of(ModelSpec.model_validate(WINO), sommerfeld=False)
    assert result.omega_h2 == pytest.approx(engine.omega_h2(engine.point()), rel=0.10)


PARTNER = {"name": "t", "phase": "unbroken", "fields": [
    {"name": "S", "role": "dark_matter", "spin": 0, "self_conjugate": True, "dark_parity": -1, "mass_gev": 150.0},
    {"name": "Psi", "role": "mediator", "spin": 0.5, "dark_parity": -1, "mass_gev": 175.5,
     "charges": {"hypercharge": -1.0}},
    {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": 400.0,
     "charges": {"su3": "3", "hypercharge": 2 / 3}},
    {"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": {"hypercharge": -1.0}}],
    "couplings": [{"name": "y", "value": 1.17}],
    "terms": [{"fields": [{"field": "Psi", "conjugate": True}, {"field": "eR"}, {"field": "S"}], "lorentz": "chiral",
               "coupling": "y", "plus_hc": True}]}


@pytest.mark.slow
@pytest.mark.skipif(not maddm.available(), reason="MadGraph is not installed")
def test_the_export_reads_back_as_the_same_model(tmp_path: Path):
    """Written, loaded by MadGraph's Python and read back (``ufo_model``): every process as before. The Yukawa
    joins two species, so it tests the UFO's creation-sense listing (its chirality came back swapped before);
    the coloured scalar tests the colour indices (φφ* → gg lost its gauge cancellation before)."""
    from adroit.constraints import tree, ufo_model
    from adroit.parameter_space.portals.generic import tree_model
    rules = fy.feynman_rules(sp.compute(ModelSpec.model_validate(PARTNER)))
    ours = tree_model(rules)
    table = ux.names(rules)
    back = ufo_model.to_model(ufo_model.dump(ux.write(rules, tmp_path, "partner"), {}), full_colour=True)[0]
    def ufo(n: str) -> str:
        return table[n][0] if n in table else table[n[:-1]][1]
    psi = next(p.name for p in rules.particles if p.name.startswith("Psi"))
    phi = next(p.name for p in rules.particles if p.name.startswith("Phi"))
    for proc, root in [(("S0", psi, "Z", "e~"), 400.0), ((psi, psi + "~", "e", "e~"), 400.0),
                       ((phi, phi + "~", "g", "g"), 2000.0), ((phi, phi + "~", "u", "u~"), 2000.0)]:
        a = tree.Process(ours, *proc).sigma(root ** 2)
        b = tree.Process(back, *(ufo(n) for n in proc)).sigma(root ** 2)
        assert b == pytest.approx(a, rel=1e-9), proc


def test_long_new_names_get_a_code():
    """φ of hypercharge 2/3 would be phip0667: MadDM's output would cut it, so it is n1 in MadGraph."""
    rules = fy.feynman_rules(sp.compute(ModelSpec.model_validate(PARTNER)))
    table = ux.names(rules)
    new = {k: v for k, v in table.items() if k not in ux.SM_NAMES}
    assert all(len(v[0].rstrip("~")) <= 5 and len(v[1].rstrip("~")) <= 5 for v in new.values())
    phi = next(k for k in new if k.startswith("Phi"))
    assert table[phi][0] == "n1" and len({v[0] for v in new.values()}) == len(new)


def test_a_contact_vertex_carries_one_order_per_boson():
    """g g φ φ* ∝ g_s² is QCD 2 (the external audit of 2026-10-17 found it QCD 1), γ g φ φ* QCD 1 QED 1; a gluon's
    three-point vertex is QCD 1 and any other vertex QED 1."""
    from adroit.model_building.feynman import MassVertex
    assert ux.coupling_order(MassVertex("VVSS", ("g", "g", "Phi", "Phi~"), 1.0)) == {"QCD": 2}
    assert ux.coupling_order(MassVertex("VVSS", ("a", "g", "Phi", "Phi~"), 1.0)) == {"QCD": 1, "QED": 1}
    assert ux.coupling_order(MassVertex("VVSS", ("W+", "W-", "H", "H"), 1.0)) == {"QED": 2}
    assert ux.coupling_order(MassVertex("FFV", ("u~", "u", "g"), 1.0)) == {"QCD": 1}
    assert ux.coupling_order(MassVertex("VSS", ("g", "Phi", "Phi~"), 1.0)) == {"QCD": 1}
    assert ux.coupling_order(MassVertex("FFS", ("chi", "u", "Phi~"), 1.0)) == {"QED": 1}


@pytest.mark.needs("madgraph")
def test_colour_indices_are_the_created_particles_as_in_madgraphs_models(tmp_path: Path):
    """T(a, i, j) has i at the created triplet (MadGraph's sm writes u~ u g as T(3,2,1)), and a coupling with one
    generator takes the conjugate representation's sign (−Tᵀ): the colour flow MadGraph assigns needs the positions,
    while every colour-summed σ is unchanged (``tests/constraints/test_pair_production.py`` checks g g → φφ* against
    the tree engine)."""
    import re
    rules = fy.feynman_rules(sp.compute(ModelSpec.model_validate(PARTNER)))
    ufo = ux.write(rules, tmp_path, "partner")
    vertices = (ufo / "vertices.py").read_text()
    table = ux.names(rules)
    phi = next(p.name for p in rules.particles if p.name.startswith("Phi"))
    n, nbar, _ = table[phi]
    quark = re.search(r"particles = \[ P\.u__tilde__, P\.u, P\.g \], color = \[ '([^']+)' \]", vertices)
    assert quark and quark.group(1) == "T(3,2,1)"
    scalar = re.search(rf"particles = \[ P\.g, P\.{ux._identifier(nbar)}, P\.{ux._identifier(n)} \], color = \[ '([^']+)' \]",
                       vertices)
    assert scalar and scalar.group(1) == "T(1,3,2)"
