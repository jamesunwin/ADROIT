"""Direct detection at tree level (G5): a typed model's Feynman rules matched onto DirectDM's quark- and gluon-level
basis, and its nucleon couplings at q → 0.

**What is integrated out.** At zero momentum transfer, the dark matter χ scatters on a quark through:
- **every neutral Z₂-even boson X** (the h, the Z, a Z′ or dark photon, a scalar; mixed mass eigenstates included):
  with χ̄Γχ X and q̄Γ′q X, the exchange gives (χ̄Γχ)(q̄Γ′q) × (+1/m_X² for a scalar, −1/m_X² for a vector);
- **every Z₂-odd coloured scalar partner φ** of fermion dark matter, L ⊃ φ* χ̄(y_L P_L + y_R P_R)q + h.c., in the
  s-channel of χq → χq. With Δ = m_φ² − m_χ² and the Fierz identities of anticommuting fields,
      (χ̄P_R q)(q̄P_L χ) = −½(χ̄γ^μP_Lχ)(q̄γ_μP_Rq),   (χ̄P_R q)(q̄P_R χ) = −½(χ̄P_Rχ)(q̄P_Rq) + tensor,
  so C61 = −(|y_L|² + |y_R|²)/8Δ, C64 = +(|y_L|² + |y_R|²)/8Δ, C62 = −C63 = (|y_R|² − |y_L|²)/8Δ and
  m_q C75 = −Re(y_L y_R*)/4Δ (the tensor part is left out, with a note).

**In vertex terms the coefficients are the same for every dark-matter type.** DirectDM's Majorana and real-scalar
operators carry a factor ½ (``maddm.expected_alpha``), and G2's vertex of a Majorana or real field is twice its
Lagrangian coefficient, so C = (χ vertex)(q vertex)/m_X² × sign throughout. G2's conventions read:
- FFS: Γ = c + ic₂γ⁵, in either slot order;
- FFV: γ(c + c₂γ⁵) with the antiparticle in the first slot (the opposite order flips c);
- SSS: the coefficient of φ*φX (½φ²X for a real φ, whose vertex is the same);
- VSS: c(p_φ − p_φ̄) for L = c X^μ φ* i∂↔_μ φ.

**The basis** is DirectDM's at μ = m_Z with five flavours, with names C61q … C64q (dimension six), C71 … C74 (gluons)
and C75q … C78q (dimension seven, m_q-weighted) for fermions; C61q, C62q, C63q, C64q, C65, C66 for scalars. The
top is integrated out at tree level: m_t t̄t → −(α_s/12π)GG, so C71 −= C75t and C65 −= C63t;
m_t t̄iγ⁵t → (α_s/8π)GG̃, so C73 += C77t (C74 += C78t, C66 += C64t). The top's vector and axial currents are dropped
(a note). A coupling not proportional to m_q is divided by the mass the Higgs's Yukawas carry
(``feynman.yukawa_mass``: m_b and m_c at m_h), so a Higgs-like coupling gives exactly 1/v.

**Nucleon couplings at q → 0** (``nucleon_couplings``), ADROIT's normalisation (σ_SI = c₁²μ²/π, σ_SD = 3c₄²μ²/16π).
A Dirac or complex relic is half particles, half antiparticles, and the vector part of c₁ changes sign between them,
so their rates add: c₁² = S² + V² (``_symmetric``).
- c₁ᴺ = Σ_{u,d,s} C75q σ_qᴺ + (2/27) m_G (Σ_{c,b} C75Q − C71) + (2C61u + C61d for p; C61u + 2C61d for n), with
  DirectDM's sigma terms and m_G (they give f_N = 0.307, the library's F_N); for scalar dark matter the scalar part
  is divided by 2m_χ;
- c₄ᴺ = 4 Σ_q C64q Δqᴺ with the LHC DM Working Group's Δq (as the library's spin-1 portals).

Spin-1 dark matter has no DirectDM basis: its scalar exchange is computed directly, c₁ = −(A/2m_V)Σ_X y_N/m_X² (the
sign of V_μV^μ → −|ε|²; the library's vector Higgs portal).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

QUARKS = ("u", "d", "s", "c", "b", "t")
LIGHT, HEAVY = ("u", "d", "s"), ("c", "b")
SIGMA = {"p": {"u": 0.017, "d": 0.032, "s": 0.0529}, "n": {"u": 0.015, "d": 0.036, "s": 0.0529}}   # DirectDM, GeV
M_G = 0.836                             # DirectDM's gluon matrix element, GeV
DELTA = {"p": {"u": 0.84, "d": -0.43, "s": -0.09}, "n": {"u": -0.43, "d": 0.84, "s": -0.09}}       # arXiv:1603.04156
TOLERANCE = 1e-14


@dataclass(frozen=True)
class Exchange:
    """A neutral Z₂-even boson's couplings: the dark matter's (scalar, pseudoscalar) or (vector, axial) vertex parts,
    or a scalar dark matter's (vertex, 0), and each quark's."""
    mediator: str
    mass: float
    spin: int
    dm: tuple[complex, complex]
    quarks: dict[str, tuple[complex, complex]]


@dataclass(frozen=True)
class Partner:
    """A coloured scalar partner φ of quark q: L ⊃ φ* χ̄(y_L P_L + y_R P_R) q + h.c., with ``s_channel`` True where the
    dark-matter particle itself joins q in φ (χq → φ → χq; G2's naming), False where its antiparticle does."""
    name: str
    mass: float
    quark: str
    y_left: complex
    y_right: complex
    s_channel: bool = False


@dataclass
class Matching:
    """The tree-level matching of one model at one point."""
    dm_type: str                                # DirectDM's D, M, C, R, or V (spin 1, no DirectDM basis)
    dm_mass: float
    exchanges: list[Exchange]
    partners: list[Partner]
    coefficients: dict[str, float]
    notes: list[str] = field(default_factory=list)
    quark_masses: dict[str, float] = field(default_factory=dict)
    carried: dict[str, dict[str, float]] = field(default_factory=dict)   # each scalar exchange's (``_carried``)


# --- reading the rules ----------------------------------------------------------------------------------------

def dm_type(state) -> str:
    """DirectDM's type of the dark-matter state (V for spin 1)."""
    return {"dirac": "D", "majorana": "M", "complex": "C", "real": "R"}.get(state.kind, "V")


def _orientation(v, particle: str) -> float:
    """+1 if the antiparticle stands first in an FFV vertex of ``particle`` with itself, −1 if the particle does."""
    return -1.0 if v.legs[0] == particle else 1.0


def _fermion_pair(v, name: str, anti: str) -> tuple[complex, complex] | None:
    """(c, c₂) of a fermion bilinear in the canonical order, if the vertex joins name and anti."""
    if v.kind not in ("FFS", "FFV") or sorted(v.legs[:2]) != sorted((name, anti)):
        return None
    sign = _orientation(v, name) if (v.kind == "FFV" and name != anti) else 1.0
    return complex(sign * v.c), complex(v.c2)


def _dm_coupling(v, dm: str, anti: str, kind: str, mediator: str) -> tuple[complex, complex] | None:
    """The dark matter's part of a vertex with ``mediator``."""
    if mediator not in v.legs:
        return None
    if kind in ("D", "M"):
        found = _fermion_pair(v, dm, anti)
        return found if found and v.legs[2] == mediator else None
    rest = sorted(x for x in v.legs if x != mediator) if v.legs.count(mediator) == 1 else []
    if rest != sorted((dm, anti)):
        return None
    if v.kind in ("SSS", "VVS"):
        return complex(v.c), 0j
    if v.kind == "VSS" and v.legs[0] == mediator:
        return complex(v.c if v.legs[1] == dm else -v.c), 0j
    return None


def exchanges(rules, dm: str, anti: str, kind: str) -> list[Exchange]:
    """Every neutral Z₂-even boson coupling to both the dark matter and a quark."""
    out = []
    for x in rules.particles:
        if x.parity != 1 or x.spin == 0.5 or x.charge != 0 or x.colour != "1" or x.mass <= 0:
            continue
        dm_part, quarks = None, {}
        for v in rules.vertices:
            if dm_part is None:
                dm_part = _dm_coupling(v, dm, anti, kind, x.name)
            for q in QUARKS:
                found = _fermion_pair(v, q, f"{q}~")
                if found is not None and v.legs[2] == x.name:
                    quarks[q] = found
        if dm_part is not None and any(abs(c) > TOLERANCE for pair in quarks.values() for c in pair):
            out.append(Exchange(x.name, x.mass, int(x.spin), dm_part, quarks))
    return out


def partners(rules, dm: str, anti: str) -> list[Partner]:
    """Every Z₂-odd coloured scalar joining fermion dark matter to a quark (``Partner``), from the vertex with the
    quark in the second slot, where Γ = c_L P_L + c_R P_R acts on the quark."""
    by = {p.name: p for p in rules.particles} | {p.anti: p for p in rules.particles if p.anti}
    out = {}
    for v in rules.vertices:
        if v.kind != "FFS" or v.legs[0] not in (dm, anti) or v.legs[1] not in QUARKS:
            continue
        phi = by.get(v.legs[2])
        if phi is None or phi.parity != -1 or phi.spin != 0 or phi.colour == "1":
            continue
        key = (phi.name, v.legs[1])
        if key not in out:
            out[key] = Partner(phi.name, phi.mass, v.legs[1], complex(v.c - 1j * v.c2), complex(v.c + 1j * v.c2),
                               s_channel=v.legs[0] == dm != anti)
    return list(out.values())


# --- Wilson coefficients -----------------------------------------------------------------------------------------

def _add(c: dict[str, float], name: str, value: complex) -> None:
    if abs(value) > 0:
        c[name] = c.get(name, 0.0) + float(complex(value).real)


def _fermion_exchange(c: dict, x: Exchange, masses: dict[str, float]) -> None:
    for q, (b1, b2) in x.quarks.items():
        if x.spin == 0:                                      # χ̄(s + ipγ⁵)χ × q̄(s′ + ip′γ⁵)q / m²
            s, p = x.dm
            for name, value in (("75", s * b1), ("76", p * b1), ("77", s * b2), ("78", p * b2)):
                _add(c, f"C{name}{q}", value / (x.mass ** 2 * masses[q]))
        else:                                                # −χ̄γ(v + aγ⁵)χ × q̄γ(v′ + a′γ⁵)q / m²
            v, a = x.dm
            for name, value in (("61", v * b1), ("62", a * b1), ("63", v * b2), ("64", a * b2)):
                _add(c, f"C{name}{q}", -value / x.mass ** 2)


CONTACT_DIM7 = {"SS": "75", "PS": "76", "SP": "77", "PP": "78"}   # Γ_χ Γ_q → DirectDM's m_q-weighted operators
CONTACT_DIM6 = {"VV": "61", "AV": "62", "VA": "63", "AA": "64"}
TENSOR_CONTACT = "a tensor contact (χ̄σχ)(q̄σq) is not in the matching: its direct detection is not computed"


def _contacts(c: dict, rules, dm: str, anti: str, kind: str, masses: dict[str, float], notes: list[str]) -> None:
    """A fermion's contact terms with quarks (FFFF, ``feynman.contact_vertices``): k (χ̄Γχ)(q̄Γ'q) is DirectDM's
    operator directly, C = k (×2 for Majorana dark matter, whose DirectDM operators carry ½), the scalar and
    pseudoscalar densities divided by m_q (its m_q-weighted dimension-seven basis). A tensor structure is noted and
    left out (``TENSOR_CONTACT``)."""
    factor = 2.0 if kind == "M" else 1.0
    for v in rules.vertices:
        if v.kind != "FFFF" or (v.legs[0], v.legs[1]) != (anti, dm):
            continue
        q = v.legs[3]
        if q not in QUARKS or v.legs[2] != f"{q}~":
            continue
        for first, second, k in v.structure:
            label = first + second
            if label in CONTACT_DIM7:
                _add(c, f"C{CONTACT_DIM7[label]}{q}", factor * k / masses[q])
            elif label in CONTACT_DIM6:
                _add(c, f"C{CONTACT_DIM6[label]}{q}", factor * k)
            elif TENSOR_CONTACT not in notes:
                notes.append(TENSOR_CONTACT)


def _scalar_exchange(c: dict, x: Exchange, masses: dict[str, float]) -> None:
    g = x.dm[0]
    for q, (b1, b2) in x.quarks.items():
        if x.spin == 0:
            _add(c, f"C63{q}", g * b1 / (x.mass ** 2 * masses[q]))
            _add(c, f"C64{q}", g * b2 / (x.mass ** 2 * masses[q]))
        else:
            _add(c, f"C61{q}", -g * b1 / x.mass ** 2)
            _add(c, f"C62{q}", -g * b2 / x.mass ** 2)


def _partner(c: dict, pt: Partner, m_dm: float, mass_q: float, majorana: bool, notes: list[str]) -> None:
    """A coloured partner's Fierz-rearranged coefficients (module docstring), for the χ of L ⊃ φ*χ̄Γq, which reaches
    φ only in the u-channel. Where the dark-matter particle is the one in the s-channel (``Partner.s_channel``) it is
    that χ's conjugate, and the C-odd bilinear χ̄γχ changes sign (C61, C63); χ̄γγ⁵χ and χ̄χ do not. For Majorana χ the
    vector bilinears vanish and the others are doubled into DirectDM's ½-normalised operators (the Yukawa joins two
    fields, so G2's vertex carries no factor 2 here). Checked against MadDM (``docs/g5_direct_detection.md``)."""
    delta = pt.mass ** 2 - m_dm ** 2
    left, right = abs(pt.y_left) ** 2, abs(pt.y_right) ** 2
    q, k = pt.quark, (2.0 if majorana else 1.0)
    if not majorana:                       # χ̄γχ is C-odd: the s-channel state is the conjugate of the formula's χ
        odd = -1.0 if pt.s_channel else 1.0
        _add(c, f"C61{q}", -odd * (left + right) / (8 * delta))
        _add(c, f"C63{q}", -odd * (right - left) / (8 * delta))
    _add(c, f"C64{q}", k * (left + right) / (8 * delta))
    _add(c, f"C62{q}", k * (right - left) / (8 * delta))
    mixed = pt.y_left * pt.y_right.conjugate()
    if abs(mixed) > 0:
        _add(c, f"C75{q}", -k * mixed.real / (4 * delta * mass_q))
        notes.append(f"{pt.name}: both chiralities couple; the tensor part of its Fierz rearrangement is left out")


def _top(c: dict, kind: str, notes: list[str]) -> None:
    """The top integrated out (module docstring)."""
    if kind in ("D", "M"):
        for top, gluon, sign in (("C75t", "C71", -1), ("C76t", "C72", -1), ("C77t", "C73", 1), ("C78t", "C74", 1)):
            if top in c:
                _add(c, gluon, sign * c.pop(top))
    else:
        for top, gluon, sign in (("C63t", "C65", -1), ("C64t", "C66", 1)):
            if top in c:
                _add(c, gluon, sign * c.pop(top))
    dropped = [k for k in c if k.endswith("t") and k[:-1] in ("C61", "C62", "C63", "C64")]
    if dropped:
        notes.append(f"the top's vector and axial currents are dropped ({', '.join(sorted(dropped))})")
        for k in dropped:
            c.pop(k)


MIXED_CONVENTION = "carries two Yukawa conventions"


def _carried(mb, x: Exchange, masses: dict[str, float], notes: list[str]) -> dict[str, float] | None:
    """The masses a scalar exchange's quark couplings carry (y = m/v), by which DirectDM's m_q-weighted operators are
    divided: the Higgs boson's ("sm") for a state that is the Higgs doublet's, the model's declared convention
    (``yukawa``) for one with no doublet component; None, noted, for a state mixing the two under a convention other
    than "sm" (its couplings carry both; the owner's decision #2: neither silently corrected)."""
    if mb.gauge.spec.yukawa == "sm" or x.spin != 0:
        return masses
    from adroit.model_building import yukawa
    carried = yukawa.carried_masses(mb, x.mediator)
    if carried is None:
        notes.append(f"{x.mediator} mixes the Higgs boson with a new scalar whose stated Yukawas are the "
                     f"{mb.gauge.spec.yukawa} convention's: its quark couplings {MIXED_CONVENTION}, so direct "
                     "detection through it is not computed")
    return carried


def match(mb, rules) -> Matching:
    """The tree-level matching at one point (module docstring)."""
    dm = mb.spectrum.dark_matter()
    kind = dm_type(dm)
    anti = dm.name if dm.kind in ("real", "majorana", "vector") else f"{dm.name}~"
    from adroit.model_building.feynman import yukawa_mass
    masses = {q: yukawa_mass(q) for q in QUARKS}           # the masses the Higgs boson's Yukawas carry (y = m/v)
    found = exchanges(rules, dm.name, anti, kind)
    pts = partners(rules, dm.name, anti) if kind in ("D", "M") else []
    c: dict[str, float] = {}
    notes: list[str] = []
    carried_by: dict[str, dict[str, float]] = {}
    for x in found:
        carried = _carried(mb, x, masses, notes)
        if carried is None:
            continue
        carried_by[x.mediator] = carried
        if kind in ("D", "M"):
            _fermion_exchange(c, x, carried)
        elif kind in ("C", "R"):
            _scalar_exchange(c, x, carried)
    for pt in pts:
        _partner(c, pt, dm.mass_gev, masses[pt.quark], kind == "M", notes)
    if kind in ("D", "M"):
        _contacts(c, rules, dm.name, anti, kind, masses, notes)
    if kind != "V":
        _top(c, kind, notes)
    if kind == "R":
        for k in [k for k in c if k[:3] in ("C61", "C62")]:   # a real scalar has no vector current
            c.pop(k)
    return Matching(kind, dm.mass_gev, found, pts, {k: v for k, v in c.items() if v != 0.0}, notes, masses,
                    carried_by)


# --- nucleon couplings at q → 0 ------------------------------------------------------------------------------------

def _scalar_density(c: dict, nucleon: str, prefix: str, gluon: str) -> float:
    """Σ C σ_q + (2/27) m_G (Σ heavy C − C_gluon): the coupling to ⟨N|Σ m_q q̄q|N⟩."""
    light = sum(c.get(f"{prefix}{q}", 0.0) * SIGMA[nucleon][q] for q in LIGHT)
    heavy = sum(c.get(f"{prefix}{q}", 0.0) for q in HEAVY) - c.get(gluon, 0.0)
    return light + 2.0 / 27.0 * M_G * heavy


def nucleon_couplings(m: Matching) -> dict[str, float]:
    """c₁ᵖ, c₁ⁿ, c₄ᵖ, c₄ⁿ at q → 0 (module docstring)."""
    c = m.coefficients
    out = {}
    for n in ("p", "n"):
        vector = (2 if n == "p" else 1) * c.get("C61u", 0.0) + (1 if n == "p" else 2) * c.get("C61d", 0.0)
        # the C-even (scalar) part, and the C-odd (vector) part that flips sign between particle and antiparticle:
        # their rates add, nucleus by nucleus (the audit's G5-1, G12: they had been combined nucleon by nucleon)
        if m.dm_type in ("D", "M"):
            out[f"c1_{n}"] = _scalar_density(c, n, "C75", "C71")
            out[f"c4_{n}"] = 4.0 * sum(c.get(f"C64{q}", 0.0) * DELTA[n][q] for q in LIGHT)
        elif m.dm_type in ("C", "R"):
            out[f"c1_{n}"] = _scalar_density(c, n, "C63", "C65") / (2.0 * m.dm_mass)
            out[f"c4_{n}"] = 0.0
        else:
            out[f"c1_{n}"] = _vector_dm(m, n)
            out[f"c4_{n}"] = 0.0
        out[f"c1_{n}_odd"] = vector if m.dm_type in ("D", "M", "C", "R") else 0.0
    return out


def _vector_dm(m: Matching, nucleon: str) -> float:
    """Spin-1 dark matter's scalar exchange, computed directly (module docstring)."""
    total = 0.0
    for x in m.exchanges:
        if x.spin != 0 or (m.carried and x.mediator not in m.carried):        # a mixed convention: noted
            continue
        carried = m.carried.get(x.mediator, m.quark_masses)
        ratio = {q: (b1 / carried[q]).real for q, (b1, _) in x.quarks.items()}
        y = sum(ratio.get(q, 0.0) * SIGMA[nucleon][q] for q in LIGHT) + \
            2.0 / 27.0 * M_G * sum(ratio.get(q, 0.0) for q in (*HEAVY, "t"))
        total += -x.dm[0].real / (2.0 * m.dm_mass) * y / x.mass ** 2
    return total


MOMENTUM_SUPPRESSED = {"D": ("C62", "C63", "C72", "C73", "C74", "C76", "C77", "C78"),
                       "M": ("C62", "C72", "C73", "C74", "C76", "C77", "C78"),
                       "C": ("C62", "C64", "C66"), "R": ("C64", "C66")}


def momentum_suppressed(m: Matching) -> list[str]:
    """The coefficients present whose operators vanish at q → 0 (or with the relative velocity)."""
    prefixes = MOMENTUM_SUPPRESSED.get(m.dm_type, ())
    return sorted(k for k, v in m.coefficients.items() if v and k.startswith(prefixes))


def contact_notes(m: Matching) -> list[str]:
    """Where the contact limit fails: a mediator or partner below 1 GeV (the recoil's q is up to a few hundred MeV)."""
    masses = [x.mass for x in m.exchanges] + [p.mass - m.dm_mass for p in m.partners]
    light = min(masses) if masses else None
    if light is not None and light < 1.0:
        return [f"a mediator {light:.3g} GeV from the contact limit: the matching does not hold at the recoil's "
                "momentum transfer"]
    return []


def is_finite(m: Matching) -> bool:
    """Whether every coefficient is finite."""
    return all(math.isfinite(v) for v in m.coefficients.values())
