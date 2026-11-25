"""The halo choice, one component shared by every model definition and selection that launches a calculation (halo
phase 1): Track 1 (a typed or library model, a portal benchmark, an approved idea), Explain a signal and Track 2.

The family is chosen from the registry (``halo_choice.FAMILIES``): the SHM by default; SHM++ (halo phase 2) as a fixed
benchmark only, so choosing it sets the treatment to the benchmark and offers no other (never the SHM's region; back on
the SHM the treatment stays the benchmark until changed); SHM + LMC
listed, disabled, with its status, and never launched (``forms.halo_flags`` refuses it again at launch). The treatment
is one the track offers (``forms.HALO_TRACKS``). Below them, the resolution the run will use (``forms.halo_preview``, the
same resolver the run calls): one line, and its parameters, source and applicability, expandable. What the form shows,
the command it launches, the request it saves and the calculation agree, since each is built from the same choice.
"""
from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from adroit.core import halo_choice
from adroit.ui import forms


class FamilySelect(ui.select):
    """A select whose options for families not yet available are shown, disabled (Quasar's ``disable`` on an option)."""

    def __init__(self, *args, disabled: tuple[str, ...] = (), **kwargs) -> None:
        self._disabled = set(disabled)
        super().__init__(*args, **kwargs)

    def _update_options(self) -> None:
        super()._update_options()
        for option, value in zip(self._props["options"], self._values):
            if value in self._disabled:
                option["disable"] = True


def family_options() -> tuple[dict[str, str], tuple[str, ...]]:
    """(each registered family's id → its label, with the status of one not available; the ids not available)."""
    options = {f.id: f.label if f.available else f"{f.label} (not available: {f.status.split(':')[0]})"
               for f in halo_choice.FAMILIES.values()}
    return options, tuple(f.id for f in halo_choice.FAMILIES.values() if not f.available)


def details(resolution: halo_choice.Resolution | None, why: str, track: str) -> tuple[str, str]:
    """(the one-line summary, the expandable details in Markdown) of a form's choice."""
    if resolution is None:
        return f"Cannot launch: {why}", ""
    r = resolution
    lines = [f"**{r.label}**", ""]
    if r.halo is not None:
        h = r.halo
        lines += [f"- ρ₀ = {h.rho_gev_cm3:g} GeV/cm³, v₀ = {h.v0_km_s:g} km/s, v_esc = {h.v_esc_km_s:g} km/s",
                  f"- v_LSR = {tuple(h.v_lsr_km_s)}, the Sun's peculiar velocity {tuple(h.v_peculiar_km_s)}, the "
                  f"Earth's {tuple(h.v_earth_km_s)} km/s ({r.axes})",
                  f"- time: {r.time}"]
    if r.region:
        lines.append(f"- uncertainty region: ρ₀ log-normal (median {r.region['rho_median_gev_cm3']:g}, σ_ln "
                     f"{r.region['sigma_ln_rho']:g}), v₀ {r.region['v0_km_s']:g} ± {r.region['sigma_v0_km_s']:g}, "
                     f"v_esc {r.region['v_esc_km_s']:g} ± {r.region['sigma_v_esc_km_s']:g} km/s, the joint "
                     f"{100 * r.region['level']:g}% region; {r.region['full_calculations']} full calculations a point")
    if r.parameters:
        p, n = r.parameters, r.numerics
        lines += [f"- ρ₀ = {p['rho_gev_cm3']:g} GeV/cm³, v₀ = {p['v0_km_s']:g} km/s, v_esc = {p['v_esc_km_s']:g} km/s; "
                  f"the Sausage's anisotropy β = {p['beta']:g} and share η = {p['eta']:g}",
                  "- components: " + ", ".join(f"{c.id} ({c.weight:g})" for c in r.components),
                  f"- v_LSR = (0, {p['v0_km_s']:g}, 0), the Sun's peculiar velocity {tuple(p['v_peculiar_km_s'])}, the "
                  f"Earth's {tuple(round(x, 3) for x in p['v_earth_km_s'])} km/s ({r.axes})",
                  f"- time: {r.time}",
                  f"- tables: {n.get('speeds')} speeds, {n.get('polar')} × {n.get('azimuth')} angular nodes, generator "
                  f"version {n.get('generator')}; " + ", ".join(f"{k} {v[:12]}" for k, v in r.tables.items()),
                  f"- {halo_choice.FIXED}"]
    if r.full_calculations is not None:
        lines.append(f"- per point: up to {r.full_calculations} full calculations of a slow search at this halo")
    lines += [f"- source: {s}" for s in r.sources]
    if r.treatment is not halo_choice.Treatment.published:
        missing = [halo_choice.unsupported(r, c) for c in halo_choice.CONSUMERS]
        lines += ["", "**Not calculated with this choice** (pending, named; an independent exclusion still stands):", ""]
        lines += [f"- {m}" for m in missing if m] or ["- none"]
    lines += ["", "**Limitations**", ""] + [f"- {x}" for x in r.limitations]
    if track == "single_idea" and r.treatment is not halo_choice.Treatment.benchmark:
        lines += ["", "The fit and the null comparisons use each search's own published halo; the choice above applies "
                      "to the band's and thermal points' constraints and the Track 1 plane."]
    return r.summary, "\n".join(lines)


def compared_families() -> list[str]:
    """The halo families a comparison runs at: every available one, by its label."""
    return [f.label for f in halo_choice.FAMILIES.values() if f.available]


def halo_section(track: str, *, mark: str = "halo") -> Callable[[], dict[str, str]]:
    """The halo choice for ``track`` (track1, single_idea or track2): the family, the treatment, the resolution's
    summary and details; returns the choice as the command builders take it (``halo``, ``halo_family``)."""
    options, disabled = family_options()
    with ui.column().classes("w-full gap-1").mark(mark):
        with ui.row().classes("items-end gap-4"):
            family = FamilySelect(options, value=halo_choice.DEFAULT_FAMILY, label="halo family",
                                  disabled=disabled).classes("w-72").mark(f"{mark}-family")
            treatment = ui.select(forms.HALO_TRACKS[track], value="", label="halo treatment") \
                .classes("w-96").mark(f"{mark}-treatment")
        summary = ui.label().classes("text-sm text-gray-700").mark(f"{mark}-summary")
        with ui.expansion("Halo: parameters, source and applicability").classes("w-full").mark(f"{mark}-details"):
            body = ui.markdown().mark(f"{mark}-details-text")

    def choice() -> dict[str, str]:
        chosen = family.value or halo_choice.DEFAULT_FAMILY
        return {"halo": treatment.value or "",
                "halo_family": chosen if treatment.value == "benchmark" and chosen != halo_choice.DEFAULT_FAMILY
                else ("" if chosen == halo_choice.DEFAULT_FAMILY else chosen)}

    def refresh(_=None) -> None:
        c = choice()
        resolution, why = forms.halo_preview(track, c["halo"], c["halo_family"])
        summary.text, body.content = details(resolution, why, track)
        if c["halo"] == "compare" and resolution is not None:         # every available family (phase B)
            summary.text = ("Compared: " + ", ".join(compared_families()) + ", each a fixed common benchmark for the "
                            "fit, the null searches and every comparison; the first is the run the study shows. "
                            + summary.text)
        summary.classes(remove="text-red-700" if resolution is not None else "text-gray-700",
                        add="text-gray-700" if resolution is not None else "text-red-700")

    def family_changed(_=None) -> None:
        if (family.value or halo_choice.DEFAULT_FAMILY) != halo_choice.DEFAULT_FAMILY:   # a benchmark only
            treatment.set_options({"benchmark": forms.HALO_TRACKS[track]["benchmark"]}, value="benchmark")
        elif set(treatment.options) != set(forms.HALO_TRACKS[track]):     # the SHM's treatments again; the choice kept
            treatment.set_options(forms.HALO_TRACKS[track], value=treatment.value)
        refresh()

    family.on_value_change(family_changed)
    treatment.on_value_change(refresh)
    refresh()
    return choice
