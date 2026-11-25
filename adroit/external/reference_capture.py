"""Unit conversion for the pinned Capt'n Oper reference, not production capture."""
from adroit.physics.conventions import AMU_GEV


def physical_capture_rate(raw_rate: float) -> float:
    """Restore the mass-density conversion in upstream opercap factor_final.

    Upstream 59b55a4 uses NAvo*rho/(mnuc*A), with rho in g/cm^3 and
    mnuc*A in GeV. Since a nucleus of mass M_GeV has molar mass
    M_GeV/AMU_GEV g/mol, number density is NAvo*rho*AMU_GEV/M_GeV.
    This factor follows from units, independently of an ADROIT comparison.
    It applies only to this upstream NREO routine; raw values are retained.

    Args:
        raw_rate: Upstream Capt'n Oper output in its published convention.

    Returns:
        Capture rate per second after the explicit mass conversion.
    """
    return raw_rate * AMU_GEV
