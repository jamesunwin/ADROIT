"""Render the declared running domain and independent-integration diagnostics."""

from adroit.core.running import ScalarRGCertificate
from adroit.core.chronology import dated_report


def study_section(certificates: list[ScalarRGCertificate]) -> list[str]:
    """Keep UV running separate from the thermal/experimental and vacuum conclusions."""
    if not certificates:
        return []
    lines = [
        "### Declared-scale scalar RG assessment",
        "",
        "One-loop running quartic criteria; no quantum-vacuum or precision matching claim.",
        "| Start (GeV) | Requested upper (GeV) | Matching | Status | First crossing (GeV) | Integration difference |",
        "|---:|---:|---|---|---:|---:|",
    ]
    for c in certificates[:20]:
        r = c.request
        lines.append(
            f"| {c.inputs.scale_gev if c.inputs else None} | {r.upper_scale_gev if r else None} | {r.scalar_matching if r else 'missing'} | {c.status} | {c.first_crossing.scale_gev if c.first_crossing else None} | {c.integration_error} |"
        )
    return [
        *lines,
        "",
        "Full trajectories, conventions, SM inputs, threshold policy and reasons are saved in the results and evidence export.",
        "",
    ]




@dated_report
def report(c: ScalarRGCertificate) -> str:
    """Show saved data without recomputation."""
    return "\n".join(
        [
            "# Declared-scale RG certificate",
            "",
            c.scope,
            "",
            c.convention,
            "",
            *study_section([c]),
            *["- " + reason for reason in c.reasons],
            "",
            "Sources: " + ", ".join(c.references),
            "",
        ]
    )
