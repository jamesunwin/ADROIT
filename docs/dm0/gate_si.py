"""DM0 gate: spin-independent xenon spectrum, WIMpy_NREFT vs an independent calculation.

The independent calculation shares NOTHING with WIMpy except the nuclear
response function (taken from WIMpy's tabulated shell-model polynomials), so it
tests the kinematics, the halo integral, the normalisation and the units.
"""
import numpy as np
import scipy.integrate as si
from scipy.special import erf
if not hasattr(si, "trapz"):
    si.trapz = si.trapezoid
if not hasattr(si, "cumtrapz"):
    si.cumtrapz = si.cumulative_trapezoid
if not hasattr(np, "trapz"):
    np.trapz = np.trapezoid
from WIMpy import DMUtils as DMU

# ---- independent implementation ------------------------------------------------
GEV_PER_AMU = 0.93149410242
C_KMS = 299792.458
HBARC_GEV_CM = 1.973269804e-14
M_NUCLEON = 0.9389187          # mean of proton and neutron, GeV
RHO = 0.3                      # GeV / cm^3
SEC_PER_DAY = 86400.0
KEV = 1e-6                     # GeV


def eta_shm(vmin, v0, vlag, vesc):
    """Mean inverse speed (s/km) of a truncated Maxwellian boosted by vlag (km/s)."""
    x, y, z = vmin / v0, vlag / v0, vesc / v0
    n = erf(z) - 2 * z * np.exp(-z * z) / np.sqrt(np.pi)
    out = np.zeros_like(x)
    a = (x <= z - y)
    b = (x > z - y) & (x < z + y)
    out[a] = (erf(x[a] + y) - erf(x[a] - y) - 4 * y * np.exp(-z * z) / np.sqrt(np.pi)) / (2 * n * y * v0)
    out[b] = (erf(z) - erf(x[b] - y) - 2 * (y + z - x[b]) * np.exp(-z * z) / np.sqrt(np.pi)) / (2 * n * y * v0)
    return out


def rate_si(E_keV, A, m_x, sigma_p_cm2, F2, v0=220.0, vlag=232.0, vesc=544.0, m_nucleon=M_NUCLEON):
    """dR/dE_R in events / kg / day / keV for isoscalar spin-independent scattering.

    dR/dE = rho sigma_p A^2 F^2(E) / (2 m_x mu_p^2) * eta(vmin)
    """
    m_T = A * GEV_PER_AMU
    mu_T = m_x * m_T / (m_x + m_T)
    mu_p = m_x * m_nucleon / (m_x + m_nucleon)
    vmin = np.sqrt(m_T * E_keV * KEV / (2 * mu_T ** 2)) * C_KMS            # km/s
    eta = eta_shm(vmin, v0, vlag, vesc)                                     # s/km
    # natural units -> per (GeV of target) per second per GeV of recoil energy
    pref = RHO * sigma_p_cm2 * A ** 2 / (2 * m_x * mu_p ** 2)               # cm^-1 GeV^-2 ... x eta
    rate = pref * F2 * eta * (C_KMS * 1e5) ** 2 / 1e5                      # c^2 [cm^2/s^2] * eta [s/cm]
    # rate is now in 1/(GeV_target * s * GeV_recoil) ; convert
    gev_per_kg = 1.0 / 1.78266192e-27
    return rate * gev_per_kg * SEC_PER_DAY * KEV


def main():
    E = np.linspace(1.0, 100.0, 100)
    sigma = 1e-46
    worst = 0.0
    for m_x in (20.0, 100.0, 1000.0):
        for A in (129, 131, 132, 134, 136):
            ref = DMU.dRdE_standard(E, 54, A - 54, m_x, sigma, vlag=232.0, sigmav=220.0 / np.sqrt(2), vesc=544.0)
            F2 = DMU.calcSIFormFactor(E, A)
            mine = rate_si(E, A, m_x, sigma, F2, m_nucleon=0.9315)   # WIMpy's nucleon-mass convention
            phys = rate_si(E, A, m_x, sigma, F2)                      # physical mean nucleon mass
            ok = ref > 1e-6 * ref.max()
            dev = np.max(np.abs(mine[ok] / ref[ok] - 1))
            conv = np.max(np.abs(phys[ok] / mine[ok] - 1))
            worst = max(worst, dev)
            print(f"m_x={m_x:6.0f} GeV  A={A}  max deviation {dev:.4%}  (nucleon-mass convention effect {conv:.2%})"
                  f"  rate(10 keV)={ref[9]:.4e} /kg/day/keV")
    print("WORST", f"{worst:.4%}", "PASS" if worst < 0.01 else "FAIL")


if __name__ == "__main__":
    main()
