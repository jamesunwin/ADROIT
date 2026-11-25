"""How the xenon limits depend on DIAMX's simulation statistics (DM3).

The validation run used 10⁶ simulated events per template. This script
repeats the LZ and XENONnT limits at three masses each with 10⁶ and 10⁷
events per template, with spectra scaled to order-one multipliers
(``xenon.TYPICAL_EVENTS``), and writes docs/dm3/xenon_convergence.txt.

    uv run python docs/dm3/xenon_convergence.py
"""

from __future__ import annotations

import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.core.dm_state import CrossSectionKind  # noqa: E402
from adroit.experiments import validation  # noqa: E402
from adroit.experiments.xenon import DiamxXenon  # noqa: E402

OUT = Path(__file__).with_name("xenon_convergence.txt")
CASES = {"LZ WS2022+WS2024": [42.2, 201.0, 956.0], "XENONnT SR0+SR1": [10.0, 16.7, 46.4]}


def main() -> None:
    """Each search, each batch size: the ratio to the published limit at each mass."""
    lines = [f"# DIAMX statistics study, {date.today()}: reproduced/published 90% SI limit"]
    for batch in (1_000_000, 10_000_000):
        for search, masses in CASES.items():
            module = DiamxXenon(search, batch_size=batch)
            (curve,) = module.published_limits()
            start = time.time()
            ours = module.limits_on(CrossSectionKind.si, masses)
            published = validation.published_at(curve, np.array(masses))
            ratios = " ".join(f"{m:g}:{o / p:.2f}" for m, o, p in zip(masses, ours, published))
            line = f"{search} | batch {batch:.0e} | {ratios} | {time.time() - start:.0f} s"
            print(line, flush=True)
            lines.append(line)
    OUT.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
