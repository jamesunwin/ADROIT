"""DM8: UFO model files from a ModelSpec (the writer; MadGraph only in the slow test)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adroit.constraints import maddm
from adroit.core.model_spec import FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm, Occurrence
from adroit.library.interactions import ufo


def term(a: str, b: str, boson: str, lorentz: str, coupling: str) -> ModelTerm:
    return ModelTerm(fields=[Occurrence(field=a, conjugate=True), Occurrence(field=b), Occurrence(field=boson)],
                     lorentz=lorentz, coupling=coupling)


def model(dm_spin: float = 0.5, majorana: bool = False, med_spin: float = 1.0, dm_lorentz: str = "vector",
          q_lorentz: str = "vector", q_coupling: str = "g_q", extra: list[ModelField] = ()) -> ModelSpec:
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=dm_spin, self_conjugate=majorana, mass_gev=100.0)
    med = ModelField(name="Zp", role=FieldRole.mediator, spin=med_spin, self_conjugate=True, mass_gev=2000.0)
    q = ModelField(name="q", role=FieldRole.standard_model, spin=0.5)
    return ModelSpec(name="toy", fields=[chi, med, q, *extra],
                     terms=[term("chi", "chi", "Zp", dm_lorentz, "g_chi"), term("q", "q", "Zp", q_lorentz, q_coupling)],
                     couplings=[ModelCoupling(name="g_chi", value=1.0), ModelCoupling(name="g_q", value=0.25)])


def test_a_vector_mediator_is_written_as_dmsimp_writes_it() -> None:
    ext = ufo.extension(model())
    assert [p.name for p in ext.particles] == ["dmchi", "dmzp"] and ext.particles[0].width == "ZERO"
    dm = ext.vertices[0]
    assert dm.particles == ["P.dmchi__tilde__", "P.dmchi", "P.dmzp"] and dm.structure == "Gamma(3,2,1)"
    assert dm.coupling == "complex(0,1)*1*(dmc_g_chi)" and dm.color == "1"
    quarks = [v for v in ext.vertices if v.particles[-1] == "P.dmzp"][1:]
    assert len(quarks) == 6 and all(v.color == "Identity(1,2)" for v in quarks)
    assert {p.name for p in ext.parameters} >= {"MDMCHI", "MDMZP", "WDMZP", "dmc_g_chi", "dmc_g_q", "MU", "MD", "MS"}


def test_couplings_in_proportion_to_quark_masses_use_each_quark_s_mass() -> None:
    ext = ufo.extension(model(med_spin=0.0, dm_lorentz="scalar", q_lorentz="scalar", q_coupling="g_q*m_q/v"))
    by_quark = {v.particles[1]: v.coupling for v in ext.vertices if v.particles[-1] == "P.dmzp"}
    assert by_quark["P.b"] == "complex(0,1)*1*(dmc_g_q*MB/vev)" and by_quark["P.u"].endswith("(dmc_g_q*MU/vev)")
    light = [v for v in ext.vertices if v.particles[-1] == "P.H"]
    assert len(light) == 3 and light[0].coupling == "-(complex(0,1)*ymdown)/vev"


def test_majorana_pseudoscalar_and_identical_scalars() -> None:
    axial = ufo.extension(model(majorana=True, dm_lorentz="axial", q_lorentz="axial"))
    assert axial.vertices[0].particles == ["P.dmchi", "P.dmchi", "P.dmzp"]
    assert axial.vertices[0].coupling.startswith("complex(0,1)*2*")       # the Majorana factor 2
    with pytest.raises(ValueError, match="no vector current"):
        ufo.extension(model(majorana=True))
    pseudo = ufo.extension(model(med_spin=0.0, dm_lorentz="pseudoscalar", q_lorentz="pseudoscalar"))
    assert pseudo.vertices[0].structure == "Gamma5(2,1)" and pseudo.vertices[0].coupling == "-1*(dmc_g_chi)"


def test_scalar_dark_matter_with_the_higgs_and_a_vector() -> None:
    s = ModelField(name="S", role=FieldRole.dark_matter, spin=0.0, self_conjugate=True, mass_gev=100.0)
    h = ModelField(name="h", role=FieldRole.mediator, spin=0.0, self_conjugate=True, mass_gev=125.25)
    portal = ModelSpec(name="hp", fields=[s, h], couplings=[ModelCoupling(name="lam_hs", value=0.1)],
                       terms=[ModelTerm(fields=[Occurrence(field="h"), Occurrence(field="S"), Occurrence(field="S")],
                                        lorentz="scalar", coupling="-lam_hs*v/2")])
    v = ufo.extension(portal).vertices[0]
    assert v.particles == ["P.H", "P.dms", "P.dms"] and v.coupling == "complex(0,1)*2*(-dmc_lam_hs*vev/2)"
    current = ufo.extension(model(dm_spin=0.0)).vertices[0]
    assert current.particles == ["P.dmzp", "P.dmchi__tilde__", "P.dmchi"] and current.structure == "P(1,3) - P(1,2)"


def test_what_the_writer_refuses() -> None:
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=100.0)
    a = ModelField(name="A", role=FieldRole.standard_model, spin=1.0, self_conjugate=True)
    dipole = ModelSpec(name="d", fields=[chi, a], couplings=[ModelCoupling(name="mu", value=1e-5, mass_dimension=-1)],
                       terms=[term("chi", "chi", "A", "dipole", "mu/2")])
    with pytest.raises(ValueError, match="dipole"):
        ufo.extension(dipole)
    with pytest.raises(ValueError, match="unknown symbol"):
        ufo.expression("g_x*v", model(), {})


def test_the_files_extend_a_copy_of_the_standard_model(tmp_path: Path) -> None:
    sm = tmp_path / "sm"
    sm.mkdir()
    for name in ("parameters.py", "lorentz.py", "couplings.py", "vertices.py", "coupling_orders.py", "__init__.py"):
        (sm / name).write_text("# sm\n")
    (sm / "particles.py").write_text("".join(f"{q} = Particle(name = '{q}',\n mass = Param.ZERO,\n Y = 0)\n"
                                             for q in "uds"))
    for skipped in ("decays.py", "restrict_default.dat", "py3_model.pkl"):
        (sm / skipped).write_text("x")
    out = ufo.write(model(), tmp_path / "out", sm_dir=sm)
    assert out.name == "adroit_toy" and not (out / "decays.py").exists() and not (out / "restrict_default.dat").exists()
    particles = (out / "particles.py").read_text()
    assert "mass = Param.MU" in particles and "mass = Param.ZERO" not in particles and "dmchi = Particle(" in particles
    assert "V_DM_0 = Vertex(" in (out / "vertices.py").read_text()
    assert "DMV = CouplingOrder(" in (out / "coupling_orders.py").read_text()


@pytest.mark.slow
@pytest.mark.skipif(not maddm.available(), reason="MadGraph and MadDM are not installed")
def test_madgraph_computes_the_mediator_width(tmp_path: Path) -> None:
    """V1 at M = 2 TeV: Γ = 112.73 GeV, as DMsimp gives (112.7295 GeV)."""
    spec = model().model_copy(update={"name": "width_test"})
    widths = maddm.widths(ufo.write(spec, tmp_path), ["dmzp"], tmp_path / "w")
    assert widths[ufo.PDG_START + 1] == pytest.approx(112.73, rel=1e-3)


def test_a_photon_coupled_to_a_neutral_field_through_a_mu_is_refused() -> None:
    chi = ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=100.0)
    a = ModelField(name="A", role=FieldRole.standard_model, spin=1.0, self_conjugate=True)
    bad = ModelSpec(name="b", fields=[chi, a], couplings=[ModelCoupling(name="k", value=1e-5)],
                    terms=[term("chi", "chi", "A", "axial", "k")])
    with pytest.raises(ValueError, match="field strength"):
        ufo.extension(bad)


def test_a_long_field_name_gets_a_code() -> None:
    """dm + 'Zprime' would be six characters, beyond what MadDM's output carries: it is written as dm1."""
    long = ModelField(name="Zprime", role=FieldRole.mediator, spin=1.0, self_conjugate=True, mass_gev=500.0)
    ext = ufo.extension(model(extra=[long]))
    assert ext.names == {"chi": "dmchi", "Zp": "dmzp", "Zprime": "dm1"}
    assert {p.name for p in ext.particles} == {"dmchi", "dmzp", "dm1"}
