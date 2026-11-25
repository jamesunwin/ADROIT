"""DM10: the system's results beside published analyses of the same questions.

Each comparison quotes the paper's conclusion (its abstract, fetched from the
arXiv API) and sets the system's own result beside it, from stored results
(DM6's Path 2 on LZ's extended window, docs/dm6/lz_case_xenon.json) or
computed here. One comparison is computed afresh: arXiv:2609.21823 limits the
elastic operators that explain LZ's event by capture in the Sun; the same
question is put to the system's own capture calculation and IceCube's record
(DM7), for every elastic candidate of LZ's space with a local significance of at
least 3σ, at masses up to 1 TeV, at the coupling that explains the event.

Run from the repository root (about two minutes; low priority):

    nice -n 10 uv run python docs/dm10/comparisons.py

Writes docs/dm10/comparisons.json; docs/dm10_evaluation.md (section 4) reads it.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.experiments import registry  # noqa: E402
from adroit.orchestrator import signal  # noqa: E402

HERE = Path(__file__).parent
CASE = ROOT / "docs/dm6/lz_case_xenon.json"
WEAK_SCALE_GEV = 1000.0
Z_MIN = 3.0


def _dm7_channels():
    """DM7's channel-by-channel capture comparison (docs/dm7/lz_complementary.py)."""
    spec = importlib.util.spec_from_file_location("lz_complementary", ROOT / "docs/dm7/lz_complementary.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.channels


def leaders() -> list[dict]:
    """DM6's leaders on LZ's event: label, kind (inelastic or elastic), Z, and whether the null searches agree."""
    case = json.loads(CASE.read_text())
    return [{"label": e["label"], "kind": "inelastic (endothermic)" if ",d=" in e["label"] else "elastic",
             "z_signal": round(e["z_signal"], 2), "p_pg": round(e["p_pg"], 2)}
            for e in case["tournament"]["ranking"] if e["label"] != "background only"]


def elastic_capture() -> list[dict]:
    """Each elastic candidate with Z ≥ 3 up to 1 TeV: μ̂, the capture rate and C/allowed per IceCube channel."""
    channels = _dm7_channels()
    case = json.loads(CASE.read_text())
    module = registry.load_module("LZ extended window (2026)")
    space = {c.label: c for c in signal.model_space(module)}
    out = []
    for fit in case["fits"]:
        c = space[fit["label"]]
        if c.splitting_kev or fit["z_local"] < Z_MIN or c.mass_gev > WEAK_SCALE_GEV:
            continue
        total = signal._signal(module, c).total_events
        mu_hat = math.sqrt(fit["s_hat"] / total)
        candidate = signal._verdict_candidate(module, c, mu_hat)
        by_channel = channels(candidate)
        out.append({"label": c.label, "card": c.card_id, "mass_gev": c.mass_gev, "z_local": round(fit["z_local"], 2),
                    "mu_hat": mu_hat, "ratio": {ch: v["ratio"] for ch, v in by_channel.items()}})
        print(out[-1]["label"], {k: f"{v:.2g}" for k, v in out[-1]["ratio"].items()}, flush=True)
    return out


def summary(rows: list[dict]) -> dict[str, str]:
    """By mass: how many candidates IceCube's record excludes in each channel (C/allowed > 1)."""
    out = {}
    for m in sorted({r["mass_gev"] for r in rows}):
        at = [r for r in rows if r["mass_gev"] == m]
        counts = {ch: sum(r["ratio"].get(ch, 0.0) > 1.0 for r in at) for ch in ("bb", "WW", "tautau")}
        out[f"{m:g} GeV"] = f"{len(at)} candidates; excluded: " + ", ".join(f"{ch} {n}" for ch, n in counts.items())
    return out


def main() -> None:
    rows = elastic_capture()
    record = {"leaders": leaders(), "elastic_capture": rows, "elastic_capture_by_mass": summary(rows)}
    (HERE / "comparisons.json").write_text(json.dumps(record, indent=1))
    print(json.dumps(record["elastic_capture_by_mass"], indent=1))


if __name__ == "__main__":
    main()
