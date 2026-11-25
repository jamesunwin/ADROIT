"""A model as a physicist reads it (the owner, 2026-10-13): a field table and a Lagrangian in the usual notation."""

import pytest

from adroit.core.model_spec import Charges, FieldRole, ModelCoupling, ModelField, ModelSpec, ModelTerm, Occurrence, Phase
from adroit.model_building import display


def quintuplet() -> ModelSpec:
    """The owner's model: a vectorlike pair of left-handed Weyl 5-plets with Y = ±1 and their Dirac mass term."""
    fields = [ModelField(name=n, role=FieldRole.dark_matter, spin=0.5, chirality="L", mass_gev=6000.0, dark_parity=-1,
                         charges=Charges(su2=5, hypercharge=y)) for n, y in (("F5P", 1.0), ("F5M", -1.0))]
    return ModelSpec(name="quintuplet", phase=Phase.unbroken, fields=fields,
                     couplings=[ModelCoupling(name="m2_F5P_F5M", mass_dimension=1)],
                     terms=[ModelTerm(fields=[Occurrence(field="F5P"), Occurrence(field="F5M")], lorentz="chiral",
                                      coupling="m2_F5P_F5M", plus_hc=True)])


@pytest.mark.parametrize("name,expected", [
    ("chi", r"\chi"), ("g_chi", r"g_{\chi}"), ("F5P", "F_{5P}"), ("Zp", "Z'"), ("A_prime", "A'"), ("Xd", "X_{d}"),
    ("lam_H_H2", r"\lambda_{H,H_{2}}"), ("phi1", r"\phi_{1}"), ("uR", "u_R"), ("Higgs", r"\mathrm{Higgs}"),
    ("χ", r"\chi")])
def test_names_become_symbols(name, expected):
    assert display.symbol(name) == expected


def test_a_name_cannot_inject_tex():
    assert "\\input" not in display.symbol(r"\input{/etc/hosts}") and "{/" not in display.symbol(r"x}{/etc")
    assert display.coefficient("os.system('x')") == display.symbol("os.system('x')")


def test_coefficients_read_as_arithmetic():
    assert display.coefficient("g_q*m_q/v") == r"\frac{g_{q}\,m_{q}}{v}"
    assert display.coefficient("-g_q") == "-g_{q}" and display.coefficient("sqrt(2)*y") == r"\sqrt{2}\,y"


def test_the_owners_quintuplet():
    spec = quintuplet()
    doc = display.document(spec)
    assert r"$(1,5)_{1}$" in doc and r"$(1,5)_{-1}$" in doc and "left-handed Weyl fermion" in doc
    assert r"i F_{5P}^\dagger \bar\sigma^\mu D_\mu F_{5P}" in doc            # charged: the covariant derivative
    assert r"m_{2,F_{5P},F_{5M}}\,F_{5P} F_{5M} + \mathrm{h.c.}" in doc      # the Dirac mass of the Weyl pair
    assert "No value yet" in doc and "$Q$" not in doc                        # Q varies across an unbroken multiplet


def test_every_library_portal_is_written_without_a_generic_operator():
    from adroit.parameter_space import library
    for entry in library.ENTRIES:
        doc = display.document(entry.spec())
        assert r"\mathcal{O}_" not in doc, entry.id
        assert doc.count(r"\begin{aligned}") == 1 and doc.endswith(r"\end{document}")


def test_operators_by_lorentz_structure():
    from adroit.parameter_space import library
    z = display.document(library.entry("dmwg_V1").spec())
    assert r"\overline{\chi} \gamma^\mu \chi\, " in z
    photon = display.document(library.entry("dark_photon_scalar").spec())
    assert r"B^{\mu\nu}" in photon and r"-\tfrac14" in photon
    yukawa = display.document(library.entry("tchannel_uR_dirac").spec())
    assert r"\overline{u_R}\, \chi^c\,\phi" in yukawa


def test_a_model_without_terms_says_so():
    spec = ModelSpec(name="wino", phase=Phase.unbroken,
                     fields=[ModelField(name="chi", role=FieldRole.dark_matter, spin=0.5, self_conjugate=True,
                                        mass_gev=2800.0, dark_parity=-1, charges=Charges(su2=3))])
    doc = display.document(spec)
    assert "no interaction terms in the model's data" in doc and r"\tfrac12 \overline{\chi}" in doc
    assert "Majorana fermion" in doc
