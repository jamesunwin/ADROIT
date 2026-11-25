"""Human-readable high-energy scalar partial-wave certificates."""

from __future__ import annotations
from adroit.core.theory import ScalarUnitarityCertificate


from adroit.core.chronology import dated_report


@dated_report
def report(c: ScalarUnitarityCertificate) -> str:
    """Render the saved basis, eigenvalues, conventions and scoped conclusion."""
    lines = [
        "# High-energy scalar partial-wave certificate",
        "",
        f"Status: **{c.status}**; complete={c.complete}; passed={c.passed}.",
        c.scope + ".",
        "",
        f"Tested domain: {c.domain}.",
        f"Criterion: {c.criterion}.",
        f"Normalization: {c.normalization}.",
        f"Parameter SHA256: `{c.parameter_sha256}`.",
        f"Numerical relative resolution: {c.settings.relative_tolerance:g}.",
    ]
    if c.inputs:
        p = c.inputs
        lines += [
            f"Scale={p.scale_gev:.12g} GeV; lambda_H={p.lambda_h:.12g}, "
            f"lambda_S={p.lambda_s:.12g}, lambda_HS={p.lambda_hs:.12g}."
        ]
    lines += [
        f"max|a0|={c.maximum_abs_a0}; boundary margin={c.boundary_margin}; "
        f"eigenpair/orthogonality residuals={c.eigenpair_residual}/{c.orthogonality_residual}.",
        "",
        *["- " + r for r in c.reasons],
        "",
        "| Channel ID | Pair | Identical | State factor |",
        "|---|---|---|---:|",
    ]
    lines += [
        f"| {b.id} | {b.labels[0]}, {b.labels[1]} | {b.identical} | {b.normalization:.12g} |"
        for b in c.channels
    ]
    lines += [
        "",
        f"Missing channels: {c.missing_channel_ids}.",
        "",
        "| Eigenmode | Re(a0) |",
        "|---:|---:|",
    ]
    lines += [f"| {i} | {e:.12g} |" for i, e in enumerate(c.eigenvalues_a0)]
    lines += [
        "",
        "Equations:",
        *["- " + k + ": " + v for k, v in c.equations.items()],
        "",
        "The complete amplitude/partial-wave matrices and eigenvectors are in unitarity.json. "
        "This test is independent of vacuum boundedness and the existing heuristic coupling caps.",
        "",
        "Sources: " + ", ".join(c.references),
        "",
    ]
    return "\n".join(lines)


def study_section(certificates: list[ScalarUnitarityCertificate]) -> list[str]:
    """Expose high-energy unitarity separately from thermal, vacuum and experiment views."""
    if not certificates:
        return []
    counts = {
        status: sum(c.status == status for c in certificates)
        for status in ("passed", "failed", "unresolved", "missing_input", "incomplete_basis")
    }
    lines = [
        "### High-energy scalar partial-wave assessment",
        "",
        "Complete scalar-potential contact limit: four real Higgs components including Goldstones "
        "and the singlet, with all 15 normalized J=0 pair channels.",
        "The |Re(a0)|<1/2 test is separate from heuristic coupling caps and the vacuum certificate. "
        "Finite-energy exchanges, gauge/Yukawa terms, running and full-theory unitarity are not certified.",
        f"Saved point classifications: {counts}.",
        "",
        "| lambda_H | lambda_S | lambda_HS | Scale (GeV) | max(abs(a0)) | Status | Pass |",
        "|---:|---:|---:|---:|---:|---|---|",
    ]
    for c in certificates[:20]:
        if c.inputs:
            p = c.inputs
            maximum = f"{c.maximum_abs_a0:.8g}" if c.maximum_abs_a0 is not None else "unresolved"
            lines += [
                f"| {p.lambda_h:.8g} | {p.lambda_s:.8g} | {p.lambda_hs:.8g} | "
                f"{p.scale_gev:.8g} | {maximum} | {c.status} | {c.passed} |"
            ]
    lines += [
        "",
        "All basis states, matrices, eigenvectors, residuals and scoped identities are "
        "retained in result.json/evidence exports; table shows at most 20.",
        "",
    ]
    return lines
