"""A second doublet's Yukawas against their independent component expansion (the external audit of 2026-10-16,
A01 and its G2 check; adapted from its `physics/g2_oracle.py`).

The expectations are derived by hand from the operators, not from another of ADROIT's writings: with
Φ = (Φ⁺, Φ⁰), Φ⁰ = (r + i z)/√2, the Weyl form Q u^c εΦ = u u^c Φ⁰ − d u^c Φ⁺ and Q d^c Φ* = u d^c Φ⁻ + d d^c Φ⁰*,
and the vertex convention c + i c₂γ⁵."""

from __future__ import annotations

import math

import pytest

from adroit.core.model_spec import ModelSpec
from adroit.model_building import feynman as fy
from adroit.model_building import spectrum as sp
from adroit.model_building.gauge_basis import GaugeBasisError

FIELDS = [
    {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 100.0},
    {"name": "H", "role": "standard_model", "spin": 0, "charges": {"su2": 2, "hypercharge": 0.5}},
    {"name": "H2", "role": "other", "spin": 0, "mass_gev": 500.0, "charges": {"su2": 2, "hypercharge": 0.5}},
    {"name": "Q", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
     "charges": {"su3": "3", "su2": 2, "hypercharge": 1 / 6}},
    {"name": "uR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
     "charges": {"su3": "3", "hypercharge": 2 / 3}},
    {"name": "dR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
     "charges": {"su3": "3", "hypercharge": -1 / 3}},
    {"name": "L", "role": "standard_model", "spin": 0.5, "chirality": "L", "generations": 3,
     "charges": {"su2": 2, "hypercharge": -0.5}},
    {"name": "eR", "role": "standard_model", "spin": 0.5, "chirality": "R", "generations": 3,
     "charges": {"hypercharge": -1.0}},
]


def _occ(*xs):
    return [{"field": x.rstrip("*"), "conjugate": x.endswith("*")} for x in xs]


def _build(right="dR", weyl=True, lorentz="chiral", reverse=False, stated=".17+.04*I", indices=True):
    left = "L" if right == "eR" else "Q"
    up = right == "uR"
    fields = _occ(left, right + "*", "H2" + ("" if up else "*")) if weyl else \
        _occ(left + "*", "H2" + ("*" if up else ""), right)
    idx = (("eps[j,i]" if reverse else "eps[i,j]") + f" {left}[i] H2[j]") if up and indices else ""
    term = {"fields": fields, "lorentz": lorentz, "coupling": stated, "plus_hc": True, "indices": idx}
    spec = ModelSpec.model_validate({"name": "components", "phase": "unbroken", "fields": FIELDS, "terms": [term]})
    mb = sp.compute(spec)
    fs = fy.scalar_fields(mb)
    return mb, fs, fy.sm_yukawa_vertices(mb, fs)


CASES = [("uR", False, False), ("uR", False, True), ("uR", True, True), ("dR", False, False), ("dR", False, True),
         ("eR", False, False), ("eR", False, True)]


@pytest.mark.parametrize("right,reverse,indices", CASES)
def test_the_weyl_form_matches_its_component_expansion(right, reverse, indices):
    """Up, down and lepton terms, the default and explicit ε, and the reversed ε order, with a complex coupling: each
    vertex equals the hand expansion (the audit's G2 check: maximum error zero in all seven)."""
    mb, fs, actual = _build(right=right, reverse=reverse, indices=indices)
    k = (0.17 + 0.04j) * (-1 if reverse else 1)
    up = right == "uR"
    f = "t" if up else "b" if right == "dR" else "tau"
    u, d = ("t", "b") if right != "eR" else ("nu_tau", "tau")
    coeff = {(c.m, c.part): fs.scalar_map[i] for i, c in enumerate(mb.gauge.comp.coordinates) if c.field == "H2"}
    for j, sym in enumerate(fs.scalars):
        leg = sym.leg(sym.state in fs.self_conjugate)
        r, z = coeff[(-0.5, "re")][j], coeff[(-0.5, "im")][j]
        plus = (coeff[(0.5, "re")][j] + 1j * coeff[(0.5, "im")][j]) / math.sqrt(2)
        minus = (coeff[(0.5, "re")][j] - 1j * coeff[(0.5, "im")][j]) / math.sqrt(2)
        a_l = k * (r + (1j if up else -1j) * z) / math.sqrt(2)
        a_r = k.conjugate() * (r + (-1j if up else 1j) * z) / math.sqrt(2)
        expected = {(f + "~", f, leg): ((a_l + a_r) / 2, (a_r - a_l) / 2j)}
        if up:
            expected[(u + "~", d, leg)] = (-k * plus / 2, k * plus / 2j)
            expected[(d + "~", u, leg)] = (-k.conjugate() * minus / 2, -k.conjugate() * minus / 2j)
        else:
            expected[(u + "~", d, leg)] = (k.conjugate() * plus / 2, k.conjugate() * plus / 2j)
            expected[(d + "~", u, leg)] = (k * minus / 2, -k * minus / 2j)
        for legs, (c, c2) in expected.items():
            got = [v for v in actual if v.legs == legs]
            assert abs(sum(v.c for v in got) - c) < 1e-12 and abs(sum(v.c2 for v in got) - c2) < 1e-12, legs


def _b_rows(vertices):
    return {v.legs: (complex(v.c), complex(v.c2)) for v in vertices if v.legs[:2] == ("b~", "b")}


def test_a_dirac_pseudoscalar_doublet_yukawa_is_the_chiral_coupling_times_i():
    """The audit's A01: k Q̄Φ iγ⁵ d_R is k Q̄Φ d_R with k → ik (γ⁵ d_R = d_R); it had been read as the scalar term. For
    k = 0.17 the CP-even neutral state r has (c, c₂) = (0, k/√2) and the CP-odd one (−k/√2, 0), where the scalar
    term gives (k/√2, 0) and (0, k/√2)."""
    pseudo = _b_rows(_build(weyl=False, lorentz="pseudoscalar", stated="0.17")[2])
    scalar = _b_rows(_build(weyl=False, lorentz="scalar", stated="0.17")[2])
    times_i = _b_rows(_build(weyl=False, lorentz="scalar", stated="0.17*I")[2])
    assert pseudo == pytest.approx(times_i) and pseudo != pytest.approx(scalar)
    w = 0.17 / math.sqrt(2)
    assert sorted((round(c.real, 12), round(c2.real, 12)) for c, c2 in pseudo.values()) == \
        sorted([(0.0, round(w, 12)), (round(-w, 12), 0.0)])


@pytest.mark.parametrize("weyl,lorentz", [(False, "vector"), (False, "axial"), (False, "tensor"), (True, "pseudoscalar")])
def test_a_doublet_yukawa_with_another_lorentz_label_is_refused(weyl, lorentz):
    """No other structure joins a left-handed doublet to a right-handed singlet through a scalar; the Weyl form has no
    γ⁵ to carry 'pseudoscalar'."""
    with pytest.raises(GaugeBasisError):
        _build(weyl=weyl, lorentz=lorentz, stated="0.17")
