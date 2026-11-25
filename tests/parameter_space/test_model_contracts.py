"""Explicit model contracts, independent amplitudes and legacy-limit regressions."""

from copy import deepcopy
import math
from pathlib import Path

import numpy as np
from pydantic import ValidationError
import pytest
import sympy as sy
import yaml

from adroit.constraints import amplitudes, annihilation, spin1, verdicts
from adroit.core.model_contracts import (
    VECTOR_FLAVOURS,
    ScalarPotentialContract,
    VectorCurrentContract,
)
from adroit.core.model_spec import ModelSpec, Phase
from adroit.core.dm_state import DarkMatterParticle
from adroit.model_building.audit import audit
from adroit.model_building.scalar_contract import coefficients, resolved_spec
from adroit.parameter_space import searches
from adroit.parameter_space.classes import Spin1Class
from adroit.parameter_space.classify import Unsupported, classify
from adroit.parameter_space.portals.higgs import HiggsPortalScalar, M_H, V
from adroit.parameter_space.portals.scalar_potential import CompleteScalarPortal
from adroit.parameter_space.scan import Axis, ScanRequest


def load(name: str) -> ModelSpec:
    return ModelSpec.model_validate(yaml.safe_load(Path(f"docs/examples/{name}.yaml").read_text()))


def vector(**couplings: float) -> ModelSpec:
    data = load("flavour_vector").model_dump(mode="json")
    data["fields"] = data["fields"][:2]
    data["couplings"] = data["couplings"][:1]
    data["terms"] = data["terms"][:1]
    data["vector_currents"]["flavours"] = {f: f for f in couplings}
    data["vector_currents"]["zero_flavours"] = [f for f in VECTOR_FLAVOURS if f not in couplings]
    for f, g in couplings.items():
        data["fields"].append(
            dict(
                name=f,
                role="standard_model",
                spin=0.5,
                dark_parity=1,
                charges=dict(
                    su3="3" if f in VECTOR_FLAVOURS[:6] else "1",
                    electric_charge=2 / 3
                    if f in ("u", "c", "t")
                    else -1 / 3
                    if f in VECTOR_FLAVOURS[:6]
                    else -1,
                ),
            )
        )
        data["couplings"].append(dict(name="C" + f, value=-g))
        data["terms"].append(
            dict(
                fields=[dict(field="V"), dict(field=f, conjugate=True), dict(field=f)],
                lorentz="vector",
                coupling="C" + f,
            )
        )
    return ModelSpec.model_validate(data)


def test_complete_flavour_partition_never_fills_missing() -> None:
    with pytest.raises(ValidationError, match="every named"):
        VectorCurrentContract(flavours={"u": "u"}, zero_flavours=[], neutrinos="absent")
    with pytest.raises(ValidationError, match="every named"):
        VectorCurrentContract(
            flavours={"u": "u"}, zero_flavours=list(VECTOR_FLAVOURS), neutrinos="absent"
        )
    with pytest.raises(ValidationError):
        VectorCurrentContract(
            flavours={}, zero_flavours=list(VECTOR_FLAVOURS), neutrinos="included"
        )
    cls, p, _ = classify(vector(u=0.2, d=-0.15, mu=0.05))
    model = cls.model(p)
    assert model.g_nu == 0 and model.flavour_couplings["u"] == 0.2
    assert all(model.couplings(f) == (0, 0) for f in model.fermions() if f.family == "neutrino")
    assert all(
        model.couplings(f) == (0, 0)
        for f in model.fermions()
        if f.name in ("s", "c", "t", "e", "tau")
    )
    _, vals = spin1.card_values(model)
    assert vals["gV_p"] == pytest.approx(0.25) and vals["gV_n"] == pytest.approx(-0.1)
    assert audit(vector(u=0.2, d=-0.15, mu=0.05)).valid


@pytest.mark.parametrize("gq", [0.25, 0, -0.12])
def test_universal_neutrino_free_limit_matches_legacy(gq: float) -> None:
    cls, p, _ = classify(vector(**{f: gq for f in VECTOR_FLAVOURS[:6]}))
    old = Spin1Class(name=cls.name)
    op = p.model_copy(update={"g_q": gq})
    assert cls.universal_point(p) == op
    assert cls.model(p) == old.model(op)
    assert spin1.width(cls.model(p), p.m_chi) == spin1.width(old.model(op), p.m_chi)
    assert cls.dd(p) == old.dd(op)
    assert cls.interaction(p).coefficients == old.interaction(op).coefficients
    assert cls.sigma_v_today(p, 1e-3) == old.sigma_v_today(op, 1e-3)
    assert verdicts.benchmark_of(cls.completion(p)) == verdicts.benchmark_of(old.completion(op))


@pytest.mark.parametrize("mchi,med,energy", [(50, 300, 120), (200, 600, 500), (50, 300, 300)])
def test_flavour_annihilation_matches_independent_spinors(
    mchi: float, med: float, energy: float
) -> None:
    cls, p, _ = classify(vector(u=0.13, d=-0.2, b=0.31, t=-0.12, mu=0.017))
    p = p.model_copy(update={"m_chi": mchi, "m_med": med})
    model = cls.model(p)
    gamma = spin1.width(model, mchi)
    ss = energy**2
    expected = 0.0
    for f in model.fermions():
        if energy > 2 * f.mass_gev:
            expected += amplitudes.s_channel_sigma(
                ss,
                mchi,
                f.mass_gev,
                (p.g_chi, 0),
                model.couplings(f),
                med,
                gamma,
                colours=f.colours,
            )
    actual = annihilation.to_standard_model(np.array([ss]), model, mchi)[0]
    assert actual == pytest.approx(expected, rel=1e-9, abs=0)


def _spinor_width(med: float, mass: float, coupling: float, colours: int) -> float:
    if med <= 2 * mass:
        return 0.0
    k = math.sqrt(med * med / 4 - mass * mass)
    k1 = np.array([[0.0, 0.0, k]])
    k2 = -k1
    rest = np.array([[med, 0.0, 0.0, 0.0]])
    # Physical rest-frame polarizations avoid polarisations()'s k=0 direction.
    total = 0.0
    for axis in np.eye(3):
        eps = np.concatenate([[0.0], axis])[None, :]
        for a in amplitudes._BASIS:
            u = amplitudes.bar(amplitudes.spinor_u(k1, mass, a))
            for b in amplitudes._BASIS:
                vf = amplitudes.spinor_v(k2, mass, b)
                amp = np.einsum("ni,nij,nj->n", u, amplitudes.slash(eps) * coupling, vf)
                total += float(abs(amp[0]) ** 2)
    return colours * (total / 3) * k / (8 * math.pi * rest[0, 0] ** 2)


@pytest.mark.parametrize(
    "med,mass,g,colours",
    [(300, 4.7, -0.3, 3), (10, 4.99, 0.1, 3), (2, 0.10566, 0.05, 1), (9.4, 4.7, 0.2, 3)],
)
def test_widths_independent_polarization_and_spin_sums(
    med: float, mass: float, g: float, colours: int
) -> None:
    assert spin1.partial_width(med, mass, colours, g, 0) == pytest.approx(
        _spinor_width(med, mass, g, colours), rel=1e-10
    )


def test_supplied_masses_signs_and_label_permutations() -> None:
    spec = vector(u=0.2, d=-0.15, b=0.1, mu=0.05)
    data = spec.model_dump(mode="json")
    for field in data["fields"]:
        if field["name"] == "b":
            field["mass_gev"] = 80
    changed = ModelSpec.model_validate(data)
    cls, p, _ = classify(changed)
    old, op, _ = classify(spec)
    assert spin1.width(cls.model(p), p.m_chi) != spin1.width(old.model(op), op.m_chi)
    assert cls.sigma_v_today(p, 1e-3)["b"] == 0
    renamed = deepcopy(data)
    names = {f["name"]: "alias_" + f["name"] for f in data["fields"]}
    for f in renamed["fields"]:
        f["name"] = names[f["name"]]
    for t in renamed["terms"]:
        for occurrence in t["fields"]:
            occurrence["field"] = names[occurrence["field"]]
        t["fields"].reverse()
    renamed["vector_currents"]["flavours"] = {
        f: names[n] for f, n in data["vector_currents"]["flavours"].items()
    }
    renamed["fields"].reverse()
    renamed["terms"].reverse()
    renamed["couplings"].reverse()
    r, rp, _ = classify(ModelSpec.model_validate(renamed))
    assert spin1.width(r.model(rp), rp.m_chi) == spin1.width(cls.model(p), p.m_chi)
    assert r.interaction(rp).coefficients == cls.interaction(p).coefficients
    assert r.sigma_v_today(rp, 1e-3) == cls.sigma_v_today(p, 1e-3)


@pytest.mark.parametrize(
    "alteration",
    ["chiral", "axial", "hc", "generation", "dimension", "missing", "extra", "majorana"],
)
def test_vector_precise_refusals(alteration: str) -> None:
    data = vector(u=0.2, d=-0.1).model_dump(mode="json")
    if alteration == "chiral":
        data["fields"][2]["chirality"] = "R"
    if alteration == "axial":
        data["terms"][1]["lorentz"] = "axial"
    if alteration == "hc":
        data["terms"][1]["plus_hc"] = True
    if alteration == "generation":
        data["fields"][2]["generations"] = 3
    if alteration == "dimension":
        data["couplings"][1]["mass_dimension"] = 1
    if alteration == "missing":
        data["terms"].pop()
    if alteration == "extra":
        data["terms"].append(
            dict(
                fields=[
                    dict(field="V"),
                    dict(field="V"),
                    dict(field="chi"),
                    dict(field="chi", conjugate=True),
                ],
                lorentz="scalar",
                coupling="1",
            )
        )
    if alteration == "majorana":
        data["fields"][0]["self_conjugate"] = True
    with pytest.raises(Unsupported):
        classify(ModelSpec.model_validate(data))


def test_nonuniversal_collider_and_native_refuse_without_false_benchmark() -> None:
    from adroit.parameter_space.native_joint import _supported

    cls, p, _ = classify(vector(u=0.2, d=-0.1, mu=0.05))
    assert cls.universal_point(p) is None and searches._z_prime(cls, p) is None
    assert verdicts.benchmark_of(cls.model(p)) is None
    assert not _supported(cls)
    assert any("colliders" in t for t in cls.pending(p))
    assert any("LEP" in t for t in cls.pending(p))
    assert not cls.isoscalar()
    assert classify(vector(u=0.2, d=0.2))[0].isoscalar()
    assert any("radiatively" in t for t in classify(vector(b=0.2))[0].pending(p))


@pytest.mark.parametrize("phase", [Phase.unbroken, Phase.broken])
def test_scalar_symbolic_expansion_masses_and_vertices(phase: Phase) -> None:
    spec = load("complete_scalar_singlet")
    if phase is Phase.broken:
        data = spec.model_dump(mode="json")
        data["phase"] = "broken"
        data["fields"][1].update(self_conjugate=True, charges={})
        spec = ModelSpec.model_validate(data)
    p = spec.scalar_potential.resolve()
    h, s = sy.symbols("h s")
    v = sy.Float(p.v_gev)
    x = (v + h) ** 2 / 2
    potential = (
        -p.mu_h2_gev2 * x
        + p.lambda_h * x * x
        + p.mu_s2_gev2 * s * s / 2
        + p.lambda_s * s**4 / 4
        + p.lambda_hs * x * s * s / 2
    )
    assert float(sy.diff(potential, h).subs({h: 0, s: 0})) == pytest.approx(0, abs=1e-9)
    assert float(sy.diff(potential, h, 2).subs({h: 0, s: 0})) == pytest.approx(
        p.higgs_mass_gev**2, rel=1e-12
    )
    assert float(sy.diff(potential, s, 2).subs({h: 0, s: 0})) == pytest.approx(
        p.singlet_mass_gev**2, rel=1e-12
    )
    # Independent derivatives give vertex factors (minus i times these).
    assert float(sy.diff(potential, h, 1, s, 2).subs({h: 0, s: 0})) == pytest.approx(
        p.lambda_hs * p.v_gev
    )
    assert float(sy.diff(potential, h, 2, s, 2)) == pytest.approx(p.lambda_hs)
    assert float(sy.diff(potential, s, 4)) == pytest.approx(6 * p.lambda_s)
    resolved = resolved_spec(spec)
    assert len(resolved.terms) == (5 if phase is Phase.unbroken else 7)
    assert audit(spec).valid, audit(spec).problems
    verified = resolved_spec(resolved)
    assert verified == resolved
    cls, point, _ = classify(spec)
    assert isinstance(cls, CompleteScalarPortal) and point.g_chi == p.lambda_hs
    if phase is Phase.broken:
        expected = coefficients(p, phase)
        expr = sum(
            sy.Float(coef) * sy.prod(h if o.field == "H" else s for o in fields)
            for fields, coef, _ in expected.values()
        )
        # Remove constant and tadpole before comparing the physical polynomial.
        delta = sy.Poly(sy.expand(expr + potential - potential.subs({h: 0, s: 0})), h, s)
        assert all(abs(float(c)) < 1e-8 for c in delta.coeffs())


def test_equivalent_scalar_bases_and_retained_self_coupling() -> None:
    spec = load("complete_scalar_singlet")
    p = spec.scalar_potential.resolve()
    data = spec.model_dump(mode="json")
    data["scalar_potential"].update(
        basis="potential", mu_h2_gev2=p.mu_h2_gev2, mu_s2_gev2=p.mu_s2_gev2, lambda_h=p.lambda_h
    )
    derived = ModelSpec.model_validate(data)
    assert derived.scalar_potential.resolve() == p
    cls, point, _ = classify(spec)
    other, otherpoint, _ = classify(derived)
    assert cls == other and point == otherpoint
    data["scalar_potential"]["lambda_s"] = 0.6
    different, dp, _ = classify(ModelSpec.model_validate(data))
    assert different.potential != cls.potential
    assert different.dd(dp) == cls.dd(point)
    energies = np.array([4 * point.m_chi**2 * 1.01, 4 * point.m_chi**2 * 2.0])
    legacy = HiggsPortalScalar(name=cls.name)
    for name, value in cls.channels(energies, point).items():
        assert np.array_equal(value, legacy.channels(energies, point)[name])
        assert np.array_equal(value, different.channels(energies, dp)[name])
    assert cls.nucleon(point) == legacy.nucleon(point)
    updated = cls.point_potential(point.model_copy(update={"m_chi": 50, "g_chi": 1}))
    assert updated.mu_s2_gev2 < 0 and updated.lambda_s == 0.2


@pytest.mark.parametrize(
    "alteration",
    [
        "missing_self",
        "missing_vacuum",
        "mixing",
        "redundant",
        "SMmass",
        "Z2breaking",
        "missing_term",
        "dimension",
        "odd_higgs",
    ],
)
def test_scalar_precise_refusals(alteration: str) -> None:
    data = load("complete_scalar_singlet").model_dump(mode="json")
    if alteration == "missing_self":
        data["scalar_potential"].pop("lambda_s")
    if alteration == "missing_vacuum":
        data["scalar_potential"].pop("vacuum")
    if alteration == "mixing":
        data["scalar_potential"]["vacuum"]["singlet_vev_gev"] = 1
    if alteration == "redundant":
        data["scalar_potential"]["mu_s2_gev2"] = 7
    if alteration == "SMmass":
        data["scalar_potential"]["higgs_mass_gev"] = 130
    if alteration == "odd_higgs":
        data["fields"][1]["dark_parity"] = -1
    if alteration in ("missing_term", "Z2breaking", "dimension"):
        data = resolved_spec(ModelSpec.model_validate(data)).model_dump(mode="json")
        if alteration == "missing_term":
            data["terms"].pop()
        if alteration == "Z2breaking":
            data["terms"].append(dict(fields=[dict(field="S")] * 3, lorentz="scalar", coupling="1"))
        if alteration == "dimension":
            data["couplings"][0]["mass_dimension"] = 0
    with pytest.raises((ValidationError, Unsupported)):
        classify(ModelSpec.model_validate(data))


def test_scalar_overflow_redundant_field_masses_and_aliases() -> None:
    data = load("complete_scalar_singlet").model_dump(mode="json")
    overflow = deepcopy(data["scalar_potential"])
    overflow["singlet_mass_gev"] = 1e308
    with pytest.raises(ValidationError, match="overflow"):
        ScalarPotentialContract.model_validate(overflow)
    tiny = deepcopy(data["scalar_potential"])
    tiny["vacuum"]["v_gev"] = 1e-300
    with pytest.raises(ValidationError, match="domain"):
        ScalarPotentialContract.model_validate(tiny)
    data["fields"][0]["mass_gev"] = 201
    with pytest.raises(Unsupported, match="conflicts"):
        classify(ModelSpec.model_validate(data))
    data["fields"][0]["mass_gev"] = 200
    data["fields"][0]["name"] = "dark_scalar"
    data["fields"][1]["name"] = "doublet"
    data["scalar_potential"].update(singlet_field="dark_scalar", higgs_field="doublet")
    cls, p, _ = classify(ModelSpec.model_validate(data))
    old, op, _ = classify(load("complete_scalar_singlet"))
    assert cls.dd(p) == old.dd(op) and cls.potential.singlet_field == "dark_scalar"
    assert cls.invisible(p) == old.invisible(op)


@pytest.mark.parametrize("example", ["flavour_vector", "complete_scalar_singlet"])
def test_typed_round_trip_and_axis_refusals(example: str) -> None:
    cls, p, _ = classify(load(example))
    req = ScanRequest(
        model_class=cls,
        fixed=p,
        x=Axis(parameter="g_chi", low=0.1, high=0.2, n=2),
        y=Axis(parameter="m_chi", low=50, high=100, n=2),
        workers=1,
    )
    assert ScanRequest.model_validate_json(req.model_dump_json()) == req
    with pytest.raises(ValidationError):
        ScanRequest.model_validate(
            req.model_copy(update={"x": Axis(parameter="g_q", low=0.1, high=0.2, n=2)}).model_dump()
        )
    if isinstance(cls, CompleteScalarPortal):
        with pytest.raises(ValueError):
            cls.nucleon(p.model_copy(update={"m_med": 130}))
    else:
        with pytest.raises(ValueError):
            cls.model(p.model_copy(update={"g_q": 0.25}))


@pytest.mark.parametrize("gu,gd", [(0.2, -0.15), (0.2, -0.1), (0, 0.2), (0.2, 0.2)])
def test_vector_nuclear_rate_matches_independent_coherent_charge(gu: float, gd: float) -> None:
    from adroit.core.dm_state import DarkMatterParticle, HaloModel
    from adroit.physics import conventions as cv, halo, nuclear, rates, targets
    from adroit.physics.nuclear import NuclearModel

    cls, p, _ = classify(vector(u=gu, d=gd))
    energies = np.array([1.0, 5.0, 15.0])
    target = targets.single_isotope("Ar40")
    particle = DarkMatterParticle(mass_gev=p.m_chi)
    actual = rates.differential_rate(
        energies, particle, cls.interaction(p), target, model=NuclearModel.helm
    )
    q = np.sqrt(2 * cv.nuclear_mass_gev(40) * energies * cv.KEV)
    eta = halo.velocity_integrals(
        np.array([cv.v_min_km_s(e, cv.nuclear_mass_gev(40), p.m_chi) for e in energies]),
        HaloModel(),
    )[0]
    # Helm carries only M. Exact propagator and leading conserved valence charge.
    charge = p.g_chi * (18 * (2 * gu + gd) + 22 * (gu + 2 * gd)) / (p.m_med**2 + q * q)
    expected = (
        0.3
        / p.m_chi
        * charge**2
        * nuclear.helm_form_factor(q, 40) ** 2
        * eta
        * cv.C_KM_S
        / (2 * math.pi)
        * rates.RATE_UNIT
    )
    # M_vector retains its order-q^2/m_N^2 relativistic correction as well.
    assert actual.rate == pytest.approx(expected, rel=0.003, abs=0)
    assert any(c.operator == 3 for c in cls.interaction(p).coefficients)


def test_scalar_pair_amplitude_from_potential_derivatives_independent_quadrature() -> None:
    from scipy.integrate import quad
    from adroit.constraints import processes

    cls, p, _ = classify(load("complete_scalar_singlet"))
    h, s = sy.symbols("h s")
    pot = cls.potential
    x = (pot.v_gev + h) ** 2 / 2
    vv = (
        -pot.mu_h2_gev2 * x
        + pot.lambda_h * x * x
        + pot.mu_s2_gev2 * s * s / 2
        + pot.lambda_s * s**4 / 4
        + pot.lambda_hs * x * s * s / 2
    )

    def vertex(nh: int, ns: int) -> float:
        return float(sy.diff(vv, h, nh, s, ns).subs({h: 0, s: 0}))

    ghss, ghhh, ghhss = vertex(1, 2), vertex(3, 0), vertex(2, 2)
    for energy in (420.0, 600.0, 1000.0):
        ss = energy**2
        pp = math.sqrt(ss / 4 - p.m_chi**2)
        kk = math.sqrt(ss / 4 - M_H**2)
        propagator = 1 / (ss - M_H**2 + 1j * M_H * cls.width_h(p))

        def square(z: float) -> float:
            t = p.m_chi**2 + M_H**2 - ss / 2 + 2 * pp * kk * z
            u = p.m_chi**2 + M_H**2 - ss / 2 - 2 * pp * kk * z
            return (
                abs(
                    ghhss
                    + ghss * ghhh * propagator
                    + ghss**2 * (1 / (t - p.m_chi**2) + 1 / (u - p.m_chi**2))
                )
                ** 2
            )

        independent = (
            quad(square, -1, 1, epsabs=1e-13, epsrel=1e-10)[0] * kk / pp / (64 * math.pi * ss)
        )
        numerical = processes.scalars_to_scalars(
            ss, p.m_chi, M_H, p.g_chi * (1 + 3 * M_H**2 * propagator), p.g_chi * V, p.m_chi
        )
        assert numerical == pytest.approx(independent, rel=1e-10, abs=0)


def test_exact_detector_limit_scaling_and_zero_charge(monkeypatch: pytest.MonkeyPatch) -> None:
    from adroit.parameter_space import flavour_limits
    from adroit.parameter_space.limits import StatisticalLimit

    calls = []

    def limit(mass: float, med: float, gp: float, gn: float) -> StatisticalLimit:
        calls.append((mass, med, gp, gn))
        return StatisticalLimit(
            value=0.02, confidence_level=0.95, source="detector", construction="checked"
        )

    monkeypatch.setattr(flavour_limits, "limit95", limit)
    cls, p, _ = classify(vector(u=0.2, d=-0.15))
    result = cls.dd_statistical_limit(p)
    assert calls == [(50.0, 300.0, pytest.approx(0.25), pytest.approx(-0.1))]
    assert result.value == pytest.approx(0.1) and result.confidence_level == 0.95
    assert result.source == "detector"
    assert cls.dd_statistical_limit(p.model_copy(update={"g_chi": -0.4})).value == pytest.approx(
        0.05
    )


def test_limit_refuses_unvalidated_mass_and_no_nuclear_charge() -> None:
    from adroit.parameter_space.flavour_limits import limit95

    assert limit95(50, 300, 0, 0).value is None
    assert limit95(1e10, 300, 0.2, 0.1).value is None
    with pytest.raises(ValueError):
        limit95(50, 300, float("nan"), 0)


def test_zero_coefficient_wrong_dimension_is_not_silently_accepted() -> None:
    data = vector(u=0, d=0.2).model_dump(mode="json")
    data["couplings"][1]["mass_dimension"] = 1
    with pytest.raises(Unsupported, match="dimensionless"):
        classify(ModelSpec.model_validate(data))


def test_direct_scalar_engine_cannot_overwrite_supplied_sm_inputs() -> None:
    data = load("complete_scalar_singlet").scalar_potential.model_dump()
    data["higgs_mass_gev"] = 130
    potential = ScalarPotentialContract.model_validate(data).resolve()
    with pytest.raises(ValidationError, match="fixed SM inputs"):
        CompleteScalarPortal(potential=potential)


@pytest.mark.parametrize("example", ["flavour_vector", "complete_scalar_singlet"])
def test_cli_intake_preserves_contract_and_appropriate_default_axes(
    example: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from typer.testing import CliRunner
    import importlib
    from adroit.orchestrator.cli import app

    runs = importlib.import_module("adroit.orchestrator.runs")
    captured = []

    def fake(request, folder, name, parent, resume=False):
        captured.append(request)
        return tmp_path, "captured"

    monkeypatch.setattr(runs, "track1", fake)
    response = CliRunner().invoke(
        app, ["track1", f"docs/examples/{example}.yaml", "--no-literature", "--out", str(tmp_path)]
    )
    assert response.exit_code == 0, response.output
    assert classify(captured[0].spec)[0].family in ("flavour_vector", "complete_scalar_singlet")
    if example == "complete_scalar_singlet":
        assert captured[0].x is None
    else:
        from adroit.parameter_space.scan_setup import preview
        cls,point,_=classify(captured[0].spec)
        assert captured[0].x is None and preview(cls,point).x['parameter']=="m_med"


@pytest.mark.parametrize("example", ["flavour_vector", "complete_scalar_singlet"])
def test_extra_explicit_sm_interaction_is_refused_instead_of_ignored(example: str) -> None:
    spec = load(example)
    if example == "complete_scalar_singlet":
        spec = resolved_spec(spec)
    data = spec.model_dump(mode="json")
    data["fields"].append(
        dict(name="extra_e", role="standard_model", spin=0.5, charges=dict(electric_charge=-1))
    )
    data["terms"].append(
        dict(
            fields=[dict(field="extra_e", conjugate=True), dict(field="extra_e")] * 2,
            lorentz="vector",
            coupling="1e-6",
        )
    )
    with pytest.raises(Unsupported, match="additional"):
        classify(ModelSpec.model_validate(data))
    data["terms"][-1]["coupling"] = "0"
    cls, _, _ = classify(ModelSpec.model_validate(data))
    assert cls.family in ("flavour_vector", "complete_scalar_singlet")


def test_universal_dijet_handoff_uses_matching_legacy_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adroit.parameter_space import resonances

    cls, p, _ = classify(vector(**{f: 0.25 for f in VECTOR_FLAVOURS[:6]}))
    received = []

    def production(c, point):
        received.append((type(c), point.g_q))
        assert type(c) is Spin1Class
        return None

    monkeypatch.setattr(searches, "_z_prime", production)
    assert resonances.dijet(cls, p, False) is None
    assert received == [(Spin1Class, 0.25)]


def test_nonreference_masses_keep_rates_but_refuse_reference_spectra(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from adroit.parameter_space import scan

    spec = vector(b=0.3)
    data = spec.model_dump(mode="json")
    data["fields"][2]["mass_gev"] = 80
    cls, p, _ = classify(ModelSpec.model_validate(data))
    assert "nonreference" in cls.spectrum_reference_reason(p)
    assert cls.sigma_v_today(p, 1e-3)["b"] == 0
    old, op, _ = classify(spec)
    assert not old.spectrum_reference_reason(op)
    assert scan._icecube(cls, p)[:2] == (None, None)
    # Source lookups must not substitute a standard-mass shower/curve.
    monkeypatch.setattr(searches.s, "_blocked", lambda *args: None)
    monkeypatch.setattr(searches, "_f_eff", lambda *args: pytest.fail("reference f_eff called"))
    changed = p.model_copy(update={"m_chi": 200, "g_chi": 1})
    cmb = searches.cmb(cls, changed, True)
    assert cmb is None or cmb.excluded in (None, False)
    if cmb is not None:
        assert "nonreference" in cmb.why and cmb.ratio is None
    pb = searches.antiprotons(cls, changed, True)
    assert pb is None or (pb.excluded is None and "nonreference" in pb.why)
    candidate = verdicts.Candidate(
        label="changed mass",
        particle=DarkMatterParticle(mass_gev=200),
        interaction=cls.interaction(changed),
        completion=cls.model(changed),
    )
    from adroit.constraints import database

    indirect = verdicts.indirect(candidate, database.record("fermi-1503.02641-dsph"))
    assert indirect.excluded is None and "nonreference" in indirect.needed_calculation


def test_a_flavour_vector_tie_refuses_a_g_chi_scan():
    """Mini audit (M9 residual): a dark current sharing its symbol with the quark currents lost the tie when g_χ
    was scanned, since this class keeps the flavour couplings fixed."""
    from adroit.parameter_space.classify import Unsupported, flavour_tie
    from adroit.parameter_space.scan import Axis
    from adroit.parameter_space.scan_setup import model_relations
    data = vector(u=0.2, d=0.2).model_dump(mode="json")
    dark = data["terms"][0]["coupling"]
    value = next(c["value"] for c in data["couplings"] if c["name"] == dark)
    for term in data["terms"][1:]:
        term["coupling"] = dark
    data["couplings"] = [c for c in data["couplings"] if not c["name"].startswith("C") or c["name"] == dark]
    tied = ModelSpec.model_validate(data)
    assert classify(tied)[0].flavour_couplings["u"] == pytest.approx(-value)
    assert flavour_tie(tied) == {dark}
    with pytest.raises(Unsupported, match="break the tie"):
        model_relations(tied, "", Axis(parameter="g_chi", low=0.01, high=1.0), Axis(parameter="m_chi", low=10, high=100))
    assert model_relations(tied, "", Axis(parameter="m_med", low=100, high=1000),
                           Axis(parameter="m_chi", low=10, high=100)) == []
    assert flavour_tie(vector(u=0.2, d=0.2)) == set()
