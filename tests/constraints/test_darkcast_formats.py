"""DarkCast's limits as DarkCast reads them (the owner's record review, 2026-10-13): LHCb's displaced search is a map of
r = observed yield limit / predicted yield on an (m, ε) grid, which ADROIT had read as coupling boundaries."""

import numpy as np
import pytest

from adroit.constraints import review, searches as s
from adroit.parameter_space import searches as ps

pytestmark = pytest.mark.skipif(s._tool("DarkCast") is None, reason="DarkCast is not in the tools folder")
STEMS = ps.VISIBLE_PROMPT + ps.VISIBLE_DISPLACED + ps.INVISIBLE + ["BaBar_TheBABAR2016rlg"]


@pytest.mark.parametrize("stem", STEMS)
def test_every_limit_is_read_in_the_format_darkcast_defines(stem):
    limit = s.darkcast(stem)
    if limit.is_map:
        r = np.asarray(limit.rvalues)
        assert r.shape == (len(limit.masses), len(limit.grid)) and (r > 0).all() and not limit.bands
    else:
        assert len(limit.bands) == 1 and not limit.grid
        lower, upper = (np.asarray(x) if x is not None else None for x in limit.bands[0])
        assert len(lower) == len(limit.masses) and (lower > 0).all()
        assert upper is None or (upper >= lower).all()
    assert np.all(np.diff(limit.masses) > 0)


def test_lhcbs_displaced_search_is_an_r_map_and_excludes_where_r_is_below_one():
    limit = s.darkcast("LHCb_Aaij2019bvg_displaced")
    assert limit.is_map and (len(limit.masses), len(limit.grid)) == (99, 926)              # 91,674 rows
    for m, epsilon, r in ((0.2501, 3.575e-5, 0.4914), (0.2996, 2.830e-5, 0.5209)):         # the owner's two points
        assert s._map_value(limit, m, epsilon) == pytest.approx(r, rel=1e-3)
        assert s.darkcast_excludes("LHCb_Aaij2019bvg_displaced", m, epsilon) is True
        assert s.darkcast_ratio("LHCb_Aaij2019bvg_displaced", m, epsilon) == pytest.approx(1 / r, rel=1e-3)
    assert s.darkcast_excludes("LHCb_Aaij2019bvg_displaced", 0.25, 1e-3) is None           # beyond its ε grid


def test_the_dark_photon_evaluator_uses_the_map():
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.portals.vector import DarkPhoton
    out = ps._dark_photon_native(DarkPhoton(), Point(m_chi=0.2, m_med=0.2501, g_chi=0.1, g_q=3.575e-5), True)
    assert out.excluded is True and out.why == "LHCb_Aaij2019bvg_displaced"


def test_the_record_plot_shades_each_named_searchs_region():
    regions = review.darkcast_regions("LHCb_Aaij2019bvg_displaced", s.darkcast("LHCb_Aaij2019bvg_displaced"))
    assert regions and all(c.region for c in regions) and regions[0].label == "LHCb 2019 displaced"
    assert all(1e-6 < y < 1e-4 for c in regions for y in c.y)                     # the r = 1 contour, not r itself
    assert review.search_name("NA64_NA642019imj") == "NA64 2019 invisible"                 # the data file's name
    babar = review.darkcast_regions("BaBar_Lees2014xha", s.darkcast("BaBar_Lees2014xha"))[0]
    assert max(babar.y) == 1.0 and min(babar.y) > 1e-5                           # above its lower limit, up to ε = 1


def test_visible_and_invisible_searches_are_drawn_on_their_own_panels(tmp_path):
    """ε √BR(visible) and ε √BR(χχ̄) are different quantities; a search with several islands is named once."""
    from adroit.constraints import database
    record = database.record("darkcast-dark-photon")
    groups = review.panels(record)
    assert [label.split(":")[0] for label, _, _ in groups] == ["ε √BR(visible)", "ε √BR(χχ̄)"]
    invisible = {c.label for c in groups[1][1]}
    assert invisible == {"BaBar 2017", "NA64 2019 invisible", "NA62 2019", "LEP 2011"}
    assert all(c.label == "LHCb 2019 displaced" for c in review.darkcast_regions(
        "LHCb_Aaij2019bvg_displaced", s.darkcast("LHCb_Aaij2019bvg_displaced")))
    assert review.plot(record, tmp_path / "darkcast.png").exists()
