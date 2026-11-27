"""1.0.1 (the owner, 2026-11-25): the plane marks a relic crossing "may be unreliable" only for a real warning, never
for an informational note. All 34 crossings of the owner's axial example carried "halo: excluded throughout the tested
halo region", and every one had been drawn as "unreliable (see the contour table)"."""
from types import SimpleNamespace

import matplotlib
import matplotlib.axes
import pytest

from adroit.parameter_space.classes import Point
from adroit.parameter_space.verdict import Crossing, reliability_warnings

matplotlib.use("Agg")
INFORMATIONAL = ["halo: excluded throughout the tested halo region",
                 "the equation of state's band: excluded also at the roots with Saikawa & Shirai's upper and lower "
                 "tables (…); the two supplied tables, not every equation of state between them",
                 "theory: the electroweak vacuum is metastable (a deeper … minimum) but outlives the universe: …"]
WARNING = "a record's edge: the limit is read at its validated range's edge here"


def _crossing(m: float, flags: list[str]) -> Crossing:
    return Crossing(point=Point(m_chi=m, m_med=1000.0, g_chi=0.1), status="excluded", excluded_by=["direct detection"],
                    flags=flags, kind="contour", converged=True)


def _labels(tmp_path, monkeypatch, crossings) -> list[str]:
    from adroit.parameter_space import plots
    labels = []
    real = matplotlib.axes.Axes.legend
    monkeypatch.setattr(matplotlib.axes.Axes, "legend", lambda self, handles=(), **k: (
        labels.extend(h.get_label() for h in handles), real(self, handles=handles, **k))[1])
    request = SimpleNamespace(x=SimpleNamespace(parameter="m_chi", log=True),
                              y=SimpleNamespace(parameter="g_chi", log=True), model_class=SimpleNamespace(name="axial"))
    scan = SimpleNamespace(points=[SimpleNamespace(excluded={}, omega_h2=None) for _ in range(9)],
                           xs=[100.0, 300.0, 1000.0], ys=[0.01, 0.1, 1.0], request=request)
    plots.plane(scan, SimpleNamespace(crossings=crossings, target=0.12), tmp_path / "p.png")
    return labels


def test_informational_notes_are_not_warnings() -> None:
    assert reliability_warnings(_crossing(300.0, INFORMATIONAL)) == []
    assert reliability_warnings(_crossing(300.0, INFORMATIONAL + [WARNING])) == [WARNING]


@pytest.mark.parametrize("flags, marked", [(INFORMATIONAL[:1], False), (INFORMATIONAL, False),
                                           ([WARNING], True), (INFORMATIONAL[:1] + [WARNING], True)])
def test_the_plane_marks_only_a_real_warning(tmp_path, monkeypatch, flags, marked) -> None:
    labels = _labels(tmp_path, monkeypatch, [_crossing(300.0, flags), _crossing(500.0, INFORMATIONAL[:1])])
    assert ("verdict may be unreliable (warning in the report)" in labels) is marked
    assert not any("contour table" in label for label in labels)


# --- V1-04 (the independent audit of 1.0.1): the saved DD plot's limit is in its comparison's convention -------------

def _saved(sigma, limit, channel, status="excluded", m=250.0):
    evaluation = SimpleNamespace(dd_kind=channel.kind if channel else "SD-proton", dd_sigma_cm2=sigma,
                                 dd_limit_cm2=limit, dd_channels=[channel] if channel else [])
    return SimpleNamespace(point=Point(m_chi=m, m_med=1000.0, g_chi=0.1), status=status, kind="contour",
                           converged=True, evaluation=evaluation)


def _drawn(tmp_path, monkeypatch, crossings):
    """(the plotted limit line's y values, the plotted model σ values) of ``plots.direct_detection_saved``."""
    from adroit.parameter_space import plots
    lines, points = [], []
    real_plot, real_scatter = matplotlib.axes.Axes.plot, matplotlib.axes.Axes.scatter
    monkeypatch.setattr(matplotlib.axes.Axes, "plot", lambda self, x, y, *a, **k: (lines.append(list(y)),
                                                                                    real_plot(self, x, y, *a, **k))[1])
    monkeypatch.setattr(matplotlib.axes.Axes, "scatter", lambda self, x, y, *a, **k: (
        points.append(list(y)), real_scatter(self, x, y, *a, **k))[1])
    assert plots.direct_detection_saved(SimpleNamespace(crossings=crossings), tmp_path / "dd.png") is not None
    return lines[0], points[0]


@pytest.mark.needs("diamx")
def test_an_excluded_mixed_sd_point_is_drawn_above_its_limit(tmp_path, monkeypatch) -> None:
    """The audit's case: σ_p = 2e-42, L_p = 1e-41, equal couplings at 250 GeV against PandaX-4T alone: ratio 0.2 F
    ≈ 7.2, excluded. The plot had drawn σ at 0.2 of the bare limit."""
    from adroit.parameter_space import dd_channels, limits
    monkeypatch.setattr(limits, "per_module95", lambda kind, mass_gev, excluded=(): (
        (("PandaX-4T Run0+Run1", 1e-41),) if kind == "SD-proton" else (), ()))
    monkeypatch.setattr(limits, "tolerance", lambda *a: 0.0)
    proton = dd_channels.Channel(kind="SD-proton", sigma_cm2=2e-42, sd_p=1.0, sd_n=1.0)
    neutron = dd_channels.Channel(kind="SD-neutron", sigma_cm2=2e-42, sd_p=1.0, sd_n=1.0)
    out = dd_channels._sd_with_interference(proton, neutron, 250.0)
    assert out.ratio > 1 and out.rate_factor
    monkeypatch.undo()
    [limit], [sigma] = _drawn(tmp_path, monkeypatch, [_saved(out.sigma_cm2, out.limit.value, out)])
    assert sigma == 2e-42 and limit == pytest.approx(1e-41 / out.rate_factor)
    assert (sigma > limit) == (out.ratio > 1)                       # the drawn side is the stored comparison's


@pytest.mark.parametrize("sigma, limit, ratio, band, expected", [
    (3e-46, 1e-45, 0.3, None, 1e-45),                                # an ordinary point: its saved limit
    (2e-42 * 35.87, 1e-41, 7.174, None, 1e-41),                      # saved before 1.0.1: σ × F with ratio σF/L
])
def test_the_drawn_limit_matches_each_saved_comparison(tmp_path, monkeypatch, sigma, limit, ratio, band,
                                                        expected) -> None:
    from adroit.parameter_space.dd_channels import ChannelOutcome
    channel = ChannelOutcome(kind="SD-proton", sigma_cm2=sigma, ratio=ratio, ratio_band=band)
    [drawn], [model] = _drawn(tmp_path, monkeypatch, [_saved(sigma, limit, channel,
                                                              "excluded" if ratio > 1 else "viable")])
    assert drawn == pytest.approx(expected, rel=1e-3) and (model > drawn) == (ratio > 1)



# --- F1-03: an interference band is drawn as the limit's range, open-ended where the couplings can cancel -----------

def _drawn_band(tmp_path, monkeypatch, crossings):
    """(the plotted single-limit lines, the vertical ranges (x, low, high), the open-ended markers) of the saved plot."""
    from adroit.parameter_space import plots
    lines, ranges, markers = [], [], []
    real_plot, real_vlines, real_scatter = (matplotlib.axes.Axes.plot, matplotlib.axes.Axes.vlines,
                                            matplotlib.axes.Axes.scatter)
    monkeypatch.setattr(matplotlib.axes.Axes, "plot", lambda self, x, y, *a, **k: (lines.append(list(y)),
                                                                                    real_plot(self, x, y, *a, **k))[1])
    monkeypatch.setattr(matplotlib.axes.Axes, "vlines", lambda self, x, lo, hi, *a, **k: (
        ranges.extend(zip(x, lo, hi)), real_vlines(self, x, lo, hi, *a, **k))[1])
    monkeypatch.setattr(matplotlib.axes.Axes, "scatter", lambda self, x, y, *a, **k: (
        markers.append(k.get("marker")), real_scatter(self, x, y, *a, **k))[1])
    assert plots.direct_detection_saved(SimpleNamespace(crossings=crossings), tmp_path / "dd.png") is not None
    return lines, ranges, markers


@pytest.mark.parametrize("band, status, inside", [
    ((0.0, 1.6), "pending", True),            # the audit's case: cancellation possible, undecided, open-ended
    ((0.2, 1.6), "pending", True),            # straddling: undecided, the range crosses the point
    ((0.1, 0.9), "viable", False),            # wholly allowed: the whole range above the point
    ((1.2, 3.0), "excluded", False),          # wholly excluded: the whole range below the point
])
def test_a_band_is_a_range_never_a_single_boundary(tmp_path, monkeypatch, band, status, inside) -> None:
    from adroit.parameter_space.dd_channels import ChannelOutcome
    sigma = 4e-42
    channel = ChannelOutcome(kind="SD-proton", sigma_cm2=sigma, ratio=band[1], ratio_band=band)
    lines, ranges, markers = _drawn_band(tmp_path, monkeypatch, [_saved(sigma, 1e-41, channel, status)])
    assert lines == []                                              # no single "95% limit" through a band
    [(_, low, high)] = ranges
    assert low == pytest.approx(sigma / band[1])
    assert (low <= sigma <= high) == inside
    if band[0] == 0.0:
        assert "^" in markers                                       # open-ended, marked
    elif band == (0.1, 0.9):
        assert low > sigma
    elif band == (1.2, 3.0):
        assert high < sigma


# --- F1-02: a new Constrain a model study draws its points against their own comparisons ----------------------------

@pytest.mark.needs("diamx")
def test_a_new_track1_study_draws_an_excluded_mixed_sd_point_above_its_limit(tmp_path, monkeypatch) -> None:
    """Through ``track1._plots`` (the path a new run takes): the audit's PandaX case, excluded with ratio ≈ 7.2, had
    been drawn below the bare pure-nucleon limit by the live plot."""
    from adroit.orchestrator import track1
    from adroit.parameter_space import dd_channels, limits, plots
    monkeypatch.setattr(limits, "per_module95", lambda kind, mass_gev, excluded=(): (
        (("PandaX-4T Run0+Run1", 1e-41),) if kind == "SD-proton" else (), ()))
    monkeypatch.setattr(limits, "tolerance", lambda *a: 0.0)
    proton = dd_channels.Channel(kind="SD-proton", sigma_cm2=2e-42, sd_p=1.0, sd_n=1.0)
    neutron = dd_channels.Channel(kind="SD-neutron", sigma_cm2=2e-42, sd_p=1.0, sd_n=1.0)
    out = dd_channels._sd_with_interference(proton, neutron, 250.0)
    monkeypatch.undo()
    assert out.ratio > 1 and out.rate_factor
    verdict = SimpleNamespace(crossings=[_saved(out.sigma_cm2, out.limit.value, out)])
    monkeypatch.setattr(plots, "plane", lambda *a, **k: tmp_path / "plane.png")
    lines = []
    real_plot = matplotlib.axes.Axes.plot
    monkeypatch.setattr(matplotlib.axes.Axes, "plot", lambda self, x, y, *a, **k: (lines.append(list(y)),
                                                                                    real_plot(self, x, y, *a, **k))[1])
    # the scan as a new run has it: a point with its SD kind, so the old live plot (before F1-02) draws its pure-proton
    # envelope and limit (stood in here at the audit's 1e-41) rather than returning no figure
    monkeypatch.setattr(limits, "table", lambda kind: ([10.0, 1000.0], [1e-41, 1e-41], None))
    monkeypatch.setattr(limits, "at95", lambda kind, m: SimpleNamespace(value=1e-41))
    model_class = SimpleNamespace(dd=lambda p: ("SD-proton", 2e-42))
    scan = SimpleNamespace(points=[SimpleNamespace(dd_kind="SD-proton", point=Point(m_chi=250.0, m_med=1000.0,
                                                                                     g_chi=0.98))],
                           request=SimpleNamespace(model_class=model_class))
    names = track1._plots(scan, verdict, tmp_path, "control")
    assert "direct_detection.png" in names
    assert lines and all(limit == pytest.approx(1e-41 / out.rate_factor) for limit in lines[-1])
    assert 2e-42 > lines[-1][0]


# --- the plane's legend names why a point excluded at the reference halo is held (the B − L example's six) ----------

@pytest.mark.parametrize("region, pending, words", [
    ("incomplete", [], "not established throughout the halo region"),
    ("halo_sensitive", ["EOS-sensitive: …"], "not established throughout the halo region"),
    ("excluded_throughout", ["EOS-sensitive: excluded at the nominal root, pending at the root with the upper table"],
     "nominal equation of state"),
    ("excluded_throughout", ["records: unknown version"], "another open check"),
])
def test_a_held_point_is_labelled_by_its_own_reason(region, pending, words) -> None:
    """Six B − L thermal points, excluded throughout the halo region but EOS-sensitive, had been labelled "not
    established throughout the halo region"."""
    from adroit.parameter_space import plots
    crossing = SimpleNamespace(pending=pending)
    assessment = SimpleNamespace(regional=SimpleNamespace(state=region))
    assert words in plots._why_held(crossing, assessment)



@pytest.mark.parametrize("marks", [True, False])
def test_the_warning_marks_can_be_left_to_the_report(tmp_path, monkeypatch, marks) -> None:
    """``warning_marks=False`` (the paper's B − L figure) draws no diamond and no legend entry for one; the default
    still does. The warnings stay in the report either way."""
    from adroit.parameter_space import plots
    labels = []
    real = matplotlib.axes.Axes.legend
    monkeypatch.setattr(matplotlib.axes.Axes, "legend", lambda self, handles=(), **k: (
        labels.extend(h.get_label() for h in handles), real(self, handles=handles, **k))[1])
    request = SimpleNamespace(x=SimpleNamespace(parameter="m_chi", log=True),
                              y=SimpleNamespace(parameter="g_chi", log=True), model_class=SimpleNamespace(name="axial"))
    scan = SimpleNamespace(points=[SimpleNamespace(excluded={}, omega_h2=None) for _ in range(9)],
                           xs=[100.0, 300.0, 1000.0], ys=[0.01, 0.1, 1.0], request=request)
    plots.plane(scan, SimpleNamespace(crossings=[_crossing(300.0, [WARNING])], target=0.12), tmp_path / "p.png",
                warning_marks=marks)
    assert any("unreliable" in x for x in labels) is marks



# --- RA-05: a study saved without its comparisons never draws a pure-nucleon limit as the model's boundary -----------

def test_a_legacy_mixed_sd_point_is_not_drawn_against_a_limit_called_its_own(tmp_path, monkeypatch) -> None:
    """An evaluation-less crossing (a study saved before its points kept their comparisons), both nucleons coupling,
    excluded with ratio ≈ 7.2: the fallback draws the pure-proton limits, labelled as for a pure coupling and not this
    model's comparison, never as the model's own 95% limit."""
    from adroit.parameter_space import limits, plots
    monkeypatch.setattr(limits, "table", lambda kind: ([10.0, 1000.0], [1e-41, 1e-41], None))
    monkeypatch.setattr(limits, "at95", lambda kind, m: SimpleNamespace(value=1e-41))
    labels, titles = [], []
    real_legend, real_set = matplotlib.axes.Axes.legend, matplotlib.axes.Axes.set
    monkeypatch.setattr(matplotlib.axes.Axes, "legend", lambda self, *a, **k: (
        labels.extend(h.get_label() for h in self.get_legend_handles_labels()[0]), real_legend(self, *a, **k))[1])
    monkeypatch.setattr(matplotlib.axes.Axes, "set", lambda self, **k: (titles.append(k.get("title", "")),
                                                                         real_set(self, **k))[1])
    point = Point(m_chi=250.0, m_med=1000.0, g_chi=0.98)
    crossing = SimpleNamespace(point=point, status="excluded", kind="contour", converged=True, evaluation=None)
    result = SimpleNamespace(points=[SimpleNamespace(dd_kind="SD-proton", point=point)],
                             request=SimpleNamespace(model_class=SimpleNamespace(dd=lambda p: ("SD-proton", 2e-42))))
    assert plots.direct_detection(result, SimpleNamespace(crossings=[crossing]), tmp_path / "dd.png") is not None
    limit_labels = [x for x in labels if "limit" in x or "envelope" in x]
    assert limit_labels and all("pure" in x for x in limit_labels)
    assert not any("own couplings" in x for x in labels) and any("pure-coupling" in x for x in titles)


# --- every exclusion drawn; the signal region optional; thermal points by the 68% band (the owner, 2026-11-26) ----

def _plane_labels(tmp_path, monkeypatch, points, crossings, **kw):
    from adroit.parameter_space import plots
    labels = []
    real = matplotlib.axes.Axes.legend
    monkeypatch.setattr(matplotlib.axes.Axes, "legend", lambda self, handles=(), **k: (
        labels.extend(h.get_label() for h in handles), real(self, handles=handles, **k))[1])
    request = SimpleNamespace(x=SimpleNamespace(parameter="g_chi", log=False),
                              y=SimpleNamespace(parameter="m_chi", log=True), model_class=SimpleNamespace(name="x"))
    scan = SimpleNamespace(points=points, xs=[0.1, 0.5, 1.0], ys=[100.0, 300.0, 1000.0], request=request)
    plots.plane(scan, SimpleNamespace(crossings=crossings, target=0.12), tmp_path / "p.png", **kw)
    return labels


def _grid(excluded: dict):
    return [SimpleNamespace(excluded=dict(excluded), omega_h2=None, ratios={}, chi2={}, records={},
                            point=Point(m_chi=y, m_med=1000.0, g_chi=x))
            for y in (100.0, 300.0, 1000.0) for x in (0.1, 0.5, 1.0)]


def test_an_exclusion_outside_the_colour_list_is_drawn_hatched(tmp_path, monkeypatch) -> None:
    """The CMS dijet search excluded the whole axial plane and nothing showed it: every excluding constraint is drawn."""
    labels = _plane_labels(tmp_path, monkeypatch, _grid({"LHC dijet resonances (CMS, ATLAS)": True}), [])
    assert "excluded: LHC dijet resonances (CMS, ATLAS)" in labels


def test_thermal_points_are_coloured_by_the_band_and_the_signal_region_is_optional(tmp_path, monkeypatch) -> None:
    band = [(100.0, 0.2, 0.3, 0.4), (1000.0, 0.6, 0.8, 1.0)]
    crossings = [SimpleNamespace(point=Point(m_chi=300.0, m_med=1000.0, g_chi=g), kind="contour", converged=True,
                                 status="excluded", flags=[]) for g in (0.5, 0.95)]
    signal = ["meets"] * 9
    plain = _plane_labels(tmp_path, monkeypatch, _grid({}), crossings, band=band, signal=signal)
    assert not any("signal criterion" in x for x in plain)                     # off by default
    assert any("inside the fitted 68% interval" in x for x in plain) and any("outside it" in x for x in plain)
    hatched = _plane_labels(tmp_path, monkeypatch, _grid({}), crossings, band=band, signal=signal, signal_region=True)
    assert any("signal criterion" in x for x in hatched)


# --- RE-02 and RE-03 (the fourth recheck): the colours follow the intervals as saved and as drawn -------------------

def _coloured(tmp_path, monkeypatch, band, pieces, crossings, log_x=False):
    """{g_chi: face colour} of the thermal points ``plots.plane`` draws."""
    from adroit.parameter_space import plots
    seen = {}
    real = matplotlib.axes.Axes.scatter

    def record(self, x, y, *a, **k):
        if k.get("zorder") == 6:
            for xi in x:
                seen[round(float(xi), 6)] = k.get("color")
        return real(self, x, y, *a, **k)
    monkeypatch.setattr(matplotlib.axes.Axes, "scatter", record)
    request = SimpleNamespace(x=SimpleNamespace(parameter="g_chi", log=log_x),
                              y=SimpleNamespace(parameter="m_chi", log=True), model_class=SimpleNamespace(name="x"))
    xs = [0.01, 0.1, 1.0] if log_x else [0.0, 0.5, 1.0]
    scan = SimpleNamespace(points=[SimpleNamespace(excluded={}, omega_h2=None, ratios={}, chi2={}, records={})
                                   for _ in range(9)], xs=xs, ys=[100.0, 300.0, 1000.0], request=request)
    points = [SimpleNamespace(point=Point(m_chi=m, m_med=1000.0, g_chi=g), kind="contour", converged=True,
                              status="excluded", flags=[]) for m, g in crossings]
    plots.plane(scan, SimpleNamespace(crossings=points, target=0.12), tmp_path / "p.png", band=band,
                band_pieces=pieces)
    return seen


def test_a_disconnected_interval_colours_by_its_pieces_and_leaves_its_neighbours_unestablished(tmp_path,
                                                                                              monkeypatch) -> None:
    band = [(100.0, 0.4, 0.5, 0.6), (1000.0, 0.4, 0.5, 0.6)]          # 300 GeV is disconnected: not in the band
    pieces = [(300.0, 0.1, 0.3), (300.0, 0.7, 0.9)]
    seen = _coloured(tmp_path, monkeypatch, band, pieces, [(300.0, 0.2), (300.0, 0.5), (300.0, 0.8), (200.0, 0.45)])
    assert seen[0.2] == seen[0.8] == "tab:red"            # in a saved piece
    assert seen[0.5] == "white"                            # in the gap
    assert seen[0.45] == "lightgrey"                       # beside the disconnected mass: not established


def test_on_a_log_axis_the_colours_follow_the_band_as_drawn(tmp_path, monkeypatch) -> None:
    band = [(100.0, 0.01, 0.015, 0.02), (1000.0, 0.5, 0.7, 0.9)]
    m = 316.2278
    seen = _coloured(tmp_path, monkeypatch, band, [], [(m, 0.1), (m, 0.3)], log_x=True)
    assert seen[0.1] == "tab:red" and seen[0.3] == "white"   # the drawn edges here are about [0.071, 0.134]
