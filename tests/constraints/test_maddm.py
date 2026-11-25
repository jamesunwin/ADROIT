"""DM8: driving MadDM (its outputs parsed offline)."""

from __future__ import annotations

from pathlib import Path

import pytest

from adroit.constraints import maddm

RESULTS = """################################################
Omegah2                       = 2.02e+00
Omegah_Planck                 = 1.20e-01
x_f                           = 1.80e+01
sigmav_xf                     = 5.45e-28 	 # cm^3 s^-1
%_dmchidmchix_ddx             = 20.00 %
SigmaN_SI_p                   = [1.51e-41,3.36e-48]           # LZ2024
SigmaN_SD_n                   = [1.23e-61,6.06e-43]           # LZ2024
"""
MADDM_OUT = """ Omegah^2:    2.0190267639632062
 alpha_d:    0.0000000000000000      :   -6.2499999927864713E-008 :    0.0000000000000000      :    0.0000000000000000
 alpha_t:    1.5110695878613314E-016 :   -6.2499999981867206E-008 :   -6.7158649692841426E-017 :    0.0000000000000000
"""
CARD = """DECAY  6   1.508336e+00 #  WT
DECAY  9100002   1.127299e+02 #  WDMZP
#  BR             NDA  ID1    ID2   ...
   4.705939e-01   2    -9100001  9100001 # 53.05
"""


def test_results_are_parsed() -> None:
    r = maddm.parse_results(RESULTS)
    assert r["Omegah2"] == 2.02 and r["x_f"] == 18.0 and r["sigmav_xf"] == 5.45e-28
    assert r["SigmaN_SI_p"] == 1.51e-41 and "Omegah_Planck" in r


def test_quark_coefficients_and_widths_are_parsed() -> None:
    alpha = maddm.parse_alpha(MADDM_OUT)
    assert alpha["d"][1] == -6.2499999927864713e-08 and len(alpha["t"]) == 4
    assert maddm.parse_widths(CARD) == {6: 1.508336, 9100002: 112.7299}


def test_the_command_file() -> None:
    both = maddm.script(Path("/m/x"), "dmchi", "run", {"MDMCHI": 100.0, "WDMZP": 112.7}, relic=True, direct=True)
    assert both.splitlines()[:4] == ["import model /m/x", "define darkmatter dmchi", "generate relic_density",
                                     "add direct"]
    assert "direct_electron = OFF" in both and "set WDMZP 112.7" in both
    direct = maddm.script(Path("/m/x"), "dmchi", "run", {}, relic=False, direct=True)
    assert "generate direct" in direct and "relic" not in direct
    assert isinstance(maddm.available(), bool)



def test_a_derivation_is_compared_with_madd_m_s_coefficients() -> None:
    """V1: α_SIo = C61q = −g_χ g_q/M²; the top's vector current and uncoupled quarks are set aside."""
    from adroit.core.model_spec import FieldRole, ModelCoupling, ModelField, ModelSpec
    from adroit.library.interactions import derivation as dv
    spec = ModelSpec(name="v1", fields=[ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, mass_gev=100.0),
                                        ModelField(name="Zp", role=FieldRole.mediator, spin=1.0, mass_gev=2000.0)],
                     couplings=[ModelCoupling(name="g_chi", value=1.0), ModelCoupling(name="g_q", value=0.25)])
    c = -0.25 / 2000.0 ** 2
    derivation = dv.Derivation(model_name="v1", terms=[dv.WilsonTerm(name=f"C61{q}", expression="-g_chi*g_q/m_Zp**2")
                                                       for q in "udscb"])
    alpha = {q: [0.0, c * 0.997, 0.0, 0.0] for q in "udscbt"}
    found = maddm.MadDMCoefficients(alpha=alpha, coupled=list("udscbt"), masses={q: 1.0 for q in "udscbt"})
    good = maddm.check(spec, derivation, found)
    assert good.covered and good.agree and good.max_relative_difference == pytest.approx(0.003, abs=1e-4)
    reversed_ = maddm.check(spec, derivation, found.model_copy(update={"alpha": {q: [0.0, -v[1], 0.0, 0.0]
                                                                                  for q, v in alpha.items()}}))
    assert reversed_.agree and reversed_.sign == -1
    off = maddm.check(spec, derivation, found.model_copy(update={"alpha": {q: [0.0, 2 * c, 0.0, 0.0] for q in alpha}}))
    assert not off.agree
    zero = maddm.check(spec, derivation, found.model_copy(update={"alpha": {q: [0.0] * 4 for q in alpha}}))
    assert not zero.covered and zero.agree
    stray = maddm.check(spec, derivation, found.model_copy(update={"coupled": ["u", "d"]}))
    assert stray.spurious == ["b", "c", "s", "t"]


def test_majorana_coefficients_are_halved() -> None:
    """MadDM's self-conjugate vertex is 2iα; DirectDM's Majorana operators carry ½."""
    from adroit.core.model_spec import FieldRole, ModelCoupling, ModelField, ModelSpec
    from adroit.library.interactions import derivation as dv
    spec = ModelSpec(name="m", fields=[ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5,
                                                  self_conjugate=True, mass_gev=100.0)],
                     couplings=[ModelCoupling(name="g", value=1e-6)])
    terms = [dv.WilsonTerm(name="C64u", expression="g"), dv.WilsonTerm(name="C75u", expression="g")]
    majorana = maddm.expected_alpha(spec, dv.Derivation(model_name="m", dm_type="M", terms=terms), {q: 2.0 for q in "udscbt"})
    dirac = maddm.expected_alpha(spec, dv.Derivation(model_name="m", dm_type="D", terms=terms), {q: 2.0 for q in "udscbt"})
    assert majorana["u"] == [0.5 * x for x in dirac["u"]] and dirac["u"][:3] == [2e-6, 0.0, 1e-6]


NAMES_INC = """C     Annihilation process names
      PROCESS_NAMES(1) = 'chi00chi00x_zz'
      PROCESS_NAMES(2) = 'chi00chi00x_wpwm'
      PROCESS_NAMES(10) = 'chi00chi00x_ttx'
"""
SIGMA_V_OUT = """ Omegah^2:    9.3829980322312531E-002
sigma*v:chi00chi00x_     8.3169759E-29 cm^3/s
sigma*v:chi00chi00x_     1.8717000E-27 cm^3/s
sigma*v:chi00chi00x_     1.0138000E-28 cm^3/s
"""


def test_maddm_sigma_v_is_read_by_full_process_name_and_in_our_convention() -> None:
    """maddm.out truncates the names; process_names.inc has them, in order (10 after 2). MadDM's 2 → 2 σv is ½σv_rel
    at v_rel = 2√3 v_halo, with c = 2.99×10¹⁰ cm/s."""
    found = maddm.parse_sigma_v(NAMES_INC, SIGMA_V_OUT)
    assert found == {"zz": 8.3169759e-29, "wpwm": 1.8717e-27, "ttx": 1.0138e-28}
    v, ours = maddm.relative({"zz": 1.0}, halo=2e-5)
    assert v == pytest.approx(2 * 3 ** 0.5 * 2e-5) and ours["zz"] == pytest.approx(2 * 2.99792458 / 2.99)
    with pytest.raises(RuntimeError):
        maddm.parse_sigma_v(NAMES_INC, SIGMA_V_OUT + SIGMA_V_OUT)


def test_the_indirect_command_file_asks_for_sigma_v_only(tmp_path: Path) -> None:
    lines = maddm.indirect_script(Path("/m/x"), "s0", "run").splitlines()
    assert lines[0] == "set maddm_first_indirect False" and "generate indirect_detection 2to2lo" in lines
    assert "indirect = sigmav" in lines and "set sigmav_method inclusive" in lines
    with pytest.raises(ValueError, match="code"):                  # maddm.out would cut 'd2bar0d2bar0_zz'
        maddm.indirect(tmp_path, "d2bar0", "run", tmp_path / "work")


def test_long_names_get_a_code_for_madgraph() -> None:
    """MadDM keeps 12 characters of 'χχ̄_final': a name longer than five gets a code not yet taken."""
    from adroit.library.interactions import ufo
    assert ufo.code_name("chi0", "n", set()) == "chi0"
    assert ufo.code_name("d2bar0", "n", {"n1", "n2~"}) == "n3"
    assert ufo.code_name("chi0", "n", {"chi0"}) == "n1"
