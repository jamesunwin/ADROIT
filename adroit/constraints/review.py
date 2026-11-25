"""A person's review of a constraint record: its curves beside the source figure, and the verification.

The build plan's rule is that a record is used only once a person has verified it. This
module gives that person what they need, and writes down what they decided:
- ``curves(record)``: every curve the record's data hold (a digitised file, or the tools
  folder's DarkCast limits and f_eff tables), as (x, y) points;
- ``plot(record, path)``: the curves drawn on the axes the source uses;
- ``fetch_source(record)``: the source paper (arXiv PDF) into the tools folder, so its
  figure page can be shown beside the plot (it is never copied into this repository);
- ``verify(record_id, by)``: the person's verification, written into ``records.yaml``
  (``verified_on`` today, ``verified_by`` the name), leaving the rest of the file as it is.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING,Literal

import numpy as np
from pydantic import Field

from adroit.core.dm_state import ConstraintRecord
from adroit.core.state import StrictModel

if TYPE_CHECKING:
    from adroit.constraints.review_tasks import RecordReviewPacket

SOURCES = "record-sources"                  # the folder in the tools directory holding fetched papers


class Curve(StrictModel):
    """One curve of a record: its label and points."""

    label: str
    x: list[float] = Field(default_factory=list)
    y: list[float] = Field(default_factory=list)
    region: bool = False              # a closed outline of an excluded region, drawn shaded
    panel: str = ""                   # the PANELS prefix it belongs to, when not its label's start


class Reading:
    """One reading of a curated record (``reading``): the record as the records file held it, its data file's bytes
    read once (their SHA-256, and their parse), and what is derived from them, once: its curves, the curves the tools
    folder cannot give, its version. Every part of a review, its packet, report, figure, version and signature state,
    and the hash a person's verification is bound to, is taken from one reading (the auditor's DJ recheck, DK-02,
    2026-11-07: read apart, a data file changed and restored between the reads had given a packet bound to the
    restored A, its signature current, beside B's curves or figure)."""

    def __init__(self, record: ConstraintRecord, data: dict | None, data_sha256: str, error: str = "") -> None:
        self.record, self.data, self.data_sha256, self.error = record, data, data_sha256, error
        self._curves: list[Curve] | None = None
        self._missing: list[str] | None = None

    def parsed(self) -> dict:
        """The data file as this reading parsed it; ``OSError`` where it could not be read."""
        if self.error:
            raise OSError(self.error)
        return self.data if self.data is not None else {}

    @property
    def curves(self) -> list[Curve]:
        """The record's curves (``curves``), of this reading: taken once."""
        if self._curves is None:
            self._curves = _curves(self.record, self)
        return self._curves

    @property
    def missing(self) -> list[str]:
        """The curves its figure cannot show (``missing_curves``): taken once."""
        if self._missing is None:
            self._missing = missing_curves(self.record)
        return self._missing

    def version(self) -> str:
        """The record's version (``review_identity.fingerprint``) of this reading's data; ``OSError`` or ``ValueError``
        where it cannot be taken."""
        from adroit.constraints.review_identity import fingerprint
        return fingerprint(self.record, self.parsed() if self.record.data_file else None)


def reading(record_id: str) -> Reading:
    """A curated record read once (``Reading``): the record from the records file, and its data file's bytes, read
    once and parsed as every reader of a record's data parses them (``review_identity._data``). ``KeyError`` for no
    such record; a data file that cannot be read or parsed is the reading's ``error``."""
    import hashlib

    import yaml

    from adroit.constraints import database
    from adroit.core.config import PROJECT_ROOT
    record = database.record(record_id)
    if not record.data_file:
        return Reading(record, None, "")
    try:
        content = (PROJECT_ROOT / record.data_file).read_bytes()
    except OSError as error:
        return Reading(record, None, "", f"{record.data_file} cannot be read ({error})")
    digest = hashlib.sha256(content).hexdigest()
    try:
        data = yaml.load(content.decode("utf-8"), Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))
    except (ValueError, yaml.YAMLError) as error:
        return Reading(record, None, digest, f"{record.data_file} cannot be parsed ({error})")
    return Reading(record, data, digest)


def _data_of(record: ConstraintRecord, held: Reading | None) -> dict:
    """A record's data file, parsed: of the reading ``held``, else as the database reads it now."""
    from adroit.constraints import database
    return held.parsed() if held is not None else database.data(record.id)


def _is_point(item) -> bool:
    return isinstance(item, (list, tuple)) and len(item) == 2 and all(isinstance(v, (int, float)) for v in item)


def _walk(obj, path: str, out: list[Curve]) -> None:
    """Every list of [x, y] points in a nested structure, and every table of 'columns' and 'rows'."""
    if isinstance(obj, dict):
        if "columns" in obj and "points" in obj:
            points = [q for q in obj["points"] if _is_point(q)]
            out.append(Curve(label=f"{path}{obj['columns'][1]} against {obj['columns'][0]}",
                             x=[q[0] for q in points], y=[q[1] for q in points]))
            return
        if "columns" in obj and "rows" in obj:
            columns, rows = obj["columns"], obj["rows"]
            for i, name in enumerate(columns[1:], start=1):
                pairs = [(r[0], r[i]) for r in rows if r[i] is not None]
                out.append(Curve(label=f"{path}{name}", x=[a for a, _ in pairs], y=[b for _, b in pairs]))
            return
        for key, value in obj.items():
            _walk(value, f"{path}{key} / " if path or key != "points" else "", out)
        return
    if isinstance(obj, list) and len(obj) >= 3 and all(_is_point(p) for p in obj):
        out.append(Curve(label=path.rstrip(" /") or "curve", x=[p[0] for p in obj], y=[p[1] for p in obj]))
        return
    if isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk(item, f"{path}{i} / " if len(obj) > 1 else path, out)


def search_name(stem: str) -> str:
    """A DarkCast search's name to read: "BaBar_Lees2014xha" → "BaBar 2014", "LHCb_Aaij2019bvg_displaced" →
    "LHCb 2019 displaced"."""
    import re

    from adroit.constraints import searches
    try:
        return searches.darkcast_info(stem)["name"]
    except KeyError:
        pass
    parts = stem.split("_")
    year = re.search(r"(?:19|20)\d{2}", parts[1]) if len(parts) > 1 else None
    return " ".join(filter(None, [parts[0], year.group(0) if year else "", " ".join(parts[2:])]))


def darkcast_regions(stem: str, limit, top: float = 1.0) -> list[Curve]:
    """A DarkCast limit's excluded regions as closed outlines, named by search: between its lower and upper
    boundaries (up to ε = ``top`` for a one-sided limit), or inside its r-value map's r = 1 contour."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    name = search_name(stem)
    if limit.is_map:
        m, g = np.meshgrid(np.log(limit.masses), np.log(limit.grid), indexing="ij")
        r = np.log(np.maximum(np.asarray(limit.rvalues), 1e-300))
        fig, ax = plt.subplots()
        contour = ax.contour(m, g, r, levels=[0.0])                     # log r = 0: r = 1
        plt.close(fig)
        paths = [p for seg in contour.allsegs[0] for p in [seg] if len(p) >= 3]
        return [Curve(label=name, region=True, x=np.exp(p[:, 0]).tolist(), y=np.exp(p[:, 1]).tolist())
                for p in paths]                                         # one search, perhaps several islands
    out = []
    masses = np.asarray(limit.masses)
    for k, (lower, upper) in enumerate(limit.bands):
        lower = np.asarray(lower)
        upper = np.full_like(lower, top) if upper is None else np.minimum(np.asarray(upper), top)
        keep = (lower > 0) & (lower < 1e4) & (upper > lower)
        if keep.sum() >= 2:
            x, low, high = masses[keep], lower[keep], upper[keep]
            out.append(Curve(label=name if k == 0 else f"{name} ({k + 1})", region=True,
                             x=[*x.tolist(), *x[::-1].tolist()], y=[*low.tolist(), *high[::-1].tolist()]))
    return out


def _tool_curves(record: ConstraintRecord) -> list[Curve]:
    """Curves held in the tools folder: DarkCast's limits and Slatyer's f_eff."""
    from adroit.constraints import searches
    out = []
    if record.id in ("darkcast-dark-photon", "lmu-ltau-babar-belle2") and searches._tool("DarkCast"):
        from adroit.parameter_space import searches as applied
        if record.id.startswith("lmu"):
            limit = searches.darkcast("BaBar_TheBABAR2016rlg")
            masses, lower = np.asarray(limit.masses), np.asarray(limit.bands[0][0])
            keep = (lower > 0) & (lower < 1e4)
            out.append(Curve(label="BaBar_TheBABAR2016rlg lower", x=masses[keep].tolist(), y=lower[keep].tolist()))
        else:
            for panel, stems in (("visible", applied.VISIBLE_PROMPT + applied.VISIBLE_DISPLACED),
                                 ("invisible", applied.INVISIBLE)):
                out += [c.model_copy(update={"panel": panel}) for stem in stems
                        for c in darkcast_regions(stem, searches.darkcast(stem))]
    if record.id == "planck-2018-pann":
        table = searches.f_eff_table()
        if table is not None:
            masses, names, values = table
            for name in ("e^+e^-", r"\mu^+\mu^-", r"\tau^+\tau^-", r"b\bar{b}", "W^+W^-", r"\gamma\gamma"):
                column = values[:, names.index(name)]
                keep = column > 0                  # the table's zeros below a threshold mean "not computed"
                out.append(Curve(label=f"f_eff {name}", x=masses[keep].tolist(), y=column[keep].tolist()))
    return out


def quoted(data: dict[str, float]) -> list[str]:
    """A record's inline data as lines to read, each value with its uncertainty (``value``/``sigma``, ``x``/``x_sigma``
    or ``x``/``sigma_x``) quoted to the uncertainty's decimal place: Planck's Ω_c h² reads 0.1200 ± 0.0012, not 0.12
    beside 0.0012 (YAML keeps no trailing zeros; the owner, 2026-10-13)."""
    from decimal import Decimal

    def error_of(key: str) -> str | None:
        names = ["sigma"] if key == "value" else [f"{key}_sigma", f"sigma_{key}"]
        return next((name for name in names if name in data), None)
    lines, used = [], set()
    for key, value in data.items():
        if key in used:
            continue
        error = error_of(key)
        if error is None:
            lines.append(f"{key} = {value}")
            continue
        places = max(0, -Decimal(repr(data[error])).normalize().as_tuple().exponent)
        lines.append(f"{key} = {value:.{places}f} ± {data[error]:.{places}f}")
        used.add(error)
    return lines


def _own_part(record: ConstraintRecord, data: dict) -> dict:
    """The part of a shared data file that is this record's: CMS's panel (…-V1), IceCube's SD or SI limits."""
    suffix = record.id.rsplit("-", 1)[-1]
    if isinstance(data.get("panels"), dict) and suffix in data["panels"]:
        return {**data, "panels": {suffix: data["panels"][suffix]}}
    limits = data.get("limits")
    if isinstance(limits, dict) and suffix in ("sd", "si"):
        return {**data, "limits": {k: v for k, v in limits.items() if k.lower().startswith(suffix)}}
    return data


def missing_curves(record: ConstraintRecord) -> list[str]:
    """The curves a record's review shows from the tools folder (``_tool_curves``) that cannot be drawn because the
    tool is not installed, each with what to fetch (the fallback review's D4: they had been left out silently)."""
    from adroit.constraints import searches
    out = []
    if record.id in ("darkcast-dark-photon", "lmu-ltau-babar-belle2") and not searches._tool("DarkCast"):
        what = "BaBar's curve" if record.id.startswith("lmu") else "every search's excluded region"
        out.append(f"{what} (from DarkCast, which is not in the tools folder: `adroit setup --fetch`)")
    if record.id == "planck-2018-pann" and searches.f_eff_table() is None:
        out.append("the f_eff curves (Slatyer's f_eff table is not in the tools folder: `adroit setup --fetch`)")
    return out


def curves(record: ConstraintRecord, held: Reading | None = None) -> list[Curve]:
    """Every curve of a record (none for a record of single numbers): of the reading ``held`` (``Reading``), else of
    its data as read now."""
    return held.curves if held is not None else _curves(record, None)


def _curves(record: ConstraintRecord, held: Reading | None) -> list[Curve]:
    out: list[Curve] = []
    if record.data_file:
        data = _own_part(record, _data_of(record, held))
        _walk({k: v for k, v in data.items() if k not in ("source", "correction_note")}, "", out)
    return out + _tool_curves(record)


# Legend names for curves whose labels are data keys (the owner's record review, 2026-10-13).
LEGEND: dict[str, str] = {
    "g_prime against m_zprime_gev": "Belle II, Z′ → invisible (arXiv:2212.03066 Fig. 3)",
    "BaBar_TheBABAR2016rlg lower": "BaBar, e⁺e⁻ → μ⁺μ⁻Z′, Z′ → μ⁺μ⁻ (arXiv:1606.03501 Fig. 5, via DarkCast)",
    **{f"{frame} / {level}": f"ΔN_eff = {level}" for frame in ("no_mixing", "natural_mixing")
       for level in ("0.5", "0.2", "0.1")},
}

# Records whose curves are different quantities: each group of curves, by the start of its label, is drawn on its own
# panel and axis (the owner's data audit, 2026-10-12). Per record: the x-axis, then (label prefix, y-axis, log y).
PANELS: dict[str, tuple[str, list[tuple[str, str, bool]]]] = {
    "atlas-1903.06248-dilepton": ("m_Z′ (GeV)", [
        ("limit_fb", "95% CL upper limit on fiducial σ × BR(ℓℓ) (fb), by Γ/m", True),
        ("sigma_", "predicted σ × BR (fb): B−L at g = 1; the SSM at LO and fiducial", True)]),
    "atlas-1910.08447-dijet-gaussian": ("m (GeV)", [
        ("gaussian_limits", "95% CL upper limit on σ × A × BR(jj) (pb), by σ_G/m (%)", True),
        ("zprime_acceptance", "acceptance A of the DM Z′ (dimensionless), by g_q′", False)]),
    "lmu-ltau-babar-belle2": ("m_Z′ (GeV)", [
        ("g_prime", "90% CL upper limit on g′ (Belle II)", True),
        ("BaBar_", "90% CL upper limit on g′ (BaBar)", True)]),
    "planck-2018-pann": ("m_χ (GeV)", [("f_eff", "f_eff (dimensionless), by channel", False)]),
    "darkcast-dark-photon": ("m_A′ (GeV)", [
        ("visible", "ε √BR(visible): each search's excluded region, at its own CL (DarkCast)", True),
        ("invisible", "ε √BR(χχ̄): each search's excluded region, at its own CL (DarkCast)", True)]),
    "escudero-1901.02010-neff": ("log₁₀(m_Z′/MeV)", [          # the owner's review, 2026-11-06: the source's axes
        ("no_mixing", "log₁₀ g_μ−τ: no kinetic mixing (Fig. 2, top)", False),
        ("natural_mixing", "log₁₀ g_μ−τ: ε = g_μ−τ/70 (Fig. 2, bottom)", False)]),
}

# Records holding a two-dimensional grid of limits (``grid``): per record, the x-axis, the rows' key and its axis, the
# step between rows (each row drawn from its value up one step, as the source draws it) and the colour bar's label and
# range in log10 of the limit (the owner's review, 2026-11-06: the record page had shown nothing for it).
GRIDS: dict[str, tuple[str, str, str, float, str, tuple[float, float]]] = {
    "lhcb-1612.07818-b-to-k-mumu": (
        "m_χ (MeV)", "log10_tau_ps", "log₁₀(τ_χ/ps): LHCb's 41 lifetimes, each drawn from its value up one row", 0.1,
        "log₁₀ of the 95% CL limit on BR(B⁺ → K⁺χ) × BR(χ → μ⁺μ⁻)", (-10.0, -6.82)),
}


def panels(record: ConstraintRecord, held: Reading | None = None) -> list[tuple[str, list[Curve], bool]]:
    """The record's curves grouped for plotting: (y-axis, curves, log y) per panel. One panel unless the record is in
    ``PANELS``; a curve no group claims gets a panel of its own kind rather than being dropped. ``held``: of that
    reading of the record (``Reading``)."""
    found = curves(record, held)
    if record.id not in PANELS:
        return [("", found, all(v > 0 for c in found for v in c.y))] if found else []
    out = []
    for prefix, label, log in PANELS[record.id][1]:
        group = [c for c in found if (c.panel or c.label).startswith(prefix)]
        if group:
            out.append((label, group, log and all(v > 0 for c in group for v in c.y)))
    claimed = {id(c) for _, group, _ in out for c in group}
    rest = [c for c in found if id(c) not in claimed]
    if rest:
        out.append(("other curves", rest, all(v > 0 for c in rest for v in c.y)))
    return out + _derived(record, found, held)


def _derived(record: ConstraintRecord, found: list[Curve],
             held: Reading | None = None) -> list[tuple[str, list[Curve], bool]]:
    """Panels computed from the record's own columns, for the audit: the dilepton recast's SSM fiducial-to-LO ratio
    beside the constant correction it applies."""
    if record.id != "atlas-1903.06248-dilepton":
        return []
    by = {c.label: c for c in found}
    fid, lo = by.get("sigma_br_fid_ssm_fb"), by.get("sigma_br_lo_ssm_fb")
    if fid is None or lo is None:
        return []
    lo_at = dict(zip(lo.x, lo.y))
    pairs = [(x, y / lo_at[x]) for x, y in zip(fid.x, fid.y) if lo_at.get(x)]
    constant = _data_of(record, held).get("correction_fid_over_lo")
    ratio = [Curve(label="SSM σ_fid/σ_LO (from the two columns above)", x=[a for a, _ in pairs], y=[b for _, b in pairs])]
    if constant is not None and pairs:
        from adroit.parameter_space.searches import DILEPTON_MAX
        ratio.append(Curve(label=f"the constant correction applied (to {DILEPTON_MAX / 1e3:g} TeV), {constant}",
                           x=[pairs[0][0], DILEPTON_MAX], y=[constant, constant]))
    return [("derived: fiducial over leading-order σ (dimensionless)", ratio, False)]


def plot(record: ConstraintRecord, path: Path) -> Path | None:
    """The record's figure (``figure``) written whole to ``path``'s own entry (``write_atomic``); None if it has none
    to draw."""
    from adroit.core.durable import write_atomic
    data = figure(record)
    if data is None:
        return None
    write_atomic(path, data)
    return path


def grid(record: ConstraintRecord, held: Reading | None = None) -> list[dict] | None:
    """A record's two-dimensional grid of limits (``GRIDS``): its rows, each at one value of the rows' key, with
    segments [low, high, log10 limit] along the x-axis; None for a record without one. ``held``: of that reading of
    the record (``Reading``)."""
    if record.id not in GRIDS or not record.data_file:
        return None
    rows = _data_of(record, held).get("rows")
    return rows if rows and all(isinstance(r, dict) and "segments" in r for r in rows) else None


def _grid_figure(record: ConstraintRecord, rows: list[dict]) -> bytes:
    """The grid as a map, each row's segments drawn as cells one row-step high from the row's value (the source's
    own figure, as LHCb's Fig. 4 is drawn), on a 1-unit raster along x; cells with no segment (vetoed) left blank."""
    import io

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x_label, key, y_label, step, value_label, (low, high) = GRIDS[record.id]
    start = min(s[0] for r in rows for s in r["segments"])
    stop = max(s[1] for r in rows for s in r["segments"])
    columns = int(np.ceil(stop - start)) + 1
    image = np.full((len(rows), columns), np.nan)
    for i, r in enumerate(sorted(rows, key=lambda r: r[key])):
        for lo, hi, v in r["segments"]:
            image[i, int(np.floor(lo - start)):int(np.ceil(hi - start)) + 1] = v
    values = sorted(r[key] for r in rows)
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    shown = ax.imshow(image, origin="lower", aspect="auto", cmap="jet_r", vmin=low, vmax=high, interpolation="nearest",
                      extent=(start, start + columns, values[0], values[-1] + step))
    fig.colorbar(shown, ax=ax).set_label(value_label, fontsize=7)
    ax.set_xlabel(x_label, fontsize=8)
    ax.set_ylabel(y_label, fontsize=7)
    ax.set_title(record.name, fontsize=8, wrap=True)
    fig.tight_layout()
    stream = io.BytesIO()
    fig.savefig(stream, format="png", dpi=110)
    plt.close(fig)
    return stream.getvalue()


def figure(record: ConstraintRecord, held: Reading | None = None) -> bytes | None:
    """The record's curves on log–log axes (linear where a value is not positive), one panel per quantity
    (``panels``), with a note under the figure naming any curve that could not be drawn (``missing_curves``), as PNG
    bytes: what the record's page shows, drawn for it (the auditor's DH recheck, DI-01, 2026-11-06: a page naming a figure's
    file, read by the browser later, can show another rendering's); None if it has none to draw. ``held``: drawn from
    that reading of the record (``Reading``), its curves and the note the packet beside it shows (DK-02)."""
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    groups = panels(record, held)
    if not groups:
        rows = grid(record, held)
        return _grid_figure(record, rows) if rows else None
    fig, axes = plt.subplots(len(groups), 1, figsize=(7.5, 5.0 if len(groups) == 1 else 3.3 * len(groups)),
                             sharex=True, squeeze=False)
    for ax, (label, group, log_y) in zip(axes[:, 0], groups):
        if sum(c.region for c in group) > 10:              # enough colours that no two named searches share one
            ax.set_prop_cycle(color=[*plt.get_cmap("tab20").colors, *plt.get_cmap("tab20b").colors])
        colours: dict[str, str] = {}
        for c in group:
            if c.region:                                  # an excluded region: shaded, named once in the legend
                named = c.label in colours
                line, = ax.plot(c.x + c.x[:1], c.y + c.y[:1], lw=0.8, color=colours.get(c.label),
                                label="_" + c.label if named else c.label)
                colours[c.label] = line.get_color()
                ax.fill(c.x, c.y, alpha=0.18, color=line.get_color())
            else:
                ax.plot(c.x, c.y, lw=1.2, label=LEGEND.get(c.label, c.label))
        if log_y:
            ax.set_yscale("log")
        if label:
            ax.set_ylabel(label, fontsize=7, wrap=True)
        if len({c.label for c in group}) <= 12:
            ax.legend(fontsize=6)
        elif all(c.region for c in group):                # many named searches: a compact legend beside the plot
            ax.legend(fontsize=4.5, ncol=2, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
        ax.grid(alpha=0.3, which="both")
    if all(v > 0 for _, group, _ in groups for c in group for v in c.x):
        axes[-1, 0].set_xscale("log")
    axes[0, 0].set_title(record.name, fontsize=8, wrap=True)
    axes[-1, 0].set_xlabel(PANELS[record.id][0] if record.id in PANELS else record.quantity or "", fontsize=8)
    if missing := (held.missing if held is not None else missing_curves(record)):
        fig.text(0.01, 0.005, "Not shown: " + "; ".join(missing), fontsize=6, color="firebrick", wrap=True)
        fig.tight_layout(rect=(0, 0.04, 1, 1))
    else:
        fig.tight_layout()
    stream = io.BytesIO()
    fig.savefig(stream, format="png", dpi=110)
    plt.close(fig)
    return stream.getvalue()


ARXIV_ID = re.compile(r"(\d{4}\.\d{4,5}|[a-z][a-z.-]*/\d{7})(v\d+)?")     # 1808.03684, hep-ex/0311019


def on_arxiv(record: ConstraintRecord) -> bool:
    """Whether the record's figure reference is an arXiv paper (the PDG's review is not: ``pdg-2024-ew``)."""
    return record.figure is not None and ARXIV_ID.fullmatch(record.figure.arxiv) is not None


def source_path(record: ConstraintRecord, tools_dir: Path | None = None) -> Path | None:
    """Where the record's source PDF lives in the tools folder (whether or not it has been fetched)."""
    from adroit.core.config import get_settings
    if record.figure is None:
        return None
    return (tools_dir or get_settings().tools_dir) / SOURCES / f"{record.figure.arxiv.replace('/', '_')}.pdf"


def fetch_source(record: ConstraintRecord, tools_dir: Path | None = None) -> Path | None:  # pragma: no cover - network
    """The record's source paper from arXiv, into the tools folder (once); None for a source that is not an arXiv paper
    (``on_arxiv``: it is put there by hand, at ``source_path``)."""
    import requests
    target = source_path(record, tools_dir)
    if target is None or target.exists() or not on_arxiv(record):
        return target if target is not None and target.exists() else None
    target.parent.mkdir(parents=True, exist_ok=True)
    reply = requests.get(f"https://arxiv.org/pdf/{record.figure.arxiv}", timeout=120,
                         headers={"User-Agent": "adroit (research software; fetches public papers)"})
    reply.raise_for_status()
    target.write_bytes(reply.content)
    return target


def verify(record_id: str, by: str, on: date | None = None, path: Path | None = None,
           expected_sha256: str = "") -> None:
    """Write a person's verification of one record into ``records.yaml`` (the rest of the file unchanged).

    Raises:
        ValueError: if no name is given, the record is unknown, or it is already verified.
    """
    from adroit.constraints import database
    if not by.strip():
        raise ValueError("a verification needs the name of the person who made it")
    path = path or database.RECORDS
    from adroit.core.durable import lock, lock_for
    with lock(lock_for(path)):              # read, changed and written under it (M3): no lost update
        _verify_locked(record_id, by, path, on, expected_sha256)
    database.records.cache_clear()
    database.data.cache_clear()


def _verify_locked(record_id: str, by: str, path: Path, on: date | None, expected_sha256: str) -> None:
    """``verify``'s read-modify-write of ``records.yaml``, under its lock; the file published whole
    (``durable.write_atomic``), so a reader or a crash sees the old file or the new one, never part of one."""
    from adroit.constraints.review_identity import fingerprint, signature_status
    from adroit.core.durable import write_atomic
    import json
    import yaml
    text = path.read_text(encoding="utf-8")
    found = re.search(rf"^(  - id: {re.escape(record_id)}\n)", text, re.M)
    if found is None:
        raise ValueError(f"no record {record_id!r} in {path.name}")
    block_end = text.find("\n  - id: ", found.end())
    block = text[found.end(): block_end if block_end >= 0 else len(text)]
    raw = next(r for r in yaml.safe_load(text)["records"] if r["id"] == record_id)
    current = ConstraintRecord.model_validate(raw)
    payload_hash = fingerprint(current)          # its data read once: the state and the version bound are of it (DL-01)
    status = signature_status(current, lambda: payload_hash)
    if status.usable:
        raise ValueError(f"{record_id} is already verified")
    if expected_sha256 and expected_sha256 != payload_hash:
        raise ValueError("scientific content changed since the review panel; inspect it again before signing")
    history = [h.model_dump(mode="json") for h in current.verification_history]
    if current.verified_on and current.verified_by:
        history.append({"on": current.verified_on.isoformat(), "by": current.verified_by,
                        "payload_sha256": current.verification_sha256 or status.signed_sha256})
    block = re.sub(r"^    (verified_on|verified_by|verification_sha256|verification_history):[^\n]*\n?", "", block, flags=re.M)
    name = json.dumps(by.strip(), ensure_ascii=False)     # always a string: YAML reads No, On, 123 or Null bare as
    stamp = (f"    verified_on: {(on or date.today()).isoformat()}\n"        # another type (the audit loop's AL1-09)
             f"    verified_by: {name}\n"
             f"    verification_sha256: {payload_hash}\n")
    if history:
        stamp += f"    verification_history: {json.dumps(history, ensure_ascii=False)}\n"
    suffix = text[block_end:] if block_end >= 0 else ""
    signed = text[:found.end()] + stamp + block + suffix
    _signed_as_written(signed, record_id, by.strip(), payload_hash)
    write_atomic(path, signed)


def _signed_as_written(text: str, record_id: str, by: str, payload_hash: str) -> None:
    """The records file about to be published, read back as every reader reads it (``database``): it loads, and the
    record carries the signature just made, as given. Raises ValueError, and nothing is written, if not (AL1-09: a
    name YAML read as a boolean had been written, and the records file then loaded nowhere)."""
    import yaml
    try:
        records = [ConstraintRecord(**entry) for entry in yaml.safe_load(text)["records"]]
    except (yaml.YAMLError, TypeError, KeyError, ValueError) as error:
        raise ValueError(f"signing {record_id} would leave the records file unreadable ({error}); nothing written") \
            from None
    signed = next((r for r in records if r.id == record_id), None)
    if signed is None or signed.verified_by != by or signed.verification_sha256 != payload_hash:
        raise ValueError(f"signing {record_id} would not record the signature as given; nothing written")


def start_timing(packet: RecordReviewPacket, participant: str, condition: Literal["manual","assisted"], path: Path) -> None:
    """Start the existing researcher-controlled protocol on one immutable review packet."""
    from adroit.evaluation.assistance_timing import start, save
    if not participant.strip() or condition not in ("manual", "assisted"):
        raise ValueError("review timing needs a named researcher and manual/assisted condition")
    if path.exists():
        raise ValueError("review timing session already exists")
    try:
        save(start(participant.strip(),f"constraint-review:{packet.record_id}",packet.timing_identity,condition),path,
             new=True)
    except FileExistsError:
        raise ValueError("review timing session already exists: another was started there meanwhile") from None


def mark_timing(path: Path, action: Literal["pause","resume","finish"], *, attest: bool = False, success: bool | None = None) -> None:
    """Pause/resume/finish an attested review timer; never infer success from a UI click."""
    from adroit.evaluation.assistance_timing import ResearcherSession, transition, save
    if action not in ("pause", "resume", "finish"):
        raise ValueError("review timer action must be pause, resume or finish")
    session=ResearcherSession.model_validate_json(path.read_text())
    save(transition(session,action,attest=attest,success=success),path)
