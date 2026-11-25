"""Path 2 on LZ's event of interest (arXiv:2609.02823): the case study of DM6.

LZ's 612 physical models are fitted to the event, grouped into degeneracy
classes at 20 events, and the best of the 8 leading classes are combined
with the null experiments. The four non-xenon modules are used, since the
other xenon searches need new DIAMX templates for every spectrum (about five
minutes each); `--with-xenon` adds XENONnT and PandaX-4T. LZ's own WS2024
search shares its data with the extended window, so it is never combined
with it.

    uv run python docs/dm6/lz_case.py [--with-xenon]

It writes lz_case.md and lz_case.json (lz_case_xenon.* with --with-xenon) in docs/dm6/.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.orchestrator import signal  # noqa: E402

HERE = Path(__file__).parent
NON_XENON = ["CRESST-III 2019", "CDMSlite Run 2", "PICO-60 C3F8 (2019)", "DEAP-3600 (2019)"]
XENON = ["XENONnT SR0+SR1", "PandaX-4T Run0+Run1"]


def main() -> None:
    with_xenon = "--with-xenon" in sys.argv
    request = signal.SignalRequest(experiment="LZ extended window (2026)",
                                   null_modules=NON_XENON + (XENON if with_xenon else []))
    result = signal.run(request)
    stem = "lz_case_xenon" if with_xenon else "lz_case"
    (HERE / f"{stem}.json").write_text(result.model_dump_json(indent=1))
    text = signal.report(result)
    (HERE / f"{stem}.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
