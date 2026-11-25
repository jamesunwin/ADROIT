"""Reproducible native SI envelope for the existing PICO counting reconstruction.

Run: uv run --with pymupdf python scripts/validate_native_pico_si.py --write
Only the two new native validation files are written. Existing DM3 envelopes,
records, and their human verification remain untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from adroit.core.dm_state import CrossSectionKind, LimitCurve  # noqa: E402
from adroit.experiments.pico60 import Pico60  # noqa: E402
from adroit.experiments.validation import validate  # noqa: E402

CURVE = "adroit/experiments/data/digitised/pico60_2019_fig8_native_si.yaml"
CERTIFICATE = "adroit/experiments/data/native_pico_si_validation.yaml"
RESPONSE_INPUTS = (
    "adroit/experiments/pico60.py",
    "adroit/experiments/base.py",
    "adroit/experiments/data/digitised/pico60_2019_fig3.yaml",
    "adroit/physics/rates.py",
    "adroit/physics/halo.py",
    "adroit/physics/nuclear.py",
    "adroit/physics/targets.py",
    "adroit/physics/conventions.py",
    "adroit/statistics/poisson.py",
    "adroit/core/dm_state.py",
    *(
        str(p.relative_to(ROOT))
        for p in sorted((ROOT / "adroit/physics/data").rglob("*"))
        if p.is_file()
    ),
)


def digitise(pdf: Path) -> dict:
    """Read the maroon vector path and drawn logarithmic major ticks of Fig. 8."""
    import pymupdf

    with pymupdf.open(pdf) as doc:
        drawings = doc[7].get_drawings()
    candidates = [
        d
        for d in drawings
        if d.get("color")
        and np.allclose(d["color"], (0.6, 0, 0.2), atol=1e-6)
        and len(d["items"]) > 10
    ]
    if len(candidates) != 2 or candidates[0]["items"] != candidates[1]["items"]:
        raise ValueError("expected the duplicated thick-maroon PICO Fig. 8 path")
    points = []
    for item in candidates[0]["items"]:
        if item[0] == "l":
            points.extend([(v.x, v.y) for v in item[1:]])
        elif item[0] == "c":
            p = np.array([[v.x, v.y] for v in item[1:]])
            for t in np.linspace(0, 1, 33):
                points.append(
                    (1 - t) ** 3 * p[0]
                    + 3 * (1 - t) ** 2 * t * p[1]
                    + 3 * (1 - t) * t * t * p[2]
                    + t**3 * p[3]
                )
        else:
            raise ValueError("unrecognized curve primitive")
    v = np.array(points)
    v = v[np.argsort(v[:, 0])]
    x, indices = np.unique(v[:, 0], return_index=True)
    # Exact drawn axis endpoints: mass 1 and 100 GeV; sigma ticks -38 and -46.
    x0, x2 = 81.9996337890625, 282.0846862792969
    y0, y8 = 64.76896667480469, 213.3778533935547
    return {
        "source": "arXiv:1902.04031v1, Fig. 8, p. 8, thick maroon combined exposure",
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "method": "PDF vector vertices/Bezier evaluation; exact drawn logarithmic major ticks",
        "axes": {"mass_1_100_points": [x0, x2], "sigma_minus38_minus46_points": [y0, y8]},
        "mass_gev": (10 ** ((x - x0) / ((x2 - x0) / 2))).tolist(),
        "cross_section_cm2": (10 ** (-38 - (v[indices, 1] - y0) / ((y8 - y0) / 8))).tolist(),
    }


def build_certificate(data: dict) -> dict:
    """Apply the unchanged DM3 1.3/3%-edge rule to a specified SI mass bank."""
    curve = LimitCurve(
        experiment=Pico60.name,
        kind=CrossSectionKind.si,
        masses_gev=data["mass_gev"],
        cross_sections_cm2=data["cross_section_cm2"],
        source=data["source"],
    )
    masses = sorted(set(np.geomspace(4.0, 80.0, 21).tolist() + [5.0, 8.6, 10.0, 20.0, 30.0, 50.0]))
    result = validate(Pico60(), curve, np.array(masses))
    if not result.passed or result.validated_range != (4.0, 80.0):
        raise ValueError(f"native SI validation failed: {result.model_dump()}")
    return {
        "experiment": Pico60.name,
        "kind": "SI",
        "range_gev": [4.0, 80.0],
        "purpose": "native counting likelihood only; existing DM3 limit envelopes unchanged",
        "fidelity": "B: fixed best-fit efficiency curves; unavailable calibration covariance omitted",
        "curve_file": CURVE,
        "curve_sha256": hashlib.sha256(yaml.safe_dump(data, sort_keys=False).encode()).hexdigest(),
        "response_hashes": {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in RESPONSE_INPUTS
        },
        "validation": result.model_dump(mode="json"),
    }


def main() -> None:
    """Validate, and write only with explicit --write."""
    from adroit.core.config import get_settings

    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--pdf", type=Path, default=get_settings().tools_dir / "papers/1902.04031.pdf"
    )
    parser.add_argument("--preflight", action="store_true",
                        help="only check that PyMuPDF and the paper are available (release checks, R17-9)")
    args = parser.parse_args()
    if args.preflight:
        try:
            import pymupdf  # noqa: F401
        except ImportError as error:
            raise SystemExit(f"PyMuPDF is not available: {error}") from error
        if not args.pdf.is_file():
            raise SystemExit(f"the PICO-60 paper is not in the tools folder: {args.pdf}")
        print("available")
        return
    data = digitise(args.pdf)
    cert = build_certificate(data)
    if args.write:
        (ROOT / CURVE).write_text(yaml.safe_dump(data, sort_keys=False))
        (ROOT / CERTIFICATE).write_text(yaml.safe_dump(cert, sort_keys=False))
    print(
        {
            "range": cert["range_gev"],
            "points": len(cert["validation"]["masses_gev"]),
            "ratios": [
                min(
                    cert["validation"]["reproduced_cm2"][i] / p
                    for i, p in enumerate(cert["validation"]["published_cm2"])
                ),
                max(
                    cert["validation"]["reproduced_cm2"][i] / p
                    for i, p in enumerate(cert["validation"]["published_cm2"])
                ),
            ],
        }
    )


if __name__ == "__main__":
    main()
