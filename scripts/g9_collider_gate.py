"""G9's gate, colliders for a generic model: every development-half zoo model gets its LHC verdict (SModelS on the
SLHA spectrum from G1 and G2) or a named reason, and the generic route agrees with the library's families (the wino,
the higgsino, a coloured and a slepton-like t-channel partner) on the spectrum's cross-section and SModelS's r.
Offline ($0); the held-out half is not read.

    .venv/bin/python scripts/g9_collider_gate.py --out docs/g9/collider_gate.json
"""

from __future__ import annotations

import argparse
import sys
import json
from pathlib import Path

AGREE = 0.05                        # SModelS's r: the library's and the generic route's within 5%


def _partner_spec(partner: str, m_chi: float, m_med: float, g: float):
    """A Majorana χ with a scalar partner coupled to one right-handed SM fermion, as the library's t-channel class."""
    from adroit.core.model_spec import ModelSpec
    charges = {"uR": {"su3": "3", "hypercharge": 2 / 3}, "eR": {"hypercharge": -1.0}}[partner]
    fields = [{"name": "chi", "role": "dark_matter", "spin": 0.5, "self_conjugate": True, "dark_parity": -1,
               "mass_gev": m_chi},
              {"name": "Phi", "role": "mediator", "spin": 0, "dark_parity": -1, "mass_gev": m_med, "charges": charges},
              {"name": partner, "role": "standard_model", "spin": 0.5, "chirality": "R", "charges": charges}]
    terms = [{"fields": [{"field": "Phi", "conjugate": True}, {"field": "chi", "conjugate": True},
                         {"field": partner}], "lorentz": "chiral", "coupling": "y", "plus_hc": True}]
    return ModelSpec.model_validate({"name": f"partner_{partner}", "phase": "unbroken", "fields": fields,
                                     "terms": terms, "couplings": [{"name": "y", "value": g}]})


def library_pairs() -> list[tuple[str, object, object, object, object]]:
    """(label, library engine, its point, generic engine, its point) for each family the library's tables cover."""
    from adroit.evaluation import zoo
    from adroit.parameter_space import library
    from adroit.parameter_space.classes import Point
    from adroit.parameter_space.portals.generic import GenericModel
    from adroit.parameter_space.portals.tchannel import TChannel
    out = []
    for label, entry_id, key, m in (("wino", "wino_majorana_triplet_bottaro", "wino", 600.0),
                                    ("higgsino", "higgsino_dirac_doublet_bottaro", "higgsino", 600.0)):
        e = next(x for x in zoo.entries() if x.id == entry_id)
        engine, point = zoo._generic(e, e.targets[0])
        held = library.entry(key)
        out.append((label, held.model_class, held.point.model_copy(update={"m_chi": m}), engine,
                    point.model_copy(update={"m_chi": m})))
    for partner, m_chi, m_med in (("uR", 300.0, 1200.0), ("eR", 100.0, 300.0)):
        lib = TChannel(partner=partner, majorana=True)
        engine = GenericModel.of(_partner_spec(partner, m_chi, m_med, 1.0))
        out.append((f"t-channel {partner}", lib, Point(m_chi=m_chi, m_med=m_med, g_chi=1.0), engine, engine.point()))
    return out


def zoo_rows() -> list[dict]:
    """Every development-half zoo model through the generic route: its spectrum's σ, or the reason."""
    from adroit.evaluation import core, zoo
    from adroit.parameter_space.classify import Unsupported
    rows = []
    for e in zoo.entries():
        if core.half_of("model_zoo", e.id).value != "development":
            continue
        try:
            engine, point = zoo._generic(e, e.targets[0])
        except Unsupported as error:
            rows.append({"id": e.id, "built": False, "why": str(error)})
            continue
        text, sigma, why = engine.lhc_spectrum(point)
        rows.append({"id": e.id, "built": True, "m_chi": point.m_chi, "sigma_pb": sigma, "why": why,
                     "slha": text, "higgs_mu": engine.higgs_mu(point), "_at": (engine, point)})
    return rows


def lo_against_tables() -> list[dict]:
    """MadGraph's leading order (``constraints.pair_production``) against the higher-order tables, for the
    families they cover: K = table / LO, which the LO lower-bound rule assumes is above 1. The partners' Yukawa is
    0.01, so that their production is QCD's or the Drell–Yan's alone, as the tables'."""
    from adroit.constraints import lhc
    from adroit.constraints import pair_production as pp
    from adroit.evaluation import zoo
    from adroit.parameter_space.portals.generic import GenericModel
    rows = []
    e = next(x for x in zoo.entries() if x.id == "wino_majorana_triplet_bottaro")
    engine, point = zoo._generic(e, e.targets[0])
    p = point.model_copy(update={"m_chi": 600.0})
    mb, rules, _ = engine.at(p)
    lo = pp.cross_sections(rules, mb.spectrum.dark_matter().name, "g9_wino_600")["total_pb"]
    table = sum(lhc.cross_section_pb(k, 600.0) for k in ("wino_c1c1", "wino_c1p_n", "wino_c1m_n"))
    rows.append({"family": "wino, m = 600 GeV (C₁C₁ + C₁N₂)", "lo_pb": lo, "table_pb": table, "k": table / lo})
    for partner, kind, m_chi, m_med in (("eR", "slepton", 100.0, 300.0), ("uR", "coloured", 300.0, 1200.0)):
        engine = GenericModel.of(_partner_spec(partner, m_chi, m_med, 0.01))
        mb, rules, _ = engine.at(engine.point())
        lo = pp.cross_sections(rules, mb.spectrum.dark_matter().name, f"g9_{partner}")["total_pb"]
        table = lhc.cross_section_pb(kind, m_med)
        rows.append({"family": f"{kind} partner ({partner}), m_φ = {m_med:.0f} GeV", "lo_pb": lo, "table_pb": table,
                     "k": table / lo})
    return rows


def run(out: Path) -> dict:
    from adroit.constraints import lhc
    from adroit.parameter_space import searches
    rows = zoo_rows()
    pairs = []
    for label, lib, lp, gen, gp in library_pairs():
        lt, ls = searches.lhc_spectrum(lib, lp) or ("", None)
        gt, gs, why = gen.lhc_spectrum(gp)
        pairs.append({"family": label, "m_chi": lp.m_chi, "m_med": lp.m_med, "library_sigma_pb": ls,
                      "generic_sigma_pb": gs, "why": why, "library_slha": lt, "generic_slha": gt})
    texts = [r["slha"] for r in rows if r.get("sigma_pb")] + \
        [t for p in pairs for t in (p["library_slha"], p["generic_slha"]) if t]
    results = dict(zip(texts, lhc.run(texts), strict=True)) if texts and lhc.available() else {}
    for r in rows:
        text, at = r.pop("slha", ""), r.pop("_at", None)
        if at is None:
            r["verdict"] = "refused: " + r["why"]
            continue
        outcome = searches.lhc_search(*at, unverified=False, prefetched=results.get(text))
        r["r_max"] = results.get(text, {}).get("r_max")
        r["verdict"] = ("undecided" if outcome is None or outcome.excluded is None else
                        "excluded" if outcome.excluded else "allowed")
        r["outcome_why"] = "" if outcome is None else outcome.why
    for p in pairs:
        lr_, gr = (results.get(p.pop(k), {}).get("r_max") for k in ("library_slha", "generic_slha"))
        p |= {"library_r": lr_, "generic_r": gr,
              "agree": lr_ is not None and gr is not None and abs(gr - lr_) <= AGREE * max(abs(lr_), 1e-3)
              and p["library_sigma_pb"] == p["generic_sigma_pb"]}
    decided = [r for r in rows if r["verdict"] in ("excluded", "allowed")]
    named = all(r in decided or r.get("why") or r.get("outcome_why") for r in rows)
    summary = {"development_models": len(rows), "decided": len(decided), "undecided_or_refused_with_reason":
               len(rows) - len(decided), "every_model_decided_or_named": named,
               "families_agree": sum(p["agree"] for p in pairs), "families": len(pairs)}
    k = lo_against_tables()
    summary["lo_is_below_the_tables"] = all(r["k"] > 1.0 for r in k)
    summary["gate"] = (named and summary["families_agree"] == summary["families"]
                       and summary["lo_is_below_the_tables"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "zoo": rows, "families": pairs, "lo_against_tables": k}, indent=1,
                              default=str))
    return summary


def main() -> int:
    """Run the gate; the exit code is 0 met, 1 not met (``core.receipts``)."""
    from adroit.core.receipts import exit_code
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="runs/g9/collider_gate.json")
    args = parser.parse_args()
    summary = run(Path(args.out))
    print(summary)
    return exit_code(summary["gate"])


if __name__ == "__main__":
    sys.exit(main())
