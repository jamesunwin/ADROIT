"""The plots of a Track 1 report (DM13): the parameter plane, and direct detection along the relic contour."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from adroit.parameter_space import limits
from adroit.parameter_space.scan import ScanResult
from adroit.parameter_space.verdict import Verdict

COLOURS = {"direct detection": "tab:blue", "gamma rays (Fermi-LAT dwarfs)": "tab:green",
           "capture in the Sun (IceCube)": "tab:orange", "colliders (CMS)": "0.55", "perturbativity": "tab:purple",
           "invisible Higgs width (ATLAS)": "tab:brown", "invisible Z width (LEP)": "tab:pink"}
STATUS = {"viable": "tab:green", "pending": "gold", "excluded": "tab:red"}
LABELS = {"m_chi": "dark matter mass m_χ (GeV)", "m_med": "mediator mass (GeV)", "g_chi": "g_χ", "g_q": "g_q",
          "g_l": "g_ℓ"}


def _label(result: ScanResult, slot: str) -> str:
    cls = result.request.model_class
    return subscripts(cls.label(slot) if hasattr(cls, "label") and cls.label(slot) != slot else LABELS.get(slot, slot))


def subscripts(text: str) -> str:
    """An axis label with its subscripts typeset (m_S → m with subscript S, λ_hs → λ with subscript hs), where the
    underscore had been printed (the workbench review, 2026-10-15)."""
    import re
    return re.sub(r"([A-Za-zλχμφψηξ])_([A-Za-z0-9ℓχμ]+)", lambda m: f"${m.group(1)}_{{\\mathrm{{{m.group(2)}}}}}$", text)


JOINT_MARKS = {   # a crossing's joint reading on Explain a signal's plane (``assessment.joint``): marker, colour, words
    "explains": ("*", "tab:green", "a joint thermal explanation of the signal"),
    "explains_one_halo": ("*", "tab:green", "a joint thermal explanation of the signal"),
    "explains_published_halo": ("*", "gold", "meets the signal and survives, at different halo assignments"),
    "excluded": ("o", "tab:red", "excluded at the reference halo"),
    "does_not_explain": ("o", "white", "does not explain the signal"),
}


def plane(result: ScanResult, verdict: Verdict, path: Path, title: str = "",
          band: list[tuple[float, float, float, float]] | None = None, signal: list[str] | None = None,
          assessments=None, joint: list[str] | None = None, signal_label: str = "",
          band_pieces: list[tuple[float, float, float]] | None = None) -> Path:
    """Each constraint's excluded region, the Ωh² = target contour, and the contour's points by status.

    ``band``: an anomaly's 68% best-fit region as (m_χ, x low, best, high),
    where x is the scanned physical parameter m_med or g_chi: fixed-mass physical-fit intervals, not a joint confidence
    region across mass and coupling.

    The shading is each constraint's exclusion at the reference halo (the region's centre over a halo region), and so
    are the markers: a contour point excluded there whose exclusion is not established throughout the region is drawn
    excluded with a distinct outline, never as plain pending (the owner's plan of 2026-11-24, section 3), read from
    the stored assessment (``assessment.from_crossing``; ``assessments`` where the study stored them).

    Explain a signal's plane (the plan's section 2) adds, from its stored assessment: ``signal``, each scan point's
    signal state (hatched where its physical prediction meets the signal criterion; a cross where it was not assessed),
    and ``joint``, each crossing's row of the decision table, which its marker shows.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    xs, ys = np.array(result.xs), np.array(result.ys)
    shape = (len(ys), len(xs))
    fig, ax = plt.subplots(figsize=(7.5, 6))
    handles = []
    for name, colour in COLOURS.items():
        grid = np.array([np.nan if p.excluded.get(name) is None else float(p.excluded[name])
                         for p in result.points]).reshape(shape)
        if np.nansum(grid) > 0:
            ax.contourf(xs, ys, grid, levels=[0.5, 1.5], colors=[colour], alpha=0.3)
            handles.append(plt.Rectangle((0, 0), 1, 1, color=colour, alpha=0.3, label=f"excluded: {name}"))
    omega = np.array([p.omega_h2 or np.nan for p in result.points]).reshape(shape)
    if np.isfinite(omega).any() and np.nanmin(omega) < verdict.target < np.nanmax(omega):
        ax.contour(xs, ys, omega, levels=[verdict.target], colors="black", linewidths=1.8)
        handles.append(plt.Line2D([], [], color="black", lw=1.8, label=f"Ωh² = {verdict.target:.3g} (grid interpolation only)"))
    x_of = lambda p: getattr(p, result.request.x.parameter)      # noqa: E731
    y_of = lambda p: getattr(p, result.request.y.parameter)      # noqa: E731
    if signal is not None and len(signal) == len(result.points):
        meets = np.array([1.0 if s == "meets" else 0.0 for s in signal]).reshape(shape)
        if meets.any():
            ax.contourf(xs, ys, meets, levels=[0.5, 1.5], colors="none", hatches=["///"], zorder=3)
            ax.contour(xs, ys, meets, levels=[0.5], colors="magenta", linestyles="--", linewidths=1.2, zorder=3)
            handles.append(plt.Rectangle((0, 0), 1, 1, facecolor="none", edgecolor="magenta", hatch="///",
                                         label=signal_label or "meets the signal criterion"))
        unassessed = [r.point for r, s in zip(result.points, signal) if s == "unassessed"]
        if unassessed:
            ax.scatter([x_of(p) for p in unassessed], [y_of(p) for p in unassessed], marker="x", s=10, color="0.45",
                       linewidths=0.6, zorder=3)
            handles.append(plt.Line2D([], [], marker="x", ls="", color="0.45", label="signal not assessed here"))
    contour = [(i, c) for i, c in enumerate(verdict.crossings) if c.kind == "contour" and c.converged]
    if joint is not None and len(joint) == len(verdict.crossings):
        shown = set()
        for i, c in contour:
            marker, colour, words = JOINT_MARKS.get(joint[i], ("o", "gold", "unresolved"))
            ax.scatter([x_of(c.point)], [y_of(c.point)], s=70 if marker == "*" else 24, marker=marker, color=colour,
                       edgecolor="black", linewidths=0.5, zorder=6)
            if words not in shown:
                shown.add(words)
                handles.append(plt.Line2D([], [], marker=marker, ls="", color=colour, markeredgecolor="black",
                                          label=f"relic contour: {words}"))
    else:
        from adroit.parameter_space.assessment import from_crossing
        read = assessments if assessments is not None and len(assessments) == len(verdict.crossings) else \
            [from_crossing(c) for c in verdict.crossings]
        central = {i for i, c in contour if c.status != "excluded" and read[i].experimental.state == "excluded"}
        for status, colour in STATUS.items():
            pts = [c.point for i, c in contour if c.status == status and i not in central]
            if pts:
                ax.scatter([x_of(p) for p in pts], [y_of(p) for p in pts], s=22, color=colour,
                           edgecolor="black", linewidths=0.4, zorder=5)
                handles.append(plt.Line2D([], [], marker="o", ls="", color=colour, markeredgecolor="black",
                                          label=f"relic contour: {status}"))
        if central:
            pts = [c.point for i, c in contour if i in central]
            ax.scatter([x_of(p) for p in pts], [y_of(p) for p in pts], s=30, color=STATUS["excluded"],
                       edgecolor="gold", linewidths=1.6, zorder=5)
            handles.append(plt.Line2D([], [], marker="o", ls="", color=STATUS["excluded"], markeredgecolor="gold",
                                      markeredgewidth=1.6, label="relic contour: excluded at the central SHM, "
                                      "not established throughout the halo region"))
    if band and result.request.y.parameter == "m_chi" and result.request.x.parameter in ("m_med", "g_chi"):
        rows = sorted(band)
        ys_b = [r[0] for r in rows]
        lo = [min(r[1], xs.max() * 10) for r in rows]
        hi = [min(r[3], xs.max() * 10) for r in rows]
        ax.fill_betweenx(ys_b, lo, hi, color="magenta", alpha=0.25, zorder=4)
        ax.plot([r[2] for r in rows], ys_b, color="magenta", lw=1.6, zorder=4)
        handles.append(plt.Rectangle((0, 0), 1, 1, color="magenta", alpha=0.4,
                                     label="the physical fit's 68% interval at each fixed mass (not a joint region)"))
        ax.set_xlim(xs.min(), xs.max())
    if band_pieces and result.request.y.parameter == "m_chi" and result.request.x.parameter in ("m_med", "g_chi"):
        for m, lo, hi in band_pieces:                 # a disconnected 68% region: each piece, never a span over a gap
            ax.plot([lo, hi], [m, m], color="magenta", lw=2.4, solid_capstyle="butt", zorder=4)
        handles.append(plt.Line2D([], [], color="magenta", lw=2.4,
                                  label="the physical fit's disconnected 68% intervals at a fixed mass"))
    flagged = [c.point for c in verdict.crossings if c.flags]
    if flagged:
        ax.scatter([getattr(p, result.request.x.parameter) for p in flagged],
                   [getattr(p, result.request.y.parameter) for p in flagged], s=90, facecolors="none",
                   edgecolors="black", linewidths=1.2, marker="D", zorder=6)
        handles.append(plt.Line2D([], [], marker="D", ls="", markerfacecolor="none", markeredgecolor="black",
                                  label="unreliable (see the contour table)"))
    for axis, values, setter in ((result.request.x, result.xs, ax.set_xscale),
                                 (result.request.y, result.ys, ax.set_yscale)):
        name, options = _scale(axis.log, values)
        setter(name, **options)
    ax.set(xlabel=_label(result, result.request.x.parameter), ylabel=_label(result, result.request.y.parameter),
           title=title or result.request.model_class.name)
    ax.legend(handles=handles, fontsize=7, loc="best")
    fig.tight_layout()
    from adroit.evidence.bindings import write_figure    # its digest kept for the report's binding
    write_figure(fig, path, 120)
    plt.close(fig)
    return path


def _scale(log: bool, values) -> tuple[str, dict]:
    """(scale, its options): "log" for a log axis of positive values; for one of negative values (a negative portal
    coupling: G12's live check L3) "symlog", logarithmic in |value| down to the smallest; else "linear"."""
    if not log:
        return "linear", {}
    if min(values) > 0:
        return "log", {}
    return "symlog", {"linthresh": min(abs(v) for v in values if v) or 1.0}


def direct_detection_saved(verdict: Verdict, path: Path) -> Path | None:
    """Direct detection along the relic contour from saved evaluations only (the stacked audit's S18-11): each
    converged contour point's saved σ and the 95% limit saved with it; nothing is evaluated and no current limit
    table is read. A point saved without its evaluation is left out; with none, there is no figure."""
    saved = sorted(((c, c.evaluation) for c in verdict.crossings if c.kind == "contour" and c.converged
                    and c.evaluation is not None and c.evaluation.dd_kind in ("SI", "SD-proton", "SD-neutron")),
                   key=lambda pair: pair[0].point.m_chi)
    if not saved:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    kind = saved[0][1].dd_kind
    fig, ax = plt.subplots(figsize=(7, 5))
    bounds = [(c.point.m_chi, e.dd_limit_cm2) for c, e in saved if e.dd_limit_cm2 is not None]
    if bounds:
        ax.plot([m for m, _ in bounds], [v for _, v in bounds], color="tab:blue", marker=".",
                label="95% limit saved with each point")
    ax.scatter([c.point.m_chi for c, _ in saved], [e.dd_sigma_cm2 for _, e in saved],
               c=[STATUS.get(c.status, "grey") for c, _ in saved], edgecolor="black", linewidths=0.4, s=24,
               label="the model on its relic contour (saved)", zorder=5)
    ax.set(xscale="log", yscale="log", xlabel="dark matter mass m_χ (GeV)",
           ylabel=f"σ_{kind} per nucleon (cm²)", title="Direct detection along the thermal-relic contour (saved)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    from adroit.evidence.bindings import write_figure    # its digest kept for the report's binding
    write_figure(fig, path, 120)
    plt.close(fig)
    return path


def direct_detection(result: ScanResult, verdict: Verdict, path: Path) -> Path | None:
    """The model's cross-section along the relic contour, against the validated envelope of the modules."""
    kind = next((p.dd_kind for p in result.points if p.dd_kind in ("SI", "SD-proton", "SD-neutron")), None)
    crossings = [c for c in verdict.crossings if c.kind == "contour" and c.converged]
    if kind is None or not crossings:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    cls = result.request.model_class
    pts = sorted((c.point for c in crossings), key=lambda p: p.m_chi)
    sig = [cls.dd(p)[1] for p in pts]
    grid, best, _ = limits.table(kind)
    fig, ax = plt.subplots(figsize=(7, 5))
    finite = np.isfinite(best)
    ax.plot(np.array(grid)[finite], np.array(best)[finite], color="tab:blue",
            linestyle="--", label=f"native 90% validated envelope ({kind})")
    masses = sorted(set(p.m_chi for p in pts) | set(p.point.m_chi for p in result.points))
    pairs = [(m, limits.at95(kind, m).value) for m in masses]
    pairs = [(m, v) for m, v in pairs if v is not None]
    if pairs:
        ax.plot([m for m, _ in pairs], [v for _, v in pairs], color="tab:blue", marker=".",
                label="95% module calculation (at evaluated masses)")
    colours = [STATUS[c.status] for c in sorted(crossings, key=lambda c: c.point.m_chi)]
    ax.scatter([p.m_chi for p in pts], sig, c=colours, edgecolor="black", linewidths=0.4, s=24,
               label="the model on its relic contour", zorder=5)
    ax.set(xscale="log", yscale="log", xlabel="dark matter mass m_χ (GeV)",
           ylabel=f"σ_{kind} per nucleon (cm²)", title="Direct detection along the thermal-relic contour")
    ax.legend(fontsize=8)
    fig.tight_layout()
    from adroit.evidence.bindings import write_figure    # its digest kept for the report's binding
    write_figure(fig, path, 120)
    plt.close(fig)
    return path
