"""The complementary constraints on LZ's leading candidates (DM7, on DM6's case study).

For each of the eight leaders of docs/dm6/lz_case.json, at the coupling that
explains LZ's event (every coupling × μ̂), the verdict of every record in the
curated database (verified by the owner, 2026-10-01). For capture in the Sun the
capture rate is also compared with each of IceCube's three channels, soft
(b b̄) to hard (W⁺W⁻, τ⁺τ⁻), since a bare operator does not fix the channel.

Run from the repository root (about a minute):

    nice -n 10 uv run python docs/dm7/lz_complementary.py

Writes docs/dm7/lz_complementary.md and .json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from adroit.constraints import capture, database, verdicts  # noqa: E402
from adroit.core.dm_state import DarkMatterParticle  # noqa: E402
from adroit.experiments import registry  # noqa: E402
from adroit.orchestrator import signal  # noqa: E402

HERE = Path(__file__).parent
CASE = ROOT / "docs/dm6/lz_case.json"


def channels(candidate: verdicts.Candidate) -> dict[str, dict[str, float]]:
    """C against the capture rate each IceCube channel allows (SD translation)."""
    record = database.record("icecube-1612.05949-sd")
    limits = database.data(record.id)["limits"]["SD_proton"]["limits_cm2"]
    m = candidate.particle.mass_gev
    rate = capture.capture_rate(candidate.particle, candidate.interaction)
    out = {}
    for channel, points in limits.items():
        sigma = database.interpolate_limit(points, m)
        if sigma is not None:
            allowed = capture.capture_rate(DarkMatterParticle(mass_gev=m),
                                           verdicts._reference("SD_proton", sigma, m))
            out[channel] = {"capture_s": rate, "allowed_s": allowed, "ratio": rate / allowed}
    return out


def main() -> None:
    """Judge the leaders and write the record."""
    case = json.loads(CASE.read_text())
    module = registry.load_module("LZ extended window (2026)")
    space = {c.label: c for c in signal.model_space(module)}
    rows, record = [], {}
    for combo in case["combinations"]:
        c = space[combo["label"]]
        candidate = signal._verdict_candidate(module, c, combo["mu_hat_signal"])
        judged = verdicts.judge(candidate)
        by_channel = channels(candidate)
        record[c.label] = {"mu_hat": combo["mu_hat_signal"], "verdicts": [v.model_dump() for v in judged],
                           "icecube_by_channel": by_channel}
        solar = ", ".join(f"{ch} {v['ratio']:.2g}" for ch, v in by_channel.items()) or "—"
        rows.append(f"| {c.label} | {combo['mu_hat_signal']:.3g} | {by_channel and next(iter(by_channel.values()))['capture_s']:.3g} | {solar} | "
                    f"{verdicts.summary(judged)} |")
    lines = ["# Complementary constraints on LZ's leading candidates", "",
             "The verified records of the curated database. μ̂ is the factor on LZ's unit "
             "couplings that explains the event. C is the Sun's capture rate (s⁻¹); the next column "
             "gives C over the rate IceCube's limit allows, channel by channel (> 1: excluded if the "
             "Sun is in equilibrium and annihilation goes into that channel).", "",
             "| candidate | μ̂ | C (s⁻¹) | C / allowed, by channel | verdicts |", "|---|---|---|---|---|", *rows]
    (HERE / "lz_complementary.md").write_text("\n".join(lines) + "\n")
    (HERE / "lz_complementary.json").write_text(json.dumps(record, indent=1, default=str))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
