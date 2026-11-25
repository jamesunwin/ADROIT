"""Human-readable scoped certificates, with the same saved inputs as exports."""

from __future__ import annotations

from adroit.core.theory import ScalarVacuumCertificate


from adroit.core.chronology import dated_report


def _decay_lines(c: ScalarVacuumCertificate) -> list[str]:
    """The metastable vacuum's bounce and lifetime, when computed."""
    d = c.decay
    if d is None:
        return []
    return ["", f"Tunnelling to {d.true_vacuum} at (h, s) = ({d.true_field_gev[0]:.6g}, {d.true_field_gev[1]:.6g}) "
            f"GeV: **{d.status}** (decided by {d.decided_by or 'nothing'}).",
            f"S_E = {d.bounce_action}, bounds [{d.action_lower_bound}, {d.action_upper_bound}]; R = {d.radius_gev_inv} "
            f"GeV⁻¹; ln P = {d.log_probability} (margin ±{d.margin:g}). {d.method}."]


@dated_report
def report(c: ScalarVacuumCertificate) -> str:
    """Render a certificate without performing a theory or physics calculation."""
    lines = [
        "# Tree-level scalar vacuum certificate",
        "",
        f"Vacuum: **{c.vacuum}**; boundedness: **{c.boundedness}**; quartic: {c.quartic}.",
        f"Complete={c.complete}; passed={c.passed}. {c.scope}.",
        "",
        f"Tested domain: {c.domain}.",
        f"Parameter identity: `{c.parameter_sha256}`.",
    ]
    if c.inputs:
        p = c.inputs
        lines += [
            f"Scale={p.scale_gev:.12g} GeV; declared v={p.v_gev:.12g} GeV, S=0.",
            f"mu_H²={p.mu_h2_gev2:.12g} GeV², mu_S²={p.mu_s2_gev2:.12g} GeV²; "
            f"lambda_H={p.lambda_h:.12g}, lambda_S={p.lambda_s:.12g}, lambda_HS={p.lambda_hs:.12g}.",
        ]
    lines += [
        f"Relative resolution: {c.settings.relative_tolerance:g}.",
        f"Declared stationarity residual: {c.declared_stationarity_residual}.",
        f"Local classification: {c.local_classification}; global minimum V={c.global_minimum_gev4} GeV⁴.",
        "",
        *["- " + text for text in c.reasons],
        *_decay_lines(c),
        "",
        "| Stationary orbit | H†H (GeV²) | S²/2 (GeV²) | V (GeV⁴) | Local type | Residual |",
        "|---|---:|---:|---:|---|---:|",
    ]
    lines += [
        f"| {e.name} | {e.x_gev2:.12g} | {e.y_gev2:.12g} | {e.potential_gev4:.12g} | "
        f"{e.local_classification} | {e.stationarity_residual:.3g} |"
        for e in c.extrema
    ]
    for family in c.families:
        lines += [
            "",
            f"Stationary family {family.name} (dimension {family.dimension}): "
            + "; ".join(family.equations)
            + f"; V={family.potential_gev4:.12g} GeV⁴.",
            f"Anchor={family.anchor_exact}, directions={family.directions_exact}; "
            f"parameter interval [{family.parameter_low_exact}, {family.parameter_high_exact}] "
            "(None is unbounded); " + family.domain + ".",
        ]
    if c.runaway:
        r = c.runaway
        lines += [
            "",
            f"Runaway ray d={r.direction_exact}: quartic={r.quartic_exact}, "
            f"quadratic={r.quadratic_exact}; negative leading {r.leading}. {r.explanation}.",
        ]
    lines += [
        "",
        "Equations:",
        *["- " + name + ": " + eq for name, eq in c.equations.items()],
        "",
        "Sources: " + ", ".join(c.references),
        "",
    ]
    return "\n".join(lines)


def study_section(certificates: list[ScalarVacuumCertificate]) -> list[str]:
    """Show theory conclusions beside, independently of, a thermal/experimental headline."""
    if not certificates:
        return []
    counts = {
        name: sum(c.vacuum == name for c in certificates)
        for name in ("global", "degenerate", "metastable", "short_lived", "local", "unstable", "unresolved")
    }
    lines = [
        "### Tree-level scalar vacuum assessment",
        "",
        "The thermal/experimental view above is reported separately from this scalar-potential assessment.",
        "A failed global-vacuum certificate (unbounded, unstable, or decaying within the age of the universe) "
        "invalidates the declared DM vacuum at tree level; a metastable vacuum that outlives the universe passes. "
        "A pass covers the scalar potential at its stated scale; finite-temperature history, unitarity and RG "
        "remain separate.",
        f"Saved point classifications: {counts}.",
        "",
        "| m_S² (GeV²) | lambda_HS | lambda_S | Scale (GeV) | Vacuum | Boundedness | Pass |",
        "|---:|---:|---:|---:|---|---|---|",
    ]
    for c in certificates[:20]:
        p = c.inputs
        if p:
            mass2 = p.mu_s2_gev2 + p.lambda_hs * p.v_gev * p.v_gev / 2
            lines += [
                f"| {mass2:.8g} | {p.lambda_hs:.8g} | {p.lambda_s:.8g} | {p.scale_gev:.8g} | "
                f"{c.vacuum} | {c.boundedness} | {c.passed} |"
            ]
    lines += [
        "",
        "All point equations, extrema, flat families, residuals and parameter identities are retained "
        "in result.json and the evidence export; table shows at most 20.",
        "",
    ]
    return lines
