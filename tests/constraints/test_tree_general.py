"""G3: the general tree-level engine against MadGraph, the hand-written processes, gauge invariance and Fermi
statistics (docs/g3_tree.md)."""

import gzip
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest

from adroit.constraints import amplitudes, processes, tree, tree_colour, ufo_model
from adroit.constraints.processes import frame

DATA = Path(__file__).parent / "data"
REFERENCES = json.loads((DATA / "g3_madgraph.json").read_text())


@lru_cache(maxsize=None)
def ufo(name: str) -> tree.Model:
    """A UFO model as MadGraph evaluated it (``docs/g3/madgraph_references.py``), with full colour."""
    return ufo_model.to_model(json.loads(gzip.decompress((DATA / f"g3_ufo_{name}.json.gz").read_bytes())),
                              full_colour=True)[0]


@pytest.mark.parametrize("key", sorted(REFERENCES))
def test_every_process_matches_madgraph_at_fixed_phase_space_points(key):
    """|M|² (summed over final, averaged over initial spins and colours) equals MadGraph's standalone matrix
    element, which includes 1/2 for identical final particles."""
    case = REFERENCES[key]
    model = ufo(case["model"])
    names = case["names"]
    assert [abs(model.particles[n].mass) for n in names] == pytest.approx(case["masses"], rel=1e-9, abs=1e-12)
    process = tree.Process(model, *names)
    identical = 2.0 if names[2] == names[3] else 1.0
    ours = [process.squared(p["sqrt_s"] ** 2, np.array([p["cos_theta"]]))[0] / identical for p in case["points"]]
    assert ours == pytest.approx([p["me"] for p in case["points"]], rel=1e-9)


def test_the_reference_set_covers_every_spin_and_flow_class():
    kinds = set()
    for case in REFERENCES.values():
        model = ufo(case["model"])
        spins = tuple(sorted(model.particles[n].spin for n in case["names"][:2])), \
            tuple(sorted(model.particles[n].spin for n in case["names"][2:]))
        majorana = any(model.particles[n].spin == 0.5 and not model.particles[n].anti for n in case["names"])
        kinds.add((spins, majorana))
    for wanted in [((0.5, 0.5), (0.0, 0.0)), ((0.5, 0.5), (1.0, 1.0)), ((0.5, 0.5), (0.0, 1.0)),
                   ((0.5, 0.5), (0.5, 0.5)), ((0.0, 0.5), (0.5, 1.0)), ((0.0, 0.5), (0.0, 0.5)),
                   ((0.0, 0.0), (0.5, 0.5)), ((0.0, 0.0), (1.0, 1.0)), ((1.0, 1.0), (0.0, 0.0)),
                   ((0.0, 1.0), (0.0, 1.0)), ((1.0, 1.0), (1.0, 1.0)), ((1.0, 1.0), (0.5, 0.5))]:
        assert any(spins == wanted for spins, _ in kinds), wanted
    assert any(m for _, m in kinds)


@pytest.mark.parametrize("names", [("n1", "n1", "b", "b~"), ("n1", "x1+", "u", "d~"), ("su1", "su1", "u", "u"),
                                   ("go", "go", "u", "u~"), ("x1+", "x1-", "Z", "h01")])
def test_the_square_does_not_depend_on_the_arbitrary_fermion_flow(names, monkeypatch):
    model = ufo("MSSM_SLHA2")
    s, x = (2.5 * sum(abs(model.particles[n].mass) for n in names[:2])) ** 2, np.array([-0.4, 0.3])
    first = tree.Process(model, *names).squared(s, x)
    monkeypatch.setattr(tree, "FLOW_FROM_HIGHER", True)
    assert tree.Process(model, *names).squared(s, x) == pytest.approx(first, rel=1e-12)


# --- the hand-written processes of ``processes`` and ``amplitudes`` ------------------------------------------

def t_channel(majorana: bool, colour: str = "1", y: float = 0.7) -> tree.Model:
    """χ (Dirac or Majorana), a scalar partner φ and a fermion f: y φ* χ̄ P_R f + h.c."""
    m = tree.Model({})
    m.add(tree.Particle("chi", 0.5, 450.0, anti="" if majorana else "chi~"),
          tree.Particle("phi", 0, 600.0, anti="phi~", colour=colour), tree.Particle("f", 0.5, 4.7, anti="f~", colour=colour))
    m.vertices += [tree.Vertex("FFS", ("chi" if majorana else "chi~", "f", "phi~"), y / 2, -1j * y / 2),
                   tree.Vertex("FFS", ("f~", "chi", "phi"), y / 2, 1j * y / 2)]
    return m


@pytest.mark.parametrize("majorana", [False, True])
def test_t_channel_annihilation_with_fermi_statistics(majorana):
    s = 1500.0 ** 2
    initial = ("chi", "chi") if majorana else ("chi", "chi~")
    assert tree.Process(t_channel(majorana), *initial, "f", "f~").sigma(s) == pytest.approx(
        processes.t_channel_to_fermions(s, 450.0, 4.7, 600.0, 0.7, majorana), rel=1e-12)


@pytest.mark.parametrize("colour", ["1", "3"])
def test_partner_pairs_into_same_fermions_through_a_majorana_mass_insertion(colour):
    """φφ → ff: Majorana χ in the t- and u-channels with clashing fermion flows (sextet and antitriplet)."""
    s = 1500.0 ** 2
    assert tree.Process(t_channel(True, colour), "phi", "phi", "f", "f").sigma(s) == pytest.approx(
        processes.partners_to_same_fermions(s, 600.0, 4.7, 450.0, 0.7, colour == "3"), rel=1e-12)


def qcd(g: float = 1.1) -> tree.Model:
    """A coloured scalar φ and quark q with the gluon (V_ggg = −ig f), and a Majorana χ: y φ* χ̄ P_R q + h.c."""
    m = t_channel(True, "3")
    m.add(tree.Particle("G", 1, 0.0, colour="8"))
    m.vertices += [tree.Vertex("VSS", ("G", "phi", "phi~"), -g), tree.Vertex("VVSS", ("G", "G", "phi", "phi~"), g * g),
                   tree.Vertex("VVV", ("G", "G", "G"), -1j * g), tree.Vertex("FFV", ("f~", "f", "G"), -g, 0.0)]
    return m


def test_coloured_partner_pairs_and_coannihilation_match_the_hand_built_amplitudes():
    s, g = 1500.0 ** 2, 1.1
    m = qcd(g)
    assert tree.Process(m, "phi", "phi~", "G", "G").sigma(s) == pytest.approx(
        processes.partners_to_gauge_bosons(s, 600.0, g, True), rel=1e-12)
    assert tree.Process(m, "phi", "phi~", "f", "f~").sigma(s) == pytest.approx(
        processes.partners_to_fermions(s, 600.0, 4.7, g, 1.0, True, y=0.7, m_chi=450.0), rel=1e-12)
    assert tree.Process(m, "chi", "phi", "f", "G").sigma(s) == pytest.approx(
        processes.dm_partner_to_fermion_boson(s, 450.0, 600.0, 4.7, 0.7, g, 1.0, True), rel=1e-12)


def test_massive_vector_processes_match_the_hand_built_amplitudes():
    s, g = 1500.0 ** 2, 1.1
    m = tree.Model({})
    m.add(tree.Particle("phi", 0, 600.0, anti="phi~"), tree.Particle("V", 1, 300.0), tree.Particle("chi", 0.5, 500.0, anti="chi~"),
          tree.Particle("Zp", 1, 300.0, 3.0), tree.Particle("Z", 1, 91.19, 2.5), tree.Particle("h", 0, 125.0))
    m.vertices += [tree.Vertex("VSS", ("V", "phi", "phi~"), -g), tree.Vertex("VVSS", ("V", "V", "phi", "phi~"), 2 * g * g),
                   tree.Vertex("FFV", ("chi~", "chi", "Zp"), -0.8, -0.3), tree.Vertex("FFV", ("chi~", "chi", "Z"), -0.4, -0.25),
                   tree.Vertex("VVS", ("Z", "Z", "h"), 30.0)]
    assert tree.Process(m, "phi", "phi~", "V", "V").sigma(s) == pytest.approx(
        processes.scalars_to_massive_vectors(s, 600.0, 300.0, g), rel=1e-12)
    assert tree.Process(m, "chi", "chi~", "Zp", "Zp").sigma(s) == pytest.approx(
        amplitudes.pair_sigma(s, 500.0, 300.0, (0.8, 0.3), points=20), rel=1e-12)
    assert tree.Process(m, "chi", "chi~", "Z", "h").sigma(s) == pytest.approx(
        processes.fermion_to_vector_scalar(s, 500.0, (0.4, 0.25), 91.19, 125.0, 30.0, 91.19, 2.5, points=20), rel=1e-12)


# --- gauge invariance ---------------------------------------------------------------------------------------

def _ward(process: tree.Process, leg: int, s: float) -> float:
    """|Σ diagrams| / max |diagram| with one external gauge boson's polarisation replaced by its momentum."""
    x = np.array([0.3, -0.5])
    p1, p2, k1, k2, _, _ = frame(s, *(process.mass(i) for i in range(4)), x)
    ext, configs = process._externals([p1, p2, k1, k2])
    ext["eps"][leg] = np.tile([p1, p2, k1, k2][leg], (configs, 1)).astype(complex)
    ext["slash"][leg] = amplitudes.slash(ext["eps"][leg])
    amps = [process._amplitude(d, ext) for d in process.diagrams()]
    return float(np.abs(sum(amps)).max() / max(np.abs(a).max() for a in amps))


def test_ward_identities_of_abelian_and_coloured_processes():
    scalar_qed = tree.Model({})
    scalar_qed.add(tree.Particle("phi", 0, 300.0, anti="phi~"), tree.Particle("A", 1, 0.0))
    scalar_qed.vertices += [tree.Vertex("VSS", ("A", "phi", "phi~"), -0.3),
                            tree.Vertex("VVSS", ("A", "A", "phi", "phi~"), 2 * 0.09)]
    assert _ward(tree.Process(scalar_qed, "A", "phi", "A", "phi"), 0, 900.0 ** 2) < 1e-13      # Compton
    assert _ward(tree.Process(scalar_qed, "phi", "phi~", "A", "A"), 2, 900.0 ** 2) < 1e-13
    m = qcd()
    assert _ward(tree.Process(m, "chi", "phi", "f", "G"), 3, 1500.0 ** 2) < 1e-12           # χφ → q g


def gauge_consistent_sm() -> tree.Model:
    """The SM UFO with zero widths and an exactly gauge-consistent third generation: W t b̄ with the eνW coupling
    (V_tb = 1, the other CKM entries dropped) and h t t̄ = m_t/v, v from the WWh coupling (2M_W²/v).

    The UFO's own inputs do not cancel exactly at high energy, in MadGraph as here (docs/g3_tree.md): its top
    Yukawa is a separate input (an MS-bar value, not √2 m_t/v) and its CKM entries are rounded to 7 digits; and a
    fixed width in an s-channel propagator breaks the cancellation too (the reason for the complex-mass scheme).
    """
    from dataclasses import replace
    full = ufo("sm")
    w = full.particles["W+"].mass
    v = 2 * w * w / abs(next(x.c for x in full.vertices if x.kind == "VVS" and set(x.legs) == {"W+", "W-", "H"}))
    lepton = {x.legs: x for x in full.vertices if x.kind == "FFV" and set(x.legs) in ({"e+", "ve", "W-"},
                                                                                     {"ve~", "e-", "W+"})}
    out = []
    for x in full.vertices:
        if x.kind == "FFV" and {"t", "t~"} & set(x.legs) and {"W+", "W-"} & set(x.legs):
            if not {"b", "b~"} & set(x.legs):
                continue                                                    # V_td = V_ts = 0
            reference = next(iter(lepton.values()))
            x = replace(x, c=reference.c, c2=reference.c2)                  # V_tb = 1
        if x.legs == ("t~", "t", "H"):
            x = replace(x, c=x.c * full.particles["t"].mass / (abs(x.c) * v))
        out.append(x)
    return tree.Model({n: replace(p, width=0.0) for n, p in full.particles.items()}, out)


def test_unitary_gauge_cancellations_keep_vector_pair_production_bounded():
    """e⁺e⁻ → W⁺W⁻ and, for a massive Dirac doublet member, tt̄ → W⁺W⁻ (s-channel γ, Z, h with t-channel fermion
    exchange): σ·s stays bounded, where each diagram alone grows like s². Engine and MadGraph agree to 10⁻⁷ at
    100 TeV even where the UFO's inputs spoil the cancellation (docs/g3_tree.md)."""
    sm = gauge_consistent_sm()
    for names in (("e+", "e-", "W+", "W-"), ("t", "t~", "W+", "W-")):
        p = tree.Process(sm, *names)
        low, high = (p.sigma(r * r) * r * r for r in (2e3, 2e5))
        assert high / low < 5.0, names


# --- the colour algebra and the UFO reader ---------------------------------------------------------------------

def test_su3_tensors_and_default_colour_structures():
    t = tree_colour.generators()
    f, d = tree_colour.structure_constants()
    commutator = np.einsum("aij,bjk->abik", t, t) - np.einsum("bij,ajk->abik", t, t)
    assert commutator == pytest.approx(1j * np.einsum("abc,cik->abik", f, t), abs=1e-14)
    assert np.einsum("aij,aji->", t, t) == pytest.approx(4.0)                       # Tr T^aT^a = 8/2
    assert f[0, 1, 2] == pytest.approx(1.0) and d[0, 0, 7] == pytest.approx(1 / np.sqrt(3))
    assert tree_colour.default_structure(["8", "3", "3bar"]) == "T(1,2,3)"
    assert tree_colour.default_structure(["3bar", "3", "1"]) == "Identity(1,2)"
    assert tree_colour.default_structure(["8", "8", "8"]) == "f(1,2,3)"
    with pytest.raises(ValueError):
        tree_colour.default_structure(["3", "3", "3"])
    seagull = tree_colour.vertex_tensor("", ["8", "8", "3", "3bar"])
    assert seagull == pytest.approx(np.einsum("aik,bkj->abij", t, t) + np.einsum("bik,akj->abij", t, t))


def test_the_colour_interference_of_singlet_and_octet_exchange_vanishes():
    m = qcd()
    m.add(tree.Particle("A", 1, 0.0))
    m.vertices += [tree.Vertex("VSS", ("A", "phi", "phi~"), -0.3), tree.Vertex("FFV", ("f~", "f", "A"), -0.3, 0.0)]
    p = tree.Process(m, "phi", "phi~", "f", "f~")
    kinds = [d.x.name if d.x else "" for d in p.diagrams()]
    photon, gluon = kinds.index("A"), kinds.index("G")
    assert abs(p._colour[photon, gluon]) < 1e-14 and p._colour[photon, photon] == pytest.approx(9.0)


def test_ufo_four_vector_structures_and_colour_remapping():
    assert ufo_model._metric_pairs("Metric(1,4)*Metric(2,3) - Metric(1,3)*Metric(2,4)") == (0.0, -1.0, 1.0)
    assert ufo_model._metric_pairs("Metric(1,4)*Metric(2,3) - (Metric(1,3)*Metric(2,4))/2. - "
                                   "(Metric(1,2)*Metric(3,4))/2.") == (-0.5, -0.5, 1.0)
    assert ufo_model._metric_pairs("Metric(1,2)*P(3,1)") is None
    assert ufo_model._remap_colour("T(1,-1,3)*T(2,4,-1)", [2, 0, 1, 3]) == "T(2,-1,1)*T(3,4,-1)"


def test_the_ufo_reading_and_the_negative_majorana_mass():
    """A UFO vertex names the particles its fields create: [n1, u, su1~] with P_R is ū P_R χ ũ_L, the engine's
    (u~, n1, su1). SLHA's negative n3 mass is rotated into the couplings (χ → iγ⁵χ)."""
    m = ufo("MSSM_SLHA2")
    assert m.particles["su1"].pdg == 1000002                                         # ũ_L
    vertex = next(v for v in m.vertices if v.legs == ("u~", "n1", "su1"))
    left, right = vertex.c - 1j * vertex.c2, vertex.c + 1j * vertex.c2               # (c − ic₂)P_L + (c + ic₂)P_R
    assert abs(left) < 1e-12 < abs(right)                                            # ũ_L couples to u_L only
    assert m.particles["n3"].mass > 0


def test_a_process_with_an_odd_number_of_fermions_is_refused():
    with pytest.raises(ValueError, match="odd"):
        tree.Process(ufo("MSSM_SLHA2"), "n1", "n2", "x1+", "W-")


def test_two_body_widths_of_bosons_and_fermions_match_madgraph():
    """MadGraph's ``compute_widths`` at the same card: the top, χ̃₁⁺, χ̃⁰₂, W and Z to its 7 printed digits; ũ_L
    once the partial widths MadGraph set to zero (below its QCD scale) are added back. (The gluino differs by
    α_s(M_Z)/α_s(m_g̃) in every channel: MadGraph runs α_s to the parent's mass.)"""
    reference = json.loads((DATA / "g3_madgraph_widths.json").read_text())
    madgraph = {int(k): v for k, v in reference["widths"].items()}
    model = ufo("MSSM_SLHA2")
    ours = ufo_model.widths(model, ["t", "x1+", "n2", "W+", "Z", "su1"])
    for name, code in (("t", 6), ("x1+", 1000024), ("n2", 1000023), ("W+", 24), ("Z", 23)):
        assert ours[name] == pytest.approx(madgraph[code], rel=2e-6), name
    dropped = sum(width for _, width in reference["dropped"]["su1"])
    assert ours["su1"] == pytest.approx(madgraph[1000002] + dropped, rel=2e-6)


def test_a_very_light_vector_coupled_to_a_conserved_current_keeps_its_rate():
    """The audit's G7-2 (G12): χχ̄ → V′V′ at m = 1 TeV lost the longitudinal cancellation in double precision below
    m_V ~ 0.1 GeV (negative σ at 10 MeV). With k^μ/m taken out of ε_L (Ward identity) it is m_V-independent."""
    import math

    from adroit.core.model_spec import ModelSpec
    from adroit.parameter_space.portals.generic import GenericModel
    g = math.sqrt(4 * math.pi * 0.03)

    def sigma(mv: float, root: float) -> float:
        spec = ModelSpec.model_validate({"name": "dqed", "phase": "broken", "fields": [
            {"name": "chi", "role": "dark_matter", "spin": 0.5, "dark_parity": -1, "mass_gev": 1000.0},
            {"name": "Ad", "role": "mediator", "spin": 1, "self_conjugate": True, "mass_gev": mv}],
            "terms": [{"fields": [{"field": "chi", "conjugate": True}, {"field": "chi"}, {"field": "Ad"}],
                       "lorentz": "vector", "coupling": f"{g}"}]})
        engine = GenericModel.for_spec(spec)
        mb, _, model = engine.at(engine.point())
        dm = mb.spectrum.dark_matter().name
        assert tree.conserved_current(model, "Ad")
        return tree.Process(model, dm, dm + "~", "Ad", "Ad").sigma(root ** 2)
    for root in (2100.0, 10000.0):
        reference = sigma(1.0, root)
        assert all(sigma(mv, root) == pytest.approx(reference, rel=1e-6) for mv in (1e-2, 1e-4))


# --- the faster generic route (F2) ----------------------------------------------------------------------------------

def test_slash_is_the_contraction_with_the_gamma_matrices():
    """F2: a̸ as a matrix product gives the same numbers as the contraction γ^μ a_μ it replaced."""
    rng = np.random.default_rng(7)
    for a in (rng.normal(size=(50, 4)), rng.normal(size=(50, 4)) + 1j * rng.normal(size=(50, 4))):
        reference = np.einsum("nm,mij->nij", a * amplitudes.METRIC, amplitudes.GAMMA)
        assert np.array_equal(amplitudes.slash(a), reference)


@pytest.mark.parametrize("key", sorted(REFERENCES))
def test_the_stacked_cross_section_is_sigma_at_each_pair_of_final_masses(key):
    """F2: ``sigma_offshell`` evaluates ``sigma(s, (m₃, m₄))`` for many pairs at once (to 10⁻¹²), in chunks smaller
    than the pairs, a pair above √s giving 0 and a massless leg kept massless."""
    case = REFERENCES[key]
    model = ufo(case["model"])
    names = case["names"]
    process = tree.Process(model, *names)
    m = [abs(model.particles[n].mass) for n in names]
    root = max(m[0] + m[1], m[2] + m[3]) * 1.3 + 1.0
    pairs = np.array([[m[2], m[3]], [0.5 * m[2] + 0.1, m[3]], [m[2], 0.7 * m[3] + 0.2], [root, m[3] + 1.0],
                      [0.0, m[3]], [m[2] + 0.3, 0.0]])
    expected = [process.sigma(root ** 2, tuple(p)) for p in pairs]
    assert process.sigma_offshell(root ** 2, pairs, rows=64).tolist() == pytest.approx(expected, rel=1e-12, abs=0)
