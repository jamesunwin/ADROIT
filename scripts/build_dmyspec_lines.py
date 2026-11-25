"""Tabulate DMγSpec's resummed line rates for ADROIT (G8, the owner's decision on the lines, 2026-10-15).

DMγSpec (Beneke, Urban & Vollmann, arXiv:2203.01692; GPLv3, installed by the user in ``<tools>/dmyspec``, never
copied into this repository) gives the photon spectrum of wino and higgsino annihilation with the endpoint
Sudakov-resummed at NLL′ and the Sommerfeld effect from the NLO electroweak potentials. This script runs in
DMγSpec's own environment (``<tools>/.venv-dmyspec``: SciPy 1.13, the last with ``interp2d``) and writes, at
DMγSpec's 500 grid masses (0.5–100 TeV), the photon yield within the H.E.S.S. window x = E/M ∈ [1 − 0.10, 1]:

    σv_window = ∫ d(σv)/dx dx over the window (photons: 2 per γγ, 1 per Zγ, plus the endpoint continuum),
    σv_line = σv_window / 2,

σv_line being the γγ-equivalent rate the H.E.S.S. records compare (``searches._line_comparison``). Sommerfeld
tables: the single-particle speed v = 10⁻³ ('NLO -3'; the higgsino with δm_N = 20 MeV). ADROIT reads only the
JSON this writes (``constraints.resummed_lines``).

    ~/agentic-dm-tools/.venv-dmyspec/bin/python scripts/build_dmyspec_lines.py
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

TOOLS = Path(os.environ.get("ADROIT_TOOLS_DIR", Path.home() / "agentic-dm-tools"))
FOLDER = TOOLS / "dmyspec"
WINDOW = 0.10
MODELS = {"wino": "NLO -3", "higgsino": "NLO -3 dm 355 dmN 20"}
GRID = [0.5 + 0.005 * k for k in range(100)] + [1.0 + 0.01 * k for k in range(100)] + \
       [2.0 + 0.02 * k for k in range(100)] + [4.0 + 0.05 * k for k in range(60)] + \
       [7.0, 7.1, 7.3, 7.4, 7.6, 7.7, 7.8, 8.0, 8.1, 8.3, 8.5, 8.6, 8.8, 9.0, 9.1, 9.3, 9.5, 9.7, 9.9, 10.0, 10.2,
        10.4, 10.6, 10.8, 11.0, 11.3, 11.5, 11.7, 11.9, 12.1, 12.4, 12.6, 12.9, 13.1, 13.4, 13.6, 13.9, 14.1, 14.4,
        14.7, 15.0, 15.3, 15.5, 15.8, 16.1, 16.5, 16.8, 17.1, 17.4, 17.8, 18.1, 18.4, 18.8, 19.2, 19.5, 19.9, 20.3,
        20.7, 21.1, 21.5, 21.9, 22.3, 22.7, 23.2, 23.6, 24.1, 24.5, 25.0, 25.5, 26.0, 26.5, 27.0, 27.5, 28.0, 28.5,
        29.1, 29.7, 30.2, 30.8, 31.4, 32.0, 32.6, 33.2, 33.9, 34.5, 35.2, 35.9, 36.5, 37.2, 38.0, 38.7, 39.4, 40.2,
        41.0, 41.7, 42.5, 43.4, 44.2, 45.0, 45.9, 46.8, 47.7, 48.6, 49.5, 50.5, 51.4, 52.4, 53.4, 54.5, 55.5, 56.6,
        57.6, 58.8, 59.9, 61.0, 62.2, 63.4, 64.6, 65.8, 67.1, 68.4, 69.7, 71.0, 72.4, 73.8, 75.2, 76.6, 78.1, 79.6,
        81.1, 82.7, 84.3, 85.9, 87.5, 89.2, 90.9, 92.7, 94.5, 96.3, 98.1, 100.0]   # DMγSpec's own grid (TeV)


def main() -> None:
    sys.path.insert(0, str(FOLDER))
    os.chdir(FOLDER)                                  # DMγSpec reads its data relative to its folder
    from resummation import cumulxsection             # noqa: E402 - DMγSpec, in its own environment
    tables = {}
    for model, sf in MODELS.items():
        rows = []
        for m in GRID:
            window = float(cumulxsection(1.0 - WINDOW, m, model, sf, rel=-4)) * 1e-26
            rows.append([round(1e3 * m, 6), window, 0.5 * window])
        tables[model] = {"sommerfeld_table": sf, "columns": ["mass_gev", "sigma_v_window_cm3_s", "sigma_v_line_cm3_s"],
                         "data": rows}
        print(model, len(rows), "masses", flush=True)
    out = {"source": "DMγSpec 1.0.0 (Beneke, Urban & Vollmann, arXiv:2203.01692), NLL′ endpoint + NLO Sommerfeld",
           "window": WINDOW, "speed": "single-particle v = 1e-3", "created": dt.date.today().isoformat(),
           "tables": tables}
    (FOLDER / "adroit_lines.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
