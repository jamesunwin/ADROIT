"""The neutrino fog at the command line: the standard floor (O'Hare's published curve) or ADROIT's own map with
advanced settings, each with a plot and a short report. Local and $0; an overlay, never a constraint."""
from __future__ import annotations

import math
from pathlib import Path

import typer

app = typer.Typer(pretty_exceptions_show_locals=False, help="The neutrino fog for spin-independent scattering: where coherent neutrino scattering hides "
                       "a direct-detection discovery (O'Hare, arXiv:2109.03116). An overlay, never a constraint. $0.")


def _grid(text: str) -> tuple[float, float, int]:
    """'LOW:HIGH:POINTS' as a logarithmic grid specification."""
    try:
        low, high, points = text.split(':')
        spec = (float(low), float(high), int(points))
    except ValueError:
        raise typer.BadParameter(f'expected LOW:HIGH:POINTS, got {text!r}') from None
    if not 0 < spec[0] < spec[1] or spec[2] < 2:
        raise typer.BadParameter(f'a grid needs 0 < LOW < HIGH and at least two points: {text!r}')
    return spec


def _pairs(items: list[str]) -> dict[str, float]:
    """['8B=0.05', …] as {name: value}."""
    out = {}
    for item in items:
        name, _, value = item.partition('=')
        try:
            out[name.strip()] = float(value)
        except ValueError:
            raise typer.BadParameter(f'expected NAME=VALUE, got {item!r}') from None
    return out


@app.command('standard')
def standard(target: str = typer.Option('Xe', '--target', help='Xe, Ar, Ge, NaI, CaWO4, He or F'),
             out: Path = typer.Option(Path('runs/neutrino_fog'), '--out', help='folder for floor.csv and floor.png')) -> None:
    """The standard floor: O'Hare's published n = 2 curve for a target (for xenon, the curve LZ and XENONnT draw)."""
    from adroit.physics import neutrino_fog as nf
    try:
        masses, sigmas = nf.published_floor(target)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    _export(out, {'floor.csv': 'mass_gev,sigma_cm2\n' + ''.join(f'{m:.6g},{s:.6g}\n' for m, s in zip(masses, sigmas)),
                  'floor.png': figure({f"{target}: O'Hare 2021 (n = 2), published": (masses, sigmas)})})
    typer.echo(f"{out / 'floor.csv'}\n{out / 'floor.png'}")


@app.command('map')
def compute(target: str = typer.Option('Xe131', '--target', help="an isotope (Xe131, O'Hare's choice) or a natural "
                                       'target (Xe, Ar, Ge, NaI, CaWO4, …)'),
            masses: str = typer.Option('0.1:10000:60', '--masses', help='LOW:HIGH:POINTS in GeV (logarithmic)'),
            sigmas: str = typer.Option('1e-50:1e-43:500', '--sigmas', help='LOW:HIGH:POINTS in cm² (logarithmic; '
                                       'fewer than 500 points biases the floor by up to ~20%)'),
            threshold: float = typer.Option(1e-4, '--threshold-kev', help='lowest recoil energy (keV); the floor '
                                            'does not depend on it above the masses it cuts off'),
            uncertainty: list[str] = typer.Option([], '--uncertainty', help="a flux's fractional uncertainty, e.g. "
                                                   'Atm=0.1 or 8B=0.05; repeatable'),
            scale: list[str] = typer.Option([], '--scale', help='a group of uncertainties scaled together: solar, '
                                            "atmospheric, dsnb, geo or reactor, e.g. solar=0.1 (O'Hare's improved case)"),
            exclude: list[str] = typer.Option([], '--exclude', help='a flux left out (pp, pep, hep, 7Be1, 7Be2, 8B, '
                                              '13N, 15O, 17F, DSNB, Atm, GeoU, GeoTh, GeoK, Reactor); repeatable'),
            halo: str = typer.Option('ohare', '--halo', help="the halo: ohare (his floors' SHM) or standard "
                                     "(ADROIT's default, arXiv:2105.00599)"),
            binning: str = typer.Option('window', '--binning', help="window: only the recoils inside the window "
                                        "count; ohare: each spectrum normalised to its whole range, as his code "
                                        "does (the reproduction of his published floors)"),
            exposure: float = typer.Option(0.0, '--exposure', help='also the classic 3σ discovery limit at this '
                                           'exposure (tonne-years) and threshold'),
            out: Path = typer.Option(Path('runs/neutrino_fog'), '--out', help='folder for fog.json, floor.csv, '
                                     'fog.png and report.md')) -> None:
    """ADROIT's own fog (advanced settings): the discovery exposure at every mass and σ, the index n and the floor,
    compared with the published floor. Local; about a second per mass at 500 σ points."""
    from adroit.core.dm_state import HaloModel
    from adroit.physics import neutrino_fog as nf
    if halo not in ('ohare', 'standard'):
        raise typer.BadParameter('the halo is ohare or standard')
    if binning not in ('window', 'ohare'):
        raise typer.BadParameter('the binning is window or ohare')
    try:
        settings = nf.FogSettings(target=target, threshold_kev=threshold, masses_gev=_grid(masses),
                                  sigmas_cm2=_grid(sigmas), uncertainties=_pairs(uncertainty),
                                  group_scale=_pairs(scale), exclude=exclude, binning=binning,
                                  halo=nf.ohare_halo() if halo == 'ohare' else HaloModel())
        result = nf.fog(settings)
        classic = nf.discovery_limit(settings, exposure) if exposure > 0 else None
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None
    write(result, out, classic, exposure)
    typer.echo('\n'.join(str(out / name) for name in ('fog.json', 'floor.csv', 'fog.png', 'report.md')))


def write(result, out: Path, classic=None, exposure: float = 0.0) -> None:
    """fog.json, floor.csv, fog.png and report.md for a computed fog, prepared whole, then written under one hold of
    ``out`` (``_export``)."""
    from adroit.physics import neutrino_fog as nf
    rows = [(m, f) for m, f in zip(result.masses_gev, result.floor_cm2) if f is not None]
    element = nf.published_target(result.settings.target) or ''      # by name, not by stripping digits (NF-04)
    curves = {'ADROIT (n = 2)': tuple(zip(*rows)) if rows else ((), ())}
    if element in nf.PUBLISHED:
        curves[f"O'Hare 2021, published ({element})"] = nf.published_floor(element)
    if classic is not None:
        curves[f'3σ discovery limit, {exposure:g} t·yr above {result.settings.threshold_kev:g} keV'] = classic
    from adroit.evidence.version import as_found
    _export(out, {'fog.json': result.model_dump_json(indent=1),
                  'floor.csv': 'mass_gev,sigma_cm2\n' + ''.join(f'{m:.6g},{f:.6g}\n' for m, f in rows),
                  'fog.png': figure(curves, result),
                  'report.md': report(result, element) + as_found(
                      "It was computed from the target, the halo and the neutrino fluxes ADROIT held when it ran.")})


def _export(out: Path, members: dict[str, str | bytes]) -> None:
    """The fog's files, written whole under one hold of ``out`` (``durable.export``: each to its own entry, a link
    replaced, never written through; refused in a saved study's folder; the auditor's DI recheck, DJ-01, 2026-11-07)."""
    from adroit.core.durable import export
    try:
        export(out, members)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from None


def report(result, element: str) -> str:
    """The settings, the fluxes, and the floor beside the published one."""
    from adroit.physics import neutrino_fog as nf
    s = result.settings
    window = ('only the recoils inside the window counted' if s.binning == 'window' else
              "each spectrum normalised to its whole range (O'Hare's code)")
    lines = ['# The neutrino fog', '', f'Target {s.target}; recoils {s.threshold_kev:g}–{s.max_recoil_kev:g} keV in '
             f'{s.bins} logarithmic bins, {window}; halo: {s.halo.label}; fluxes: {", ".join(result.fluxes)}.', '',
             'An overlay, never a constraint: beneath the floor a discovery needs a disproportionate exposure; nothing '
             'there is excluded.', '', '| flux | uncertainty |', '|---|---|']
    lines += [f'| {f.name} | {f.uncertainty:g} |' for f in nf.fluxes(s)]
    lines += ['', '| mass (GeV) | floor (cm²) | published | ratio |', '|---|---|---|---|']
    show = lambda v: '—' if v is None else f'{v:.3g}'        # noqa: E731
    for m, f in zip(result.masses_gev, result.floor_cm2):
        ref = nf.floor_at(m, element) if element in nf.PUBLISHED else None
        lines.append(f'| {m:.4g} | {show(f)} | {show(ref)} | {f"{f / ref:.3f}" if f and ref else "—"} |')
    odd = [(m, sorted(set(row) - {'reached', 'not reached'})) for m, row in zip(result.masses_gev, result.status)
           if set(row) - {'reached', 'not reached'}]
    if odd:
        lines += ['', 'Not a discovery exposure (each kept apart from "not reached"): ' + '; '.join(
            f'{m:.4g} GeV: {", ".join(kinds)}' for m, kinds in odd) + '.']
    return '\n'.join(lines) + '\n'


def plot(path: Path, curves: dict, result=None) -> Path:
    """The floor curves on the (m, σ) plane, over the index n where a map is given (``figure``), written whole to
    ``path``'s own entry."""
    from adroit.core.durable import write_atomic
    write_atomic(path, figure(curves, result))
    return path


def figure(curves: dict, result=None) -> bytes:
    """``plot``'s figure, as PNG bytes."""
    import io
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    if result is not None:
        n = np.array([[math.nan if v is None else v for v in row] for row in result.index]).T
        mesh = ax.pcolormesh(result.masses_gev, result.sigmas_cm2, np.clip(n, 2, 6), cmap='Blues', shading='auto', alpha=0.8)
        fig.colorbar(mesh, ax=ax, label='n = −(d ln σ / d ln N)⁻¹ (the fog: n > 2)')
    for label, (m, s) in curves.items():
        if len(m):
            ax.plot(m, s, lw=1.6, label=label)
    ax.set(xscale='log', yscale='log', xlabel='dark matter mass (GeV)', ylabel='SI DM–nucleon cross section (cm²)',
           title='The neutrino fog (spin-independent)')
    ax.grid(alpha=0.3, which='both')
    ax.legend(fontsize=7)
    fig.tight_layout()
    stream = io.BytesIO()
    fig.savefig(stream, format='png', dpi=130)
    plt.close(fig)
    return stream.getvalue()
