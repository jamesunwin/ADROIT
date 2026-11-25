"""Independent analytic LO cross-checks of the MG5 tables (pure numpy/scipy).

Narrow-resonance LO formulas (tau = M^2/s, s = (13 TeV)^2):

* spin-1, L = Y1_mu qbar gamma^mu (gV + gA gamma5) q :
      sigma_hat(q qbar -> Y1) = (pi/3) (gV^2 + gA^2) delta(s_hat - M^2)
      sigma(pp -> Y1) = (pi / (3 s)) sum_q (gVq^2 + gAq^2) L_qqbar(tau),
      L_qqbar(tau) = int_tau^1 dx/x [ q(x) qbar(tau/x) + qbar(x) q(tau/x) ]   (f = PDFs at mu_F)

* spin-0 with Yukawa-like couplings  L = -sum_q g_q (m_q/v) S qbar (1 or i gamma5) q :
      sigma(pp -> S) = sigma_0 * tau * dL_gg/dtau ,  dL_gg/dtau = int_tau^1 dx/x g(x) g(tau/x)
      CP-even:  sigma_0 = G_F alpha_s^2 / (288 sqrt2 pi) | (3/4) sum_q g_q A_H(tau_q) |^2
      CP-odd :  sigma_0 = G_F alpha_s^2 / (288 sqrt2 pi) | (3/4) sum_q g_q A_A(tau_q) |^2
      tau_q = M^2 / (4 m_q^2),
      A_H(t) = 2 [t + (t - 1) f(t)] / t^2   (-> 4/3 for t -> 0),
      A_A(t) = 2 f(t) / t                   (-> 2   for t -> 0),
      f(t) = arcsin^2 sqrt(t)                             (t <= 1)
           = -1/4 [ ln((1 + sqrt(1-1/t)) / (1 - sqrt(1-1/t))) - i pi ]^2   (t > 1)
  (Djouadi, Phys. Rept. 457 (2008) 1 and 459 (2008) 1).  Heavy-top limit: sigma_A/sigma_H = 9/4.

PDFs are read directly from LHAPDF6 'lhagrid1' files (bicubic spline in ln x, ln Q^2),
alpha_s runs at two loops with nf = 5 from alpha_s(MZ) (as MG5 does for built-in PDFs).
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from scipy.integrate import quad, solve_ivp
from scipy.interpolate import RectBivariateSpline

LHAPDF_DIR = Path.home() / "agentic-dm-tools/lhapdf"
GEV2_TO_PB = 0.3893794e9
GF = 1.16637e-5
MZ = 91.1876
SQRTS = 13000.0


class GridPDF:
    """Minimal LHAPDF6 grid reader (central member) returning x f(x, Q)."""

    def __init__(self, name: str, member: int = 0):
        path = LHAPDF_DIR / name / f"{name}_{member:04d}.dat"
        text = path.read_text().split("---")
        self.blocks = []
        for blk in text[1:]:
            lines = [ln for ln in blk.strip().splitlines() if ln.strip()]
            if len(lines) < 4:
                continue
            xs = np.array(lines[0].split(), float)
            qs = np.array(lines[1].split(), float)
            flav = [int(v) for v in lines[2].split()]
            vals = np.array([ln.split() for ln in lines[3:]], float).reshape(len(xs), len(qs), len(flav))
            splines = {}
            for i, pid in enumerate(flav):
                splines[pid] = RectBivariateSpline(np.log(xs), np.log(qs ** 2), vals[:, :, i], kx=3, ky=3)
            self.blocks.append((qs[0], qs[-1], splines))

    def xfx(self, pid: int, x: float, q: float) -> float:
        """x f(x, Q) for parton ``pid`` (21 = gluon)."""
        for qlo, qhi, spl in self.blocks:
            if qlo <= q <= qhi or (q > qhi and spl is self.blocks[-1][2]):
                if pid not in spl:
                    return 0.0
                return float(spl[pid](math.log(x), math.log(q * q))[0, 0])
        return float(self.blocks[0][2].get(pid, lambda *a: [[0.0]])(math.log(x), math.log(q * q))[0][0])


@lru_cache(maxsize=4)
def get_pdf(name: str) -> GridPDF:
    """Cached PDF loader."""
    return GridPDF(name)


def alpha_s(q: float, asmz: float = 0.130, nf: int = 5) -> float:
    """Two-loop running alpha_s with fixed nf (exact numerical solution of the RGE)."""
    b0 = (33 - 2 * nf) / (12 * math.pi)
    b1 = (153 - 19 * nf) / (24 * math.pi ** 2)
    sol = solve_ivp(lambda t, a: [-2 * (b0 * a[0] ** 2 + b1 * a[0] ** 3)],
                    [math.log(MZ), math.log(q)], [asmz], rtol=1e-10, atol=1e-12)
    return float(sol.y[0, -1])


def lumi(pdf: GridPDF, pa: int, pb: int, tau: float, muf: float) -> float:
    """int_tau^1 dx/x f_a(x) f_b(tau/x)  (PDFs, not x*PDFs) at scale muf."""
    def integrand(lnx: float) -> float:
        x = math.exp(lnx)
        x2 = tau / x
        return pdf.xfx(pa, x, muf) * pdf.xfx(pb, x2, muf) / tau  # f f = (xf)(x2 f)/(x x2)
    val, _ = quad(integrand, math.log(tau), 0.0, limit=200, epsabs=0, epsrel=1e-6)
    return val


def sigma_zprime(mass: float, couplings: dict[int, float], pdf_name: str = "NNPDF23_lo_as_0130_qed",
                 scale_factor: float = 1.0) -> float:
    """LO sigma(pp -> Y1) in pb; couplings = {quark pid: gV^2 + gA^2}."""
    pdf = get_pdf(pdf_name)
    s = SQRTS ** 2
    tau = mass ** 2 / s
    tot = 0.0
    for q, g2 in couplings.items():
        tot += g2 * (lumi(pdf, q, -q, tau, mass * scale_factor) + lumi(pdf, -q, q, tau, mass * scale_factor))
    return math.pi / (3 * s) * tot * GEV2_TO_PB


def _f(t: complex) -> complex:
    """Loop function f(tau) of Djouadi's review."""
    if t <= 1:
        return complex(math.asin(math.sqrt(t)) ** 2, 0.0)
    r = math.sqrt(1 - 1 / t)
    z = complex(math.log((1 + r) / (1 - r)), -math.pi)
    return -0.25 * z * z


def amp_h(t: float) -> complex:
    """CP-even fermion form factor A_H(tau), normalised to 4/3 for tau -> 0."""
    if t < 1e-6:
        return 4.0 / 3.0 + 0j
    return 2 * (t + (t - 1) * _f(t)) / t ** 2


def amp_a(t: float) -> complex:
    """CP-odd fermion form factor A_A(tau), normalised to 2 for tau -> 0."""
    if t < 1e-6:
        return 2.0 + 0j
    return 2 * _f(t) / t


def ggs_amp2(mass: float, quarks: dict[float, float], cp: str = "even") -> float:
    """|(3/4) sum_q g_q A(tau_q)|^2 for quarks = {m_q: g_q}."""
    amp = amp_h if cp == "even" else amp_a
    tot = sum(g * amp(mass ** 2 / (4 * mq ** 2)) for mq, g in quarks.items())
    return abs(0.75 * tot) ** 2


def sigma_ggs(mass: float, quarks: dict[float, float], cp: str = "even",
              pdf_name: str = "NNPDF23_lo_as_0130_qed", asmz: float = 0.130,
              scale_factor: float = 1.0) -> float:
    """LO sigma(gg -> S) in pb for Yukawa-like couplings g_q (multiples of m_q/v)."""
    pdf = get_pdf(pdf_name)
    mu = mass * scale_factor
    a_s = alpha_s(mu, asmz)
    sigma0 = GF * a_s ** 2 / (288 * math.sqrt(2) * math.pi) * ggs_amp2(mass, quarks, cp)
    tau = mass ** 2 / SQRTS ** 2
    return sigma0 * tau * lumi(pdf, 21, 21, tau, mu) * GEV2_TO_PB


def heft_factor(mass: float, mt: float) -> float:
    """Squared finite-mt factor built into MG5's 'heft' GH coupling (truncated expansion)."""
    r = mass ** 2 / mt ** 2
    return (1 + 7 * r / 120 + r ** 2 / 168 + 13 * r ** 3 / 16800) ** 2


if __name__ == "__main__":
    for m in (50, 125, 1000, 3000):
        print(m, "Z' d-only:", f"{sigma_zprime(m, {1: 1.0}):.5g}",
              " ggS t+b even:", f"{sigma_ggs(m, {172.0: 1, 4.7: 1}):.5g}",
              " odd:", f"{sigma_ggs(m, {172.0: 1, 4.7: 1}, 'odd'):.5g}")
