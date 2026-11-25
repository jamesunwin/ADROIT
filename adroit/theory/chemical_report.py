"""Expose conditional conversion diagnostics and missing physical prerequisites."""

from adroit.core.chemical_equilibrium import ChemicalEquilibriumCertificate
from adroit.core.chronology import dated_report


def study_section(certificates: list[ChemicalEquilibriumCertificate]) -> list[str]:
    """Report the effective-relic assumption independently from experimental exclusions."""
    if not certificates:
        return []
    lines = [
        "### Coannihilation chemical-equilibrium prerequisite",
        "",
        "Effective coannihilation relic values assume common chemical potentials.",
        "A source-regulated component certificate is explicitly scoped to its requested accuracy. Inclusive/plasma and kinetic claims remain separate; missing required component rates stay pending.",
        "| m_chi (GeV) | m_phi (GeV) | y | Inclusive/plasma prerequisite | Component assessment | Born diagnostic | Minimum conservative rate/H |",
        "|---:|---:|---:|---|---|---|---:|",
    ]
    for c in certificates[:20]:
        p = c.inputs.point
        lines.append(
            f"| {p.m_chi:g} | {p.m_med:g} | {p.g_chi:g} | {c.physical_prerequisite} | {c.component_prerequisite or c.status} | {c.born_diagnostic_passed} | {c.minimum_relaxation_over_h} |"
        )
    return [
        *lines,
        "",
        "Kinetic equilibrium and the assumed initial thermal/cosmological history are not certified. Full rates, uncertainty, regulator variations and missing channels are saved in result.json/evidence.",
        "",
    ]




@dated_report
def report(c: ChemicalEquilibriumCertificate) -> str:
    """Render saved rates and scope without making any calculations."""
    return "\n".join(
        [
            "# Chemical-equilibrium prerequisite",
            "",
            c.scope,
            "",
            *study_section([c]),
            *["- " + s for s in c.reasons],
            "",
            "Missing channels: " + ", ".join(c.missing_channels),
            "",
            "Sources: " + ", ".join(c.references),
            "",
        ]
    )
